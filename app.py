import streamlit as st
import datetime
import calendar
import json
import os
import uuid
import hashlib
import random

# ----------------- 0. 網頁基本設定 & GitHub Favicon -----------------
st.set_page_config(
    page_title="多功能共享線上行事曆",
    page_icon="https://raw.githubusercontent.com/3323jayden-dot/calendar-app/main/istockphoto-1033804852-612x612.jpg",
    layout="centered"
)

USER_FILE = "users.json"
CALENDARS_FILE = "shared_calendars.json"

DEFAULT_CATEGORIES = {
    "考試": {"bg": "#FFF0F0", "text": "#E53935", "icon": "📖"},
    "作業": {"bg": "#FFFDE7", "text": "#FB8C00", "icon": "📄"},
    "練習": {"bg": "#E8F5E9", "text": "#2E7D32", "icon": "🏋️"},
    "備忘": {"bg": "#E3F2FD", "text": "#1E88E5", "icon": "✏️"},
    "批改": {"bg": "#F3E5F5", "text": "#8E24AA", "icon": "📝"},
    "出題": {"bg": "#E0F7FA", "text": "#0288D1", "icon": "📋"},
    "行政": {"bg": "#F5F5F5", "text": "#616161", "icon": "📁"},
}

# ----------------- JSON 檔案讀寫工具 -----------------
def load_json(filepath, default_data):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    save_json(filepath, default_data)
    return default_data

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_token(email, password):
    return hashlib.sha256(f"{email}_{password}_calendar_secret".encode()).hexdigest()[:16]

users = load_json(USER_FILE, {})
all_calendars = load_json(CALENDARS_FILE, {})

# Session State 初始化
if "verify_code" not in st.session_state:
    st.session_state.verify_code = None
if "pending_email" not in st.session_state:
    st.session_state.pending_email = None

# ----------------- 1. 網址憑證自動登入機制 -----------------
query_params = st.query_params
url_user = query_params.get("user")
url_token = query_params.get("token")

current_user_email = None

if url_user and url_token and url_user in users:
    expected_token = generate_token(url_user, users[url_user]["password"])
    if url_token == expected_token:
        current_user_email = url_user

# ----------------- 2. Email 註冊 / 登入介面 -----------------
if not current_user_email:
    st.title("🔐 共享線上行事曆")
    tab_login, tab_register = st.tabs(["🔑 帳號登入", "✉️ Email 註冊"])
    
    with tab_login:
        with st.form("login_form"):
            email_in = st.text_input("電子郵件 (Email)").strip().lower()
            pass_in = st.text_input("密碼", type="password").strip()
            
            if st.form_submit_button("登入並保持登入", use_container_width=True):
                if email_in in users and users[email_in]["password"] == pass_in:
                    token = generate_token(email_in, pass_in)
                    st.query_params["user"] = email_in
                    st.query_params["token"] = token
                    st.success(f"登入成功！歡迎，{users[email_in].get('name', email_in)}")
                    st.rerun()
                else:
                    st.error("Email 或密碼錯誤！")
                    
    with tab_register:
        st.markdown("##### 1. 輸入註冊資訊並發送驗證碼")
        reg_name = st.text_input("您的顯示暱稱 (例如：張小明)").strip()
        reg_email = st.text_input("您的 Email 帳號").strip().lower()
        reg_pass = st.text_input("設定密碼", type="password").strip()
        
        if st.button("📩 傳送 6 位數驗證碼", use_container_width=True):
            if not reg_email or "@" not in reg_email:
                st.warning("請輸入有效的 Email！")
            elif reg_email in users:
                st.error("這個 Email 已經註冊過了！")
            elif not reg_name or not reg_pass:
                st.warning("請填寫完整的暱稱與密碼！")
            else:
                code = str(random.randint(100000, 999999))
                st.session_state.verify_code = code
                st.session_state.pending_email = reg_email
                st.success(f"✅ 驗證碼已發送！(測試模式預覽：驗證碼為 [{code}])")
                
        st.divider()
        st.markdown("##### 2. 輸入驗證碼完成註冊")
        input_code = st.text_input("請輸入收到 6 位數驗證碼").strip()
        
        if st.button("🎉 完成註冊並登入", use_container_width=True):
            if input_code and input_code == st.session_state.verify_code and reg_email == st.session_state.pending_email:
                users[reg_email] = {
                    "name": reg_name,
                    "password": reg_pass,
                    "categories": DEFAULT_CATEGORIES.copy()
                }
                save_json(USER_FILE, users)
                st.session_state.verify_code = None
                st.session_state.pending_email = None
                
                # 自動登入
                token = generate_token(reg_email, reg_pass)
                st.query_params["user"] = reg_email
                st.query_params["token"] = token
                st.success("註冊成功！正在跳轉...")
                st.rerun()
            else:
                st.error("驗證碼不正確或已失效！")
    st.stop()

