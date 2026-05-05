import streamlit as st
import requests
from datetime import datetime

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="FDA 510(k) 專業查詢器", page_icon="🩺", layout="wide")

# --- 2. CSS 樣式優化 ---
st.markdown("""
    <style>
    .main-title { font-size: 32px; font-weight: 800; color: #1E1E1E; text-align: center; margin-bottom: 5px; }
    .info-text { font-size: 16px; color: #666; text-align: center; margin-bottom: 25px; }
    .card { border-left: 6px solid #ccc; padding: 20px; background: #ffffff; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid #eee; }
    .index-badge { background: #333; color: #fff; padding: 4px 10px; border-radius: 6px; font-size: 0.9em; font-weight: bold; margin-right: 12px; }
    .date-label { font-size: 0.85em; color: #666; }
    .date-value { font-weight: 700; color: #333; font-family: monospace; }
    .code-label { background: #eef2f7; color: #334e68; padding: 3px 8px; border-radius: 4px; font-family: monospace; font-weight: bold; font-size: 0.9em; border: 1px solid #d1d9e0; }
    .tag-blue { background: #e3f2fd; color: #1976d2; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
    </style>
    <div class="main-title">🩺 FDA 510(k) 專業檢索系統</div>
    <div class="info-text">整合 OpenFDA 數據庫：包含判定日期、審查時程與 PDF 文件狀態驗證</div>
    """, unsafe_allow_html=True)

# --- 3. 核心輔助函式 ---

@st.cache_data(ttl=3600)
def get_product_definition(p_code):
    """透過 Product Code 查詢 FDA 分類 API 取得官方英文名稱"""
    if not p_code or p_code == 'Unknown': return "Definition not found"
    try:
        class_url = f'https://api.fda.gov/device/classification.json?search=product_code:"{p_code}"'
        resp = requests.get(class_url, timeout=5).json()
        if 'results' in resp:
            return resp['results'][0].get('device_name', 'Definition not found')
    except:
        pass
    return "Unknown"

def format_date(date_str):
    """將 YYYYMMDD 轉為 YYYY-MM-DD"""
    if not date_str or len(date_str) != 8: return "N/A"
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

def calc_days(d1, d2):
    """計算收到日期與判定日期之間的天數"""
    try:
        fmt = "%Y%m%d"
        delta = datetime.strptime(d2, fmt) - datetime.strptime(d1, fmt)
        return delta.days
    except:
        return None

