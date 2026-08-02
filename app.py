import calendar
from datetime import date, datetime
import io
import json
import os
import random
import re
import string
import zipfile

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
CALENDARS_FILE = "calendars.json"  # 儲存共享行事曆與成員關係

# 💡 管理員 Email 帳號
ADMIN_EMAIL = "admin@example.com"

# 💡 PWA 桌面圖示直連網址
ICON_URL = "https://raw.githubusercontent.com/3323jayden-dot/calendar-app/main/istockphoto-1033804852-612x612.jpg"


# ==============================================================================
# 1. JSON 資料讀寫與輔助函式 (必須提至最上方)
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


# 載入全域資料
users = load_data(USERS_FILE, {})
events = load_data(EVENTS_FILE, [])
calendars_data = load_data(CALENDARS_FILE, [])


def get_user_calendars(user_email):
    """取得該使用者擁有的共享行事曆清單"""
    if not user_email:
        return []
    user_cals = []
    for c in calendars_data:
        # 如果是建立者或是成員之一
        if c.get("owner") == user_email or user_email in c.get("members", []):
            user_cals.append(c)
    return user_cals


# ==============================================================================
# 2. 自動保持登入邏輯（使用 Streamlit 原生 st.query_params）
# ==============================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

# 從網址參數讀取使用者資訊（自動登入）
query_params = st.query_params
if "user" in query_params and not st.session_state.logged_in:
    saved_user = query_params["user"]
    if saved_user:
        st.session_state.logged_in = True
        st.session_state.user_email = saved_user

# ==============================================================================
# 3. PWA 手機安裝與 Manifest 注入 (支援 iOS & Android)
# ==============================================================================
pwa_html = f"""
<script>
(function() {{
    const currentSearch = window.parent.location.search || window.location.search;
    const startUrl = '/' + currentSearch;

    const manifest = {{
      "name": "多功能雲端助理",
      "short_name": "雲端助理",
      "start_url": startUrl,
      "display": "standalone",
      "background_color": "#ffffff",
      "theme_color": "#007aff",
      "icons": [
        {{ "src": "{ICON_URL}", "sizes": "192x192", "type": "image/jpeg", "purpose": "any maskable" }},
        {{ "src": "{ICON_URL}", "sizes": "512x512", "type": "image/jpeg", "purpose": "any maskable" }}
      ]
    }};

    const stringManifest = JSON.stringify(manifest);
    const blob = new Blob([stringManifest], {{type: 'application/json'}});
    const manifestURL = URL.createObjectURL(blob);
    
    const oldLink = document.head.querySelector('link[rel="manifest"]');
    if (oldLink) oldLink.remove();

    let linkTag = document.createElement('link');
    linkTag.rel = 'manifest';
    linkTag.href = manifestURL;
    document.head.appendChild(linkTag);

    let appleIcon = document.createElement('link');
    appleIcon.rel = 'apple-touch-icon';
    appleIcon.href = '{ICON_URL}';
    document.head.appendChild(appleIcon);

    if ('serviceWorker' in navigator) {{
      const swCode = `
        self.addEventListener('install', (e) => self.skipWaiting());
        self.addEventListener('activate', (e) => self.clients.claim());
      `;
      const blobSW = new Blob([swCode], {{type: 'text/javascript'}});
      const swURL = URL.createObjectURL(blobSW);
      navigator.serviceWorker.register(swURL).catch(err => console.log('SW fail:', err));
    }}
}})();
</script>
"""
components.html(pwa_html, height=0)


