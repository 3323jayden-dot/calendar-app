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

# ----------------- 使用者登入機制 -----------------
# 預設帳號密碼對照表 (你可以自由修改或新增帳密)
USER_DATABASE = {
    "admin": "123456",
    "jayden": "password",
    "user1": "1234"
}

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

# 如果尚未登入，顯示登入畫面
if st.session_state.logged_in_user is None:
    st.title("🔐 請先登入系統")
    st.info("輸入帳號密碼以存取您的個人專屬行事曆")
    
    with st.form("login_form"):
        username = st.text_input("帳號").strip().lower()
        password = st.text_input("密碼", type="password").strip()
        submit_login = st.form_submit_button("登入", use_container_width=True)
        
        if submit_login:
            if username in USER_DATABASE and USER_DATABASE[username] == password:
                st.session_state.logged_in_user = username
                st.success(f"登入成功！歡迎，{username}")
                st.rerun()
            else:
                st.error("帳號或密碼錯誤，請重新輸入！")
    st.stop()  # 未登入則中斷執行後續畫面

# ----------------- 個人專屬檔案讀取與儲存 -----------------
current_user = st.session_state.logged_in_user
DATA_FILE = f"calendar_{current_user}.json"  # 每個人獨立的檔案名稱

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

# ----------------- 頂部導覽列（含登出） -----------------
col_user_info, col_logout = st.columns([4, 1])
with col_user_info:
    st.caption(f"👤 當前使用者：**{current_user}** (專屬資料檔：`{DATA_FILE}`)")
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
