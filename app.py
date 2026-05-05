import streamlit as st
import requests

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="FDA 510(k) 查詢", page_icon="🩺", layout="wide")

# --- 2. CSS 樣式與標題 ---
# 新增了 .index-badge 樣式來美化序號
st.markdown("""
    <style>
    .main-title { font-size: 28px; font-weight: 800; color: #1E1E1E; text-align: center; margin-bottom: 10px; }
    .info-text { font-size: 16px; color: #666; text-align: center; margin-bottom: 20px; }
    .card { border-left: 6px solid #ccc; padding: 16px; background: #f8f9fa; border-radius: 10px; margin-bottom: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .index-badge { background: #4a4a4a; color: #ffffff; padding: 4px 10px; border-radius: 6px; font-size: 0.9em; font-weight: bold; margin-right: 12px; letter-spacing: 1px;}
    </style>
    <div class="main-title">🩺 FDA 510(k) 查詢器</div>
    <div class="info-text">透過 OpenFDA API 檢索申報資料並自動驗證 PDF 文件</div>
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
    q = f'k_number:"{kn}"' if kn else "+AND+".join([f'device_name:{k}*' for k in [k1, k2] if k])
    if not q: return st.error("請輸入號碼或關鍵字")

    url = f'https://api.fda.gov/device/510k.json?search={q}&limit={lmt}'
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    with st.spinner('正在從 FDA 搜尋、驗證 PDF 並排序中...'):
        try:
            resp = session.get(url)
            if resp.status_code != 200: return st.warning("找不到相符的結果")
            
            raw_data = resp.json().get('results', [])
            processed_results = []

            # 第一步：預處理資料並驗證 PDF (為了後續排序)
            for r in raw_data:
                k = r.get('k_number')
                pdf = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{k[1:3]}/{k}.pdf"
                # 驗證連結有效性
                is_ok = session.head(pdf, timeout=3).status_code == 200
                
                r['is_ok'] = is_ok
                r['pdf_url'] = pdf
                processed_results.append(r)

            # 第二步：根據 PDF 是否存在進行排序 (True 的排前面)
            processed_results.sort(key=lambda x: x['is_ok'], reverse=True)

            st.success(f"找到 {len(processed_results)} 筆資料 (已將有 PDF 的結果置頂)")

            # 第三步：渲染結果
            for i, r in enumerate(processed_results, 1):
                k = r.get('k_number')
                pdf = r['pdf_url']
                is_ok = r['is_ok']
                
                # 取得 Product Code
                product_code = r.get('product_code', '未知')
                
                color = "#28a745" if is_ok else "#ffc107"
                status = "✅ PDF 已就緒" if is_ok else "⚠️ 無 Summary 文件"
                
                # PDF 按鈕 HTML
                pdf_link = f'<a href="{pdf}" target="_blank" style="color: #d9534f; text-decoration: none; font-weight: 600;">📄 下載 PDF</a>' if is_ok else ""

                # 扁平化 HTML 字串 (加入 index-badge 樣式與 Product Code 欄位)
                html_card = (
                    f'<div class="card" style="border-left-color: {color};">'
                    f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">'
                    f'<div><span class="index-badge">ITEM {i:02d}</span><span style="font-size: 1.2em; font-weight: 800; color: #111;">510(k): {k}</span></div>'
                    f'<span style="color: {color}; font-weight: bold; background: white; padding: 2px 10px; border-radius: 20px; border: 1px solid {color}; font-size: 0.85em;">{status}</span>'
                    f'</div>'
                    f'<div style="margin-bottom: 8px;"><b>產品代碼：</b>{product_code}</div>'
                    f'<div style="margin-bottom: 8px;"><b>產品設備：</b>{r.get("device_name", "未知")}</div>'
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

# --- 5. 執行搜尋按鈕觸發 ---
if submit:
    run_query(k_num, kw1, kw2, limit)
