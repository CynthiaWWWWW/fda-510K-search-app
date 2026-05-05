import requests
from IPython.display import display, HTML

# ================= 1. 設定搜尋參數 =================
keyword_1 = "irrigator"
keyword_2 = ""
limit = 15  # 抓取數量
# =================================================

def run_fda_search_numbered():
    k_list = [k.strip() for k in [keyword_1, keyword_2] if k.strip()]
    if not k_list:
        display(HTML("<b style='color:red;'>❌ 請輸入關鍵字。</b>"))
        return

    search_query = "+AND+".join([f'device_name:"{k}"' for k in k_list])
    api_url = f'https://api.fda.gov/device/510k.json?search={search_query}&limit={limit}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    display(HTML(f"<h3>🔍 搜尋關鍵字: <span style='color:blue;'>{search_query}</span></h3>"))
    display(HTML("<p>正在驗證連結並排序，請稍候...</p>"))
    
    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code != 200:
            display(HTML("<p>❌ 找不到資料。</p>"))
            return
            
        raw_results = response.json().get('results', [])
        processed_results = []

        # --- 步驟 1: 預先檢查所有連結 ---
        for r in raw_results:
            k_num = r.get('k_number')
            prefix = k_num[1:3]
            base_url = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{prefix}/{k_num}"
            
            valid_url = None
            for ext in [".pdf", ".PDF"]:
                try:
                    check = requests.head(base_url + ext, headers=headers, timeout=5, allow_redirects=True)
                    if check.status_code == 200:
                        valid_url = base_url + ext
                        break
                except:
                    continue
            
            processed_results.append({
                'k_num': k_num,
                'device_name': r.get('device_name', '未知產品'),
                'applicant': r.get('applicant', '未知廠商'),
                'url': valid_url,
                'has_file': True if valid_url else False
            })

        # --- 步驟 2: 排序 (有檔案的優先) ---
        sorted_results = sorted(processed_results, key=lambda x: x['has_file'], reverse=True)

        # --- 步驟 3: 顯示結果 (加上序號) ---
        display(HTML(f"<p>✅ 檢查完成！共 {len(sorted_results)} 筆結果：</p><hr>"))

        for i, item in enumerate(sorted_results, 1):  # 從 1 開始編號
            if item['has_file']:
                html_output = f"""
                <div style="margin-bottom: 15px; border-left: 5px solid #28a745; padding-left: 15px; background-color: #f9fff9; padding-top: 10px; padding-bottom: 10px;">
                    <span style="background-color: #007bff; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; margin-right: 10px;">#{i}</span>
                    <b style="color: #28a745;">✅ [有效連結]</b><br>
                    <div style="margin-top: 5px; margin-left: 45px;">
                        <b>產品:</b> {item['device_name']}<br>
                        <b>廠商:</b> {item['applicant']} ({item['k_num']})<br>
                        <a href="{item['url']}" target="_blank" style="color: #007bff; text-decoration: underline; font-weight: bold;">
                            👉 點擊開啟 PDF Summary
                        </a>
                    </div>
                </div>
                """
            else:
                html_output = f"""
                <div style="margin-bottom: 15px; border-left: 5px solid #ccc; padding-left: 15px; opacity: 0.7; padding-top: 10px; padding-bottom: 10px;">
                    <span style="background-color: #6c757d; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; margin-right: 10px;">#{i}</span>
                    <b style="color: #666;">⚪ [目前無文件]</b><br>
                    <div style="margin-top: 5px; margin-left: 45px;">
                        <b>產品:</b> {item['device_name']} ({item['k_num']})<br>
                        <b>廠商:</b> {item['applicant']}
                    </div>
                </div>
                """
            display(HTML(html_output))

    except Exception as e:
        display(HTML(f"<p style='color:red;'>⚠️ 發生錯誤: {e}</p>"))

run_fda_search_numbered()
