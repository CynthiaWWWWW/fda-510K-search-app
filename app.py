import streamlit as st  # 匯入 Streamlit 工具箱
import requests  # 匯入 Requests 工具箱

# 設定網頁標題
st.set_page_config(page_title="FDA 510(k) 搜尋工具", page_icon="🔍")

st.title("🔍 FDA 510(k) 醫療器材搜尋器")
st.markdown("輸入關鍵字進行搜尋，若無 PDF 文件將引導至 FDA 官網登記頁面。")

# 側邊欄設定
with st.sidebar:
    st.header("搜尋參數")
    keyword_1 = st.text_input("產品關鍵字 (例如輸入 Las)", "Laser")
    keyword_2 = st.text_input("廠商或細項關鍵字", "")
    limit = st.slider("抓取資料筆數", 5, 50, 15)
    st.info("模式：字首包含搜尋 (Prefix Search)")

# 核心搜尋函式
def run_search(k1, k2, lmt):
    k_list = [k.strip() for k in [k1, k2] if k.strip()]
    if not k_list:
        st.error("請輸入至少一個關鍵字！")
        return

    # 搜尋語法：關鍵字後方加上 *
    search_query = "+AND+".join([f'device_name:{k}*' for k in k_list])
    api_url = f'https://api.fda.gov/device/510k.json?search={search_query}&limit={lmt}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    with st.spinner('正在從 FDA 搜尋並驗證 PDF 連結...'):
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
                
                # 1. 準備 PDF 檔案連結
                base_pdf_url = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{prefix}/{k_num}"
                # 2. 準備 FDA 官方登記網頁連結 (Database Page)
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

            for i, item in enumerate(sorted_res, 1):
                if item['has_file']:
                    # --- 有 PDF 的顯示樣式 ---
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
                    # --- 沒有 PDF 的顯示樣式 (連結到登記網頁) ---
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
            st.error(f"連線發生錯誤: {e}")

# 執行按鈕
if st.sidebar.button("執行搜尋"):
    run_search(keyword_1, keyword_2, limit)
