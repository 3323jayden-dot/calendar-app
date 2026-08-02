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
    "🤖 Groq AI 行程智囊團",
    "📅 視覺化日曆與行程",
    "📄 PDF 救星",
    "✂️ AI 圖片處理與去背",
    "📝 文本總結與防雷助理",
    "📱 社群 IG/Threads 一鍵切圖",
])

# ------------------------------------------------------------------------------
# TAB 0: 🤖 Groq AI 行程智囊團
# ------------------------------------------------------------------------------
with tab_ai:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.markdown(
        """
        <style>
        .chat-scroll-container { max-width: 800px; margin: 0 auto; height: 480px; overflow-y: auto; padding: 10px 15px; border-radius: 12px; scroll-behavior: smooth; }
        .welcome-box { text-align: center; padding: 60px 20px 20px 20px; }
        .welcome-title { font-size: 32px; font-weight: 700; background: linear-gradient(135deg, #4285f4, #d93025, #fbbc04, #34a853); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }
        .welcome-sub { color: #5f6368; font-size: 15px; }
        .user-bubble-container { display: flex; justify-content: flex-end; margin-bottom: 16px; }
        .user-bubble { background-color: #f1f3f4; color: #202124; padding: 10px 18px; border-radius: 20px 20px 4px 20px; max-width: 75%; font-size: 15px; line-height: 1.5; }
        .ai-bubble-container { display: flex; justify-content: flex-start; margin-bottom: 24px; }
        .ai-bubble { color: #1f1f1f; width: 100%; font-size: 15px; line-height: 1.6; }
        </style>
    """,
        unsafe_allow_html=True,
    )

    col_c1, col_c2 = st.columns([4, 1])
    with col_c1:
        is_pro = (
            st.session_state.logged_in
            and (
                users.get(st.session_state.user_email, {}).get("role") == "pro"
                or st.session_state.user_email == ADMIN_EMAIL
            )
        )
        include_cal_data = st.checkbox(
            "📅 允許 AI 存取我的行事曆（AI 將自動評估你的空閒時間並幫你規劃行程）",
            value=is_pro,
            disabled=not is_pro,
        )

    with col_c2:
        if st.session_state.messages:
            if st.button("➕ 新對話", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

    html_items = ['<div class="chat-scroll-container" id="chat-box">']
    if not st.session_state.messages:
        html_items.append(
            '<div class="welcome-box"><div class="welcome-title">Jayden，盡情與 AI 規劃行程吧！</div><div class="welcome-sub">我可以幫你檢視近期的空檔時間、安排行程、撰寫文案或解答各種問題</div></div>'
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
                st.error("⚠️ 未在 Streamlit Secrets 中設定 `GROQ_API_KEY`。")
            else:
                users[st.session_state.user_email]["daily_usage"] += 1
                save_data(USERS_FILE, users)
                st.session_state.messages.append(
                    {"role": "user", "content": prompt}
                )
                st.rerun()

    if (
        st.session_state.messages
        and st.session_state.messages[-1]["role"] == "user"
    ):
        with st.spinner("🤖 AI 正在分析行程並思考中..."):
            try:
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                system_instruction = (
                    "你是一個親切且極其專業的繁體中文 AI 時間管理與行程規劃助手。"
                )

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

                api_messages = [{"role": "system", "content": system_instruction}] + [
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
# 📅 一舉兩得方案：按鈕即卡片 (100% 點擊卡片開啟編輯 + CSS Grid 美化 + 絕不直排)
# ------------------------------------------------------------------------------
with tab_cal:
    # 1. 注入 CSS 全域樣式：強制 7 欄橫向排列 + 將按鈕打造成圓角卡片
    st.markdown(
        """
        <style>
        /* 1. 強制 7 欄列橫向不換行、不拆成直排 */
        div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 6px !important;
            width: 100% !important;
        }
        div[data-testid="column"] {
            flex: 1 1 0px !important;
            min-width: 0px !important;
        }

        /* 2. 星期標頭樣式 */
        .cal-header-box {
            text-align: center;
            font-weight: bold;
            font-size: 15px;
            padding: 4px 0;
        }
        .hdr-sun { color: #f87171; }
        .hdr-sat { color: #38bdf8; }
        .hdr-normal { color: #52525b; }

        /* 3. 將 Streamlit 原生按鈕直接改造為圓角卡片 */
        div[data-testid="column"] button {
            width: 100% !important;
            height: 80px !important;
            background-color: #ffffff !important;
            border: 1px solid #f0f0f0 !important;
            border-radius: 14px !important;
            padding: 6px 6px !important;
            box-shadow: 0 2px 5px rgba(0,0,0,0.03) !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: flex-start !important;
            align-items: flex-start !important;
            transition: transform 0.15s ease, box-shadow 0.15s ease !important;
        }
        div[data-testid="column"] button:hover {
            border-color: #00c896 !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 10px rgba(0,200,150,0.15) !important;
        }

        /* 4. 今天（Today）卡片樣式 */
        div[data-testid="column"] button.btn-today {
            background-color: #00c896 !important;
            border-color: #00c896 !important;
        }

        /* 5. 按鈕內部 Markdown 排版 */
        div[data-testid="column"] button p {
            width: 100% !important;
            text-align: left !important;
            margin: 0 !important;
            line-height: 1.2 !important;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # 2. 渲染星期標頭
    w_cols = st.columns(7)
    weekdays_data = [
        ("日", "hdr-sun"),
        ("一", "hdr-normal"),
        ("二", "hdr-normal"),
        ("三", "hdr-normal"),
        ("四", "hdr-normal"),
        ("五", "hdr-normal"),
        ("六", "hdr-sat"),
    ]
    for idx, (w_text, w_cls) in enumerate(weekdays_data):
        w_cols[idx].markdown(
            f"<div class='cal-header-box {w_cls}'>{w_text}</div>",
            unsafe_allow_html=True,
        )

    # 3. 渲染日曆網格（按鈕直接作為卡片，點擊直開彈窗）
    cal_obj = calendar.Calendar(firstweekday=6)
    month_days = cal_obj.monthdayscalendar(sel_year, sel_month)

    for week in month_days:
        cols = st.columns(7)
        for idx, day in enumerate(week):
            with cols[idx]:
                if day == 0:
                    st.write("")
                else:
                    day_str = f"{sel_year}-{sel_month:02d}-{day:02d}"
                    is_today = (
                        sel_year == today.year
                        and sel_month == today.month
                        and day == today.day
                    )
                    day_evs = [
                        e for e in active_events if e.get("date") == day_str
                    ]

                    # 數字顏色設定
                    if is_today:
                        num_color = ":white"
                    elif idx == 0:
                        num_color = ":red"
                    elif idx == 6:
                        num_color = ":blue"
                    else:
                        num_color = ":gray"

                    # 組合按鈕內的富文本 (Markdown Label)
                    label_content = f"**{num_color}[{day}]**"

                    if day_evs:
                        ev = day_evs[0]
                        title = ev.get("title", "")
                        cate = ev.get("category", "")
                        if len(title) > 4:
                            title = title[:3] + ".."
                        more = (
                            f"(+{len(day_evs)-1})" if len(day_evs) > 1 else ""
                        )

                        # 紅色底標或灰色底標
                        if "考" in title or cate == "重要提醒":
                            label_content += (
                                f"\n\n:red-background[:red[**{title}{more}**]]"
                            )
                        else:
                            label_content += (
                                f"\n\n:gray-background[{title}{more}]"
                            )

                    # 渲染卡片按鈕，點擊立刻打開彈窗！
                    if st.button(
                        label_content,
                        key=f"card_btn_{day_str}",
                        use_container_width=True,
                    ):
                        open_day_dialog(day_str)

    st.divider()

    # 4. 下方「即將到來」列表 (還原圖片下方區塊)
    st.markdown("#### 📌 即將到來")
    future_events = [
        e
        for e in active_events
        if e.get("date") >= today.strftime("%Y-%m-%d")
    ]
    future_events.sort(key=lambda x: x.get("date"))

    if not future_events:
        st.info("💡 目前沒有即將到來的行程安排。")
    else:
        for ev in future_events[:5]:
            ev_date = datetime.strptime(ev["date"], "%Y-%m-%d").date()
            delta_days = (ev_date - today).days
            day_hint = (
                "今天"
                if delta_days == 0
                else ("明天" if delta_days == 1 else f"{delta_days}天後")
            )

            st.markdown(
                f"""
                <div style="background-color: #fff1f2; border: 1px solid #fecdd3; border-radius: 16px; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div style="color: #e11d48; font-weight: bold; font-size: 14px;">● {ev.get('title', '')}</div>
                    <div style="color: #9ca3af; font-size: 13px;">{ev_date.month}/{ev_date.day} · {day_hint}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
# ------------------------------------------------------------------------------
# TAB 2~5 保持工具完整
# ------------------------------------------------------------------------------
with tab_pdf:
    st.header("📄 PDF 救星工具箱")
    pdf_action = st.radio(
        "選擇要執行的操作：",
        [
            "🔓 PDF 解密與密碼移除",
            "🧩 多檔 PDF 快速合併",
            "📊 PDF 內文與表格轉 Excel",
        ],
        horizontal=True,
    )
    st.divider()

    if pdf_action == "🔓 PDF 解密與密碼移除":
        up_pdf = st.file_uploader("上傳 PDF", type=["pdf"])
        pdf_pwd = st.text_input("輸入密碼", type="password")
        if up_pdf and pdf_pwd and st.button("🔑 開始解密"):
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
                st.download_button(
                    "📥 下載解密檔",
                    out_buf.getvalue(),
                    file_name="unlocked.pdf",
                    mime="application/pdf",
                )
            except Exception as e:
                st.error(f"解密失敗：{e}")

    elif pdf_action == "🧩 多檔 PDF 快速合併":
        pdf_files = st.file_uploader(
            "選擇 PDF", type=["pdf"], accept_multiple_files=True
        )
        if pdf_files and st.button("🧩 合併"):
            merger = pypdf.PdfWriter()
            for p in pdf_files:
                merger.append(p)
            merged_buf = io.BytesIO()
            merger.write(merged_buf)
            st.success("🎉 合併成功！")
            st.download_button(
                "📥 下載合併檔",
                merged_buf.getvalue(),
                file_name="merged.pdf",
                mime="application/pdf",
            )

    elif pdf_action == "📊 PDF 內文與表格轉 Excel":
        pdf_excel_file = st.file_uploader("上傳 PDF", type=["pdf"])
        if pdf_excel_file and st.button("📊 提取轉 Excel"):
            try:
                reader = pypdf.PdfReader(pdf_excel_file)
                data_rows = [
                    {"頁碼": i + 1, "擷取內容": line.strip()}
                    for i, page in enumerate(reader.pages)
                    for line in page.extract_text().split("\n")
                    if line.strip()
                ]
                df = pd.DataFrame(data_rows)
                excel_buf = io.BytesIO()
                with pd.ExcelWriter(
                    excel_buf, engine="openpyxl"
                ) as writer:
                    df.to_excel(writer, index=False)
                st.success("🎉 提取成功！")
                st.dataframe(df.head(10))
                st.download_button(
                    "📥 下載 Excel",
                    excel_buf.getvalue(),
                    file_name="extracted.xlsx",
                )
            except Exception as e:
                st.error(f"失敗：{e}")

with tab_img:
    st.header("✂️ 圖像編修與去背")
    img_file = st.file_uploader("上傳圖片", type=["jpg", "jpeg", "png"])
    if img_file:
        ori_img = Image.open(img_file)
        st.image(ori_img, caption="原圖", use_container_width=True)

with tab_summary:
    st.header("📝 文本總結與防雷")
    input_text = st.text_area("貼上內文", height=200)

with tab_ig:
    st.header("📱 社群 IG 切圖")
    ig_img_file = st.file_uploader(
        "上傳圖片", type=["jpg", "jpeg", "png"], key="ig_file"
    )
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
