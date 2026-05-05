import streamlit as st
import requests

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="FDA 510(k) 查詢器", page_icon="🩺", layout="wide")

# --- 2. CSS 樣式 ---
st.markdown("""
    <style>
    .main-title { font-size: 28px; font-weight: 800; color: #1E1E1E; text-align: center; margin-bottom: 10px; }
    .info-text { font-size: 16px; color: #666; text-align: center; margin-bottom: 20px; }
    .card { border-left: 6px solid #ccc; padding: 16px; background: #f8f9fa; border-radius: 10px; margin-bottom: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .index-badge { background: #4a4a4a; color: #ffffff; padding: 4px 10px; border-radius: 6px; font-size: 0.9em; font-weight: bold; margin-right: 12px; letter-spacing: 1px;}
    .code-label { background: #e9ecef; color: #495057; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-weight: bold; margin-right: 8px;}
    </style>
    <div class="main-title">🩺 FDA 510(k) 查詢工具</div>
    <div class="info-text">連線 OpenFDA 資料庫檢索並驗證 PDF 文件狀態</div>
    """, unsafe_allow_html=True)

# --- 3. 核心輔助函式 ---

@st.cache_data(ttl=3600)
def get_product_definition(p_code):
    """透過 Product Code 查詢 FDA 分類 API 取得官方英文名稱"""
    if not p_code or p_code == '未知':
        return "Definition not found"
    
    try:
        class_url = f'https://api.fda.gov/device/classification.json?search=product_code:"{p_code}"'
        resp = requests.get(class_url, timeout=5).json()
        if 'results' in resp:
            return resp['results'][0].get('device_name', 'Definition not found')
    except:
        pass
    return "Unknown"

# --- 4. 主查詢函式 ---
def run_query(kn, k1, k2, app, lmt):
    # 建立搜尋語法
    if kn:
        # 如果有輸入 510(k) 號碼，以此為最高優先權
        q = f'k_number:"{kn}"'
    else:
        # 組合關鍵字與廠商名稱
        query_parts = []
        if k1: query_parts.append(f'device_name:{k1}*')
        if k2: query_parts.append(f'device_name:{k2}*')
        if app: query_parts.append(f'applicant:"{app}"') # 廠商名稱通常包含空格，使用雙引號精確比對
        
        q = "+AND+".join(query_parts)

    if not q: 
        return st.error("請輸入 510(k) 號碼、產品關鍵字或廠商名稱")

    url = f'https://api.fda.gov/device/510k.json?search={q}&limit={lmt}'
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    with st.spinner('正在從 FDA 搜尋並驗證 PDF 連結...'):
        try:
            resp = session.get(url)
            if resp.status_code != 200: 
                return st.warning("找不到相符的查詢結果，請嘗試減少關鍵字或檢查廠商名稱拼字。")
            
            raw_data = resp.json().get('results', [])
            processed_results = []

            for r in raw_data:
                k = r.get('k_number')
                # 建立 PDF 預期連結
                pdf = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{k[1:3]}/{k}.pdf"
                
                # 驗證 PDF 連結有效性
                try:
                    is_ok = session.head(pdf, timeout=2).status_code == 200
                except:
                    is_ok = False
                
                p_code = r.get('product_code', '')
                eng_def = get_product_definition(p_code)
                
                raw_date = r.get('decision_date', '')
                formatted_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else raw_date

                r['is_ok'] = is_ok
                r['pdf_url'] = pdf
                r['product_desc'] = eng_def
                r['formatted_date'] = formatted_date
                processed_results.append(r)

            # 排序：有 PDF 的結果置頂
            processed_results.sort(key=lambda x: x['is_ok'], reverse=True)

            st.success(f"搜尋完成：共 {len(processed_results)} 筆資料")

            for i, r in enumerate(processed_results, 1):
                k = r.get('k_number')
                pdf = r['pdf_url']
                is_ok = r['is_ok']
                p_code = r.get('product_code', 'N/A')
                p_desc = r['product_desc']
                decision_date = r['formatted_date']
                
                color = "#28a745" if is_ok else "#ffc107"
                status = "✅ PDF 已就緒" if is_ok else "⚠️ 無 Summary"
                pdf_link = f'<a href="{pdf}" target="_blank" style="color: #d9534f; text-decoration: none; font-weight: 600;">📄 下載 PDF</a>' if is_ok else ""

                html_card = (
                    f'<div class="card" style="border-left-color: {color};">'
                    f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">'
                    f'<div><span class="index-badge">{i:02d}</span><span style="font-size: 1.2em; font-weight: 800; color: #111;">510(k) 號碼: {k}</span></div>'
                    f'<span style="color: {color}; font-weight: bold; background: white; padding: 2px 10px; border-radius: 20px; border: 1px solid {color}; font-size: 0.85em;">{status}</span>'
                    f'</div>'
                    f'<div style="margin-bottom: 8px;"><b>判定日期：</b>{decision_date}</div>'
                    f'<div style="margin-bottom: 8px;"><b>產品代碼與分類：</b><span class="code-label">{p_code}</span> <span style="color: #555;">{p_desc}</span></div>'
                    f'<div style="margin-bottom: 8px;"><b>設備名稱：</b>{r.get("device_name", "Unknown")}</div>'
                    f'<div style="margin-bottom: 12px;"><b>申請廠商：</b>{r.get("applicant", "Unknown")}</div>'
                    f'<div style="display: flex; gap: 15px;">'
                    f'<a href="https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID={k}" target="_blank" style="color: #007bff; text-decoration: none; font-weight: 600;">🌐 官方資訊</a>'
                    f'{pdf_link}'
                    f'</div>'
                    f'</div>'
                )
                st.markdown(html_card, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"連線發生錯誤：{e}")

# --- 5. 側邊欄設定 ---
with st.sidebar:
    st.header("搜尋參數設定")
    k_num = st.text_input("510(k) 號碼 (例如 K231234)", "").strip().upper()
    st.divider()
    kw1 = st.text_input("主關鍵字 (Device Name)", "Laser")
    kw2 = st.text_input("次要關鍵字", "")
    # --- 新增：申請廠商查詢欄位 ---
    app_name = st.text_input("申請廠商名稱 (Applicant)", placeholder="例如: Apple Inc.")
    
    limit = st.slider("抓取筆數", min_value=10, max_value=100, value=50, step=10)
    submit = st.button("啟動查詢", use_container_width=True, type="primary")

if submit:
    run_query(k_num, kw1, kw2, app_name, limit)
