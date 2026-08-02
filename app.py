import streamlit as st
import json
import os
import io
import zipfile
import re
from datetime import datetime, date
import calendar
from PIL import Image, ImageEnhance, ImageOps
import pandas as pd
import pypdf
import calendar
from datetime import date
import streamlit as st
from groq import Groq  # 1. 記得在最上方 import groq
# ------------------------------------------------------------------------------
# 1. 自動保持登入邏輯（使用 Streamlit 原生 st.query_params）
# ------------------------------------------------------------------------------
# 初始化 Session State
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

# ------------------------------------------------------------------------------
# 資料載入與儲存輔助 (請確認檔名與變數名稱)
# ------------------------------------------------------------------------------
CALENDARS_FILE = "calendars.json" # 儲存共享行事曆與成員關係

# 載入行事曆清單 (若檔案不存在則預設為空清單)
calendars_data = load_data(CALENDARS_FILE) if 'load_data' in globals() else []

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
# 0. 基本頁面配置與檔案設定
# ==============================================================================
st.set_page_config(
    page_title="多功能雲端助理與行事曆系統",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

USERS_FILE = "users.json"
EVENTS_FILE = "events.json"

# 💡 管理員 Email 帳號
ADMIN_EMAIL = "admin@example.com"

# 💡 PWA 桌面圖示直連網址
ICON_URL = "https://raw.githubusercontent.com/3323jayden-dot/calendar-app/main/istockphoto-1033804852-612x612.jpg"

# ==============================================================================
# 1. PWA 手機安裝與 Manifest 注入 (支援 iOS & Android)
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
st.components.v1.html(pwa_html, height=0)


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


# ==============================================================================
# 3. 會員驗證系統與側邊欄 (登入 / 註冊 / 管理員後台)
# ==============================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

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
                    "password": password_input
                }
                save_data(USERS_FILE, users)
                st.sidebar.success("🎉 註冊成功！請切換至「帳號登入」。")
                
    elif auth_mode == "帳號登入":
        if st.sidebar.button("登入系統", use_container_width=True):
            if email_input in users and users[email_input]["password"] == password_input:
                st.session_state.logged_in = True
                st.session_state.user_email = email_input
                st.sidebar.success("登入成功！")
                st.rerun()
            else:
                st.sidebar.error("帳號或密碼輸入錯誤！")
