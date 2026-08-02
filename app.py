import calendar
import io
import json
import os
import random
import re
import string
import zipfile
from datetime import date, datetime, timedelta

from groq import Groq
import pandas as pd
from PIL import Image, ImageEnhance, ImageOps
import pypdf
import streamlit as st
import streamlit.components.v1 as components

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
ICON_URL = "https://raw.githubusercontent.com/3323jayden-dot/calendar-app/main/istockphoto-1033804852-612x612.jpg"

PLAN_LIMITS = {
    "free": 5,
    "pro": 100,
}


# ==============================================================================
# 1. JSON 資料讀寫與輔助函式
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


def get_user_calendars(user_email):
    if not user_email:
        return []
    user_cals = []
    for c in calendars_data:
        if c.get("owner") == user_email or user_email in c.get("members", []):
            user_cals.append(c)
    return user_cals


def get_user_all_events(user_email):
    my_cals = get_user_calendars(user_email)
    my_cal_codes = [c["code"] for c in my_cals]

    user_events = []
    for ev in events:
        if ev.get("creator") == user_email and not ev.get("cal_code"):
            user_events.append(ev)
        elif ev.get("cal_code") in my_cal_codes:
            user_events.append(ev)
    return user_events


def check_and_update_usage(user_email):
    if user_email not in users:
        return False, "用戶不存在", 0, 0

    user_info = users[user_email]
    today_str = str(date.today())

    if user_info.get("last_use_date") != today_str:
        user_info["last_use_date"] = today_str
        user_info["daily_usage"] = 0

    role = user_info.get("role", "free")
    limit = PLAN_LIMITS.get(role, 5)
    current_usage = user_info.get("daily_usage", 0)

    if current_usage >= limit:
        return (
            False,
            f"⚠️ 您今日的 API 發問額度已達上限 ({current_usage}/{limit} 次)！升級為 Pro 即可解鎖更多額度。",
            current_usage,
            limit,
        )

    return True, "", current_usage, limit


# ==============================================================================
# 2. Session State 初始化
# ==============================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""


# ==============================================================================
# 3. 會員驗證系統與側邊欄 (穩定登出邏輯)
# ==============================================================================
st.sidebar.title("🔐 會員系統")

if not st.session_state.logged_in:
    auth_mode = st.sidebar.radio("選擇操作選項", ["帳號登入", "會員註冊"])
    email_input = st.sidebar.text_input("電子郵件 (Email)").strip().lower()
    password_input = st.sidebar.text_input("密碼", type="password")

    if auth_mode == "會員註冊":
        name_input = st.sidebar.text_input("使用者暱稱").strip()
        if st.sidebar.button("註冊帳號", use_container_width=True):
            if not email_input or not password_input or not name_input:
                st.sidebar.error("請完整填寫所有欄位！")
            elif email_input in users:
                st.sidebar.error("此電子郵件已經註冊過了！")
            else:
                users[email_input] = {
                    "name": name_input,
                    "password": password_input,
                    "role": "pro" if email_input == ADMIN_EMAIL else "free",
                    "daily_usage": 0,
                    "last_use_date": str(date.today()),
                }
                save_data(USERS_FILE, users)
                st.sidebar.success("🎉 註冊成功！請切換至「帳號登入」。")

    elif auth_mode == "帳號登入":
        if st.sidebar.button("登入系統", use_container_width=True):
            if (
                email_input in users
                and users[email_input]["password"] == password_input
            ):
                st.session_state.logged_in = True
                st.session_state.user_email = email_input
                st.sidebar.success("登入成功！")
                st.rerun()
            else:
                st.sidebar.error("帳號或密碼輸入錯誤！")
