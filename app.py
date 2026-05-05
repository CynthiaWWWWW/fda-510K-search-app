import streamlit as st  # 匯入 Streamlit 網頁框架套件
import requests  # 匯入 Requests 套件用於發送網路請求

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="FDA 510(k) 查詢", page_icon="🩺", layout="wide")  # 設定網頁標題、圖示與寬版佈局

# --- 2. CSS 樣式與標題 ---
st.markdown("""
    <style>
    .main-title { font-size: 28px; font-weight: 800; color: #1E1E1E; text-align: center; margin-bottom: 10px; } /* 設定主標題樣式 */
    .info-text { font-size: 16px; color: #666; text-align: center; margin-bottom: 20px; } /* 設定說明文字樣式 */
    .card { border-left: 6px solid #ccc; padding: 16px; background: #f8f9fa; border-radius: 10px; margin-bottom: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); } /* 設定結果卡片樣式 */
    </style>
    <div class="main-title">🩺 FDA 510(k) 查詢器</div>
    <div class="info-text">透過 OpenFDA API 檢索申報資料並自動驗證 PDF 文件</div>
    """, unsafe_allow_html=True)  # 注入自訂 CSS 並顯示標題

# --- 3. 側邊欄搜尋參數 ---
with st.sidebar:  # 建立側邊控制欄
    st.header("搜尋參數設定")  # 側邊欄標題
    k_num = st.text_input("510(k) 號碼 (例如 K231234)", "").strip().upper()  # 號碼輸入框，自動轉大寫並去除空白
    st.divider()  # 顯示分隔線
    kw1 = st.text_input("產品關鍵字", "Laser")  # 主要關鍵字輸入框 (變數名稱為 kw1)
    kw2 = st.text_input("廠商或細項關鍵字", "")  # 次要關鍵字輸入框 (變數名稱為 kw2)
    limit = st.slider("抓取資料筆數", 5, 50, 10)  # 滑桿設定顯示筆數
    submit = st.button("啟動查詢", use_container_width=True, type="primary")  # 搜尋按鈕，設定為主要樣式

# --- 4. 核心搜尋函式 ---
def run_query(kn, k1, k2, lmt):  # 定義查詢與顯示函式
    # 建立 API 查詢字串：優先使用 K 號碼，否則組合關鍵字
    q = f'k_number:"{kn}"' if kn else "+AND+".join([f'device_name:{k}*' for k in [k1, k2] if k])
    if not q: return st.error("請輸入號碼或關鍵字")  # 若無任何輸入則顯示錯誤

    url = f'https://api.fda.gov/device/510k.json?search={q}&limit={lmt}'  # 組合 OpenFDA API 網址
    session = requests.Session()  # 使用 Session 複用連線以提升效能
    session.headers.update({'User-Agent': 'Mozilla/5.0'})  # 設定標準瀏覽器標頭避免被 API 拒絕

    with st.spinner('正在從 FDA 搜尋並驗證 PDF 連結...'):  # 顯示查詢中的進度動畫
        try:
            resp = session.get(url)  # 發送 GET 請求取得資料
            if resp.status_code != 200: return st.warning("找不到相符的結果")  # 若 API 沒找到資料則提示
            
            data = resp.json().get('results', [])  # 從回傳結果中提取產品列表
            st.success(f"找到 {len(data)} 筆資料")  # 顯示成功訊息與筆數

            for i, r in enumerate(data, 1):  # 遍歷每一筆查詢結果
                k = r.get('k_number')  # 取得 510(k) 號碼
                # 根據 FDA 規則推導 PDF 位址
                pdf = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{k[1:3]}/{k}.pdf"
                
                # 驗證連結有效性 (使用 HEAD 請求)
                is_ok = session.head(pdf, timeout=3).status_code == 200
                color = "#28a745" if is_ok else "#ffc107"  # 依是否有檔案決定邊框顏色
                status = "✅ PDF 已就緒" if is_ok else "⚠️ 無 Summary 文件"  # 狀態文字

                html_card = f"""
                <div class="card" style="border-left-color: {color};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <span style="font-size: 1.2em; font-weight: 800; color: #111;">#{i} 510(k): {k}</span>
                        <span style="color: {color}; font-weight: bold; background: white; padding: 2px 10px; border-radius: 20px; border: 1px solid {color}; font-size: 0.85em;">{status}</span>
                    </div>
                    <div style="margin-bottom: 8px;"><b>產品設備：</b>{r.get('device_name', '未知')}</div>
                    <div style="margin-bottom: 12px;"><b>申請廠商：</b>{r.get('applicant', '未知')}</div>
                    <div style="display: flex; gap: 15px;">
                        <a href="https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID={k}" target="_blank" style="color: #007bff; text-decoration: none; font-weight: 600;">🌐 官網資訊</a>
                        {'<a href="' + pdf + '" target="_blank" style="color: #d9534f; text-decoration: none; font-weight: 600;">📄 下載 PDF</a>' if is_ok else ""}
                    </div>
                </div>
                """
                st.markdown(html_card, unsafe_allow_html=True)  # 渲染結果卡片

        except Exception as e:  # 捕捉意外的網路或解析錯誤
            st.error(f"連線發生錯誤：{e}")  # 顯示詳細錯誤訊息

# --- 5. 執行搜尋按鈕觸發 ---
if submit:  # 當使用者點擊「啟動查詢」按鈕時
    # 修正處：將原本錯誤的 keyword_1, keyword_2 修改為上方定義的 kw1, kw2
    run_query(k_num, kw1, kw2, limit)
