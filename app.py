import streamlit as st
import requests

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="FDA 510(k) 查詢器", page_icon="🩺", layout="wide")

# --- 2. CSS 樣式與標題 ---
st.markdown("""
    <style>
    .main-title { font-size: 32px; font-weight: 800; color: #1E1E1E; text-align: center; margin-bottom: 5px; }
    .info-text { font-size: 16px; color: #666; text-align: center; margin-bottom: 25px; }
    .card { border-left: 6px solid #ccc; padding: 20px; background: #ffffff; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid #eee; }
    .idx-badge { background-color: #343a40; color: white; padding: 3px 12px; border-radius: 6px; font-size: 0.85em; margin-right: 12px; font-weight: 600; display: inline-block; }
    .k-num-text { font-size: 1.25em; font-weight: 800; color: #000; vertical-align: middle; }
    .label { font-weight: 700; color: #444; min-width: 140px; display: inline-block; }
    .value-text { color: #111; font-weight: 400; }
    </style>
    <div class="main-title">🩺 FDA 510(k) 專業查詢器</div>
    <div class="info-text">精確區分產品名稱與法規分類，並自動驗證 PDF 文件</div>
    """, unsafe_allow_html=True)

# --- 3. 側邊欄搜尋參數 ---
with st.sidebar:
    st.header("搜尋參數設定")
    k_num = st.text_input("510(k) 號碼 (例如 K231234)", "").strip().upper()
    st.divider()
    kw1 = st.text_input("產品關鍵字", "Laser")
    kw2 = st.text_input("廠商或細項關鍵字", "")
    limit = st.slider("抓取資料筆數", 5, 50, 10)
    submit = st.button("啟動查詢", use_container_width=True, type="primary")

# --- 4. 核心搜尋函式 ---
def run_query(kn, k1, k2, lmt):
    # 建立 API 查詢字串
    q = f'k_number:"{kn}"' if kn else "+AND+".join([f'device_name:{k}*' for k in [k1, k2] if k])
    if not q: return st.error("請輸入號碼或關鍵字")

    url = f'https://api.fda.gov/device/510k.json?search={q}&limit={lmt}'
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    with st.spinner('🔍 正在從 FDA 獲取精確數據並驗證檔案...'):
        try:
            resp = session.get(url)
            if resp.status_code != 200: return st.warning("找不到相符的結果")
            
            raw_data = resp.json().get('results', [])
            processed_results = []

            # 步驟一：資料預處理與欄位正確映射
            for r in raw_data:
                k = r.get('k_number', 'N/A')
                pdf_url = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{k[1:3]}/{k}.pdf"
                
                # 驗證 PDF 連結有效性
                is_ok = session.head(pdf_url, timeout=3).status_code == 200
                
                processed_results.append({
                    "k_num": k,
                    "device_name": r.get('proprietary_name', '未標示名稱'), # 這是廠商自取的 Device Name
                    "classification_name": r.get('device_name', '未知分類'), # 這是官方的 Classification Name
                    "applicant": r.get('applicant', '未知'),
                    "is_ok": is_ok,
                    "pdf_url": pdf_url
                })

            # 步驟二：排序 (有 PDF 的排前面)
            processed_results.sort(key=lambda x: x['is_ok'], reverse=True)

            st.success(f"✅ 找到 {len(processed_results)} 筆結果")

            # 步驟三：輸出結果
            for i, item in enumerate(processed_results, 1):
                color = "#28a745" if item['is_ok'] else "#ffc107"
                status = "✅ PDF 已就緒" if item['is_ok'] else "⚠️ 無官方 Summary"
                
                pdf_btn = f'<a href="{item["pdf_url"]}" target="_blank" style="color: #ffffff; background-color: #d9534f; padding: 5px 15px; border-radius: 4px; text-decoration: none; font-size: 0.85em; font-weight: 600;">📄 下載 PDF</a>' if item['is_ok'] else ""

                # 建構扁平化 HTML
                html_card = (
                    f'<div class="card" style="border-left-color: {color};">'
                    f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px;">'
                    f'<div>'
                    f'<span class="idx-badge">NO. {i:02d}</span>'
                    f'<span class="k-num-text">510(k): {item["k_num"]}</span>'
                    f'</div>'
                    f'<span style="color: {color}; font-weight: bold; background: #fff; padding: 3px 12px; border-radius: 20px; border: 1px solid {color}; font-size: 0.85em;">{status}</span>'
                    f'</div>'
                    f'<div style="margin-bottom: 8px;"><span class="label">產品名稱：</span><span class="value-text">{item["device_name"]}</span></div>'
                    f'<div style="margin-bottom: 8px;"><span class="label">分類名稱：</span><span class="value-text">{item["classification_name"]}</span></div>'
                    f'<div style="margin-bottom: 18px;"><span class="label">申請廠商：</span><span class="value-text">{item["applicant"]}</span></div>'
                    f'<div style="display: flex; gap: 20px; align-items: center; border-top: 1px solid #eee; padding-top: 15px;">'
                    f'<a href="https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID={item["k_num"]}" target="_blank" style="color: #007bff; text-decoration: none; font-weight: 600; font-size: 0.85em;">🌐 查看官方詳細資訊</a>'
                    f'{pdf_btn}'
                    f'</div>'
                    f'</div>'
                )
                
                st.markdown(html_card, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"執行時發生錯誤：{e}")

# --- 5. 執行查詢 ---
if submit:
    run_query(k_num, kw1, kw2, limit)