else:
    u_data = users.get(st.session_state.user_email, {})
    current_user_name = u_data.get("name", "會員")
    user_role = u_data.get("role", "free")

    role_badge = (
        "👑 Admin / Pro"
        if st.session_state.user_email == ADMIN_EMAIL
        else ("⭐ Pro 尊榮會員" if user_role == "pro" else "🌱 Free 免費會員")
    )

    st.sidebar.success(f"歡迎，**{current_user_name}**！")
    st.sidebar.markdown(f"**目前身分**：`{role_badge}`")

    _, _, usage, limit = check_and_update_usage(st.session_state.user_email)
    st.sidebar.progress(
        min(usage / limit, 1.0),
        text=f"今日用量：{usage} / {limit} 次",
    )

    # 🚪 強制穩定登出按鈕
    if st.sidebar.button("🚪 安全登出", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_email = ""
        st.rerun()

# 🛡️ 管理員專屬後台
if (
    st.session_state.logged_in
    and st.session_state.user_email == ADMIN_EMAIL
):
    st.sidebar.divider()
    with st.sidebar.expander(
        "🛡️ 系統後台管理 (Admin Only)", expanded=False
    ):
        st.markdown("**管理員控制台**")
        if users:
            selected_user_email = st.selectbox(
                "選擇要管理的會員", list(users.keys())
            )
            if selected_user_email:
                u_info = users[selected_user_email]
                st.text(f"暱稱: {u_info.get('name', '未設定')}")

                new_role = st.selectbox(
                    "調整會員等級",
                    ["free", "pro"],
                    index=0 if u_info.get("role") == "free" else 1,
                )
                new_pwd = st.text_input(
                    "修改該帳號密碼",
                    value=u_info.get("password", ""),
                    key="admin_pwd_edit",
                )

                if st.button("💾 更新會員設定"):
                    users[selected_user_email]["role"] = new_role
                    users[selected_user_email]["password"] = new_pwd
                    save_data(USERS_FILE, users)
                    st.success("會員權限已成功更新！")
                    st.rerun()


# ==============================================================================
# 4. 主畫面：分頁與模組 (Tabs)
# ==============================================================================
st.title("⚡ 多功能數位工作助理與行事曆")

tab_ai, tab_cal, tab_pdf, tab_img, tab_summary, tab_ig = st.tabs([
    "💻 Groq AI 行程智囊團",
    "📅 視覺化日曆與行程",
    "📄 PDF 救星",
    "✂️ AI 圖片處理與去背",
    "📝 文本總結與防雷助理",
    "📱 社群 IG/Threads 一鍵切圖",
])

# ------------------------------------------------------------------------------
# TAB 0: 🤖 Groq AI 行程智囊團 (支援模式選擇 + 歷史紀錄儲存與刪除)
# ------------------------------------------------------------------------------
with tab_ai:
    import sqlite3

    # 1. 初始化資料庫結構
    def init_ai_db():
        conn = sqlite3.connect("chat_history.db")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                title TEXT,
                mode TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                role TEXT,
                content TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        conn.close()

    init_ai_db()

    # DB 操作輔助函式
    def get_user_sessions(email):
        conn = sqlite3.connect("chat_history.db")
        c = conn.cursor()
        c.execute(
            "SELECT session_id, title, mode FROM sessions WHERE user_email = ? ORDER BY session_id DESC",
            (email,),
        )
        rows = c.fetchall()
        conn.close()
        return rows

    def create_session(email, mode):
        conn = sqlite3.connect("chat_history.db")
        c = conn.cursor()
        c.execute(
            "INSERT INTO sessions (user_email, title, mode) VALUES (?, ?, ?)",
            (email, "新對話", mode),
        )
        s_id = c.lastrowid
        conn.commit()
        conn.close()
        return s_id

    def save_msg(session_id, role, content):
        conn = sqlite3.connect("chat_history.db")
        c = conn.cursor()
        c.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.commit()
        conn.close()

    def get_session_msgs(session_id):
        conn = sqlite3.connect("chat_history.db")
        c = conn.cursor()
        c.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY message_id ASC",
            (session_id,),
        )
        rows = c.fetchall()
        conn.close()
        return [{"role": r[0], "content": r[1]} for r in rows]

    def delete_session(session_id):
        conn = sqlite3.connect("chat_history.db")
        c = conn.cursor()
        c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        c.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    def update_session_title(session_id, title):
        conn = sqlite3.connect("chat_history.db")
        c = conn.cursor()
        c.execute(
            "UPDATE sessions SET title = ? WHERE session_id = ?",
            (title, session_id),
        )
        conn.commit()
        conn.close()

    # 2. 定義 AI 模式 Prompts
    SYSTEM_PROMPTS = {
        "📅 行程規劃專家": "你是一個親切且極其專業的繁體中文 AI 時間管理與行程規劃助手，擅長評估空閒時間與最佳化排程。",
        "📝 文案/報告潤飾": "你是一位專業的文案與報告潤飾大師，請協助使用者修飾文字、調整口吻並提供結構建議。",
        "💻 程式/自動化諮詢": "你是一位資深軟體工程師，請幫助使用者解答 Python、自動化流程與 API 相關問題。",
        "💬 輕鬆閒聊": "你是一個親切友善的對話夥伴，用輕鬆幽默的方式回答使用者的日常生活問題。",
    }

    # 3. 自訂 CSS 樣式
    st.markdown(
        """
        <style>
        .chat-scroll-container { max-width: 800px; margin: 0 auto; height: 420px; overflow-y: auto; padding: 10px 15px; border-radius: 12px; scroll-behavior: smooth; border: 1px solid #f0f0f0; background-color: #fafafa; }
        .welcome-box { text-align: center; padding: 50px 20px 20px 20px; }
        .welcome-title { font-size: 28px; font-weight: 700; background: linear-gradient(135deg, #4285f4, #d93025, #fbbc04, #34a853); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }
        .welcome-sub { color: #5f6368; font-size: 14px; }
        .user-bubble-container { display: flex; justify-content: flex-end; margin-bottom: 16px; }
        .user-bubble { background-color: #e3f2fd; color: #1565c0; padding: 10px 18px; border-radius: 20px 20px 4px 20px; max-width: 75%; font-size: 15px; line-height: 1.5; }
        .ai-bubble-container { display: flex; justify-content: flex-start; margin-bottom: 24px; }
        .ai-bubble { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 12px 18px; border-radius: 20px 20px 20px 4px; color: #1f1f1f; width: 100%; font-size: 15px; line-height: 1.6; }
        </style>
    """,
        unsafe_allow_html=True,
    )

    current_email = st.session_state.get("user_email", "guest")

    # 4. 功能列：選擇模式 + 歷史紀錄切換與刪除
    col_m1, col_m2, col_m3 = st.columns([2, 2, 1])

    with col_m1:
        ai_mode = st.selectbox(
            "🎯 AI 助手模式",
            list(SYSTEM_PROMPTS.keys()),
            key="ai_mode_select",
        )

    # 取得目前使用者的所有歷史對話
    user_sessions = (
        get_user_sessions(current_email)
        if st.session_state.get("logged_in")
        else []
    )

    # 管理 current_session_id
    if "current_session_id" not in st.session_state or not any(
        s[0] == st.session_state.current_session_id for s in user_sessions
    ):
        if user_sessions:
            st.session_state.current_session_id = user_sessions[0][0]
        else:
            st.session_state.current_session_id = None

    with col_m2:
        session_options = {
            s[0]: f"{s[1]} ({s[2][:4]})" for s in user_sessions
        }
        if session_options:
            selected_s_id = st.selectbox(
                "📜 歷史對話紀錄",
                options=list(session_options.keys()),
                format_func=lambda x: session_options[x],
                index=0,
            )
            st.session_state.current_session_id = selected_s_id
        else:
            st.selectbox(
                "📜 歷史對話紀錄",
                options=["(尚無歷史紀錄)"],
                disabled=True,
            )

    with col_m3:
        st.write("")
        st.write("")
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("➕", help="開啟新對話", use_container_width=True):
                if st.session_state.get("logged_in"):
                    new_id = create_session(current_email, ai_mode)
                    st.session_state.current_session_id = new_id
                    st.rerun()
                else:
                    st.warning("請先登入")
        with btn_col2:
            if st.button(
                "🗑️",
                help="刪除此紀錄",
                use_container_width=True,
                disabled=not st.session_state.current_session_id,
            ):
                if st.session_state.current_session_id:
                    delete_session(st.session_state.current_session_id)
                    st.session_state.current_session_id = None
                    st.rerun()

    # 載入當前對話紀錄
    if st.session_state.current_session_id:
        st.session_state.messages = get_session_msgs(
            st.session_state.current_session_id
        )
    else:
        st.session_state.messages = []

    # 5. 權限與行事曆整合選項
    col_c1, col_c2 = st.columns([4, 1])
    with col_c1:
        is_pro = st.session_state.get("logged_in", False) and (
            users.get(st.session_state.user_email, {}).get("role") == "pro"
            or st.session_state.user_email == ADMIN_EMAIL
        )
        include_cal_data = st.checkbox(
            "📅 允許 AI 存取我的行事曆（AI 將自動評估你的空閒時間並幫你規劃行程）",
            value=is_pro,
            disabled=not is_pro,
        )

    # 6. 渲染聊天視窗
    html_items = ['<div class="chat-scroll-container" id="chat-box">']
    if not st.session_state.messages:
        html_items.append(
            f'<div class="welcome-box"><div class="welcome-title">My friend!盡情與 AI 規劃行程吧！</div><div class="welcome-sub">當前模式：【{ai_mode}】｜ 可以幫你檢視近期的空檔時間、安排行程、撰寫文案或解答各種問題</div></div>'
        )
    else:
        for msg in st.session_state.messages:
            content = msg["content"].replace("\n", "<br>")
            if msg["role"] == "user":
                html_items.append(
                    f'<div class="user-bubble-container"><div class="user-bubble">{content}</div></div>'
                )
            else:
                html_items.append(
                    f'<div class="ai-bubble-container"><div class="ai-bubble">{content}</div></div>'
                )
    html_items.append("</div>")
    st.markdown("".join(html_items), unsafe_allow_html=True)

    # 7. 接收使用者輸入與 API 呼叫處理
    if prompt := st.chat_input("輸入問題或請 AI 幫你規劃行程..."):
        if not st.session_state.logged_in:
            st.error("⚠️ 請先於左側邊欄「登入帳號」後再使用 AI 對話功能。")
        else:
            allowed, msg, _, _ = check_and_update_usage(
                st.session_state.user_email
            )
            if not allowed:
                st.error(msg)
            elif (
                "GROQ_API_KEY" not in st.secrets
                or not st.secrets["GROQ_API_KEY"]
            ):
                st.error(
                    "⚠️ 未在 Streamlit Secrets 中設定 `GROQ_API_KEY`。"
                )
            else:
                users[st.session_state.user_email]["daily_usage"] += 1
                save_data(USERS_FILE, users)

                # 若尚未建立 Session 則自動建立
                if not st.session_state.current_session_id:
                    st.session_state.current_session_id = create_session(
                        current_email, ai_mode
                    )

                # 儲存與寫入訊息
                save_msg(st.session_state.current_session_id, "user", prompt)
                st.session_state.messages.append(
                    {"role": "user", "content": prompt}
                )

                # 第一句話自動更新為此話頭
                if len(st.session_state.messages) == 1:
                    title_snippet = (
                        prompt[:10] + "..." if len(prompt) > 10 else prompt
                    )
                    update_session_title(
                        st.session_state.current_session_id, title_snippet
                    )

                st.rerun()

    # 8. 呼叫 Groq API 生成回答
    if (
        st.session_state.messages
        and st.session_state.messages[-1]["role"] == "user"
    ):
        with st.spinner("🤖 AI 正在分析行程並思考中..."):
            try:
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])

                # 套用選定的模式 Prompt
                system_instruction = SYSTEM_PROMPTS[ai_mode]

                if include_cal_data and st.session_state.logged_in:
                    user_evs = get_user_all_events(st.session_state.user_email)
                    if user_evs:
                        ev_summary = "\n".join([
                            f"- 日期: {e.get('date')} | 行程名稱: {e.get('title')} | 分類: {e.get('category','一般')} | 備註: {e.get('description','')}"
                            for e in user_evs
                        ])
                        system_instruction += f"\n\n目前使用者的完整行事曆如下：\n{ev_summary}\n\n今天日期是：{date.today()}。請根據上述行程評估其空閒時間並提供排程建議。"
                    else:
                        system_instruction += f"\n\n目前使用者的行事曆上沒有任何行程。今天日期是：{date.today()}。"

                api_messages = [
                    {"role": "system", "content": system_instruction}
                ] + [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ]

                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=api_messages,
                    temperature=0.7,
                    max_tokens=1500,
                )

                ai_reply = response.choices[0].message.content

                # 儲存回答至 DB 與 State
                save_msg(
                    st.session_state.current_session_id, "assistant", ai_reply
                )
                st.session_state.messages.append(
                    {"role": "assistant", "content": ai_reply}
                )
                st.rerun()
            except Exception as e:
                st.error(f"❌ 發生錯誤：{e}")