# --- 4. 主查詢函式 ---
def run_query(kn, k1, k2, lmt):
    # 建立搜尋字串
    if kn:
        q = f'k_number:"{kn}"'
    else:
        q = "+AND+".join([f'device_name:{k}*' for k in [k1, k2] if k])
    
    if not q: return st.error("請輸入 510(k) 號碼或產品關鍵字")

    url = f'https://api.fda.gov/device/510k.json?search={q}&limit={lmt}'
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    with st.spinner('正在從 FDA 伺服器同步數據並驗證文件...'):
        try:
            resp = session.get(url)
            if resp.status_code != 200: return st.warning("找不到相符的查詢結果，請嘗試調整關鍵字")
            
            raw_data = resp.json().get('results', [])
            processed_results = []

            for r in raw_data:
                k = r.get('k_number')
                # 處理日期與天數
                d_rec = r.get('date_received', '')
                d_dec = r.get('decision_date', '')
                review_days = calc_days(d_rec, d_dec)
                
                # 處理 PDF 連結與狀態
                pdf = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{k[1:3]}/{k}.pdf"
                try:
                    is_ok = session.head(pdf, timeout=2).status_code == 200
                except:
                    is_ok = False
                
                # 取得產品分類定義
                p_code = r.get('product_code', '')
                r['product_desc'] = get_product_definition(p_code)
                r['formatted_decision_date'] = format_date(d_dec)
                r['review_days'] = review_days
                r['is_ok'] = is_ok
                r['pdf_url'] = pdf
                processed_results.append(r)

            # 排序：有 PDF 的結果置頂，再按日期降序排列
            processed_results.sort(key=lambda x: (x['is_ok'], x.get('decision_date', '')), reverse=True)

            st.info(f"💡 找到 {len(processed_results)} 筆結果。備註：Predicate Device (對照品) 資訊通常詳列於 PDF Summary 的第 5 章節。")

            for i, r in enumerate(processed_results, 1):
                k = r.get('k_number')
                is_ok = r['is_ok']
                color = "#28a745" if is_ok else "#ffa000"
                status = "✅ 510(k) Summary 已就緒" if is_ok else "⚠️ 尚無文件 (或為舊式聲明)"
                
                days_html = f'<span class="tag-blue">⏱ 審查週期: {r["review_days"]} 天</span>' if r["review_days"] else ""
                pdf_btn = f'<a href="{r["pdf_url"]}" target="_blank" style="background-color: #d9534f; color: white; padding: 6px 14px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 0.9em;">📄 下載 PDF</a>' if is_ok else ""

                html_card = f"""
                <div class="card" style="border-left-color: {color};">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <span class="index-badge">{i:02d}</span>
                            <span style="font-size: 1.3em; font-weight: 800; color: #111;">510(k) #: {k}</span>
                        </div>
                        <div style="text-align: right;">
                            <div class="date-label">Decision Date</div>
                            <div class="date-value">{r['formatted_decision_date']}</div>
                        </div>
                    </div>
                    
                    <div style="margin: 15px 0;">
                        <div style="margin-bottom: 8px;">
                            <b>設備名稱：</b><span style="color: #004085; font-weight: 600;">{r.get('device_name', 'Unknown').title()}</span>
                        </div>
                        <div style="margin-bottom: 8px;">
                            <b>產品代碼：</b><span class="code-label">{r.get('product_code')}</span> 
                            <span style="color: #555; font-size: 0.95em;">{r['product_desc']}</span>
                        </div>
                        <div style="margin-bottom: 8px;">
                            <b>申請廠商：</b>{r.get('applicant', 'Unknown')}
                        </div>
                        <div style="margin-top: 10px;">
                            {days_html}
                        </div>
                    </div>

                    <div style="background: #fcfcfc; border: 1px dashed #ddd; padding: 10px; border-radius: 6px; font-size: 0.9em; color: #444;">
                        🔍 <b>Predicate Device (對照品)：</b> 結構化數據不直接提供，請點擊下方下載 PDF 後查閱 <u>Section 5 (510k Summary)</u>。
                    </div>

                    <div style="display: flex; gap: 15px; margin-top: 20px; align-items: center;">
                        <a href="https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID={k}" target="_blank" style="color: #007bff; text-decoration: none; font-weight: 600; font-size: 0.9em;">🌐 查看官方資料庫</a>
                        {pdf_btn}
                        <span style="margin-left: auto; color: {color}; font-size: 0.85em; font-weight: bold;">{status}</span>
                    </div>
                </div>
                """
                st.markdown(html_card, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"連線或解析發生錯誤：{str(e)}")

# --- 5. 側邊欄設定 ---
with st.sidebar:
    st.header("🔍 檢索參數設定")
    k_num = st.text_input("精確查詢 510(k) 號碼", placeholder="例如: K231234").strip().upper()
    
    st.divider()
    st.subheader("關鍵字組合查詢")
    kw1 = st.text_input("主要設備關鍵字", "Laser", help="例如: Laser, Catheter, AI")
    kw2 = st.text_input("次要篩選關鍵字", "", placeholder="例如廠商名稱或細項功能")
    
    limit = st.slider("抓取資料筆數", 10, 100, 30, 10)
    
    st.info("💡 提示：輸入 510(k) 號碼時會優先進行精確查詢，忽略下方關鍵字。")
    
    submit = st.button("開始檢索數據", use_container_width=True, type="primary")

# --- 6. 執行查詢 ---
if submit:
    run_query(k_num, kw1, kw2, limit)
else:
    st.write("---")
    st.caption("請於左側側邊欄輸入查詢條件並點擊「開始檢索數據」按鈕。")