# ==============================================================================
# 4. 會員驗證系統與側邊欄 (登入 / 註冊 / 管理員後台)
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
    current_user_name = users.get(st.session_state.user_email, {}).get(
        "name", "會員"
    )
    st.sidebar.success(f"歡迎回來，**{current_user_name}**！")
    st.sidebar.caption(f"目前帳號：`{st.session_state.user_email}`")

    if st.sidebar.button("安全登出", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_email = ""
        st.rerun()

# 🛡️ 管理員專屬後台
if (
    st.session_state.logged_in
    and st.session_state.user_email == "3323jayden@gmail.com"
):
    st.sidebar.divider()
    with st.sidebar.expander(
        "🛡️ 系統後台管理 (Admin Only)", expanded=False
    ):
        st.markdown("**管理員帳號控制台**")
        if not users:
            st.info("尚無註冊會員資料。")
        else:
            selected_user_email = st.selectbox(
                "選擇要管理的會員", list(users.keys())
            )
            if selected_user_email:
                u_info = users[selected_user_email]
                st.text(f"用戶暱稱: {u_info.get('name', '未設定')}")

                new_pwd_input = st.text_input(
                    "該帳號密碼",
                    value=u_info.get("password", ""),
                    key="admin_pwd_edit",
                )

                c_save, c_del = st.columns(2)
                with c_save:
                    if st.button("💾 更新資料"):
                        users[selected_user_email]["password"] = new_pwd_input
                        save_data(USERS_FILE, users)
                        st.success("更新成功！")
                        st.rerun()
                with c_del:
                    if selected_user_email != ADMIN_EMAIL:
                        if st.button("🗑️ 刪除帳號"):
                            del users[selected_user_email]
                            save_data(USERS_FILE, users)
                            st.warning("帳號已刪除")
                            st.rerun()


# ==============================================================================
# 5. 主畫面：分頁與模組 (Tabs)
# ==============================================================================
st.title("⚡ 多功能數位工作助理與行事曆")

tab_ai, tab_cal, tab_pdf, tab_img, tab_summary, tab_ig = st.tabs([
    "🤖 Groq AI 智囊團",
    "📅 視覺化日曆與行程",
    "📄 PDF 救星",
    "✂️ AI 圖片處理與去背",
    "📝 文本總結與防雷助理",
    "📱 社群 IG/Threads 一鍵切圖",
])

# ------------------------------------------------------------------------------
# TAB 0: 🤖 Groq AI 智囊團
# ------------------------------------------------------------------------------
with tab_ai:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.markdown(
        """
        <style>
        .chat-scroll-container {
            max-width: 800px;
            margin: 0 auto;
            height: 500px;
            overflow-y: auto;
            padding: 10px 15px;
            border-radius: 12px;
            scroll-behavior: smooth;
        }
        .welcome-box {
            text-align: center;
            padding: 80px 20px 20px 20px;
        }
        .welcome-title {
            font-size: 34px;
            font-weight: 700;
            background: linear-gradient(135deg, #4285f4, #d93025, #fbbc04, #34a853);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .welcome-sub { color: #5f6368; font-size: 15px; }
        .user-bubble-container {
            display: flex;
            justify-content: flex-end;
            margin-bottom: 16px;
        }
        .user-bubble {
            background-color: #f1f3f4;
            color: #202124;
            padding: 10px 18px;
            border-radius: 20px 20px 4px 20px;
            max-width: 75%;
            font-size: 15px;
            line-height: 1.5;
            word-break: break-word;
        }
        .ai-bubble-container {
            display: flex;
            justify-content: flex-start;
            margin-bottom: 24px;
        }
        .ai-bubble {
            color: #1f1f1f;
            width: 100%;
            font-size: 15px;
            line-height: 1.6;
            word-break: break-word;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    if st.session_state.messages:
        c_space, c_reset = st.columns([5, 1])
        with c_reset:
            if st.button("➕ 新對話", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

    html_items = ['<div class="chat-scroll-container" id="chat-box">']

    if not st.session_state.messages:
        html_items.append(
            '<div class="welcome-box">'
            '<div class="welcome-title">Jayden，儘管發問吧！</div>'
            '<div class="welcome-sub">我可以幫你規劃行程、撰寫文案或解答各種問題</div>'
            "</div>"
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

    if prompt := st.chat_input("問問 AI 助手..."):
        if (
            "GROQ_API_KEY" not in st.secrets
            or not st.secrets["GROQ_API_KEY"]
        ):
            st.error(
                "⚠️ 未在 Streamlit Secrets 中設定 `GROQ_API_KEY`，請先至後台設定。"
            )
        else:
            st.session_state.messages.append(
                {"role": "user", "content": prompt}
            )
            st.rerun()

    if (
        st.session_state.messages
        and st.session_state.messages[-1]["role"] == "user"
    ):
        with st.spinner("AI 思考中..."):
            try:
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                api_messages = [
                    {
                        "role": "system",
                        "content": "你是一個親切且專業的繁體中文 AI 助手。",
                    }
                ] + [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ]

                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=api_messages,
                    temperature=0.7,
                )

                ai_reply = response.choices[0].message.content
                st.session_state.messages.append(
                    {"role": "assistant", "content": ai_reply}
                )
                st.rerun()
            except Exception as e:
                st.error(f"❌ 發生錯誤：{e}")

    if st.session_state.messages:
        components.html(
            """
            <script>
                setTimeout(function() {
                    var chatBox = window.parent.document.getElementById('chat-box');
                    if (chatBox) {
                        chatBox.scrollTop = chatBox.scrollHeight;
                    }
                }, 100);
            </script>
            """,
            height=0,
        )

# ------------------------------------------------------------------------------
# TAB 1: 📅 視覺化日曆網格
# ------------------------------------------------------------------------------
with tab_cal:
    st.header("📅 視覺化月曆與行程表")

    if not st.session_state.logged_in:
        st.warning(
            "⚠️ 目前為訪客預覽模式。登入後可切換個人/共享行事曆並新增行程。"
        )
        user_email = "guest"
    else:
        user_email = st.session_state.user_email

    today = date.today()

    col_cal_sel, col_cal_mgmt = st.columns([2, 2])
    my_shared_cals = get_user_calendars(user_email)
    cal_options = ["🔒 個人專屬行事曆"] + [
        f"👥 {c['name']} (代碼: {c['code']})" for c in my_shared_cals
    ]

    with col_cal_sel:
        selected_cal_option = st.selectbox("📌 切換行事曆範疇", cal_options)
        if selected_cal_option == "🔒 個人專屬行事曆":
            current_cal_mode = "personal"
            current_cal_code = None
        else:
            current_cal_mode = "shared"
            current_cal_code = selected_cal_option.split("(代碼: ")[1].replace(
                ")", ""
            )

    with col_cal_mgmt:
        if st.session_state.logged_in:
            with st.popover("➕ 管理 / 加入共享行事曆"):
                st.markdown("#### 👥 建立新的共享行事曆")
                new_cal_name = st.text_input(
                    "共享行事曆名稱", placeholder="例如：專案組、家庭日曆"
                )
                if st.button("建立共享行事曆", use_container_width=True):
                    if new_cal_name.strip():
                        inv_code = "".join(
                            random.choices(
                                string.ascii_uppercase + string.digits, k=6
                            )
                        )
                        new_cal = {
                            "name": new_cal_name.strip(),
                            "code": inv_code,
                            "owner": user_email,
                            "members": [user_email],
                        }
                        calendars_data.append(new_cal)
                        save_data(CALENDARS_FILE, calendars_data)
                        st.success(
                            f"建立成功！邀請碼為：**{inv_code}**"
                        )
                        st.rerun()
                    else:
                        st.error("請輸入名稱")

                st.divider()
                st.markdown("#### 🔑 透過邀請碼加入")
                join_code = st.text_input("輸入 6 位邀請碼").strip().upper()
                if st.button("加入共享行事曆", use_container_width=True):
                    target_cal = next(
                        (c for c in calendars_data if c.get("code") == join_code),
                        None,
                    )
                    if target_cal:
                        if user_email not in target_cal.setdefault("members", []):
                            target_cal["members"].append(user_email)
                            save_data(CALENDARS_FILE, calendars_data)
                            st.success(
                                f"已成功加入「{target_cal['name']}」！"
                            )
                            st.rerun()
                        else:
                            st.info("您已經是該行事曆的成員囉！")
                    else:
                        st.error("無效的邀請碼。")

    if current_cal_mode == "personal":
        active_events = [
            e
            for e in events
            if e.get("creator") == user_email and not e.get("cal_code")
        ]
    else:
        active_events = [
            e for e in events if e.get("cal_code") == current_cal_code
        ]

    c_y, c_m, _ = st.columns([1, 1, 2])
    with c_y:
        sel_year = st.number_input(
            "選擇年份", min_value=2020, max_value=2030, value=today.year
        )
    with c_m:
        sel_month = st.number_input(
            "選擇月份", min_value=1, max_value=12, value=today.month
        )

    @st.dialog("📅 行程安排與管理", width="large")
    def show_event_dialog(selected_date_str):
        st.subheader(
            f"📌 {selected_date_str} 的行程 ({selected_cal_option})"
        )
        day_events = [
            e for e in active_events if e.get("date") == selected_date_str
        ]

        if not day_events:
            st.info("💡 當天目前沒有任何行程安排。")
        else:
            for idx, ev in enumerate(day_events):
                with st.expander(
                    f"📌 {ev['title']} ({ev.get('category', '一般')})",
                    expanded=True,
                ):
                    st.write(
                        f"**詳細備註**：{ev.get('description') if ev.get('description') else '無'}"
                    )
                    st.caption(f"建立者：{ev.get('creator', '未知')}")
                    if st.session_state.logged_in and (
                        st.session_state.user_email == ev.get("creator")
                        or st.session_state.user_email == ADMIN_EMAIL
                    ):
                        if st.button(
                            "🗑️ 刪除此行程",
                            key=f"dlg_del_{selected_date_str}_{idx}",
                        ):
                            events.remove(ev)
                            save_data(EVENTS_FILE, events)
                            st.success("行程已刪除！")
                            st.rerun()

        st.divider()
        st.markdown(f"### ➕ 新增至【{selected_cal_option}】")
        if st.session_state.logged_in:
            with st.form(
                f"dialog_add_form_{selected_date_str}", clear_on_submit=True
            ):
                e_title = st.text_input("行程名稱（必填）")
                e_cate = st.selectbox(
                    "行程分類", ["工作", "個人", "重要提醒", "休閒"]
                )
                e_desc = st.text_area("行程詳細備註")
                if st.form_submit_button(
                    "💾 儲存並新增行程", use_container_width=True
                ):
                    if not e_title.strip():
                        st.error("請填寫行程名稱！")
                    else:
                        new_ev = {
                            "title": e_title.strip(),
                            "date": selected_date_str,
                            "category": e_cate,
                            "description": e_desc.strip(),
                            "creator": user_email,
                            "cal_code": (
                                current_cal_code
                                if current_cal_mode == "shared"
                                else None
                            ),
                        }
                        events.append(new_ev)
                        save_data(EVENTS_FILE, events)
                        st.success("行程新增成功！")
                        st.rerun()
        else:
            st.info("🔒 請於側邊欄登入帳號後進行行程新增。")

    st.markdown(
        """
        <style>
        div[data-testid="column"] {
            min-width: 0px !important;
            flex: 1 1 0px !important;
        }
        div[data-testid="stHorizontalBlock"] button {
            height: 70px !important;
            padding: 2px !important;
            font-size: 14px !important;
            white-space: pre-wrap !important;
            line-height: 1.2 !important;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    cal = calendar.monthcalendar(sel_year, sel_month)
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]

    query_p = st.query_params
    if "click_date" in query_p:
        clicked_date_str = query_p["click_date"]
        del st.query_params["click_date"]
        show_event_dialog(clicked_date_str)

    html_code = """
    <style>
        .cal-wrapper { width: 100%; overflow-x: auto; }
        .cal-grid {
            display: grid !important;
            grid-template-columns: repeat(7, minmax(40px, 1fr)) !important;
            gap: 6px;
            width: 100%;
            min-width: 320px;
        }
        .cal-header {
            text-align: center;
            font-weight: bold;
            color: #718096;
            font-size: 13px;
            padding: 4px 0;
        }
        .cal-card {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            height: 65px;
            padding: 4px;
            box-sizing: border-box;
            cursor: pointer;
            transition: all 0.15s ease-in-out;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }
        .cal-card:hover {
            border-color: #cbd5e0;
            background-color: #f7fafc;
            transform: translateY(-1px);
        }
        .cal-empty { height: 65px; }
        .day-num { font-size: 14px; font-weight: bold; color: #2d3748; }
        .tag-pink {
            background-color: #ffebee;
            color: #e53935;
            font-size: 10px;
            font-weight: 600;
            padding: 2px 4px;
            border-radius: 6px;
            margin-top: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
    </style>
    <div class="cal-wrapper"><div class="cal-grid">
    """

    for w in weekdays:
        html_code += f'<div class="cal-header">週{w}</div>'

    for week in cal:
        for day in week:
            if day == 0:
                html_code += '<div class="cal-empty"></div>'
            else:
                day_str = f"{sel_year}-{sel_month:02d}-{day:02d}"
                day_events = [
                    e for e in active_events if e.get("date") == day_str
                ]

                tag_html = ""
                if day_events:
                    title = day_events[0]["title"]
                    short_title = (
                        title[:4] + ".." if len(title) > 4 else title
                    )
                    tag_html = f'<div class="tag-pink">📌{short_title}</div>'

                click_js = f"window.parent.location.href = window.parent.location.pathname + '?click_date={day_str}';"

                html_code += f"""
                <div class="cal-card" onclick="{click_js}">
                    <div class="day-num">{day}</div>
                    {tag_html}
                </div>
                """

    html_code += "</div></div>"
    components.html(html_code, height=480, scrolling=False)

# ------------------------------------------------------------------------------
# TAB 2: 📄 PDF 救星
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
        st.subheader("解密保護的 PDF 檔案")
        up_pdf = st.file_uploader(
            "上傳密碼保護的 PDF 檔案", type=["pdf"], key="unlock_pdf_input"
        )
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
                    st.download_button(
                        "📥 下載已解密 PDF",
                        out_buf.getvalue(),
                        file_name="unlocked_document.pdf",
                        mime="application/pdf",
                    )
                except Exception as e:
                    st.error(f"解密失敗，請檢查密碼是否正確：{e}")

    elif pdf_action == "🧩 多檔 PDF 快速合併":
        st.subheader("合併多份 PDF 為單一檔案")
        pdf_files = st.file_uploader(
            "選擇多個 PDF 檔案",
            type=["pdf"],
            accept_multiple_files=True,
            key="merge_pdf_input",
        )

        if pdf_files and st.button("🧩 執行合併"):
            merger = pypdf.PdfWriter()
            for p_file in pdf_files:
                merger.append(p_file)
            merged_buf = io.BytesIO()
            merger.write(merged_buf)
            st.success("🎉 PDF 合併成功！")
            st.download_button(
                "📥 下載合併後的 PDF",
                merged_buf.getvalue(),
                file_name="merged_output.pdf",
                mime="application/pdf",
            )

    elif pdf_action == "📊 PDF 內文與表格轉 Excel":
        st.subheader("提取 PDF 文字與數據至 Excel")
        pdf_excel_file = st.file_uploader(
            "上傳含有數據或內文的 PDF", type=["pdf"], key="excel_pdf_input"
        )

        if pdf_excel_file and st.button("📊 提取資料並生成 Excel"):
            try:
                reader = pypdf.PdfReader(pdf_excel_file)
                data_rows = []
                for p_idx, page in enumerate(reader.pages):
                    text = page.extract_text()
                    lines = text.split("\n")
                    for line in lines:
                        if line.strip():
                            data_rows.append(
                                {"頁碼": p_idx + 1, "擷取內容": line.strip()}
                            )

                df = pd.DataFrame(data_rows)
                excel_buf = io.BytesIO()
                with pd.ExcelWriter(
                    excel_buf, engine="openpyxl"
                ) as writer:
                    df.to_excel(writer, index=False, sheet_name="PDF 提取內容")

                st.success(f"🎉 成功提取 {len(data_rows)} 筆資料！")
                st.dataframe(df.head(10), use_container_width=True)
                st.download_button(
                    "📥 下載 Excel 試算表 (.xlsx)",
                    excel_buf.getvalue(),
                    file_name="pdf_data_extracted.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            except Exception as e:
                st.error(f"提取過程中發生錯誤：{e}")

# ------------------------------------------------------------------------------
# TAB 3: ✂️ AI 圖片處理與去背
# ------------------------------------------------------------------------------
with tab_img:
    st.header("✂️ 圖像編修與智能去背工具")
    img_file = st.file_uploader(
        "上傳圖片檔案 (JPG / PNG)",
        type=["jpg", "jpeg", "png"],
        key="img_proc_input",
    )

    if img_file:
        ori_img = Image.open(img_file)
        c_left, c_right = st.columns(2)

        with c_left:
            st.image(
                ori_img, caption="原始圖片預覽", use_container_width=True
            )

        with c_right:
            proc_mode = st.selectbox(
                "選擇處理模式",
                [
                    "純白/淺色背景去背 (轉透明 PNG)",
                    "調整尺寸與旋轉",
                    "亮度/對比度微調",
                    "黑白灰階濾鏡",
                ],
            )

            if proc_mode == "純白/淺色背景去背 (轉透明 PNG)":
                tolerance = st.slider(
                    "背景色閥值 (容差度高適用於淺色背景)", 0, 100, 30
                )
                if st.button("✂️ 執行去背"):
                    img_rgba = ori_img.convert("RGBA")
                    datas = img_rgba.getdata()
                    new_datas = []
                    for item in datas:
                        if (
                            item[0] >= (255 - tolerance)
                            and item[1] >= (255 - tolerance)
                            and item[2] >= (255 - tolerance)
                        ):
                            new_datas.append((255, 255, 255, 0))
                        else:
                            new_datas.append(item)

                    img_rgba.putdata(new_datas)
                    out_p = io.BytesIO()
                    img_rgba.save(out_p, format="PNG")
                    st.image(
                        img_rgba,
                        caption="去背完成結果",
                        use_container_width=True,
                    )
                    st.download_button(
                        "📥 下載透明背景 PNG",
                        out_p.getvalue(),
                        file_name="nobg_image.png",
                        mime="image/png",
                    )

            elif proc_mode == "調整尺寸與旋轉":
                w = st.number_input(
                    "新寬度 (px)", value=ori_img.width, step=10
                )
                h = st.number_input(
                    "新高度 (px)", value=ori_img.height, step=10
                )
                angle = st.slider("順時針旋轉角度", 0, 360, 0)

                if st.button("💾 套用修改"):
                    resized_img = ori_img.resize((int(w), int(h))).rotate(
                        angle, expand=True
                    )
                    out_p = io.BytesIO()
                    resized_img.save(out_p, format="PNG")
                    st.image(
                        resized_img,
                        caption="修改後結果",
                        use_container_width=True,
                    )
                    st.download_button(
                        "📥 下載圖片",
                        out_p.getvalue(),
                        file_name="resized_image.png",
                        mime="image/png",
                    )

            elif proc_mode == "亮度/對比度微調":
                b_val = st.slider("亮度", 0.1, 2.0, 1.0)
                c_val = st.slider("對比度", 0.1, 2.0, 1.0)
                if st.button("✨ 應用效果"):
                    enh_b = ImageEnhance.Brightness(ori_img).enhance(b_val)
                    enh_c = ImageEnhance.Contrast(enh_b).enhance(c_val)
                    out_p = io.BytesIO()
                    enh_c.save(out_p, format="PNG")
                    st.image(
                        enh_c,
                        caption="調色完成預覽",
                        use_container_width=True,
                    )
                    st.download_button(
                        "📥 下載調色圖片",
                        out_p.getvalue(),
                        file_name="enhanced_image.png",
                        mime="image/png",
                    )

            elif proc_mode == "黑白灰階濾鏡":
                if st.button("🎨 轉為黑白"):
                    gray_img = ImageOps.grayscale(ori_img)
                    out_p = io.BytesIO()
                    gray_img.save(out_p, format="PNG")
                    st.image(
                        gray_img,
                        caption="黑白濾鏡預覽",
                        use_container_width=True,
                    )
                    st.download_button(
                        "📥 下載黑白圖片",
                        out_p.getvalue(),
                        file_name="grayscale_image.png",
                        mime="image/png",
                    )

# ------------------------------------------------------------------------------
# TAB 4: 📝 萬用文本總結與防雷助理 (修復原本中斷處)
# ------------------------------------------------------------------------------
with tab_summary:
    st.header("📝 萬用文本總結與防雷條款助理")
    input_text = st.text_area(
        "請貼上欲分析長文章、新聞、合約條款或說明書內容：", height=220
    )

    if input_text and st.button("🔍 執行文本總結與關鍵風險分析"):
        col_s1, col_s2 = st.columns(2)

        with col_s1:
            st.subheader("📌 核心摘要重點")
            # 依據標點符號初步拆分句子
            sentences = [
                s.strip()
                for s in re.split(r"[。\n！!？?]", input_text)
                if s.strip()
            ]
            summary_items = sentences[:5]  # 抓取前五項重點
            for i, s in enumerate(summary_items, 1):
                st.markdown(f"**{i}.** {s}")

        with col_s2:
            st.subheader("⚠️ 關鍵風險與防雷提醒")
            # 預設風險關鍵字檢測
            risk_keywords = [
                "費用",
                "違約金",
                "限制",
                "自動續約",
                "責任",
                "不退還",
                "賠償",
                "終止",
            ]
            found_risks = [
                s for s in sentences if any(k in s for k in risk_keywords)
            ]

            if found_risks:
                for r in found_risks:
                    st.warning(f"🚨 注意事項：{r}")
            else:
                st.success("✅ 未在文章中發現明顯常見風險關鍵字。")

# ------------------------------------------------------------------------------
# TAB 5: 📱 社群 IG/Threads 一鍵切圖 (補充補全)
# ------------------------------------------------------------------------------
with tab_ig:
    st.header("📱 社群 IG / Threads 拼圖切圖助手")
    ig_img_file = st.file_uploader(
        "上傳要裁切的圖片", type=["jpg", "jpeg", "png"], key="ig_crop_input"
    )

    if ig_img_file:
        ig_img = Image.open(ig_img_file)
        st.image(ig_img, caption="原始圖片", use_container_width=True)

        split_count = st.slider("選擇要切割的直向等分數量", 2, 6, 3)

        if st.button("✂️ 開始裁切圖片"):
            w, h = ig_img.size
            part_w = w // split_count

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(
                zip_buffer, "a", zipfile.ZIP_DEFLATED, False
            ) as zip_file:
                cols_preview = st.columns(split_count)
                for i in range(split_count):
                    left = i * part_w
                    right = (i + 1) * part_w if i < split_count - 1 else w
                    box = (left, 0, right, h)
                    cropped = ig_img.crop(box)

                    # 儲存至記憶體與 ZIP 壓縮檔
                    img_byte_arr = io.BytesIO()
                    cropped.save(img_byte_arr, format="PNG")
                    zip_file.writestr(
                        f"ig_part_{i+1}.png", img_byte_arr.getvalue()
                    )

                    with cols_preview[i]:
                        st.image(cropped, caption=f"第 {i+1} 張")

            st.success("🎉 切割完成！")
            st.download_button(
                label="📥 下載全部切割圖片 (.zip)",
                data=zip_buffer.getvalue(),
                file_name="ig_sliced_images.zip",
                mime="application/zip",
            )
