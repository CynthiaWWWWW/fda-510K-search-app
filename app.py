import streamlit as st
import requests

# --- 網頁標題與基本設定 ---
st.set_page_config(page_title="FDA 510(k) 搜尋工具", page_icon="🔍")

st.title("🔍 FDA 510(k) 醫療器材搜尋器")
st.markdown("輸入關鍵字進行搜尋，系統會自動優先排序並標記可下載的 **PDF Summary**。")

# --- 側邊欄設定 ---
with st.sidebar:
    st.header("搜尋參數")
    keyword_1 = st.text_input("產品關鍵字", "Laser")
    keyword_2 = st.text_input("廠商或細項關鍵字", "")
    limit = st.slider("抓取資料筆數", 5, 50, 15)
    st.info("註：搜尋需要驗證 PDF 連結，筆數越多等待時間越長。")

# --- 核心搜尋函式 ---
def run_search(k1, k2, lmt):
    # 整理關鍵字
    k_list = [k.strip() for k in [k1, k2] if k.strip()]
    if not k_list:
        st.error("請至少輸入一個關鍵字！")
        return

    # 組合 API URL
    search_query = "+AND+".join([f'device_name:"{k}"' for k in k_list])
    api_url = f'https://api.fda.gov/device/510k.json?search={search_query}&limit={lmt}'
    
    # 偽裝瀏覽器 Header
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    with st.spinner('正在從 FDA 擷取數據並驗證 PDF 連結有效性...'):
        try:
            response = requests.get(api_url, headers=headers)
            if response.status_code != 200:
                st.warning("找不到符合條件的結果，請嘗試其他關鍵字。")
                return
            
            raw_results = response.json().get('results', [])
            processed_data = []

            # 驗證每一筆資料的連結
            for r in raw_results:
                k_num = r.get('k_number')
                prefix = k_num[1:3]
                base_url = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{prefix}/{k_num}"
                
                valid_url = None
                # 同時檢查 .pdf 與 .PDF
                for ext in [".pdf", ".PDF"]:
                    try:
                        check = requests.head(base_url + ext, headers=headers, timeout=3, allow_redirects=True)
                        if check.status_code == 200:
                            valid_url = base_url + ext
                            break
                    except:
                        continue
                
                processed_data.append({
                    'k_num': k_num,
                    'device_name': r.get('device_name', '未知產品'),
                    'applicant': r.get('applicant', '未知廠商'),
                    'url': valid_url,
                    'has_file': True if valid_url else False
                })

            # 依據有無檔案排序 (True 在前)
            sorted_res = sorted(processed_data, key=lambda x: x['has_file'], reverse=True)

            # 顯示結果
            st.divider()
            st.success(f"搜尋完成！共找到 {len(sorted_res)} 筆資料。")

            for i, item in enumerate(sorted_res, 1):
                if item['has_file']:
                    # 有效連結的樣式
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
                    # 無連結的樣式
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

# --- 點擊按鈕執行 ---
if st.sidebar.button("執行搜尋"):
    run_search(keyword_1, keyword_2, limit)
