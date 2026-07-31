import streamlit as st
import datetime
import calendar
import json
import os
import uuid
import hashlib

# 頁面基本設定
st.set_page_config(page_title="多功能共享線上行事曆", layout="centered")

# 7 大類別配色與圖示
CATEGORY_COLORS = {
    "考試": {"bg": "#FFF0F0", "text": "#E53935", "icon": "📖"},
    "作業": {"bg": "#FFFDE7", "text": "#FB8C00", "icon": "📄"},
    "練習": {"bg": "#E8F5E9", "text": "#2E7D32", "icon": "🏋️"},
    "備忘": {"bg": "#E3F2FD", "text": "#1E88E5", "icon": "✏️"},
    "批改": {"bg": "#F3E5F5", "text": "#8E24AA", "icon": "📝"},
    "出題": {"bg": "#E0F7FA", "text": "#0288D1", "icon": "📋"},
    "行政": {"bg": "#F5F5F5", "text": "#616161", "icon": "📁"},
}

USER_FILE = "users.json"
CALENDARS_FILE = "shared_calendars.json"

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

def generate_token(username, password):
    return hashlib.sha256(f"{username}_{password}_calendar_secret".encode()).hexdigest()[:16]

users = load_json(USER_FILE, {"admin": "123456"})

# ----------------- 1. 網址憑證自動登入機制 -----------------
query_params = st.query_params
url_user = query_params.get("user")
url_token = query_params.get("token")

current_user = None

if url_user and url_token and url_user in users:
    expected_token = generate_token(url_user, users[url_user])
    if url_token == expected_token:
        current_user = url_user

if not current_user:
    st.title("🔐 線上行事曆系統")
    tab_login, tab_register = st.tabs(["🔑 登入帳號", "📝 註冊新帳號"])
    
    with tab_login:
        with st.form("login_form"):
            username = st.text_input("帳號").strip().lower()
            password = st.text_input("密碼", type="password").strip()
            
            if st.form_submit_button("登入並保持登入", use_container_width=True):
                if username in users and users[username] == password:
                    token = generate_token(username, password)
                    st.query_params["user"] = username
                    st.query_params["token"] = token
                    st.success(f"登入成功！歡迎，{username}")
                    st.rerun()
                else:
                    st.error("帳號或密碼錯誤！")
                    
    with tab_register:
        with st.form("register_form"):
            new_user = st.text_input("新帳號名稱").strip().lower()
            new_pass = st.text_input("設定密碼", type="password").strip()
            confirm_pass = st.text_input("確認密碼", type="password").strip()
            if st.form_submit_button("註冊帳號", use_container_width=True):
                if not new_user or not new_pass:
                    st.warning("請填寫完整的帳號與密碼！")
                elif new_user in users:
                    st.error("這個帳號名稱已經有人使用了！")
                elif new_pass != confirm_pass:
                    st.error("兩次輸入的密碼不一致！")
                else:
                    users[new_user] = new_pass
                    save_json(USER_FILE, users)
                    st.success("🎉 註冊成功！請切換至登入頁面。")
    st.stop()

# ----------------- 2. 日曆切換與管理 -----------------
all_calendars = load_json(CALENDARS_FILE, {})

personal_cal_id = f"personal_{current_user}"
if personal_cal_id not in all_calendars:
    all_calendars[personal_cal_id] = {
        "name": f"🔒 {current_user} 的個人日曆",
        "members": [current_user],
        "events": {}
    }
    save_json(CALENDARS_FILE, all_calendars)

user_accessible_cals = {
    cid: cdata["name"] 
    for cid, cdata in all_calendars.items() 
    if current_user in cdata.get("members", [])
}

with st.sidebar:
    st.write(f"👤 當前帳號：**{current_user}**")
    
    if st.button("🚪 登出系統", use_container_width=True):
        st.query_params.clear()
        st.rerun()
        
    st.divider()
    st.subheader("📅 選擇日曆")
    
    selected_cal_id = st.selectbox(
        "切換當前檢視的日曆：",
        options=list(user_accessible_cals.keys()),
        format_func=lambda x: user_accessible_cals[x]
    )
    
    st.divider()
    st.subheader("➕ 共用日曆管理")
    
    with st.expander("建立新的共用日曆"):
        with st.form("create_cal_form"):
            new_cal_name = st.text_input("日曆名稱", placeholder="例如：專案小組 / 家族行事曆")
            if st.form_submit_button("建立"):
                if new_cal_name.strip():
                    new_id = f"shared_{uuid.uuid4().hex[:8]}"
                    all_calendars[new_id] = {
                        "name": f"👥 {new_cal_name.strip()}",
                        "members": [current_user],
                        "events": {}
                    }
                    save_json(CALENDARS_FILE, all_calendars)
                    st.success("建立成功！")
                    st.rerun()

    with st.expander("輸入邀請碼加入"):
        with st.form("join_cal_form"):
            invite_code = st.text_input("請貼上邀請碼 (ID)").strip()
            if st.form_submit_button("加入日曆"):
                if invite_code in all_calendars:
                    if current_user not in all_calendars[invite_code]["members"]:
                        all_calendars[invite_code]["members"].append(current_user)
                        save_json(CALENDARS_FILE, all_calendars)
                        st.success("成功加入該共用日曆！")
                        st.rerun()
                    else:
                        st.info("你已經在這個日曆中了！")
                else:
                    st.error("找不到此邀請碼對應的日曆！")

    current_cal_data = all_calendars[selected_cal_id]
    if selected_cal_id != personal_cal_id:
        st.divider()
        st.subheader("🔑 邀請其他人加入")
        st.caption("複製下方邀請碼給朋友，對方就能加入此共用日曆：")
        st.code(selected_cal_id, language="text")
        st.caption(f"成員：{', '.join(current_cal_data['members'])}")

