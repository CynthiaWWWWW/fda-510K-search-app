import streamlit as st  # 匯入 Streamlit 工具箱，用來製作網頁介面
import requests  # 匯入 Requests 工具箱，用來向 FDA 伺服器請求資料

# 設定網頁的標題與瀏覽器標籤上的小圖示
st.set_page_config(page_title="FDA 510(k) 搜尋工具", page_icon="🔍")

# 在網頁畫面上印出大標題
st.title("🔍 FDA 510(k) 醫療器材搜尋器")
# 在標題下方印出一段輔助說明的文字
st.markdown("輸入 510(k) 號碼或關鍵字進行搜尋，系統將自動優先排序並驗證 PDF 文件。")

# 建立網頁左側的側邊欄介面
with st.sidebar:
    st.header("搜尋參數")  # 在側邊欄顯示小標題
    # 510(k) 號碼搜尋欄位
    k_num_search = st.text_input("510(k) 號碼 (例如 K231234)", "").strip()
    st.write("--- 或使用關鍵字搜尋 ---") # 顯示分隔線
    # 產品關鍵字輸入框
    keyword_1 = st.text_input("產品關鍵字 (例如 Las)", "Laser")
    # 廠商關鍵字輸入框
    keyword_2 = st.text_input("廠商或細項關鍵字", "")
    # 建立一個拉桿，讓使用者選擇要抓取幾筆資料
    limit = st.slider("抓取資料筆數", 5, 50, 15)
    # 顯示提示訊息
    st.info("提示：若填寫了 510(k) 號碼，將優先精確搜尋該號碼。")

# 定義核心搜尋函式
def run_search(kn, k1, k2, lmt):
    # 判斷搜尋邏輯：如果填了 K 號，就用 k_number 搜尋；否則用產品名稱搜尋
    if kn:
        search_query = f'k_number:"{kn}"'
    else:
        k_list = [k.strip() for k in [k1, k2] if k.strip()]
        if not k_list:
            st.error("請輸入 510(k) 號碼或至少一個關鍵字！")
            return
        # 組合字首包含搜尋語法
        search_query = "+AND+".join([f'device_name:{k}*' for k in k_list])
    
    # 組合 OpenFDA API 網址
    api_url = f'https://api.fda.gov/device/510k.json?search={search_query}&limit={lmt}'
    
    # 設定瀏覽器標頭，避免被當成爬蟲
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # 顯示載入動畫
    with st.spinner('正在從 FDA 搜尋並驗證連結...'):
        try:
            response = requests.get(api_url, headers=headers)
            if response.status_code != 200:
                st.warning("找不到符合條件的結果。")
                return
            
            raw_results = response.json().get('results', [])
            processed_data = []

            for r in raw_results:
                k_num = r.get('k_number')
                prefix = k_num[1:3]
                
                # 準備網址連結
                base_pdf_url = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{prefix}/{k_num}"
                db_url = f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID={k_num}"
                
                valid_pdf_url = None
                for ext in [".pdf", ".PDF"]:
                    try:
                        check = requests.head(base_pdf_url + ext, headers=headers, timeout=3, allow_redirects=True)
                        if check.status_code == 200:
                            valid_pdf_url = base_pdf_url + ext
                            break
                    except:
                        continue
                
                processed_data.append({
                    'k_num': k_num,
                    'device_name': r.get('device_name', '未知產品'),
                    'applicant': r.get('applicant', '未知廠商'),
                    'pdf_url': valid_pdf_url,
                    'db_url': db_url,
                    'has_file': True if valid_pdf_url else False
                })

            # 依照有無 PDF 檔案排序
            sorted_res = sorted(processed_data, key=lambda x: x['has_file'], reverse=True)

            st.divider()
            st.success(f"搜尋完成！共找到 {len(sorted_res)} 筆資料。")

            # 顯示結果
            for i, item in enumerate(sorted_res, 1):
                # 判斷顏色區塊樣式
                bg_color = "#f0fdf4" if item['has_file'] else "#fffbef"
                border_color = "#28a745" if item['has_file'] else "#ffc107"
                status_icon = "✅ 已找到 Summary 文件" if item['has_file'] else "⚠️ 無對應 Summary 文件"
                
                # --- HTML 顯示區塊 (將 K 號碼放在第一行並放大) ---
                st.markdown(f"""
                <div style="border-left: 5px solid {border_color}; padding: 12px; margin-bottom: 15px; background-color: {bg_color}; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                    <div style="display: flex; align-items: center; margin-bottom: 8px;">
                        <span style="background-color: #007bff; color: white; padding: 2px 10px; border-radius: 4px; font-weight: bold; margin-right: 12px;">#{i}</span>
                        <span style="font-size: 1.3em; font-weight: 800; color: #333;">{item['k_num']}</span>
                        <span style="margin-left: auto; font-size: 0.9em; font-weight: bold; color: {border_color};">{status_icon}</span>
                    </div>
                    <div style="margin-left: 45px; line-height: 1.6;">
                        <b>產品名稱：</b> {item['device_name']}<br>
                        <b>申請廠商：</b> {item['applicant']}<br>
                        <div style="margin-top: 10px;">
                            {"<a href='" + item['pdf_url'] + "' target='_blank' style='color: #007bff; font-weight: bold; text-decoration: underline;'>👉 開啟 PDF Summary</a> | " if item['has_file'] else "<span style='color: #d9534f; font-size: 0.9em;'>ℹ️ 備註：此案件於 FDA 伺服器未偵測到 PDF 檔案。</span><br>"}
                            <a href="{item['db_url']}" target="_blank" style="color: #007bff; font-weight: bold; text-decoration: underline;">👉 前往 FDA 官網登記頁面</a>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"連線發生錯誤: {e}")

# 按鈕啟動
if st.sidebar.button("執行搜尋"):
    run_search(k_num_search, keyword_1, keyword_2, limit)
