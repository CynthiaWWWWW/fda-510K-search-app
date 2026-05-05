import streamlit as st  # 匯入 Streamlit 工具箱，用來製作網頁介面
import requests  # 匯入 Requests 工具箱，用來向 FDA 伺服器請求資料

# 設定網頁的標題與瀏覽器標籤上的小圖示
st.set_page_config(page_title="FDA 510(k) 搜尋工具", page_icon="🔍")

# 在網頁畫面上印出大標題
st.title("🔍 FDA 510(k) 醫療器材搜尋器")
# 在標題下方印出一段輔助說明的文字
st.markdown("輸入關鍵字進行搜尋，系統會自動優先排序並標記可下載的 **PDF Summary**。")

# 建立網頁左側的側邊欄介面
with st.sidebar:
    st.header("搜尋參數")  # 在側邊欄顯示小標題
    # 建立第一個輸入框
    keyword_1 = st.text_input("產品關鍵字 (例如輸入 Las)", "Laser")
    # 建立第二個輸入框
    keyword_2 = st.text_input("廠商或細項關鍵字", "")
    # 建立一個拉桿，讓使用者選擇要抓取幾筆資料
    limit = st.slider("抓取資料筆數", 5, 50, 15)
    # 顯示提示：現在採用的是「字首包含」搜尋模式
    st.info("模式：字首包含搜尋 (例如輸入 aser 會搜不到 laser，但輸入 las 可搜到 laser)")

# 定義核心搜尋函式
def run_search(k1, k2, lmt):
    # 整理關鍵字清單，移除空白
    k_list = [k.strip() for k in [k1, k2] if k.strip()]
    if not k_list:
        st.error("請至少輸入一個關鍵字！")
        return

    # 【重點修改處】：只在關鍵字後面加上 *
    # 語法變成 device_name:Laser*，代表搜尋以 Laser 開頭的所有單字
    search_query = "+AND+".join([f'device_name:{k}*' for k in k_list])
    
    # 組合完整的 OpenFDA API 網址
    api_url = f'https://api.fda.gov/device/510k.json?search={search_query}&limit={lmt}'
    
    # 設定瀏覽器標頭，避免被當成爬蟲
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # 顯示載入動畫
    with st.spinner('正在從 FDA 搜尋並驗證 PDF 連結...'):
        try:
            response = requests.get(api_url, headers=headers)
            if response.status_code != 200:
                st.warning("找不到符合條件的結果。請確認關鍵字是否為單字開頭。")
                return
            
            raw_results = response.json().get('results', [])
            processed_data = []

            # 遍歷搜尋結果並驗證連結
            for r in raw_results:
                k_num = r.get('k_number')
                prefix = k_num[1:3]
                base_url = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{prefix}/{k_num}"
                
                valid_url = None
                # 檢查副檔名
                for ext in [".pdf", ".PDF"]:
                    try:
                        check = requests.head(base_url + ext, headers=headers, timeout=3, allow_redirects=True)
                        if check.status_code == 200:
                            valid_url = base_url + ext
                            break
                    except:
                        continue
                
                # 存入處理後的清單
                processed_data.append({
                    'k_num': k_num,
                    'device_name': r.get('device_name', '未知產品'),
                    'applicant': r.get('applicant', '未知廠商'),
                    'url': valid_url,
                    'has_file': True if valid_url else False
                })

            # 依照有無檔案排序
            sorted_res = sorted(processed_data, key=lambda x: x['has_file'], reverse=True)

            st.divider()
            st.success(f"搜尋完成！共找到 {len(sorted_res)} 筆資料。")

            # 顯示結果
            for i, item in enumerate(sorted_res, 1):
                if item['has_file']:
                    st.markdown(f"""
                    <div style="border-left: 5px solid #28a745; padding: 10px; margin-bottom: 10px; background-color: #f0fdf4; border-radius: 5px;">
                        <span style="background-color: #007bff; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold;">#{i}</span>
                        <b style="color: #28a745;">✅ [有效連結]</b><br>
                        <div style="margin-top:5px;">
                            <b>產品：</b> {item['device_name']}<br>
                            <b>廠商：</b> {item['applicant']} ({item['k_num']})<br>
                            <a href="{item['url']}" target="_blank" style="color: #007bff; font-weight: bold; text-decoration: underline;">👉 點擊開啟 PDF Summary</a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="border-left: 5px solid #ccc; padding: 10px; margin-bottom: 10px; background-color: #f9f9f9; opacity: 0.8; border-radius: 5px;">
                        <span style="background-color: #6c757d; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold;">#{i}</span>
                        <b style="color: #666;">⚪ [目前無文件]</b><br>
                        <div style="margin-top:5px;">
                            <b>產品：</b> {item['device_name']} ({item['k_num']})<br>
                            <b>廠商：</b> {item['applicant']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"連線發生錯誤: {e}")

# 按鈕啟動搜尋
if st.sidebar.button("執行搜尋"):
    run_search(keyword_1, keyword_2, limit)