current_events = current_cal_data["events"]

# ----------------- 3. 畫面中間彈出視窗 (Modal / Dialog) -----------------
@st.dialog("📅 管理行程")
def manage_events_dialog(date_str):
    st.caption(f"日期：**{date_str}** ｜ 日曆：**{current_cal_data['name']}**")
    
    # 選擇事件類別 (卡片風格)
    cat = st.selectbox("📌 選擇事件類別", list(CATEGORY_COLORS.keys()))
    
    with st.form(key=f"modal_add_{date_str}"):
        title = st.text_input("事件標題 *", placeholder="例：數學期末考 / 開會")
        note = st.text_input("備註 (選填)", placeholder="補充說明...")
        
        if st.form_submit_button("➕ 新增事件", use_container_width=True):
            if title.strip():
                if date_str not in current_events:
                    current_events[date_str] = []
                current_events[date_str].append({
                    "category": cat,
                    "title": title.strip(),
                    "note": note.strip(),
                    "author": current_user
                })
                save_json(CALENDARS_FILE, all_calendars)
                st.success("新增成功！")
                st.rerun()
            else:
                st.error("請輸入事件標題！")
                
    # 顯示當天已存在的行程
    day_events = current_events.get(date_str, [])
    if day_events:
        st.divider()
        st.markdown("**📋 當日已有行程：**")
        for idx, evt in enumerate(day_events):
            c = CATEGORY_COLORS.get(evt["category"], CATEGORY_COLORS["行政"])
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
                    st.rerun()

# ----------------- 4. 日曆主介面與抬頭 -----------------
today = datetime.date.today()
if "current_year" not in st.session_state:
    st.session_state.current_year = today.year
if "current_month" not in st.session_state:
    st.session_state.current_month = today.month

st.title(f"{current_cal_data['name']}")

# 頂部導覽列：解決手機版 < 今天 > 垂直變形問題
c_head1, c_head2, c_head3, c_head4 = st.columns([3, 1, 1, 1])
with c_head1:
    st.markdown(f"#### 🗓️ {st.session_state.current_year} 年 {st.session_state.current_month} 月")
with c_head2:
    if st.button("＜", use_container_width=True):
        if st.session_state.current_month == 1:
            st.session_state.current_month = 12
            st.session_state.current_year -= 1
        else:
            st.session_state.current_month -= 1
        st.rerun()
with c_head3:
    if st.button("今天", use_container_width=True):
        st.session_state.current_year = today.year
        st.session_state.current_month = today.month
        st.rerun()
with c_head4:
    if st.button("＞", use_container_width=True):
        if st.session_state.current_month == 12:
            st.session_state.current_month = 1
            st.session_state.current_year += 1
        else:
            st.session_state.current_month += 1
        st.rerun()

# ----------------- 5. 繪製 HTML 響應式網格月曆 -----------------
cal = calendar.Calendar(firstweekday=6)
month_days = cal.monthdayscalendar(st.session_state.current_year, st.session_state.current_month)

html_code = """
<style>
.cal-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    margin-top: 10px;
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
    padding: 3px;
    border: 1px solid #e9ecef;
    background-color: #ffffff;
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
                c = CATEGORY_COLORS.get(evt["category"], CATEGORY_COLORS["行政"])
                tags_html += f"<div class='cal-tag' style='background:{c['bg']}; color:{c['text']};'>{c['icon']}{evt['title']}</div>"
            
            if len(day_events) > 2:
                tags_html += f"<div style='font-size:8px; color:#888;'>+{len(day_events)-2}</div>"
                
            html_code += f"<td>{day_num_html}{tags_html}</td>"
    html_code += "</tr>"

html_code += "</tbody></table>"

# 渲染月曆
st.markdown(html_code, unsafe_allow_html=True)

# ----------------- 6. 點選日期開啟懸浮視窗 (Modal) -----------------
st.write("##")
selected_date = st.date_input("👇 點選日期彈出「行程管理視窗」：", value=today)

if st.button("✨ 開啟該日行程管理視窗", use_container_width=True):
    manage_events_dialog(selected_date.strftime("%Y-%m-%d"))

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
        c = CATEGORY_COLORS.get(evt["category"], CATEGORY_COLORS["行政"])
        days_left = (evt_date - today).days
        day_text = "今天" if days_left == 0 else f"{days_left} 天後"
        st.markdown(
            f"• **{d_str}** ({day_text}) — <span style='color:{c['text']}; font-weight:bold;'>{c['icon']} [{evt['category']}] {evt['title']}</span>",
            unsafe_allow_html=True
        )
else:
    st.info("此日曆近期尚無規劃行程。")