# 當前使用者資料與分類載入
user_data = users[current_user_email]
user_categories = user_data.setdefault("categories", DEFAULT_CATEGORIES.copy())

# 個人日曆檢查
personal_cal_id = f"personal_{current_user_email}"
if personal_cal_id not in all_calendars:
    all_calendars[personal_cal_id] = {
        "name": f"🔒 {user_data.get('name', '個人')} 的行事曆",
        "members": [current_user_email],
        "events": {}
    }
    save_json(CALENDARS_FILE, all_calendars)

user_accessible_cals = {
    cid: cdata["name"] 
    for cid, cdata in all_calendars.items() 
    if current_user_email in cdata.get("members", [])
}

# ----------------- 3. 主選單 (Sidebar) -----------------
with st.sidebar:
    st.write(f"👤 當前使用者：**{user_data.get('name', current_user_email)}**")
    if st.button("🚪 登出系統", use_container_width=True):
        st.query_params.clear()
        st.rerun()
        
    st.divider()
    
    # --- 區塊 1: 帳戶設定 ---
    with st.expander("⚙️ 帳戶與偏好設定"):
        new_nickname = st.text_input("更改暱稱", value=user_data.get("name", ""))
        if st.button("儲存暱稱"):
            if new_nickname.strip():
                users[current_user_email]["name"] = new_nickname.strip()
                save_json(USER_FILE, users)
                st.success("暱稱已成功更新！")
                st.rerun()
                
        st.caption("變更密碼")
        new_pwd = st.text_input("新密碼", type="password")
        if st.button("更新密碼"):
            if new_pwd.strip():
                users[current_user_email]["password"] = new_pwd.strip()
                save_json(USER_FILE, users)
                token = generate_token(current_user_email, new_pwd.strip())
                st.query_params["token"] = token
                st.success("密碼已成功更新！")

    # --- 區塊 2: 跨日細節規劃小日曆 ---
    with st.expander("📝 跨日細節規劃 (幾號至幾號)"):
        st.caption("選擇時間區間以快速建立跨日行程：")
        date_range = st.date_input(
            "選擇區間",
            value=(datetime.date.today(), datetime.date.today()),
            key="side_range_picker"
        )
        range_cat = st.selectbox("📌 選擇類別", list(user_categories.keys()), key="side_cat")
        range_title = st.text_input("行程標題", placeholder="例：暑期實習 / 請假", key="side_title")
        range_note = st.text_area("詳細規劃/備註", placeholder="補充說明...", key="side_note")
        
        selected_cal_for_range = st.selectbox(
            "添加到哪個日曆：",
            options=list(user_accessible_cals.keys()),
            format_func=lambda x: user_accessible_cals[x],
            key="side_cal_select"
        )
        
        if st.button("✨ 批量新增區間行程", use_container_width=True):
            if range_title.strip() and isinstance(date_range, tuple) and len(date_range) == 2:
                start_d, end_d = date_range
                cal_events = all_calendars[selected_cal_for_range]["events"]
                curr_d = start_d
                while curr_d <= end_d:
                    d_str = curr_d.strftime("%Y-%m-%d")
                    if d_str not in cal_events:
                        cal_events[d_str] = []
                    cal_events[d_str].append({
                        "category": range_cat,
                        "title": range_title.strip(),
                        "note": range_note.strip(),
                        "author": user_data.get("name", current_user_email)
                    })
                    curr_d += datetime.timedelta(days=1)
                save_json(CALENDARS_FILE, all_calendars)
                st.success(f"成功新增 {start_d} 至 {end_d} 的行程！")
                st.rerun()

    # --- 區塊 3: 客製化行程分類 ---
    with st.expander("🎨 客製化行程分類"):
        st.markdown("**新增/修改類別：**")
        cat_name = st.text_input("類別名稱", placeholder="例：加班").strip()
        cat_icon = st.text_input("Emoji 圖示", value="📌").strip()
        cat_color = st.color_picker("代表顏色", "#1E88E5")
        
        if st.button("➕ 儲存分類"):
            if cat_name:
                user_categories[cat_name] = {
                    "bg": cat_color + "22",
                    "text": cat_color,
                    "icon": cat_icon
                }
                save_json(USER_FILE, users)
                st.success(f"已新增/更新分類：{cat_name}")
                st.rerun()
                
        st.caption("已有類別：")
        st.write(" / ".join(user_categories.keys()))

    # --- 區塊 4: 共用日曆切換與管理 ---
    st.divider()
    st.subheader("📅 日曆切換")
    selected_cal_id = st.selectbox(
        "切換檢視的日曆：",
        options=list(user_accessible_cals.keys()),
        format_func=lambda x: user_accessible_cals[x]
    )
    
    with st.expander("➕ 建立/加入共用日曆"):
        new_cal_name = st.text_input("新建共用日曆名稱", placeholder="例：家族專案")
        if st.button("建立"):
            if new_cal_name.strip():
                new_id = f"shared_{uuid.uuid4().hex[:8]}"
                all_calendars[new_id] = {
                    "name": f"👥 {new_cal_name.strip()}",
                    "members": [current_user_email],
                    "events": {}
                }
                save_json(CALENDARS_FILE, all_calendars)
                st.success("建立成功！")
                st.rerun()
                
        invite_code = st.text_input("輸入邀請碼加入").strip()
        if st.button("加入"):
            if invite_code in all_calendars:
                if current_user_email not in all_calendars[invite_code]["members"]:
                    all_calendars[invite_code]["members"].append(current_user_email)
                    save_json(CALENDARS_FILE, all_calendars)
                    st.success("已成功加入！")
                    st.rerun()