# ------------------------------------------------------------------------------
# TAB 1: 📅 絕不跑版！視覺化月曆與行程表 (st.dataframe 完美 7 欄卡片)
# ------------------------------------------------------------------------------
with tab_cal:
    st.header("📅 視覺化月曆與行程表")

    if not st.session_state.logged_in:
        st.warning("⚠️ 目前為訪客預覽模式。登入帳號後即可完整編輯、新增與刪除日程。")
        user_email = "guest"
    else:
        user_email = st.session_state.user_email

    today = date.today()

    col_cal_sel, col_cal_mgmt = st.columns([2, 2])
    my_shared_cals = get_user_calendars(user_email)
    cal_options = ["🔒 個人專屬行事曆"] + [f"👥 {c['name']} (代碼: {c['code']})" for c in my_shared_cals]

    with col_cal_sel:
        selected_cal_option = st.selectbox("📌 切換行事曆範疇", cal_options)
        if selected_cal_option == "🔒 個人專屬行事曆":
            current_cal_mode = "personal"
            current_cal_code = None
        else:
            current_cal_mode = "shared"
            current_cal_code = selected_cal_option.split("(代碼: ")[1].replace(")", "")

    with col_cal_mgmt:
        if st.session_state.logged_in:
            with st.popover("➕ 管理 / 加入共享行事曆"):
                st.markdown("#### 👥 建立新的共享行事曆")
                new_cal_name = st.text_input("共享行事曆名稱", placeholder="例如：專案組、家庭日曆")
                if st.button("建立共享行事曆", use_container_width=True):
                    if new_cal_name.strip():
                        inv_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                        new_cal = {
                            "name": new_cal_name.strip(),
                            "code": inv_code,
                            "owner": user_email,
                            "members": [user_email],
                        }
                        calendars_data.append(new_cal)
                        save_data(CALENDARS_FILE, calendars_data)
                        st.success(f"建立成功！邀請碼為：**{inv_code}**")
                        st.rerun()

                st.divider()
                st.markdown("#### 🔑 透過邀請碼加入")
                join_code = st.text_input("輸入 6 位邀請碼").strip().upper()
                if st.button("加入共享行事曆", use_container_width=True):
                    target_cal = next((c for c in calendars_data if c.get("code") == join_code), None)
                    if target_cal:
                        if user_email not in target_cal.setdefault("members", []):
                            target_cal["members"].append(user_email)
                            save_data(CALENDARS_FILE, calendars_data)
                            st.success(f"已成功加入「{target_cal['name']}」！")
                            st.rerun()

    if current_cal_mode == "personal":
        active_events = [e for e in events if e.get("creator") == user_email and not e.get("cal_code")]
    else:
        active_events = [e for e in events if e.get("cal_code") == current_cal_code]

    c_y, c_m = st.columns(2)
    with c_y:
        sel_year = st.number_input("選擇年份", min_value=2020, max_value=2030, value=today.year)
    with c_m:
        sel_month = st.number_input("選擇月份", min_value=1, max_value=12, value=today.month)

