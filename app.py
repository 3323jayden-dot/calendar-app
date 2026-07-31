import streamlit as st
import datetime
import calendar
import json
import os

# 頁面基本設定
st.set_page_config(page_title="個人專屬線上行事曆", layout="centered")

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

# ----------------- 帳號密碼檔 讀取與儲存 -----------------
def load_users():
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # 預設至少有一個管理員帳號 (帳號: admin, 密碼: 123456)
    default_users = {"admin": "123456"}
    save_users(default_users)
    return default_users

def save_users(users):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

# ----------------- 登入與註冊頁面 -----------------
if st.session_state.logged_in_user is None:
    st.title("🔐 線上行事曆系統")
    
    # 切換登入 / 註冊 分頁
    tab_login, tab_register = st.tabs(["🔑 登入帳號", "📝 註冊新帳號"])
    
    users = load_users()
    
    # --- 分頁 1：登入 ---
    with tab_login:
        with st.form("login_form"):
            username = st.text_input("帳號").strip().lower()
            password = st.text_input("密碼", type="password").strip()
            submit_login = st.form_submit_button("登入", use_container_width=True)
            
            if submit_login:
                if username in users and users[username] == password:
                    st.session_state.logged_in_user = username
                    st.success(f"登入成功！歡迎，{username}")
                    st.rerun()
                else:
                    st.error("帳號或密碼錯誤，請重新輸入！")
                    
    # --- 分頁 2：註冊 ---
    with tab_register:
        with st.form("register_form"):
            new_user = st.text_input("新帳號名稱 (建議英文/數字)").strip().lower()
            new_pass = st.text_input("設定密碼", type="password").strip()
            confirm_pass = st.text_input("確認密碼", type="password").strip()
            submit_register = st.form_submit_button("註冊並建立專屬行事曆", use_container_width=True)
            
            if submit_register:
                if not new_user or not new_pass:
                    st.warning("請填寫完整的帳號與密碼！")
                elif new_user in users:
                    st.error("這個帳號名稱已經有人使用了，請換一個！")
                elif new_pass != confirm_pass:
                    st.error("兩次輸入的密碼不一致，請重新確認！")
                else:
                    users[new_user] = new_pass
                    save_users(users)
                    st.success("🎉 註冊成功！請切換到「登入帳號」頁面進行登入。")

    st.stop()  # 未登入則停在此處

# ----------------- 個人專屬檔案讀取與儲存 -----------------
current_user = st.session_state.logged_in_user
DATA_FILE = f"calendar_{current_user}.json"

def load_events():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_events(events):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

if "events" not in st.session_state:
    st.session_state.events = load_events()

# ----------------- 頂部導覽列 -----------------
col_user_info, col_logout = st.columns([4, 1])
with col_user_info:
    st.caption(f"👤 當前使用者：**{current_user}** (獨立資料檔：`{DATA_FILE}`)")
with col_logout:
    if st.button("🚪 登出", use_container_width=True):
        st.session_state.logged_in_user = None
        if "events" in st.session_state:
            del st.session_state.events
        st.rerun()

# ----------------- 主介面：日曆系統 -----------------
today = datetime.date.today()
if "current_year" not in st.session_state:
    st.session_state.current_year = today.year
if "current_month" not in st.session_state:
    st.session_state.current_month = today.month

col_title, col_prev, col_today, col_next = st.columns([4, 1, 1, 1])

with col_title:
    st.title(f"📅 {st.session_state.current_year} 年 {st.session_state.current_month} 月")

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

# 星期欄位
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
                
                day_events = st.session_state.events.get(date_key, [])
                
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

# 管理選取日期的行程
if "selected_date" in st.session_state:
    st.divider()
    s_date = st.session_state.selected_date
    st.subheader(f"📝 管理行程：{s_date}")
    
    with st.form(key=f"add_form_{s_date}", clear_on_submit=True):
        col_cat, col_title_in, col_note_in = st.columns([1, 2, 2])
        with col_cat:
            cat = st.selectbox("分類", list(CATEGORY_COLORS.keys()))
        with col_title_in:
            title = st.text_input("事件標題 *", placeholder="例如：數學考試")
        with col_note_in:
            note = st.text_input("備註 (選填)", placeholder="例如：第 1~3 章")
        
        submitted = st.form_submit_button("➕ 新增行程", use_container_width=True)
        if submitted and title.strip():
            if s_date not in st.session_state.events:
                st.session_state.events[s_date] = []
            st.session_state.events[s_date].append({
                "category": cat,
                "title": title.strip(),
                "note": note.strip()
            })
            save_events(st.session_state.events)
            st.success("已成功新增！")
            st.rerun()

    if s_date in st.session_state.events and st.session_state.events[s_date]:
        for idx, evt in enumerate(st.session_state.events[s_date]):
            c = CATEGORY_COLORS.get(evt["category"], CATEGORY_COLORS["行政"])
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"<div style='background-color:{c['bg']}; color:{c['text']}; padding:8px 12px; border-radius:8px; font-weight:bold; margin-bottom:5px;'>"
                    f"{c['icon']} [{evt['category']}] {evt['title']} "
                    f"<span style='font-weight:normal; font-size:12px; color:#666;'>({evt.get('note', '')})</span></div>",
                    unsafe_allow_html=True
                )
            with c2:
                if st.button("刪除", key=f"del_{s_date}_{idx}", use_container_width=True):
                    st.session_state.events[s_date].pop(idx)
                    if not st.session_state.events[s_date]:
                        del st.session_state.events[s_date]
                    save_events(st.session_state.events)
                    st.rerun()

# 即將到來的行程
st.divider()
st.subheader("🔮 即將到來的行程")
upcoming = []
for d_str, evts in st.session_state.events.items():
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
    st.info("近期尚無規劃行程。")
