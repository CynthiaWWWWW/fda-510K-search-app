import streamlit as st  # 匯入 Streamlit 工具箱
import requests  # 匯入 Requests 工具箱

# 設定網頁標題與圖示
st.set_page_config(page_title="FDA 510(k) 搜尋工具", page_icon="🔍")

# 網頁大標題
st.title("🔍 FDA 510(k) 醫療器材搜尋器")
st.markdown("輸入 510(k) 號碼或關鍵字進行搜尋，系統將自動優先排序並驗證 PDF 文件。")

# 側邊欄搜尋參數設定
with st.sidebar:
    st.header("搜尋參數")
    # 510(k) 號碼搜尋
    k_num_search = st.text_input("510(k) 號碼 (例如 K231234)", "").strip()
    st.write("--- 或使用關鍵字搜尋 ---")
    # 關鍵字搜尋
    keyword_1 = st.text_input("產品關鍵字 (例如 Las)", "Laser")
    keyword_2 = st.text_input("廠商或細項關鍵字", "")
    # 數量選擇
    limit = st.slider("抓取資料筆數", 5, 50, 15)
    st.info("提示：若填寫了 510(k) 號碼，將優先進行精確搜尋。")

# 核心搜尋功能
def run_search(kn, k1, k2, lmt):
    # 決定搜尋模式
    if kn:
        search_query = f'k_number:"{kn}"'
    else:
        k_list = [k.strip() for k in [k1, k2] if k.strip()]
        if not k_list:
            st.error("請輸入 510(k) 號碼或至少一個關鍵字！")
            return
        # 使用字首包含搜尋語法
        search_query = "+AND+".join([f'device_name:{k}*' for k in k_list])
    
    # 組合 OpenFDA API 網址
    api_url = f'https://api.fda.gov/device/510k.json?search={search_query}&limit={lmt}'
    
    # 瀏覽器標頭偽裝
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    with st.spinner('正在從 FDA 搜尋並驗證連結...'):
        try:
            response = requests.get(api_url, headers=headers)
            if response.status_code != 200:
                st.warning("找不到符合條件的結果。")
                return
            
            raw_results = response.json().get('results', [])
            processed_data = []

            # 遍歷並驗證連結
            for r in raw_results:
                k_num = r.get('k_number')
                prefix = k_num[1:3]
                
                # 檔案連結與官網連結
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

            # 依檔案存在與否排序
            sorted_res = sorted(processed_data, key=lambda x: x['has_file'], reverse=True)

            st.divider()
            st.success(f"搜尋完成！共找到 {len(sorted_res)} 筆資料。")

            # 顯示結果卡片
            for i, item in enumerate(sorted_res, 1):
                bg_color = "#f0fdf4" if item['has_file'] else "#fffbef"
                border_color = "#28a745" if item['has_file'] else "#ffc107"
                status_text = "✅ 連結已就緒" if item['has_file'] else "⚠️ 無 Summary 文件"
                
                # --- HTML 介面更新：加上 510(k) Number 標題並加大 ---
                st.markdown(f"""
                <div style="border-left: 5px solid {border_color}; padding: 15px; margin-bottom: 20px; background-color: {bg_color}; border-radius: 8px; box-shadow: 2px 2px 8px rgba(0,0,0,0.05);">
                    <div style="display: flex; align-items: baseline; margin-bottom: 10px;">
                        <span style="background-color: #007bff; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; margin-right: 12px; font-size: 0.9em;">#{i}</span>
                        <span style="font-size: 1.25em; font-weight: 800; color: #1a1a1a;">
                            <span style="color: #555; font-weight: 600;">510(k) Number:</span> {item['k_num']}
                        </span>
                        <span style="margin-left: auto; font-size: 0.85em; font-weight: bold; color: {border_color}; background: white; padding: 2px 8px; border-radius: 20px; border: 1px solid {border_color};">
                            {status_text}
                        </span>
                    </div>
                    <div style="margin-left: 42px; line-height: 1.7; border-top: 1px solid rgba(0,0,0,0.05); padding-top: 8px;">
                        <div style="margin-bottom: 4px;"><b>產品名稱：</b> <span style="color: #333;">{item['device_name']}</span></div>
                        <div style="margin-bottom: 10px;"><b>申請廠商：</b> <span style="color: #333;">{item['applicant']}</span></div>
                        <div style="margin-top: 12px;">
                            {"<a href='" + item['pdf_url'] + "' target='_blank' style='color: #007bff; font-weight: bold; text-decoration: underline; margin-right: 15px;'>👉 開啟 PDF Summary</a>" if item['has_file'] else "<span style='color: #d9534f; font-size: 0.9em; display: block; margin-bottom: 8px;'>ℹ️ 備註：此案件於 FDA 伺服器未偵測到 PDF 檔案。</span>"}
                            <a href="{item['db_url']}" target="_blank" style="color: #007bff; font-weight: bold; text-decoration: underline;">👉 前往 FDA 官網登記頁面</a>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"連線發生錯誤: {e}")

# 按鈕啟動搜尋
if st.sidebar.button("執行搜尋"):
    run_search(k_num_search, keyword_1, keyword_2, limit)
