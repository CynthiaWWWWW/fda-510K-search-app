import streamlit as st  # 匯入 Streamlit 網頁框架套件
import requests  # 匯入 Requests 用於處理網路請求

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="FDA 510(k) 查詢", page_icon="🩺")  # 設定網頁標籤標題與圖示

# --- 2. CSS 樣式與標題 ---
st.title("🩺 FDA 510(k) 醫療器材查詢器")  # 顯示網頁大標題
st.markdown("透過 OpenFDA API 快速檢索 510(k) 申報資料並驗證 PDF 文件。")  # 顯示副標題說明

# --- 3. 側邊欄參數設定 ---
with st.sidebar:  # 建立側邊選單
    st.header("搜尋參數設定")  # 側邊欄小標題
    k_num_search = st.text_input("510(k) 號碼 (精確搜尋)", "").strip().upper()  # 號碼輸入框，自動轉大寫並去空格
    st.divider()  # 顯示分隔線
    keyword_1 = st.text_input("產品關鍵字", "Laser")  # 主要關鍵字輸入框
    keyword_2 = st.text_input("廠商名稱或細項", "")  # 次要關鍵字輸入框
    limit = st.slider("顯示結果筆數", 5, 50, 10)  # 滑桿選擇抓取數量
    search_btn = st.button("啟動查詢", use_container_width=True)  # 寬版搜尋按鈕

# --- 4. 核心功能函式 ---
def fetch_fda_data(kn, k1, k2, lmt):  # 定義抓取 FDA 資料的函式
    # 組合搜尋語法：若有 K 號碼則優先精確搜尋，否則使用關鍵字模糊搜尋
    query = f'k_number:"{kn}"' if kn else "+AND+".join([f'device_name:{k}*' for k in [k1, k2] if k])
    if not query: return st.error("請提供至少一個搜尋條件")  # 若無條件則報錯並中斷
    
    api_url = f'https://api.fda.gov/device/510k.json?search={query}&limit={lmt}'  # 組合 OpenFDA API 網址
    session = requests.Session()  # 建立 Session 以優化多次連線效能
    headers = {'User-Agent': 'Mozilla/5.0'}  # 設定簡單的瀏覽器標頭避免被阻擋

    with st.spinner('正在從 FDA 取得最新資料並驗證連結...'):  # 顯示讀取中動畫
        try:
            resp = session.get(api_url, headers=headers)  # 發送 API 請求
            if resp.status_code != 200: return st.warning("找不到相符的結果。")  # 若 API 回報非 200 則提示找不到
            
            results = resp.json().get('results', [])  # 從 JSON 結果中提取資料列表
            processed = []  # 準備存放處理後資料的清單

            for r in results:  # 遍歷每一筆 API 回傳資料
                k = r.get('k_number')  # 取得 510(k) 號碼
                # FDA PDF 路徑規則：K 號碼前兩位數代表年份資料夾 (例如 K231234 -> pdf23)
                pdf_base = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{k[1:3]}/{k}.pdf"
                
                # 驗證連結是否存在 (使用 HEAD 請求節省流量)
                has_file = session.head(pdf_base, timeout=3).status_code == 200
                
                processed.append({  # 將整理好的資訊加入清單
                    "id": k,
                    "name": r.get('device_name', '未知'),
                    "firm": r.get('applicant', '未知'),
                    "url": pdf_base if has_file else None,
                    "web": f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID={k}",
                    "ok": has_file
                })

            # 顯示結果列表
            st.success(f"找到 {len(processed)} 筆資料 (優先顯示有 PDF 之案件)")  # 顯示成功提示
            for i, item in enumerate(processed, 1):  # 遍歷並呈現卡片介面
                color = "#28a745" if item['ok'] else "#ffc107"  # 根據是否有檔案決定邊框顏色
                st.markdown(f"""
                <div style="border-left: 6px solid {color}; padding: 16px; background: #f8f9fa; border-radius: 8px; margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between;">
                        <b style="font-size: 1.2em; color: #111;">#{i} 510(k): {item['id']}</b>
                        <span style="color: {color}; font-weight: bold;">{"✅ PDF Ready" if item['ok'] else "⚠️ No Summary"}</span>
                    </div>
                    <p style="margin: 8px 0;"><b>設備：</b>{item['name']}<br><b>廠商：</b>{item['firm']}</p>
                    <div style="margin-top: 10px;">
                        <a href="{item['web']}" target="_blank" style="margin-right: 15px; color: #007bff; text-decoration: none; font-weight: 600;">🌐 官網資訊</a>
                        {f'<a href="{item["url"]}" target="_blank" style="color: #d9534f; text-decoration: none; font-weight: 600;">📄 下載 PDF</a>' if item['ok'] else ""}
                    </div>
                </div>
                """, unsafe_allow_html=True)  # 使用 HTML 渲染卡片

        except Exception as e:  # 捕捉意外錯誤
            st.error(f"連線異常：{str(e)}")  # 顯示錯誤訊息

# --- 5. 啟動邏輯 ---
if search_btn:  # 當點擊搜尋按鈕時
    fetch_fda_data(k_num_search, keyword_1, keyword_2, limit)  # 執行資料抓取函式
