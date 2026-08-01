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
if st.session_state.logged_in and st.session_state.user_email == ADMIN_EMAIL:
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

tab_cal, tab_pdf, tab_img, tab_summary, tab_ig = st.tabs([
    "📅 視覺化日曆與行程",
    "📄 PDF 救星",
    "✂️ AI 圖片處理與去背",
    "📝 文本總結與防雷助理",
    "📱 社群 IG/Threads 一鍵切圖"
])

# ------------------------------------------------------------------------------
# TAB 1: 📅 視覺化日曆網格與行程管理 (點擊日期直接跳出彈窗對話框)
# ------------------------------------------------------------------------------
with tab_cal:
    st.header("📅 視覺化月曆與行程表")
    
    if not st.session_state.logged_in:
        st.warning("⚠️ 目前為訪客預覽模式。登入後可新增與編輯您的專屬行程。")

    today = date.today()

    # 1. 定義跳出的對話框 (st.dialog)
    @st.dialog("📅 行程安排與管理", width="large")
    def show_event_dialog(selected_date_str):
        st.subheader(f"📌 {selected_date_str} 的行程")
        
        # 篩選當天行程
        day_events = [e for e in events if e.get("date") == selected_date_str]
        
        if not day_events:
            st.info("💡 當天目前沒有任何行程安排。")
        else:
            for idx, ev in enumerate(day_events):
                with st.expander(f"📌 {ev['title']} ({ev.get('category', '一般')})", expanded=True):
                    st.write(f"**備註**：{ev.get('description') if ev.get('description') else '無'}")
                    st.caption(f"建立者：{ev.get('creator', '未知')}")
                    
                    if st.session_state.logged_in and (st.session_state.user_email == ev.get('creator') or st.session_state.user_email == ADMIN_EMAIL):
                        if st.button("🗑️ 刪除此行程", key=f"dlg_del_{selected_date_str}_{idx}"):
                            events.remove(ev)
                            save_data(EVENTS_FILE, events)
                            st.success("行程已刪除！")
                            st.rerun()

        st.divider()
        
        # 彈窗內直接新增行程
        st.markdown("### ➕ 新增當天行程")
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
                            "creator": st.session_state.user_email
                        }
                        events.append(new_ev)
                        save_data(EVENTS_FILE, events)
                        st.success("行程新增成功！")
                        st.rerun()
        else:
            st.info("🔒 請於側邊欄登入帳號後進行行程新增。")


    # 2. 年月選擇器
    c_y, c_m, _ = st.columns([1, 1, 2])
    with c_y:
        sel_year = st.number_input("選擇年份", min_value=2020, max_value=2030, value=today.year)
    with c_m:
        sel_month = st.number_input("選擇月份", min_value=1, max_value=12, value=today.month)

    st.markdown("---")
    
    # 3. 按鈕排版 CSS 修正
    st.markdown("""
    <style>
    div[data-testid="column"] button {
        padding: 4px 0px !important;
        min-height: 52px !important;
        font-size: 13px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.subheader(f"🗓️ {sel_year} 年 {sel_month} 月 概覽（點擊日期跳出行程視窗）")
    
    cal = calendar.monthcalendar(sel_year, sel_month)
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    
    # 渲染星期標頭
    cols_head = st.columns(7)
    for idx, day_name in enumerate(weekdays):
        cols_head[idx].markdown(f"<div style='text-align:center; font-weight:bold; color:#555;'>週{day_name}</div>", unsafe_allow_html=True)
        
    # 渲染日曆格子 (點擊觸發 Dialog 彈窗)
    for week in cal:
        cols = st.columns(7)
        for idx, day in enumerate(week):
            if day == 0:
                cols[idx].write("")
            else:
                day_str = f"{sel_year}-{sel_month:02d}-{day:02d}"
                day_events = [e for e in events if e.get("date") == day_str]
                
                btn_label = f"{day}"
                if day_events:
                    btn_label += f"\n📌({len(day_events)})"
                    
                # 點擊按鈕直接開啟彈窗
                if cols[idx].button(btn_label, key=f"btn_cal_{day_str}", use_container_width=True):
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
