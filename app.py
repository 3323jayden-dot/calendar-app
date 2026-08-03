import calendar
import hashlib
import io
import json
import os
import random
import re
import string
from datetime import date, datetime, timedelta

import extra_streamlit_components as stx
import pandas as pd
import pypdf
import requests
import streamlit as st
from groq import Groq
from huggingface_hub import InferenceClient
from PIL import Image, ImageEnhance, ImageOps

# ==============================================================================
# 0. 基本頁面配置與檔案設定
# ==============================================================================
st.set_page_config(
    page_title="多功能雲端助理與行事曆系統",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

USERS_FILE = "users.json"
EVENTS_FILE = "events.json"
CALENDARS_FILE = "calendars.json"

ADMIN_EMAIL = "3323jayden@gmail.com"  # 系統管理者帳號

# 額度設定：Free (50次/10金幣), Pro (1000次/100金幣)
PLAN_LIMITS = {
    "free": {"chat": 50, "coins": 10},
    "pro": {"chat": 1000, "coins": 100},
}

# ==============================================================================
# 1. 安全資安輔助函式 (密碼雜湊與 Salt)
# ==============================================================================
SALT = "calendar_app_secure_salt_2026"


def hash_password(password: str) -> str:
    """將密碼進行 SHA-256 雜湊處理"""
    return hashlib.sha256((password + SALT).encode("utf-8")).hexdigest()


def verify_password(stored_password: str, provided_password: str) -> bool:
    """驗證密碼，同時相容舊的明碼與新的雜湊密碼"""
    # 判斷是否已經是 64 字元的 SHA-256 雜湊
    if len(stored_password) == 64 and all(
        c in "0123456789abcdef" for c in stored_password.lower()
    ):
        return stored_password == hash_password(provided_password)
    # 若為舊資料明碼，直接比對
    return stored_password == provided_password


# ==============================================================================
# 2. JSON 資料讀寫與輔助函式
# ==============================================================================
def load_data(filename, default_val):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_val
    return default_val


def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


users = load_data(USERS_FILE, {})
events = load_data(EVENTS_FILE, [])
calendars_data = load_data(CALENDARS_FILE, [])


def check_and_update_usage(user_email, usage_type="chat"):
    """檢查對話額度或金幣額度"""
    if user_email not in users:
        return False, "用戶不存在"

    user_info = users[user_email]
    today_str = str(date.today())

    # 每日重置聊天額度
    if user_info.get("last_use_date") != today_str:
        user_info["last_use_date"] = today_str
        user_info["daily_usage"] = 0
        save_data(USERS_FILE, users)

    role = user_info.get("role", "free")
    limits = PLAN_LIMITS.get(role, PLAN_LIMITS["free"])

    if usage_type == "chat":
        limit = limits["chat"]
        current = user_info.get("daily_usage", 0)
        if (
            current >= limit
            and not user_info.get("is_unlimited")
            and user_email != ADMIN_EMAIL
        ):
            return (
                False,
                f"⚠️ 您今日的 AI 對話額度已達上限 ({current}/{limit} 次)！",
            )
        return True, ""

    elif usage_type == "coins":
        # 繪圖金幣檢查
        coins = user_info.get("coins", limits["coins"])
        if coins < 1 and user_email != ADMIN_EMAIL:
            return False, f"⚠️ 您的繪圖金幣不足 (剩餘 {coins} 金幣)！"
        return True, ""


# ==============================================================================
# 3. 自動免登入檢測 & 登入介面
# ==============================================================================
url_user = st.query_params.get("user", "")

if not st.session_state.get("logged_in"):
    if url_user and url_user in users:
        st.session_state.logged_in = True
        st.session_state.user_email = url_user
    else:
        st.session_state.logged_in = False
        st.session_state.user_email = ""

if not st.session_state.logged_in:
    st.markdown(
        "<style>[data-testid='stSidebar'] {display: none;}</style>",
        unsafe_allow_html=True,
    )
    _, main_col, _ = st.columns([1, 2, 1])

    with main_col:
        st.markdown(
            "<h1 style='text-align: center;'>🔐 多功能數位工作助理</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align: center; color: #666;'>請先登入或註冊帳號以使用完整系統功能</p>",
            unsafe_allow_html=True,
        )

        tab_login, tab_reg = st.tabs(["🔑 帳號登入", "📝 會員註冊"])

        with tab_login:
            with st.form("login_form"):
                email_input = st.text_input("電子郵件 (Email)").strip().lower()
                password_input = st.text_input("密碼", type="password")
                remember_me = st.checkbox("保持登入狀態（下次自動登入）", value=True)
                submit_login = st.form_submit_button(
                    "🚀 登入系統", use_container_width=True, type="primary"
                )

                if submit_login:
                    if email_input in users and verify_password(
                        users[email_input]["password"], password_input
                    ):
                        # 自動將舊明碼轉為雜湊碼儲存
                        if (
                            users[email_input]["password"]
                            == password_input  # 舊明碼
                        ):
                            users[email_input]["password"] = hash_password(
                                password_input
                            )
                            save_data(USERS_FILE, users)

                        st.session_state.logged_in = True
                        st.session_state.user_email = email_input
                        if remember_me:
                            st.query_params["user"] = email_input
                        st.success("🎉 登入成功！正在進入系統...")
                        st.rerun()
                    else:
                        st.error("❌ 帳號或密碼輸入錯誤！")

        with tab_reg:
            with st.form("register_form"):
                reg_email = st.text_input("電子郵件 (Email)").strip().lower()
                reg_name = st.text_input("使用者暱稱").strip()
                reg_password = st.text_input("設定密碼", type="password")
                submit_reg = st.form_submit_button(
                    "✨ 註冊帳號", use_container_width=True
                )

                if submit_reg:
                    if not reg_email or not reg_password or not reg_name:
                        st.error("請完整填寫所有欄位！")
                    elif reg_email in users:
                        st.error("此電子郵件已經註冊過了！")
                    else:
                        role = "pro" if reg_email == ADMIN_EMAIL else "free"
                        init_coins = PLAN_LIMITS[role]["coins"]
                        users[reg_email] = {
                            "name": reg_name,
                            "password": hash_password(reg_password),  # 雜湊加密
                            "role": role,
                            "coins": init_coins,
                            "daily_usage": 0,
                            "last_use_date": str(date.today()),
                            "ai_profile": "",
                        }
                        save_data(USERS_FILE, users)
                        st.success("🎉 註冊成功！請切換至「帳號登入」頁籤進行登入。")

    st.stop()


# ==============================================================================
# 4. 側邊欄 (簡化版 + 單一頁面切換鈕 + 管理員後台)
# ==============================================================================
u_data = users.get(st.session_state.user_email, {})
current_user_name = u_data.get("name", "會員")
user_role = u_data.get("role", "free")
user_coins = u_data.get(
    "coins", PLAN_LIMITS.get(user_role, {}) .get("coins", 10)
)

st.sidebar.title("🔐 會員專區")
st.sidebar.success(f"歡迎，**{current_user_name}**！")

# 身分與額度標籤
chat_limit = PLAN_LIMITS.get(user_role, {}).get("chat", 50)
st.sidebar.markdown(f"**身分**：`{user_role.upper()}`")
st.sidebar.markdown(
    f"**今日對話**：`{u_data.get('daily_usage', 0)} / {chat_limit}` 次"
)
st.sidebar.markdown(f"**繪圖金幣**：`🪙 {user_coins}` 個")

st.sidebar.divider()

# ✨【單一切換按鈕】快速切換核心介面
if "active_mode" not in st.session_state:
    st.session_state.active_mode = "🤖 AI 對話助理"

btn_label = (
    "📅 切換至行事曆檢視"
    if st.session_state.active_mode == "🤖 AI 對話助理"
    else "🤖 切換至 AI 對話助理"
)
if st.sidebar.button(
    btn_label, use_container_width=True, type="primary"
):
    if st.session_state.active_mode == "🤖 AI 對話助理":
        st.session_state.active_mode = "📅 視覺化日曆"
    else:
        st.session_state.active_mode = "🤖 AI 對話助理"
    st.rerun()

st.sidebar.divider()

# 🚪 安全登出按鈕
if st.sidebar.button("🚪 安全登出", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.query_params.clear()
    st.rerun()

# 🛡️ 管理員專屬後台 (隱藏舊密碼，只提供重設功能與金幣調整)
if st.session_state.logged_in and st.session_state.user_email == ADMIN_EMAIL:
    st.sidebar.divider()
    with st.sidebar.expander("🛡️ 後台管理 (Admin Only)", expanded=False):
        if users:
            selected_user_email = st.selectbox(
                "選擇管理的會員", list(users.keys())
            )
            if selected_user_email:
                u_info = users[selected_user_email]
                st.caption(f"暱稱: {u_info.get('name')}")

                new_role = st.selectbox(
                    "調整等級",
                    ["free", "pro"],
                    index=0 if u_info.get("role") == "free" else 1,
                )

                new_coins = st.number_input(
                    "調整繪圖金幣數量",
                    min_value=0,
                    value=int(u_info.get("coins", 10)),
                )

                new_pwd = st.text_input(
                    "重設新密碼 (若無須修改請留空)",
                    type="password",
                    key="admin_reset_pwd",
                )

                if st.button("💾 保存變更", use_container_width=True):
                    users[selected_user_email]["role"] = new_role
                    users[selected_user_email]["coins"] = new_coins
                    if new_pwd.strip():
                        users[selected_user_email]["password"] = hash_password(
                            new_pwd.strip()
                        )
                    save_data(USERS_FILE, users)
                    st.success("✅ 會員資料已安全更新！")
                    st.rerun()


# ==============================================================================
# 5. 主畫面 A：🤖 極簡 AI 對話助理 (自動判斷意圖 + 設定集中化)
# ==============================================================================
if st.session_state.active_mode == "🤖 AI 對話助理":
    st.title("🤖 AI 數位智囊")

    # 個人設定與偏好控制項收納於頂部 Expander，不干擾聊天
    with st.expander("⚙️ AI 個人化設定與模型偏好", expanded=False):
        st.caption("設定您的個人背景與 AI 運作方式。")
        current_profile = u_data.get("ai_profile", "")
        new_profile = st.text_area(
            "個人背景與習慣偏好：",
            value=current_profile,
            placeholder="例如：我是大學生，習慣簡明扼要的回覆...",
            height=80,
        )
        if st.button("💾 儲存 AI 個人化設定"):
            users[st.session_state.user_email]["ai_profile"] = new_profile.strip()
            save_data(USERS_FILE, users)
            st.toast("✅ 偏好設定已更新！")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # 渲染聊天歷史
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 對話框輸入
    if prompt := st.chat_input("請輸入訊息 (AI 將自動識別意圖或幫您排行程)..."):
        allowed, err_msg = check_and_update_usage(
            st.session_state.user_email, "chat"
        )
        if not allowed:
            st.error(err_msg)
        elif "GROQ_API_KEY" not in st.secrets:
            st.error("⚠️ 未設定 GROQ_API_KEY！")
        else:
            # 扣減額度
            users[st.session_state.user_email]["daily_usage"] = (
                users[st.session_state.user_email].get("daily_usage", 0) + 1
            )
            save_data(USERS_FILE, users)

            st.session_state.chat_messages.append(
                {"role": "user", "content": prompt}
            )
            with st.chat_message("user"):
                st.markdown(prompt)

            # AI 自動意圖判斷與回覆
            with st.chat_message("assistant"):
                with st.spinner("AI 正在思考並判斷意圖..."):
                    try:
                        client = Groq(api_key=st.secrets["GROQ_API_KEY"])

                        # 系統提示：自動識別意圖 + 支援行程規劃
                        sys_prompt = f"""
你是一個智慧型助理。今天日期是 {date.today()}。
使用者的個人偏好設定：{u_data.get('ai_profile', '無')}。

【核心功能】
1. 請自動判斷使用者的意圖（閒聊、問答、文案潤飾或行程規劃）。
2. 若使用者提及要在特定日期安排行程/事項，請在回答最後附上一段標準 JSON 格式的行程建議指令，格式如：
`[EVENT_ADD: {{"date": "YYYY-MM-DD", "title": "行程名稱", "category": "一般"}}]`
3. 若只是普通閒聊或問答，則正常親切回答即可。
"""
                        messages_to_send = [
                            {"role": "system", "content": sys_prompt}
                        ] + [
                            {"role": m["role"], "content": m["content"]}
                            for m in st.session_state.chat_messages
                        ]

                        response = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=messages_to_send,
                            temperature=0.7,
                        )

                        ai_reply = response.choices[0].message.content

                        # 自動剖析是否寫入行程
                        event_match = re.search(
                            r"\[EVENT_ADD:\s*({.*?})\]", ai_reply
                        )
                        if event_match:
                            try:
                                ev_data = json.loads(event_match.group(1))
                                ev_data["creator"] = st.session_state.user_email
                                events.append(ev_data)
                                save_data(EVENTS_FILE, events)
                                ai_reply += (
                                    f"\n\n*(✅ 已自動將行程「{ev_data.get('title')}」新增至"
                                    f" {ev_data.get('date')} 日曆！)*"
                                )
                            except Exception:
                                pass

                        st.markdown(ai_reply)
                        st.session_state.chat_messages.append(
                            {"role": "assistant", "content": ai_reply}
                        )
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ 發生錯誤：{e}")


# ==============================================================================
# 6. 主畫面 B：📅 視覺化日曆 (彈出式對話框 st.dialog，排版絕不亂跑)
# ==============================================================================
elif st.session_state.active_mode == "📅 視覺化日曆":
    st.title("📅 視覺化月曆與行程管理")

    user_email = st.session_state.user_email
    today = date.today()

    active_events = [
        e for e in events if e.get("creator") == user_email
    ]

    c_y, c_m = st.columns(2)
    with c_y:
        sel_year = st.number_input(
            "年份", min_value=2020, max_value=2030, value=today.year
        )
    with c_m:
        sel_month = st.number_input(
            "月份", min_value=1, max_value=12, value=today.month
        )

    # 7x7 固定網格 CSS，完全不會因為表單拉撐
    st.markdown(
        """
        <style>
        .cal-container { background-color: #f8fafc; padding: 16px; border-radius: 16px; border: 1px solid #e2e8f0; }
        .cal-grid { display: grid !important; grid-template-columns: repeat(7, 1fr) !important; gap: 8px !important; }
        .cal-header { text-align: center; font-weight: bold; font-size: 14px; color: #64748b; padding: 4px 0; }
        .cal-day-card { background-color: #ffffff; border-radius: 10px; height: 75px; padding: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); display: flex; flex-direction: column; }
        .cal-day-card.today { border: 2px solid #3b82f6; background-color: #eff6ff; }
        .day-num { font-size: 14px; font-weight: 700; color: #1e293b; }
        .event-chip { font-size: 10px; background-color: #dbeafe; color: #1e40af; padding: 2px 4px; border-radius: 4px; margin-top: 4px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
        </style>
    """,
        unsafe_allow_html=True,
    )

    cal_obj = calendar.Calendar(firstweekday=6)
    month_days = cal_obj.monthdayscalendar(sel_year, sel_month)

    grid_html = "<div class='cal-container'><div class='cal-grid'>"
    for day_name in ["日", "一", "二", "三", "四", "五", "六"]:
        grid_html += f"<div class='cal-header'>{day_name}</div>"
    grid_html += "</div>"

    for week in month_days:
        grid_html += "<div class='cal-grid' style='margin-top: 8px;'>"
        for day in week:
            if day == 0:
                grid_html += "<div></div>"
            else:
                day_str = f"{sel_year}-{sel_month:02d}-{day:02d}"
                is_today = (
                    sel_year == today.year
                    and sel_month == today.month
                    and day == today.day
                )
                day_evs = [e for e in active_events if e.get("date") == day_str]
                card_cls = "cal-day-card today" if is_today else "cal-day-card"

                chip_html = ""
                if day_evs:
                    chip_html = f"<div class='event-chip'>📌 {day_evs[0].get('title')}</div>"
                    if len(day_evs) > 1:
                        chip_html += f"<div class='event-chip'>+{len(day_evs)-1} 更多</div>"

                grid_html += f"<div class='{card_cls}'><div class='day-num'>{day}</div>{chip_html}</div>"
        grid_html += "</div>"
    grid_html += "</div>"

    st.markdown(grid_html, unsafe_allow_html=True)

    st.divider()

    # 📌 彈出式視窗定義 (利用 st.dialog)
    @st.dialog("📅 編輯與管理當日行程")
    def manage_events_dialog(target_date_str):
        st.subheader(f"📌 {target_date_str} 的行程")

        day_evs = [e for e in active_events if e.get("date") == target_date_str]

        if not day_evs:
            st.info("當天尚無行程安排。")
        else:
            for idx, ev in enumerate(day_evs):
                c_info, c_del = st.columns([4, 1])
                with c_info:
                    st.write(
                        f"**• {ev.get('title')}** (`{ev.get('category','一般')}`)"
                    )
                with c_del:
                    if st.button("🗑️", key=f"dlg_del_{target_date_str}_{idx}"):
                        events.remove(ev)
                        save_data(EVENTS_FILE, events)
                        st.rerun()

        st.divider()
        st.markdown("##### ➕ 新增行程")
        with st.form(key=f"dlg_add_form_{target_date_str}"):
            new_title = st.text_input("行程名稱")
            new_cate = st.selectbox(
                "分類", ["一般", "重要提醒", "個人私事", "工作會議"]
            )
            submit_dlg = st.form_submit_button("新增行程", use_container_width=True)

            if submit_dlg:
                if new_title.strip():
                    events.append({
                        "date": target_date_str,
                        "title": new_title.strip(),
                        "category": new_cate,
                        "creator": user_email,
                    })
                    save_data(EVENTS_FILE, events)
                    st.success("✅ 行程已新增！")
                    st.rerun()
                else:
                    st.error("請輸入名稱！")

    # 日期選擇觸發按鈕
    col_sel, col_btn = st.columns([3, 1])
    with col_sel:
        pick_date = st.date_input("選擇欲編輯的日期", value=today)
    with col_btn:
        st.write("")
        st.write("")
        if st.button("✏️ 彈出管理視窗", use_container_width=True, type="primary"):
            manage_events_dialog(pick_date.strftime("%Y-%m-%d"))

# ==============================================================================
# 7. 頁尾資訊
# ==============================================================================
st.divider()
st.markdown(
    "<div style='text-align: center; color: #888; font-size: 12px;'>© 2026 共享線上行事曆與數位助理系統 All Rights Reserved.</div>",
    unsafe_allow_html=True,
)
