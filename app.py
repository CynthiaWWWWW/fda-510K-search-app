import streamlit as st  # 匯入 Streamlit 工具箱，用來製作網頁介面
import requests  # 匯入 Requests 工具箱，用來向 FDA 伺服器請求資料

# 設定網頁的標題與瀏覽器標籤上的小圖示
st.set_page_config(page_title="FDA 510(k) 搜尋工具", page_icon="🔍")

# 在網頁畫面上印出大標題
st.title("🔍 FDA 510(k) 醫療器材搜尋器")
# 在標題下方印出一段輔助說明的文字
st.markdown("輸入 510(k) 號碼或關鍵字進行搜尋，系統將自動驗證 PDF 文件連結。")

# 建立網頁左側的側邊欄介面
with st.sidebar:
    st.header("搜尋參數")  # 在側邊欄顯示小標題
    # --- 新增：510(k) 號碼搜尋欄位 ---
    k_num_search = st.text_input("510(k) 號碼 (例如 K231234)", "").strip()
    st.write("--- 或使用關鍵字搜尋 ---") # 顯示分隔線
    # 原有的產品關鍵字輸入框
    keyword_1 = st.text_input("產品關鍵字 (例如 Las)", "Laser")
    # 原有的廠商關鍵字輸入框
    keyword_2 = st.text_input("廠商或細項關鍵字", "")
    # 建立一個拉桿，讓使用者選擇要抓取幾筆資料
    limit = st.slider("抓取資料筆數", 5, 50, 15)
    # 顯示提示訊息
    st.info("提示：若填寫了 510(k) 號碼，將優先精確搜尋該號碼。")

# 定義核心搜尋函式
def run_search(kn, k1, k2, lmt):
    # 判斷搜尋邏輯：如果填了 K 號，就用 k_number 搜尋；否則用產品名稱搜尋
    if kn:
        # 使用 k_number 進行精確比對
        search_query = f'k_number:"{kn}"'
    else:
        # 整理關鍵字清單，移除空白
        k_list = [k.strip() for k in [k1, k2] if k.strip()]
        if not k_list:
            st.error("請輸入 510(k) 號碼或至少一個關鍵字！")
            return
        # 組合關鍵字搜尋語法 (字首包含搜尋)
        search_query = "+AND+".join([f'device_name:{k}*' for k in k_list])
    
    # 組合完整的 OpenFDA API 網址
    api_url = f'https://api.fda.gov/device/510k.json?search={search_query}&limit={lmt}'
    
    # 設定瀏覽器標頭，避免被當成爬蟲阻擋
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # 顯示載入動畫
    with st.spinner('正在從 FDA 搜尋並驗證連結...'):
        try:
            # 向 API 發送請求
            response = requests.get(api_url, headers=headers)
            # 如果回傳狀態碼不是 200，代表找不到資料
            if response.status_code != 200:
                st.warning("找不到符合條件的結果，請檢查號碼或關鍵字是否正確。")
                return
            
            # 解析 JSON 結果
            raw_results = response.json().get('results', [])
            processed_data = []  # 用來存放處理後的結果

            # 遍歷搜尋結果並驗證 PDF 連結
            for r in raw_results:
                k_num = r.get('k_number')
                prefix = k_num[1:3]
                
                # 準備 PDF 檔案連結
                base_pdf_url = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{prefix}/{k_num}"
                # 準備 FDA 官方登記網頁連結
                db_url = f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID={k_num}"
                
                valid_pdf_url = None
                # 嘗試檢查 .pdf 與 .PDF 後綴名
                for ext in [".pdf", ".PDF"]:
                    try:
                        # 檢查網址是否有效
                        check = requests.head(base_pdf_url + ext, headers=headers, timeout=3, allow_redirects=True)
                        if check.status_code == 200:
                            valid_pdf_url = base_pdf_url + ext
                            break
                    except:
                        continue
                
                # 將處理後的資料加入清單
                processed_data.append({
                    'k_num': k_num,
                    'device_name': r.get('device_name', '未知產品'),
                    'applicant': r.get('applicant', '未知廠商'),
                    'pdf_url': valid_pdf_url,
                    'db_url': db_url,
                    'has_file': True if valid_pdf_url else False
                })

            # 依照有無 PDF 檔案進行排序
            sorted_res = sorted(processed_data, key=lambda x: x['has_file'], reverse=True)

            st.divider()  # 畫出分隔線
            st.success(f"搜尋完成！共找到 {len(sorted_res)} 筆資料。")

            # 顯示搜尋結果
            for i, item in enumerate(sorted_res, 1):
                if item['has_file']:
                    # 有 PDF 的綠色顯示樣式
                    st.markdown(f"""
                    <div style="border-left: 5px solid #28a745; padding: 10px; margin-bottom: 15px; background-color: #f0fdf4; border-radius: 5px;">
                        <span style="background-color: #007bff; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold;">#{i}</span>
                        <b style="color: #28a745;">✅ 已找到 Summary 文件</b><br>
                        <div style="margin-top:5px; margin-left: 10px;">
                            <b>產品：</b> {item['device_name']}<br>
                            <b>廠商：</b> {item['applicant']} ({item['k_num']})<br>
                            <a href="{item['pdf_url']}" target="_blank" style="color: #007bff; font-weight: bold; text-decoration: underline;">👉 開啟 PDF Summary</a> | 
                            <a href="{item['db_url']}" target="_blank" style="color: #666; font-size: 0.9em;">查看登記資料</a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # 無 PDF 的黃色顯示樣式
                    st.markdown(f"""
                    <div style="border-left: 5px solid #ffc107; padding: 10px; margin-bottom: 15px; background-color: #fffbef; border-radius: 5px;">
                        <span style="background-color: #6c757d; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold;">#{i}</span>
                        <b style="color: #856404;">⚠️ 無對應 Summary 文件</b><br>
                        <div style="margin-top:5px; margin-left: 10px;">
                            <b>產品：</b> {item['device_name']} ({item['k_num']})<br>
                            <b>廠商：</b> {item['applicant']}<br>
                            <span style="color: #d9534f; font-size: 0.9em;">ℹ️ 備註：此案件於 FDA 伺服器未偵測到 PDF 檔案。</span><br>
                            <a href="{item['db_url']}" target="_blank" style="color: #007bff; font-weight: bold; text-decoration: underline;">👉 前往 FDA 官網查看詳細登記頁面</a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        except Exception as e:
            # 擷取連線錯誤訊息
            st.error(f"連線發生錯誤: {e}")

# 設定側邊欄「執行搜尋」按鈕的點擊觸發邏輯
if st.sidebar.button("執行搜尋"):
    run_search(k_num_search, keyword_1, keyword_2, limit)
