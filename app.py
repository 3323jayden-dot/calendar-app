import streamlit as st
import datetime
import calendar
import json
import os
import uuid
from streamlit_local_storage import LocalStorage

# 頁面基本設定
st.set_page_config(page_title="多功能共享線上行事曆", layout="centered")

# 初始化 LocalStorage
local_storage = LocalStorage()

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

# ----------------- 1. 本地儲存 (LocalStorage) 登入機制 -----------------
users = load_json(USER_FILE, {"admin": "123456"})

# 從瀏覽器本地儲存讀取紀錄
saved_user = local_storage.getItem("calendar_app_user")

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

# 如果 Session 沒有，但 LocalStorage 有紀錄，直接登入
if st.session_state.logged_in_user is None and saved_user:
    if saved_user in users:
        st.session_state.logged_in_user = saved_user
        st.rerun()

# 未登入狀態：顯示登入與註冊頁面
if st.session_state.logged_in_user is None:
    st.title("🔐 線上行事曆系統")
    tab_login, tab_register = st.tabs(["🔑 登入帳號", "📝 註冊新帳號"])
    
    with tab_login:
        with st.form("login_form"):
            username = st.text_input("帳號").strip().lower()
            password = st.text_input("密碼", type="password").strip()
            
            if st.form_submit_button("登入 (永久自動記憶)", use_container_width=True):
                if username in users and users[username] == password:
                    st.session_state.logged_in_user = username
                    # 寫入瀏覽器本地儲存 (永遠存在，除非手動清除瀏覽器紀錄)
                    local_storage.setItem("calendar_app_user", username)
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

current_user = st.session_state.logged_in_user

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

# 側邊欄：個人資訊與日曆切換
with st.sidebar:
    st.write(f"👤 當前帳號：**{current_user}**")
    
    if st.button("🚪 登出系統", use_container_width=True):
        st.session_state.logged_in_user = None
        local_storage.deleteItem("calendar_app_user")  # 清除本地儲存
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
    
    # 建立新的共用日曆
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

    # 透過邀請碼加入共用日曆
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

# ----------------- 3. 日曆主介面 -----------------
today = datetime.date.today()
if "current_year" not in st.session_state:
    st.session_state.current_year = today.year
if "current_month" not in st.session_state:
    st.session_state.current_month = today.month

col_title, col_prev, col_today, col_next = st.columns([4, 1, 1, 1])

with col_title:
    st.title(f"{current_cal_data['name']}")
    st.caption(f"🗓️ {st.session_state.current_year} 年 {st.session_state.current_month} 月")

with col_prev:
    st.write("##")
    if st.button("＜"):
        if st.session_state.current_month == 1:
            st.session_state.current_month = 12
            st.session_state.current_year -= 1
        else:
            st.session_state.current_month -= 1
        st.rerun()

with col_today:
    st.write("##")
    if st.button("今天"):
        st.session_state.current_year = today.year
        st.session_state.current_month = today.month
        st.rerun()

with col_next:
    st.write("##")
    if st.button("＞"):
        if st.session_state.current_month == 12:
            st.session_state.current_month = 1
            st.session_state.current_year += 1
        else:
            st.session_state.current_month += 1
        st.rerun()

# 星期標頭
weekdays = [("日", "#FF6B6B"), ("一", "#333"), ("二", "#333"), ("三", "#333"), ("四", "#333"), ("五", "#333"), ("六", "#00B2FE")]
cols = st.columns(7)
for idx, (day_name, color) in enumerate(weekdays):
    cols[idx].markdown(f"<div style='text-align:center; font-weight:bold; color:{color}; padding-bottom:5px;'>{day_name}</div>", unsafe_allow_html=True)

# 月曆網格
cal = calendar.Calendar(firstweekday=6)
month_days = cal.monthdayscalendar(st.session_state.current_year, st.session_state.current_month)

