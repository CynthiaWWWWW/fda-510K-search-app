import streamlit as st
import requests

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="FDA 510(k) 查詢器", page_icon="🩺", layout="wide")

# --- 2. CSS 樣式 ---
st.markdown("""
    <style>
    /* 主頁面樣式 */
    .main-title { font-size: 26px; font-weight: 800; color: #1E1E1E; text-align: center; margin-bottom: 10px; }
    .info-text { font-size: 14px; color: #666; text-align: center; margin-bottom: 20px; }
    .card { border-left: 6px solid #ccc; padding: 16px; background: #f8f9fa; border-radius: 10px; margin-bottom: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .index-badge { background: #4a4a4a; color: #ffffff; padding: 4px 10px; border-radius: 6px; font-size: 0.9em; font-weight: bold; margin-right: 12px; letter-spacing: 1px;}
    .code-label { background: #e9ecef; color: #495057; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-weight: bold; margin-right: 8px;}

    /* --- 側邊欄精修排版 --- */
    
    /* 1. 標題類：1. & 2. 項 (粗體 16px) */
    [data-testid="stSidebar"] .stMarkdown p strong {
        font-size: 16px !important;
        font-weight: 800 !important;
        display: block;
        margin-top: 8px !important;
        margin-bottom: 2px !important;
    }

    /* 2. 欄位標籤類：申請廠商、關鍵字等 (非粗體 14px) */
    [data-testid="stSidebar"] .stWidgetLabel p {
        font-size: 14px !important;
        font-weight: 400 !important;
        color: #555 !important;
        margin-bottom: -5px !important;
    }

    /* 縮小元件容器間距 */
    [data-testid="stSidebar"] .element-container {
        margin-bottom: 0px !important;
    }

    /* 輸入框底部邊距 */
    [data-testid="stSidebar"] .stTextInput {
        margin-bottom: 0px !important;
    }

    /* Slider 頂部邊距 */
    [data-testid="stSidebar"] .stSlider {
        margin-top: 10px !important;
    }

    /* 按鈕文字大小調整 */
    [data-testid="stSidebar"] .stButton button p {
        font-size: 16px !important;
        font-weight: 600 !important;
    }
    </style>
    <div class="main-title">🩺 FDA 510(k) 查詢工具</div>
    <div class="info-text">連線 OpenFDA 資料庫進行精確欄位篩選</div>
    """, unsafe_allow_html=True)

# --- 3. 核心輔助函式 ---

@st.cache_data(ttl=3600)
def get_product_definition(p_code):
    if not p_code or p_code == '未知': return "Definition not found"
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
    if kn:
        q = f'k_number:"{kn}"'
    else:
        query_parts = []
        if app.strip():
            query_parts.append(f'applicant:"{app.strip()}*"')
        if k1.strip():
            query_parts.append(f'device_name:"{k1.strip()}*"')
        if k2.strip():
            query_parts.append(f'device_name:"{k2.strip()}*"')
        q = "+AND+".join(query_parts)

    if not q: 
        return st.error("請輸入號碼、廠商或產品關鍵字")

    url = f'https://api.fda.gov/device/510k.json?search={q}&limit={lmt}'
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    with st.spinner('檢索中...'):
        try:
            resp = session.get(url)
            if resp.status_code != 200: 
                return st.warning("找不到相符結果。")
            
            raw_data = resp.json().get('results', [])
            processed_results = []

            for r in raw_data:
                k = r.get('k_number')
                pdf = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{k[1:3]}/{k}.pdf"
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

            processed_results.sort(key=lambda x: x['is_ok'], reverse=True)
            st.success(f"搜尋完成：共 {len(processed_results)} 筆")

            for i, r in enumerate(processed_results, 1):
                k = r.get('k_number', 'N/A')
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
        except:
            st.error("系統發生錯誤")

# --- 5. 側邊欄設定 ---
with st.sidebar:
    st.markdown("### 搜尋參數設定")
    
    st.markdown("**1. 510(k) 號碼查詢**")
    k_num = st.text_input("輸入 510(k) 號碼", placeholder="例如: K231234").strip().upper()
    
    st.markdown("**2. 複合篩選條件 (可同時填寫)**")
    app_name = st.text_input("申請廠商", placeholder="例如: Medtronic")
    kw1 = st.text_input("產品主要關鍵字", placeholder="例如: Bipolar")
    kw2 = st.text_input("產品次要關鍵字", placeholder="選填")
    
    st.markdown("**抓取上限**")
    limit = st.slider("筆數", min_value=10, max_value=100, value=50, step=10, label_visibility="collapsed")
    
    st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)
    # 按鈕文字已改為「查詢」
    submit = st.button("查詢", use_container_width=True, type="primary")