else:
    current_user_name = users.get(st.session_state.user_email, {}).get("name", "會員")
    st.sidebar.success(f"歡迎回來，**{current_user_name}**！")
    st.sidebar.caption(f"目前帳號：`{st.session_state.user_email}`")
    
    if st.sidebar.button("安全登出", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_email = ""
        st.rerun()

# 🛡️ 管理員專屬後台 (查看/修改所有帳號密碼)
if st.session_state.logged_in and st.session_state.user_email == "3323jayden@gmail.com":
    st.sidebar.divider()
    with st.sidebar.expander("🛡️ 系統後台管理 (Admin Only)", expanded=False):
        st.markdown("**管理員帳號控制台**")
        if not users:
            st.info("尚無註冊會員資料。")
        else:
            selected_user_email = st.selectbox("選擇要管理的會員", list(users.keys()))
            if selected_user_email:
                u_info = users[selected_user_email]
                st.text(f"用戶暱稱: {u_info.get('name', '未設定')}")
                
                new_pwd_input = st.text_input("該帳號密碼", value=u_info.get("password", ""), key="admin_pwd_edit")
                
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
# 4. 主畫面：分頁與模組 (Tabs)
# ==============================================================================
st.title("⚡ 多功能數位工作助理與行事曆")

# 確保變數名稱完整對應（包含原本的 tab_summary）
tab_ai, tab_cal, tab_pdf, tab_img, tab_summary, tab_ig = st.tabs([
    "🤖 Groq AI 智囊團", 
    "📅 視覺化日曆與行程", 
    "📄 PDF 救星", 
    "✂️ AI 圖片處理與去背", 
    "📝 文本總結與防雷助理", 
    "📱 社群 IG/Threads 一鍵切圖"
])

import streamlit.components.v1 as components
# ------------------------------------------------------------------------------
# TAB 0: 🤖 Groq AI 智囊團（Gemini 風格主頁與對話）
# ------------------------------------------------------------------------------
with tab_ai:
    # 1. 初始化聊天紀錄
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 注入 CSS 讓頁面與輸入框更像現代 AI 介面
    st.markdown("""
        <style>
        .ai-welcome-container {
            text-align: center;
            padding: 60px 20px 20px 20px;
        }
        .ai-welcome-title {
            font-size: 36px !important;
            font-weight: 700;
            background: linear-gradient(135deg, #4285f4, #d93025, #fbbc04, #34a853);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .ai-welcome-sub {
            color: #5f6368;
            font-size: 18px;
            margin-bottom: 30px;
        }
        </style>
    """, unsafe_allow_html=True)

    # 頂部控制區（如果已有對話，顯示重置按鈕）
    if st.session_state.messages:
        c_space, c_reset = st.columns([5, 1])
        with c_reset:
            if st.button("➕ 新對話", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

    # 2. 判斷狀態：尚未有對話時顯示「Gemini 風格歡迎頁」
    if not st.session_state.messages:
        st.markdown("""
            <div class="ai-welcome-container">
                <div class="ai-welcome-title">Jayden，儘管發問吧！</div>
                <div class="ai-welcome-sub">我可以幫你規劃行程、撰寫文案或解答各種問題</div>
            </div>
        """, unsafe_allow_html=True)

    # 3. 如果已有對話，渲染聊天紀錄
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 4. 底部聊天輸入框
    placeholder_text = "問問 AI 助手..." if st.session_state.messages else "在此輸入您的問題..."
    if prompt := st.chat_input(placeholder_text):
        
        # 檢查 API Key
        if "GROQ_API_KEY" not in st.secrets or not st.secrets["GROQ_API_KEY"]:
            st.error("⚠️ 未在 Streamlit Secrets 中設定 `GROQ_API_KEY`，請先至後台設定。")
        else:
            # 存入使用者訊息
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.rerun()  # 立即重整理讓畫面轉入對話模式

    # 如果最後一筆是使用者的訊息，觸發 AI 回覆
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        with st.chat_message("assistant"):
            with st.spinner("AI 思考中..."):
                try:
                    from groq import Groq
                    client = Groq(api_key=st.secrets["GROQ_API_KEY"])

                    api_messages = [
                        {"role": "system", "content": "你是一個親切且專業的繁體中文 AI 助手。"}
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
                    st.markdown(ai_reply)
                    st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ 發生錯誤：{e}")
# ------------------------------------------------------------------------------
# TAB 1: 📅 視覺化日曆網格（7 欄完美不跑版 + 支援直接點擊日期彈窗）
# ------------------------------------------------------------------------------
with tab_cal:
    st.header("📅 視覺化月曆與行程表")
    
    if not st.session_state.logged_in:
        st.warning("⚠️ 目前為訪客預覽模式。登入後可切換個人/共享行事曆並新增行程。")
        user_email = "guest"
    else:
        user_email = st.session_state.user_email

    today = date.today()

    # --- 1. 行事曆切換與管理 ---
    col_cal_sel, col_cal_mgmt = st.columns([2, 2])
    
    my_shared_cals = get_user_calendars(user_email) if 'get_user_calendars' in globals() else []
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
                        import random, string
                        inv_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                        new_cal = {
                            "name": new_cal_name.strip(),
                            "code": inv_code,
                            "owner": user_email,
                            "members": [user_email]
                        }
                        if 'calendars_data' in globals():
                            calendars_data.append(new_cal)
                            save_data(CALENDARS_FILE, calendars_data)
                        st.success(f"建立成功！邀請碼為：**{inv_code}**")
                        st.rerun()
                    else:
                        st.error("請輸入名稱")
                
                st.divider()
                st.markdown("#### 🔑 透過邀請碼加入")
                join_code = st.text_input("輸入 6 位邀請碼").strip().upper()
                if st.button("加入共享行事曆", use_container_width=True):
                    if 'calendars_data' in globals():
                        target_cal = next((c for c in calendars_data if c.get("code") == join_code), None)
                        if target_cal:
                            if user_email not in target_cal.setdefault("members", []):
                                target_cal["members"].append(user_email)
                                save_data(CALENDARS_FILE, calendars_data)
                                st.success(f"已成功加入「{target_cal['name']}」！")
                                st.rerun()
                            else:
                                st.info("您已經是該行事曆的成員囉！")
                        else:
                            st.error("無效的邀請碼。")

    # --- 2. 行程過濾 ---
    if current_cal_mode == "personal":
        active_events = [e for e in events if e.get("creator") == user_email and not e.get("cal_code")]
    else:
        active_events = [e for e in events if e.get("cal_code") == current_cal_code]

    # --- 3. 年月選擇 ---
    c_y, c_m, _ = st.columns([1, 1, 2])
    with c_y:
        sel_year = st.number_input("選擇年份", min_value=2020, max_value=2030, value=today.year)
    with c_m:
        sel_month = st.number_input("選擇月份", min_value=1, max_value=12, value=today.month)

    # --- 4. 行程對話框 ---
    @st.dialog("📅 行程安排與管理", width="large")
    def show_event_dialog(selected_date_str):
        st.subheader(f"📌 {selected_date_str} 的行程 ({selected_cal_option})")
        day_events = [e for e in active_events if e.get("date") == selected_date_str]
        
        if not day_events:
            st.info("💡 當天目前沒有任何行程安排。")
        else:
            for idx, ev in enumerate(day_events):
                with st.expander(f"📌 {ev['title']} ({ev.get('category', '一般')})", expanded=True):
                    st.write(f"**詳細備註**：{ev.get('description') if ev.get('description') else '無'}")
                    st.caption(f"建立者：{ev.get('creator', '未知')}")
                    if st.session_state.logged_in and (st.session_state.user_email == ev.get('creator') or st.session_state.user_email == ADMIN_EMAIL):
                        if st.button("🗑️ 刪除此行程", key=f"dlg_del_{selected_date_str}_{idx}"):
                            events.remove(ev)
                            save_data(EVENTS_FILE, events)
                            st.success("行程已刪除！")
                            st.rerun()

        st.divider()
        st.markdown(f"### ➕ 新增至【{selected_cal_option}】")
        if st.session_state.logged_in:
            with st.form(f"dialog_add_form_{selected_date_str}", clear_on_submit=True):
                e_title = st.text_input("行程名稱（必填）")
                e_cate = st.selectbox("行程分類", ["工作", "個人", "重要提醒", "休閒"])
                e_desc = st.text_area("行程詳細備註")
                if st.form_submit_button("💾 儲存並新增行程", use_container_width=True):
                    if not e_title.strip():
                        st.error("請填寫行程名稱！")
                    else:
                        new_ev = {
                            "title": e_title.strip(),
                            "date": selected_date_str,
                            "category": e_cate,
                            "description": e_desc.strip(),
                            "creator": user_email,
                            "cal_code": current_cal_code if current_cal_mode == "shared" else None
                        }
                        events.append(new_ev)
                        save_data(EVENTS_FILE, events)
                        st.success("行程新增成功！")
                        st.rerun()
        else:
            st.info("🔒 請於側邊欄登入帳號後進行行程新增。")

    # --- 5. 注入 CSS：強制 7 欄橫排並縮小邊距 ---
    st.markdown("""
        <style>
        /* 強制按鈕容器保持 7 欄平行橫排，不自動換行 */
        div[data-testid="column"] {
            min-width: 0px !important;
            flex: 1 1 0px !important;
        }
        /* 美化日曆按鈕樣式 */
        div[data-testid="stHorizontalBlock"] button {
            height: 70px !important;
            padding: 2px !important;
            font-size: 14px !important;
            white-space: pre-wrap !important;
            line-height: 1.2 !important;
        }
        </style>
    """, unsafe_allow_html=True)

# --- 6. HTML + CSS 終極鎖定 7 欄橫排（點擊直接開彈窗） ---
    cal = calendar.monthcalendar(sel_year, sel_month)
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    
    # 檢查網址是否有帶入點擊日期的參數 ?click_date=YYYY-MM-DD
    query_p = st.query_params
    if "click_date" in query_p:
        clicked_date_str = query_p["click_date"]
        # 清除網址參數避免重整重複跳出
        del st.query_params["click_date"]
        # 觸發行程彈窗
        show_event_dialog(clicked_date_str)

    # 組合 HTML & CSS (使用 CSS Grid 強制 7 欄，絕不換行直排)
    html_code = """
    <style>
        .cal-wrapper {
            width: 100%;
            overflow-x: auto; /* 手機螢幕太窄時可左右滑動，絕不直排 */
        }
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
        .cal-empty {
            height: 65px;
        }
        .day-num {
            font-size: 14px;
            font-weight: bold;
            color: #2d3748;
        }
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
    <div class="cal-wrapper">
        <div class="cal-grid">
    """

    # 1. 渲染星期標頭
    for w in weekdays:
        html_code += f'<div class="cal-header">週{w}</div>'

    # 2. 渲染日期格子
    for week in cal:
        for day in week:
            if day == 0:
                html_code += '<div class="cal-empty"></div>'
            else:
                day_str = f"{sel_year}-{sel_month:02d}-{day:02d}"
                day_events = [e for e in active_events if e.get("date") == day_str]
                
                tag_html = ""
                if day_events:
                    title = day_events[0]['title']
                    short_title = title[:4] + ".." if len(title) > 4 else title
                    tag_html = f'<div class="tag-pink">📌{short_title}</div>'
                
                # 點擊格子會更新網址參數並重新整理頁面
                click_js = f"window.parent.location.href = window.parent.location.pathname + '?click_date={day_str}';"
                
                html_code += f'''
                <div class="cal-card" onclick="{click_js}">
                    <div class="day-num">{day}</div>
                    {tag_html}
                </div>
                '''

    html_code += "</div></div>"

    # 使用 components 渲染 HTML
    components.html(html_code, height=480, scrolling=False)
    # --- 7. 渲染日曆日期（可直接點擊）---
    for week in cal:
        cols = st.columns(7)
        for idx, day in enumerate(week):
            if day == 0:
                cols[idx].empty()
            else:
                day_str = f"{sel_year}-{sel_month:02d}-{day:02d}"
                day_events = [e for e in active_events if e.get("date") == day_str]
                
                # 組裝按鈕內部標籤（包含日期號碼與粉紅膠囊狀態）
                btn_label = f"{day}\n"
                if day_events:
                    title = day_events[0]['title']
                    short_title = title[:4] + ".." if len(title) > 4 else title
                    btn_label += f"📌{short_title}"

                # 點擊按鈕直接開啟彈窗
                if cols[idx].button(btn_label, key=f"btn_{day_str}", use_container_width=True):
                    show_event_dialog(day_str)
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
