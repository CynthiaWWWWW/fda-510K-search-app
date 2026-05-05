import streamlit as st
import requests

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="FDA 510(k) Search", page_icon="🩺", layout="wide")

# --- 2. CSS 樣式 ---
st.markdown("""
    <style>
    .main-title { font-size: 28px; font-weight: 800; color: #1E1E1E; text-align: center; margin-bottom: 10px; }
    .info-text { font-size: 16px; color: #666; text-align: center; margin-bottom: 20px; }
    .card { border-left: 6px solid #ccc; padding: 16px; background: #f8f9fa; border-radius: 10px; margin-bottom: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .index-badge { background: #4a4a4a; color: #ffffff; padding: 4px 10px; border-radius: 6px; font-size: 0.9em; font-weight: bold; margin-right: 12px; letter-spacing: 1px;}
    .code-label { background: #e9ecef; color: #495057; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-weight: bold;}
    </style>
    <div class="main-title">🩺 FDA 510(k) Search Tool</div>
    <div class="info-text">Retrieve data from OpenFDA API with automatic PDF validation</div>
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
            # 取得官方分類的英文名稱
            return resp['results'][0].get('device_name', 'Definition not found')
    except:
        pass
    return "Unknown"

# --- 4. 主查詢函式 ---
def run_query(kn, k1, k2, lmt):
    q = f'k_number:"{kn}"' if kn else "+AND+".join([f'device_name:{k}*' for k in [k1, k2] if k])
    if not q: return st.error("Please enter a K-number or keywords")

    url = f'https://api.fda.gov/device/510k.json?search={q}&limit={lmt}'
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    with st.spinner('Searching FDA database and validating PDFs...'):
        try:
            resp = session.get(url)
            if resp.status_code != 200: return st.warning("No matching results found")
            
            raw_data = resp.json().get('results', [])
            processed_results = []

            for r in raw_data:
                k = r.get('k_number')
                pdf = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{k[1:3]}/{k}.pdf"
                # 驗證 PDF 連結是否存在
                is_ok = session.head(pdf, timeout=2).status_code == 200
                
                # 取得產品代碼的英文詳情
                p_code = r.get('product_code', '')
                eng_def = get_product_definition(p_code)
                
                r['is_ok'] = is_ok
                r['pdf_url'] = pdf
                r['product_desc'] = eng_def
                processed_results.append(r)

            # 排序：將有 PDF 的結果置頂
            processed_results.sort(key=lambda x: x['is_ok'], reverse=True)

            st.success(f"Found {len(processed_results)} records (PDF-available results moved to top)")

            for i, r in enumerate(processed_results, 1):
                k = r.get('k_number')
                pdf = r['pdf_url']
                is_ok = r['is_ok']
                p_code = r.get('product_code', 'N/A')
                p_desc = r['product_desc']
                
                color = "#28a745" if is_ok else "#ffc107"
                status = "✅ PDF Ready" if is_ok else "⚠️ No Summary"
                pdf_link = f'<a href="{pdf}" target="_blank" style="color: #d9534f; text-decoration: none; font-weight: 600;">📄 Download PDF</a>' if is_ok else ""

                html_card = (
                    f'<div class="card" style="border-left-color: {color};">'
                    f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