# ------------------------------------------------------------------------------
# 📅 100% 完全還原：自訂 CSS Grid 7 欄卡片月曆（支援窄螢幕，絕不直排）
# ------------------------------------------------------------------------------
with tab_cal:
    # 1. 注入強大的 CSS Grid 樣式
    st.markdown(
        """
        <style>
        /* 容器與背景 */
        .cal-container {
            background-color: #f6fbf4;
            padding: 16px;
            border-radius: 20px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }

        /* 核心：7 欄 CSS Grid，強制不論螢幕多窄都不換行成直排 */
        .cal-grid {
            display: grid !important;
            grid-template-columns: repeat(7, 1fr) !important;
            gap: 8px !important;
            width: 100% !important;
        }

        /* 星期標頭 */
        .cal-header {
            text-align: center;
            font-weight: bold;
            font-size: 15px;
            padding: 6px 0;
        }
        .header-sun { color: #f87171; }
        .header-sat { color: #38bdf8; }
        .header-weekday { color: #52525b; }

        /* 卡片主體 */
        .cal-day-card {
            background-color: #ffffff;
            border-radius: 14px;
            min-height: 75px;
            padding: 6px 6px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            display: flex;
            flex-direction: column;
            box-sizing: border-box;
        }
        .cal-day-card.today {
            background-color: #00c896 !important;
        }

        /* 日期數字 */
        .day-num {
            font-size: 16px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 4px;
        }
        .num-sun { color: #f87171; }
        .num-sat { color: #38bdf8; }
        .num-weekday { color: #27272a; }
        .today .day-num { color: #ffffff !important; }

        /* 行程標籤 */
        .event-chip {
            font-size: 10px;
            padding: 2px 4px;
            border-radius: 6px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-top: 2px;
            font-weight: 600;
        }
        .chip-red { background-color: #fde8e8; color: #e11d48; }
        .chip-gray { background-color: #f1f5f9; color: #475569; }

        /* 即將到來 (Upcoming) 列表樣式 */
        .upcoming-title {
            font-weight: 700;
            color: #71717a;
            font-size: 14px;
            margin: 16px 0 8px 0;
        }
        .upcoming-card {
            background-color: #fff1f2;
            border: 1px solid #fecdd3;
            border-radius: 20px;
            padding: 10px 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .upcoming-text {
            color: #e11d48;
            font-weight: 700;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .upcoming-date {
            color: #a1a1aa;
            font-size: 13px;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # 2. 構建完整的 7 欄 HTML 月曆
    cal_obj = calendar.Calendar(firstweekday=6)
    month_days = cal_obj.monthdayscalendar(sel_year, sel_month)

    grid_html = "<div class='cal-container'>"
    
    # 星期標頭 HTML
    grid_html += "<div class='cal-grid'>"
    grid_html += "<div class='cal-header header-sun'>日</div>"
    grid_html += "<div class='cal-header header-weekday'>一</div>"
    grid_html += "<div class='cal-header header-weekday'>二</div>"
    grid_html += "<div class='cal-header header-weekday'>三</div>"
    grid_html += "<div class='cal-header header-weekday'>四</div>"
    grid_html += "<div class='cal-header header-weekday'>五</div>"
    grid_html += "<div class='cal-header header-sat'>六</div>"
    grid_html += "</div>"

    # 每天的卡片 HTML
    for week in month_days:
        grid_html += "<div class='cal-grid' style='margin-top: 8px;'>"
        for idx, day in enumerate(week):
            if day == 0:
                grid_html += "<div></div>"
            else:
                day_str = f"{sel_year}-{sel_month:02d}-{day:02d}"
                is_today = (sel_year == today.year and sel_month == today.month and day == today.day)
                day_evs = [e for e in active_events if e.get("date") == day_str]

                # 數字色彩 (0:週日, 6:週六)
                num_cls = "num-sun" if idx == 0 else ("num-sat" if idx == 6 else "num-weekday")
                card_cls = "cal-day-card today" if is_today else "cal-day-card"

                # 行程 Chip
                chip_html = ""
                if day_evs:
                    ev = day_evs[0]
                    title = ev.get("title", "")
                    cate = ev.get("category", "")
                    chip_cls = "chip-red" if ("考" in title or cate == "重要提醒") else "chip-gray"
                    more = f" (+{len(day_evs)-1})" if len(day_evs) > 1 else ""
                    chip_html = f"<div class='event-chip {chip_cls}'>{title}{more}</div>"

                grid_html += f"<div class='{card_cls}'><div class='day-num {num_cls}'>{day}</div>{chip_html}</div>"
        grid_html += "</div>"
    
    grid_html += "</div>"

    # 3. 渲染純 HTML 月曆 (保證不拆欄、絕不跑版)
    st.markdown(grid_html, unsafe_allow_html=True)

    # 4. 還原圖片下方的「即將到來」行程列表
    st.markdown("<div class='upcoming-title'>即將到來</div>", unsafe_allow_html=True)

    # 篩選未來的行程並排序
    future_events = [e for e in active_events if e.get("date") >= today.strftime("%Y-%m-%d")]
    future_events.sort(key=lambda x: x.get("date"))

    if not future_events:
        st.info("💡 目前沒有即將到來的行程安排。")
    else:
        for ev in future_events[:5]:  # 顯示前 5 筆
            ev_date = datetime.strptime(ev["date"], "%Y-%m-%d").date()
            delta_days = (ev_date - today).days
            
            if delta_days == 0:
                day_hint = "今天"
            elif delta_days == 1:
                day_hint = "明天"
            else:
                day_hint = f"{delta_days}天後"

            date_display = f"{ev_date.month}/{ev_date.day} · {day_hint}"

            st.markdown(
                f"""
                <div class="upcoming-card">
                    <div class="upcoming-text">
                        <span>●</span>
                        <span>{ev.get('title', '')}</span>
                    </div>
                    <div class="upcoming-date">{date_display}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    # 5. 操作互動區（選擇日期編輯或新增）
    st.markdown("#### 📝 行程點擊與管理")
    all_month_days = [f"{sel_year}-{sel_month:02d}-{d:02d}" for w in month_days for d in w if d != 0]
    col_sel_d, col_btn_d = st.columns([3, 1])
    with col_sel_d:
        target_date = st.selectbox("請選擇要查看 / 管理的日期：", all_month_days)
    with col_btn_d:
        st.write("")
        st.write("")
        if st.button("🔍 開啟日期詳情", use_container_width=True, type="primary"):
            open_day_dialog(target_date)
# ------------------------------------------------------------------------------
# TAB 2: 📄 PDF 救星（解密 / 合併 / 轉 Excel）
# ------------------------------------------------------------------------------
with tab_pdf:
    st.header("📄 PDF 救星工具箱")
    pdf_action = st.radio(
        "選擇要執行的操作：",
        ["🔓 PDF 解密與密碼移除", "🧩 多檔 PDF 快速合併", "📊 PDF 內文與表格轉 Excel"],
        horizontal=True
    )
    st.divider()

    if pdf_action == "🔓 PDF 解密與密碼移除":
        st.subheader("解密保護的 PDF 檔案")
        up_pdf = st.file_uploader("上傳密碼保護的 PDF 檔案", type=["pdf"], key="unlock_pdf_input")
        pdf_pwd = st.text_input("請輸入該 PDF 的開啟密碼", type="password")
        
        if up_pdf and pdf_pwd:
            if st.button("🔑 開始解密"):
                try:
                    reader = pypdf.PdfReader(up_pdf)
                    if reader.is_encrypted:
                        reader.decrypt(pdf_pwd)
                    writer = pypdf.PdfWriter()
                    for page in reader.pages:
                        writer.add_page(page)
                    
                    out_buf = io.BytesIO()
                    writer.write(out_buf)
                    st.success("🎉 解密成功！")
                    st.download_button("📥 下載已解密 PDF", out_buf.getvalue(), file_name="unlocked_document.pdf", mime="application/pdf")
                except Exception as e:
                    st.error(f"解密失敗，請檢查密碼是否正確：{e}")

    elif pdf_action == "🧩 多檔 PDF 快速合併":
        st.subheader("合併多份 PDF 為單一檔案")
        pdf_files = st.file_uploader("選擇多個 PDF 檔案", type=["pdf"], accept_multiple_files=True, key="merge_pdf_input")
        
        if pdf_files and st.button("🧩 執行合併"):
            merger = pypdf.PdfWriter()
            for p_file in pdf_files:
                merger.append(p_file)
            merged_buf = io.BytesIO()
            merger.write(merged_buf)
            st.success("🎉 PDF 合併成功！")
            st.download_button("📥 下載合併後的 PDF", merged_buf.getvalue(), file_name="merged_output.pdf", mime="application/pdf")

    elif pdf_action == "📊 PDF 內文與表格轉 Excel":
        st.subheader("提取 PDF 文字與數據至 Excel")
        pdf_excel_file = st.file_uploader("上傳含有數據或內文的 PDF", type=["pdf"], key="excel_pdf_input")
        
        if pdf_excel_file and st.button("📊 提取資料並生成 Excel"):
            try:
                reader = pypdf.PdfReader(pdf_excel_file)
                data_rows = []
                for p_idx, page in enumerate(reader.pages):
                    text = page.extract_text()
                    lines = text.split("\n")
                    for line in lines:
                        if line.strip():
                            data_rows.append({"頁碼": p_idx + 1, "擷取內容": line.strip()})
                            
                df = pd.DataFrame(data_rows)
                excel_buf = io.BytesIO()
                with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name="PDF 提取內容")
                
                st.success(f"🎉 成功提取 {len(data_rows)} 筆資料！")
                st.dataframe(df.head(10), use_container_width=True)
                st.download_button("📥 下載 Excel 試算表 (.xlsx)", excel_buf.getvalue(), file_name="pdf_data_extracted.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception as e:
                st.error(f"提取過程中發生錯誤：{e}")


# ------------------------------------------------------------------------------
# TAB 3: ✂️ AI 圖片處理與去背
# ------------------------------------------------------------------------------
with tab_img:
    st.header("✂️ 圖像編修與智能去背工具")
    img_file = st.file_uploader("上傳圖片檔案 (JPG / PNG)", type=["jpg", "jpeg", "png"], key="img_proc_input")
    
    if img_file:
        ori_img = Image.open(img_file)
        c_left, c_right = st.columns(2)
        
        with c_left:
            st.image(ori_img, caption="原始圖片預覽", use_container_width=True)
            
        with c_right:
            proc_mode = st.selectbox(
                "選擇處理模式",
                ["純白/淺色背景去背 (轉透明 PNG)", "調整尺寸與旋轉", "亮度/對比度微調", "黑白灰階濾鏡"]
            )
            
            if proc_mode == "純白/淺色背景去背 (轉透明 PNG)":
                tolerance = st.slider("背景色閥值 (容差度高適用於淺色背景)", 0, 100, 30)
                if st.button("✂️ 執行去背"):
                    img_rgba = ori_img.convert("RGBA")
                    datas = img_rgba.getdata()
                    new_datas = []
                    for item in datas:
                        if item[0] >= (255 - tolerance) and item[1] >= (255 - tolerance) and item[2] >= (255 - tolerance):
                            new_datas.append((255, 255, 255, 0))
                        else:
                            new_datas.append(item)
                            
                    img_rgba.putdata(new_datas)
                    out_p = io.BytesIO()
                    img_rgba.save(out_p, format="PNG")
                    st.image(img_rgba, caption="去背完成結果", use_container_width=True)
                    st.download_button("📥 下載透明背景 PNG", out_p.getvalue(), file_name="nobg_image.png", mime="image/png")

            elif proc_mode == "調整尺寸與旋轉":
                w = st.number_input("新寬度 (px)", value=ori_img.width, step=10)
                h = st.number_input("新高度 (px)", value=ori_img.height, step=10)
                angle = st.slider("順時針旋轉角度", 0, 360, 0)
                
                if st.button("💾 套用修改"):
                    resized_img = ori_img.resize((int(w), int(h))).rotate(angle, expand=True)
                    out_p = io.BytesIO()
                    resized_img.save(out_p, format="PNG")
                    st.image(resized_img, caption="修改後結果", use_container_width=True)
                    st.download_button("📥 下載圖片", out_p.getvalue(), file_name="resized_image.png", mime="image/png")

            elif proc_mode == "亮度/對比度微調":
                b_val = st.slider("亮度", 0.1, 2.0, 1.0)
                c_val = st.slider("對比度", 0.1, 2.0, 1.0)
                if st.button("✨ 應用效果"):
                    enh_b = ImageEnhance.Brightness(ori_img).enhance(b_val)
                    enh_c = ImageEnhance.Contrast(enh_b).enhance(c_val)
                    out_p = io.BytesIO()
                    enh_c.save(out_p, format="PNG")
                    st.image(enh_c, caption="調色完成預覽", use_container_width=True)
                    st.download_button("📥 下載調色圖片", out_p.getvalue(), file_name="enhanced_image.png", mime="image/png")

            elif proc_mode == "黑白灰階濾鏡":
                if st.button("🎨 轉為黑白"):
                    gray_img = ImageOps.grayscale(ori_img)
                    out_p = io.BytesIO()
                    gray_img.save(out_p, format="PNG")
                    st.image(gray_img, caption="黑白濾鏡預覽", use_container_width=True)
                    st.download_button("📥 下載黑白圖片", out_p.getvalue(), file_name="grayscale_image.png", mime="image/png")


# ------------------------------------------------------------------------------
# TAB 4: 📝 萬用文本總結與防雷助理
# ------------------------------------------------------------------------------
with tab_summary:
    st.header("📝 萬用文本總結與防雷條款助理")
    input_text = st.text_area("請貼上欲分析長文章、新聞、合約條款或說明書內容：", height=220)
    
    if input_text and st.button("🔍 執行文本總結與關鍵風險分析"):
        col_s1, col_s2 = st.columns(2)
        sentences = [s.strip() for s in re.split(r'[。！!？?\n]', input_text) if len(s.strip()) > 3]
        
        with col_s1:
            st.subheader("💡 核心重點摘要")
            if not sentences:
                st.write("內容太短，無法進行有效的重點擷取。")
            else:
                summary_items = sentences[:4] if len(sentences) >= 4 else sentences
                for idx, item in enumerate(summary_items, 1):
                    st.markdown(f"**{idx}.** {item}")

        with col_s2:
            st.subheader("⚠️ 陷阱與風險關鍵字掃描")
            risk_keywords = ["違約金", "無條件", "不得異議", "自動續約", "放棄", "負擔費用", "損害賠償", "終止條款", "免責", "利息", "逾期"]
            found_keywords = [kw for kw in risk_keywords if kw in input_text]
            
            if found_keywords:
                st.error(f"🚨 注意！偵測到風險關鍵字：**{', '.join(found_keywords)}**")
                st.markdown("---")
                for s in sentences:
                    for rkw in found_keywords:
                        if rkw in s:
                            st.warning(f"🚩 `{s}`")
                            break
            else:
                st.success("✅ 未在文章中發現常見的風險與陷阱關鍵字。")


# ------------------------------------------------------------------------------
# TAB 5: 📱 社群 IG/Threads 一鍵切圖
# ------------------------------------------------------------------------------
with tab_ig:
    st.header("📱 社群 IG / Threads 一鍵九宮格與連圖裁切")
    social_file = st.file_uploader("上傳要用於排版的原始照片", type=["jpg", "jpeg", "png"], key="social_crop_input")
    
    if social_file:
        s_img = Image.open(social_file)
        crop_type = st.radio("選擇裁切模式", ["3x3 九宮格 (IG 牆面拼圖)", "1x3 橫向連圖 (Threads/IG 輪播)"], horizontal=True)
        
        if st.button("✂️ 執行切圖排版"):
            sw, sh = s_img.size
            crop_results = []
            
            if crop_type == "3x3 九宮格 (IG 牆面拼圖)":
                min_edge = min(sw, sh)
                l = (sw - min_edge) / 2
                t = (sh - min_edge) / 2
                sq_img = s_img.crop((l, t, l + min_edge, t + min_edge))
                
                step = min_edge // 3
                for r in range(3):
                    for c in range(3):
                        box = (c * step, r * step, (c + 1) * step, (r + 1) * step)
                        crop_results.append((f"ig_grid_{r+1}_{c+1}.png", sq_img.crop(box)))
                        
            elif crop_type == "1x3 橫向連圖 (Threads/IG 輪播)":
                step = sw // 3
                for c in range(3):
                    box = (c * step, 0, (c + 1) * step, sh)
                    crop_results.append((f"social_carousel_{c+1}.png", s_img.crop(box)))

            st.success(f"🎉 成功切分出 {len(crop_results)} 張圖片！")
            
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w") as zf:
                for img_name, img_obj in crop_results:
                    b = io.BytesIO()
                    img_obj.save(b, format="PNG")
                    zf.writestr(img_name, b.getvalue())

            st.download_button("📦 一鍵下載全部圖片 (ZIP 打包檔)", zip_buf.getvalue(), file_name="social_crops.zip", mime="application/zip")
            
            st.divider()
            preview_cols = st.columns(3)
            for i, (fname, p_img) in enumerate(crop_results):
                with preview_cols[i % 3]:
                    st.image(p_img, caption=fname, use_container_width=True)


# ==============================================================================
# 5. 頁尾客服資訊 (小字顯示)
# ==============================================================================
st.divider()
footer_html = """
<div style="text-align: center; color: #888888; font-size: 12px; margin-top: 20px; line-height: 1.6;">
    <p style="margin: 0;">💬 <b>客服與技術支援</b></p>
    <p style="margin: 2px 0;">服務時間：週一至週五 09:00 - 18:00</p>
    <p style="margin: 2px 0;">客服信箱：<a href="mailto:support@example.com" style="color: #007aff;">3323jayden@gmail.com</a> </p>
    <p style="margin: 6px 0 0 0; font-size: 10px; color: #aaa;">© 2026 共享線上行事曆與數位助理系統 All Rights Reserved.</p>
</div>
"""
st.markdown(footer_html, unsafe_allow_html=True)