for week in month_days:
    grid_cols = st.columns(7)
    for col_idx, day in enumerate(week):
        with grid_cols[col_idx]:
            if day != 0:
                date_key = f"{st.session_state.current_year}-{st.session_state.current_month:02d}-{day:02d}"
                is_today = (st.session_state.current_year == today.year and 
                            st.session_state.current_month == today.month and 
                            day == today.day)
                
                day_events = current_events.get(date_key, [])
                
                tags_html = ""
                for evt in day_events[:2]:
                    c = CATEGORY_COLORS.get(evt["category"], CATEGORY_COLORS["行政"])
                    tags_html += f"<div style='background:{c['bg']}; color:{c['text']}; font-size:10px; border-radius:3px; margin-top:2px; padding:1px 3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{c['icon']}{evt['title']}</div>"
                
                if len(day_events) > 2:
                    tags_html += f"<div style='font-size:9px; color:#888;'>+{len(day_events)-2}條</div>"

                btn_type = "primary" if is_today else "secondary"
                
                if st.button(f"{day}", key=f"btn_{date_key}", type=btn_type, use_container_width=True):
                    st.session_state.selected_date = date_key
                
                if tags_html:
                    st.markdown(f"<div style='margin-top:-8px; margin-bottom:8px;'>{tags_html}</div>", unsafe_allow_html=True)

# ----------------- 4. 行程編輯管理 -----------------
if "selected_date" in st.session_state:
    st.divider()
    s_date = st.session_state.selected_date
    st.subheader(f"📝 管理行程 ({s_date}) — 於 {current_cal_data['name']}")
    
    with st.form(key=f"add_form_{s_date}", clear_on_submit=True):
        col_cat, col_title_in, col_note_in = st.columns([1, 2, 2])
        with col_cat:
            cat = st.selectbox("分類", list(CATEGORY_COLORS.keys()))
        with col_title_in:
            title = st.text_input("事件標題 *", placeholder="例如：開會 / 專案發表")
        with col_note_in:
            note = st.text_input("備註 (選填)", placeholder="例如：線上會議連結")
        
        submitted = st.form_submit_button("➕ 新增行程", use_container_width=True)
        if submitted and title.strip():
            if s_date not in current_events:
                current_events[s_date] = []
            
            current_events[s_date].append({
                "category": cat,
                "title": title.strip(),
                "note": note.strip(),
                "author": current_user
            })
            save_json(CALENDARS_FILE, all_calendars)
            st.success("行程已同步新增！")
            st.rerun()

    if s_date in current_events and current_events[s_date]:
        for idx, evt in enumerate(current_events[s_date]):
            c = CATEGORY_COLORS.get(evt["category"], CATEGORY_COLORS["行政"])
            author_tag = f" (由 {evt.get('author', '未知')} 新增)" if selected_cal_id != personal_cal_id else ""
            
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"<div style='background-color:{c['bg']}; color:{c['text']}; padding:8px 12px; border-radius:8px; font-weight:bold; margin-bottom:5px;'>"
                    f"{c['icon']} [{evt['category']}] {evt['title']} "
                    f"<span style='font-weight:normal; font-size:12px; color:#666;'>({evt.get('note', '')}){author_tag}</span></div>",
                    unsafe_allow_html=True
                )
            with c2:
                if st.button("刪除", key=f"del_{s_date}_{idx}", use_container_width=True):
                    current_events[s_date].pop(idx)
                    if not current_events[s_date]:
                        del current_events[s_date]
                    save_json(CALENDARS_FILE, all_calendars)
                    st.rerun()

# ----------------- 5. 即將到來的行程 -----------------
st.divider()
st.subheader("🔮 即將到來的行程")
upcoming = []
for d_str, evts in current_events.items():
    evt_date = datetime.datetime.strptime(d_str, "%Y-%m-%d").date()
    if evt_date >= today:
        for evt in evts:
            upcoming.append((evt_date, d_str, evt))

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
