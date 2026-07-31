import streamlit as st
import datetime
import calendar
import json
import os

st.set_page_config(page_title="簡約行事曆", layout="centered")

DATA_FILE = "calendar_events.json"

CATEGORY_COLORS = {
    "考試": {"bg": "#FFF0F0", "text": "#E53935", "icon": "📖"},
    "作業": {"bg": "#FFFDE7", "text": "#FB8C00", "icon": "📄"},
    "練習": {"bg": "#E8F5E9", "text": "#2E7D32", "icon": "🏋️"},
    "備忘": {"bg": "#E3F2FD", "text": "#1E88E5", "icon": "✏️"},
    "批改": {"bg": "#F3E5F5", "text": "#8E24AA", "icon": "📝"},
    "出題": {"bg": "#E0F7FA", "text": "#0288D1", "icon": "📋"},
    "行政": {"bg": "#F5F5F5", "text": "#616161", "icon": "📁"},
}

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

st.title("📅 簡約線上行事曆")

# 日期選擇與操作區
col1, col2 = st.columns([2, 1])

with col1:
    selected_date = st.date_input("選擇日期區間/檢視日期", datetime.date.today())
    date_key = selected_date.strftime("%Y-%m-%d")

with col2:
    st.write("---")
    st.write(f"目前選擇：**{date_key}**")

# 新增 / 編輯區
with st.expander("➕ 新增 / 編輯此日期的事件", expanded=True):
    cat = st.selectbox("分類", list(CATEGORY_COLORS.keys()))
    title = st.text_input("事件標題")
    note = st.text_input("備註 (選填)")

    if st.button("儲存事件"):
        if title.strip():
            if date_key not in st.session_state.events:
                st.session_state.events[date_key] = []
            
            st.session_state.events[date_key].append({
                "category": cat,
                "title": title.strip(),
                "note": note.strip()
            })
            save_events(st.session_state.events)
            st.success("儲存成功！")
            st.rerun()

# 顯示選取日期的行程
st.subheader(f"📌 {date_key} 的所有行程")
if date_key in st.session_state.events and st.session_state.events[date_key]:
    for idx, evt in enumerate(st.session_state.events[date_key]):
        c = CATEGORY_COLORS.get(evt["category"], CATEGORY_COLORS["行政"])
        
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(
                f"<div style='background-color:{c['bg']}; color:{c['text']}; padding:10px; border-radius:8px; font-weight:bold; margin-bottom:5px;'>"
                f"{c['icon']} [{evt['category']}] {evt['title']} "
                f"<span style='font-weight:normal; font-size:0.9em; color:#666;'>({evt.get('note', '')})</span>"
                f"</div>", 
                unsafe_allow_html=True
            )
        with c2:
            if st.button("刪除", key=f"del_{date_key}_{idx}"):
                st.session_state.events[date_key].pop(idx)
                if not st.session_state.events[date_key]:
                    del st.session_state.events[date_key]
                save_events(st.session_state.events)
                st.rerun()
else:
    st.info("今天沒有安排行程")

# 總覽即將到來行程
st.subheader("🔮 即將到來的行程")
upcoming = []
today = datetime.date.today()

for d_str, evts in st.session_state.events.items():
    evt_date = datetime.datetime.strptime(d_str, "%Y-%m-%d").date()
    if evt_date >= today:
        for evt in evts:
            upcoming.append((evt_date, d_str, evt))

upcoming.sort(key=lambda x: x[0])

if upcoming:
    for evt_date, d_str, evt in upcoming[:10]:
        c = CATEGORY_COLORS.get(evt["category"], CATEGORY_COLORS["行政"])
        days_left = (evt_date - today).days
        day_text = "今天" if days_left == 0 else f"{days_left} 天後"
        
        st.write(f"• **{d_str}** ({day_text}) - {c['icon']} `{evt['category']}` **{evt['title']}**")
else:
    st.write("近期無任何規劃。")