current_cal_data = all_calendars[selected_cal_id]
current_events = current_cal_data["events"]

# ----------------- 4. 點擊日期的中間懸浮彈窗 (Dialog) -----------------
@st.dialog("📅 管理當日行程")
def manage_events_dialog(date_str):
    st.markdown(f"### **{date_str}**")
    cat = st.selectbox("📌 選擇類別", list(user_categories.keys()))
    
    with st.form(key=f"modal_add_{date_str}"):
        title = st.text_input("標題 *", placeholder="例：數學考試")
        note = st.text_input("備註 (選填)", placeholder="補充說明...")
        
        if st.form_submit_button("✨ 新增行程", use_container_width=True):
            if title.strip():
                if date_str not in current_events:
                    current_events[date_str] = []
                current_events[date_str].append({
                    "category": cat,
                    "title": title.strip(),
                    "note": note.strip(),
                    "author": user_data.get("name", current_user_email)
                })
                save_json(CALENDARS_FILE, all_calendars)
                st.query_params.pop("selected_date", None)
                st.rerun()
            else:
                st.error("請輸入標題！")
                
    day_events = current_events.get(date_str, [])
    if day_events:
        st.divider()
        st.markdown("**📋 當日行程：**")
        for idx, evt in enumerate(day_events):
            c = user_categories.get(evt["category"], DEFAULT_CATEGORIES.get("行政"))
            col_info, col_del = st.columns([4, 1])
            with col_info:
                st.markdown(
                    f"<div style='background:{c['bg']}; color:{c['text']}; padding:6px 10px; border-radius:6px; font-weight:bold; font-size:13px;'>"
                    f"{c['icon']} [{evt['category']}] {evt['title']} <span style='font-size:11px; color:#666;'>({evt.get('note','')})</span></div>",
                    unsafe_allow_html=True
                )
            with col_del:
                if st.button("🗑️", key=f"dialog_del_{date_str}_{idx}"):
                    current_events[date_str].pop(idx)
                    if not current_events[date_str]:
                        del current_events[date_str]
                    save_json(CALENDARS_FILE, all_calendars)
                    st.query_params.pop("selected_date", None)
                    st.rerun()

# ----------------- 5. 主日曆介面與絕不換行導覽 -----------------
today = datetime.date.today()
if "current_year" not in st.session_state:
    st.session_state.current_year = today.year
if "current_month" not in st.session_state:
    st.session_state.current_month = today.month

nav_action = query_params.get("nav")
if nav_action == "prev":
    if st.session_state.current_month == 1:
        st.session_state.current_month = 12
        st.session_state.current_year -= 1
    else:
        st.session_state.current_month -= 1
    st.query_params.pop("nav", None)
    st.rerun()
elif nav_action == "today":
    st.session_state.current_year = today.year
    st.session_state.current_month = today.month
    st.query_params.pop("nav", None)
    st.rerun()
elif nav_action == "next":
    if st.session_state.current_month == 12:
        st.session_state.current_month = 1
        st.session_state.current_year += 1
    else:
        st.session_state.current_month += 1
    st.query_params.pop("nav", None)
    st.rerun()

st.title(f"{current_cal_data['name']}")

base_url_params = f"user={url_user}&token={url_token}" if url_user and url_token else ""
link_prefix = f"?{base_url_params}&" if base_url_params else "?"

