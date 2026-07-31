import streamlit as st
import datetime
import calendar
import json
import os

# 頁面基本設定
st.set_page_config(page_title="簡約行事曆", layout="centered")

DATA_FILE = "calendar_events.json"

# 7 大類別配色定義
CATEGORY_COLORS = {
    "考試": {"bg": "#FFF0F0", "text": "#E53935", "icon": "📖"},
    "作業": {"bg": "#FFFDE7", "text": "#FB8C00", "icon": "📄"},
    "練習": {"bg": "#E8F5E9", "text": "#2E7D32", "icon": "🏋️"},
    "備忘": {"bg": "#E3F2FD", "text": "#1E88E5", "icon": "✏️"},
    "批改": {"bg": "#F3E5F5", "text": "#8E24AA", "icon": "📝"},
    "出題": {"bg": "#E0F7FA", "text": "#0288D1", "icon": "📋"},
    "行政": {"bg": "#F5F5F5", "text": "#616161", "icon": "📁"},
}

# 讀取與儲存 JSON
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

# 月份狀態控制
today = datetime.date.today()
if "current_year" not in st.session_state:
    st.session_state.current_year = today.year
if "current_month" not in st.session_state:
    st.session_state.current_month = today.month

# 標題與切換月份列
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

# 自訂 CSS 樣式 (模仿桌面版卡片與標籤風格)
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 8px;
    }
    .weekday-header {
        text-align: center;
        font-weight: bold;
        font-size: 16px;
        padding: 5px 0;
    }
    .today-card {
        background-color: #00BFA5 !important;
        color: white !important;
        border-radius: 8px;
        padding: 4px;
        text-align: center;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# 星期表頭
weekdays = [("日", "#FF6B6B"), ("一", "#333"), ("二", "#333"), ("三", "#333"), ("四", "#333"), ("五", "#333"), ("六", "#00B2FE")]
cols = st.columns(7)
for idx, (day_name, color) in enumerate(weekdays):
    cols[idx].markdown(f"<div class='weekday-header' style='color:{color};'>{day_name}</div>", unsafe_allow_html=True)

# 月曆網格生成
cal = calendar.Calendar(firstweekday=6)
month_days = cal.monthdayscalendar(st.session_state.current_year, st.session_state.current_month)

for week in month_days:
    grid_cols = st.columns(7)
    for col_idx, day in enumerate(week):
        with grid_cols[col_idx]:
            if day == 0:
                st.write("")  # 非本月日期留空
            else:
                date_key = f"{st.session_state.current_year}-{st.session_state.current_month:02d}-{day:02d}"
                is_today = (st.session_state.current_year == today.year and 
                            st.session_state.current_month == today.month and 
                            day == today.day)
                
                # 按鈕顯示日期與事件數
                day_events = st.session_state.events.get(date_key, [])
                btn_label = f"📌 {day}" if day_events else f"{day}"
                
                # 點擊日期按鈕開啟彈窗設定
                if st.button(btn_label, key=f"btn_{date_key}", type="primary" if is_today else "secondary"):
                    st.session_state.selected_date = date_key

                # 顯示該日期的事件彩色小標籤
                for evt in day_events[:2]:
                    c = CATEGORY_COLORS.get(evt["category"], CATEGORY_COLORS["行政"])
                    st.markdown(
                        f"<div style='background-color:{c['bg']}; color:{c['text']}; "
                        f"font-size:11px; padding:2px 4px; border-radius:4px; margin-top:2px; "
                        f"white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>"
                        f"{c['icon']}{evt['title']}</div>",
                        unsafe_allow_html=True
                    )
                if len(day_events) > 2:
                    st.caption(f"+{len(day_events)-2} 更多")

# 管理選取日期的事件 (彈窗區域)
if "selected_date" in st.session_state:
    st.divider()
    s_date = st.session_state.selected_date
    st.subheader(f"📝 管理行程：{s_date}")
    
    # 新增事件表單
    with st.form(key=f"add_form_{s_date}", clear_on_submit=True):
        col_cat, col_title_in, col_note_in = st.columns([1, 2, 2])
        with col_cat:
            cat = st.selectbox("分類", list(CATEGORY_COLORS.keys()))
        with col_title_in:
            title = st.text_input("事件標題 *", placeholder="例如：數學考試")
        with col_note_in:
            note = st.text_input("備註 (選填)", placeholder="例如：章節 1~3")
        
        submitted = st.form_submit_button("➕ 新增行程")
        if submitted and title.strip():
            if s_date not in st.session_state.events:
                st.session_state.events[s_date] = []
            st.session_state.events[s_date].append({
                "category": cat,
                "title": title.strip(),
                "note": note.strip()
            })
            save_events(st.session_state.events)
            st.success("已新增！")
            st.rerun()

    # 顯示並允許刪除該日期的行程
    if s_date in st.session_state.events and st.session_state.events[s_date]:
        for idx, evt in enumerate(st.session_state.events[s_date]):
            c = CATEGORY_COLORS.get(evt["category"], CATEGORY_COLORS["行政"])
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"<div style='background-color:{c['bg']}; color:{c['text']}; padding:8px 12px; border-radius:8px; font-weight:bold;'>"
                    f"{c['icon']} [{evt['category']}] {evt['title']} "
                    f"<span style='font-weight:normal; font-size:12px; color:#666;'>({evt.get('note', '')})</span></div>",
                    unsafe_allow_html=True
                )
            with c2:
                if st.button("刪除", key=f"del_{s_date}_{idx}"):
                    st.session_state.events[s_date].pop(idx)
                    if not st.session_state.events[s_date]:
                        del st.session_state.events[s_date]
                    save_events(st.session_state.events)
                    st.rerun()

# 即將到來的行程區塊
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
