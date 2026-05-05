import streamlit as st
import requests

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="FDA 510(k) 查詢 (含中文品名)", page_icon="🩺", layout="wide")

# --- 2. CSS 樣式 ---
st.markdown("""
    <style>
    .main-title { font-size: 28px; font-weight: 800; color: #1E1E1E; text-align: center; margin-bottom: 10px; }
    .info-text { font-size: 16px; color: #666; text-align: center; margin-bottom: 20px; }
    .card { border-left: 6px solid #ccc; padding: 16px; background: #f8f9fa; border-radius: 10px; margin-bottom: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .index-badge { background: #4a4a4a; color: #ffffff; padding: 4px 10px; border-radius: 6px; font-size: 0.9em; font-weight: bold; margin-right: 12px; letter-spacing: 1px;}
    .code-label { background: #e9ecef; color: #495057; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-weight: bold;}
    </style>
    <div class="main-title">🩺 FDA 510(k) 智慧查詢器</div>
    <div class="info-text">整合 OpenFDA 分類資料庫，自動翻譯產品代碼</div>
    """, unsafe_allow_html=True)

# --- 3. 產品代碼中英對照字典 (可持續擴充) ---
# 這裡列出常見的，若 API 查不到或不在這，則顯示英文
PRODUCT_CODE_MAP = {
    "LNH": "雷射手術器械 (Laser Surgical Instrument)",
    "GEX": "光源式外科器械 (Powered Light Source)",
    "IOL": "眼內透鏡 (Intraocular Lens)",
    "DZE": "牙科植體 (Dental Implant)",
    "LLZ": "醫用雷射系統 (Medical Laser System)",
    "NGO": "肌電圖儀 (Electromyograph)",
    "PHX": "光動力治療裝置 (Photodynamic Therapy)",
    "NCO": "生理訊號監視器 (Monitor, Physiological Patient)",
    # 您可以在此繼續手動加入常用的代碼對應
}

# --- 4. 核心輔助函式 ---

@st.cache_data(ttl=3600)
def get_product_definition(p_code):
    """透過 Product Code 查詢 FDA 分類 API 取得英文全名"""
    if not p_code or p_code == '未知':
        return "Unknown Device", "未知設備"
    
    # 1. 優先從手動字典找
    if p_code in PRODUCT_CODE_MAP:
        full_info = PRODUCT_CODE_MAP[p_code]
        return full_info, full_info # 簡化回傳

    # 2. 字典找不到，則爬取 FDA 分類 API
    try:
        class_url = f'https://api.fda.gov/device/classification.json?search=product_code:"{p_code}"'
        resp = requests.get(class_url, timeout=5).json()
        if 'results' in resp:
            eng_name = resp['results'][0].get('device_name', 'Definition not found')
            return eng_name, "（中文待核）"
    except:
        pass
    return "Unknown", "未知"

# --- 5. 主查詢函式 ---
def run_query(kn, k1, k2, lmt):
    q = f'k_number:"{kn}"' if kn else "+AND+".join([f'device_name:{k}*' for k in [k1, k2] if k])
    if not q: return st.error("請輸入號碼或關鍵字")

    url = f'https://api.fda.gov/device/510k.json?search={q}&limit={lmt}'
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    with st.spinner('正在檢索資料並解析產品分類...'):
        try:
            resp = session.get(url)
            if resp.status_code != 200: return st.warning("找不到相符的結果")
            
            raw_data = resp.json().get('results', [])
            processed_results = []

            for r in raw_data:
                k = r.get('k_number')
                pdf = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{k[1:3]}/{k}.pdf"
                # 驗證 PDF 連結
                is_ok = session.head(pdf, timeout=2).status_code == 200
                
                # 取得產品代碼詳情
                p_code = r.get('product_code', '')
                eng_def, chi_def = get_product_definition(p_code)
                
                r['is_ok'] = is_ok
                r['pdf_url'] = pdf
                r['product_desc'] = f"{eng_def} {chi_def}"
                processed_results.append(r)

            # 排序：有 PDF 的優先
            processed_results.sort(key=lambda x: x['is_ok'], reverse=True)

            st.success(f"找到 {len(processed_results)} 筆資料")

            for i, r in enumerate(processed_results, 1):
                k = r.get('k_number')
                pdf = r['pdf_url']
                is_ok = r['is_ok']
                p_code = r.get('product_code', 'N/A')
                p_desc = r['product_desc']
                
                color = "#28a745" if is_ok else "#ffc107"
                status = "✅ PDF 已就緒" if is_ok else "⚠️ 無 Summary"
                pdf_link = f'<a href="{pdf}" target="_blank" style="color: #d9534f; text-decoration: none; font-weight: 600;">📄 下載 PDF</a>' if is_ok else ""

                html_card = (
                    f'<div class="card" style="border-left-color: {color};">'
                    f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">'
                    f'<div><span class="index-badge">{i:02d}</span><span style="font-size: 1.2em; font-weight: 800; color: #111;">510(k): {k}</span></div>'
                    f'<span style="color: {color}; font-weight: bold; background: white; padding: 2px 10px; border-radius: 20px; border: 1px solid {color}; font-size: 0.85em;">{status}</span>'
                    f'</div>'
                    f'<div style="margin-bottom: 8px;"><b>產品代碼：</b><span class="code-label">{p_code}</span></div>'
                    f'<div style="margin-bottom: 8px;"><b>分類品名：</b><span style="color: #495057;">{p_desc}</span></div>'
                    f'<div style="margin-bottom: 8px;"><b>設備名稱：</b>{r.get("device_name", "未知")}</div>'
                    f'<div style="margin-bottom: 12px;"><b>申請廠商：</b>{r.get("applicant", "未知")}</div>'
                    f'<div style="display: flex; gap: 15px;">'
                    f'<a href="https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID={k}" target="_blank" style="color: #007bff; text-decoration: none; font-weight: 600;">🌐 官網資訊</a>'
                    f'{pdf_link}'
                    f'</div>'
                    f'</div>'
                )
                st.markdown(html_card, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"連線發生錯誤：{e}")

# --- 6. 側邊欄 ---
with st.sidebar:
    st.header("搜尋參數設定")
    k_num = st.text_input("510(k) 號碼", "").strip().upper()
    st.divider()
    kw1 = st.text_input("產品關鍵字", "Laser")
    kw2 = st.text_input("廠商或細項", "")
    limit = st.slider("抓取筆數", 5, 50, 10)
    submit = st.button("啟動查詢", use_container_width=True, type="primary")

if submit:
    run_query(k_num, kw1, kw2, limit)