# HTML Flexbox 防換行導覽列
nav_html = f"""
<style>
.nav-container {{
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: space-between !important;
    width: 100% !important;
    margin-bottom: 10px !important;
    gap: 5px !important;
}}
.nav-btn {{
    display: inline-block;
    padding: 6px 12px;
    background-color: #f0f2f6;
    color: #31333F;
    border-radius: 8px;
    text-decoration: none;
    font-size: 13px;
    font-weight: bold;
    text-align: center;
    border: 1px solid #d6d8db;
    white-space: nowrap;
}}
.nav-title {{
    font-size: 16px;
    font-weight: bold;
    color: #111;
    white-space: nowrap;
}}
</style>

<div class="nav-container">
    <a href="{link_prefix}nav=prev" class="nav-btn" target="_self">＜</a>
    <span class="nav-title">🗓️ {st.session_state.current_year} 年 {st.session_state.current_month} 月</span>
    <a href="{link_prefix}nav=today" class="nav-btn" target="_self">今天</a>
    <a href="{link_prefix}nav=next" class="nav-btn" target="_self">＞</a>
</div>
"""
st.markdown(nav_html, unsafe_allow_html=True)

# ----------------- 6. 繪製可點擊 HTML 大月曆 -----------------
cal = calendar.Calendar(firstweekday=6)
month_days = cal.monthdayscalendar(st.session_state.current_year, st.session_state.current_month)

html_code = """
<style>
.cal-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    margin-top: 5px;
    font-family: system-ui, -apple-system, sans-serif;
}
.cal-table th {
    text-align: center;
    padding: 6px 0;
    font-size: 13px;
    background-color: #f8f9fa;
    border: 1px solid #e9ecef;
}
.cal-table td {
    height: 60px;
    vertical-align: top;
    padding: 2px;
    border: 1px solid #e9ecef;
    background-color: #ffffff;
}
.cal-cell-link {
    display: block;
    width: 100%;
    height: 100%;
    text-decoration: none;
    color: inherit;
}
.cal-day-num {
    font-size: 12px;
    font-weight: bold;
    color: #333;
}
.cal-day-today {
    background-color: #007bff;
    color: white;
    border-radius: 50%;
    display: inline-block;
    width: 18px;
    height: 18px;
    text-align: center;
    line-height: 18px;
}
.cal-tag {
    font-size: 9px;
    border-radius: 3px;
    padding: 1px 2px;
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
</style>
<table class="cal-table">
<thead>
  <tr>
    <th style="color:#E53935;">日</th>
    <th>一</th>
    <th>二</th>
    <th>三</th>
    <th>四</th>
    <th>五</th>
    <th style="color:#0288D1;">六</th>
  </tr>
</thead>
<tbody>
"""

for week in month_days:
    html_code += "<tr>"
    for day in week:
        if day == 0:
            html_code += "<td style='background:#fcfcfc;'></td>"
        else:
            date_key = f"{st.session_state.current_year}-{st.session_state.current_month:02d}-{day:02d}"
            is_today = (st.session_state.current_year == today.year and 
                        st.session_state.current_month == today.month and 
                        day == today.day)
            
            day_num_html = f"<span class='cal-day-today'>{day}</span>" if is_today else f"<span class='cal-day-num'>{day}</span>"
            
            day_events = current_events.get(date_key, [])
            tags_html = ""
            for evt in day_events[:2]:
                c = user_categories.get(evt["category"], DEFAULT_CATEGORIES.get("行政"))
                tags_html += f"<div class='cal-tag' style='background:{c['bg']}; color:{c['text']};'>{c['icon']}{evt['title']}</div>"
            
            if len(day_events) > 2:
                tags_html += f"<div style='font-size:8px; color:#888;'>+{len(day_events)-2}</div>"
                
            link_url = f"{link_prefix}selected_date={date_key}"
            html_code += f"<td><a href='{link_url}' target='_self' class='cal-cell-link'>{day_num_html}{tags_html}</a></td>"
    html_code += "</tr>"

html_code += "</tbody></table>"
st.markdown(html_code, unsafe_allow_html=True)

# 偵測點擊事件彈窗
selected_date_param = query_params.get("selected_date")
if selected_date_param:
    manage_events_dialog(selected_date_param)

# ----------------- 7. 即將到來的行程 -----------------
st.divider()
st.subheader("🔮 即將到來的行程")
upcoming = []
for d_str, evts in current_events.items():
    try:
        evt_date = datetime.datetime.strptime(d_str, "%Y-%m-%d").date()
        if evt_date >= today:
            for evt in evts:
                upcoming.append((evt_date, d_str, evt))
    except ValueError:
        pass

upcoming.sort(key=lambda x: x[0])

if upcoming:
    for evt_date, d_str, evt in upcoming[:5]:
        c = user_categories.get(evt["category"], DEFAULT_CATEGORIES.get("行政"))
        days_left = (evt_date - today).days
        day_text = "今天" if days_left == 0 else f"{days_left} 天後"
        st.markdown(
            f"• **{d_str}** ({day_text}) — <span style='color:{c['text']}; font-weight:bold;'>{c['icon']} [{evt['category']}] {evt['title']}</span>",
            unsafe_allow_html=True
        )
else:
    st.info("近期尚無行程規劃。")
