import streamlit as st
import requests

# --- 1. 網頁基本設定 ---
# 設定網頁標題、分頁圖示以及佈局模式（wide 為寬螢幕模式）
st.set_page_config(page_title="FDA 510(k) 查詢器", page_icon="🩺", layout="wide")

# --- 2. CSS 樣式 ---
st.markdown("""
    <style>
    /* 主界面樣式 */
    .main-title { font-size: 28px; font-weight: 800; color: #1E1E1E; text-align: center; margin-bottom: 10px; }
    .info-text { font-size: 16px; color: #666; text-align: center; margin-bottom: 20px; }
    .card { border-left: 6px solid #ccc; padding: 16px; background: #f8f9fa; border-radius: 10px; margin-bottom: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .index-badge { background: #4a4a4a; color: #ffffff; padding: 4px 10px; border-radius: 6px; font-size: 0.9em; font-weight: bold; margin-right: 12px; letter-spacing: 1px;}
    .code-label { background: #e9ecef; color: #495057; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-weight: bold; margin-right: 8px;}

    /* 側邊欄間距平衡設定 */
    /* 隱藏原生標籤以消除元件間的預設格式差異 */
    [data-testid="stSidebar"] label {
        display: none;
    }

    /* 統一所有標題與標籤，設定中等舒適的間距 */
    .custom-label {
        font-size: 1rem !important;
        font-weight: normal !important;
        color: #31333F;
        display: block;
        margin-top: 10px;   /* 平衡間距：從極度緊密的 6px 放寬至 10px */
        margin-bottom: 4px; /* 與輸入框保持適度呼吸感 */
    }

    /* 側邊欄頂部標題調整 */
    [data-testid="stSidebar"] h2 {
        font-size: 1.1rem !important;
        font-weight: normal !important;
        margin-bottom: 8px !important;
        padding-bottom: 5px !important;
    }

    /* 設定側邊欄元件之間的標準垂直間隙 */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.5rem !important; /* 折衷間距：既不緊密也不稀疏 */
    }

    /* 確保輸入框容器不會有額外的底邊距 */
    div.stTextInput {
        margin-bottom: 0px !important;
    }
    </style>
    
    <div class="main-title">🩺 FDA 510(k) 查詢工具</div>
    <div class="info-text">連線 OpenFDA 資料庫進行精確欄位篩選</div>
    """, unsafe_allow_html=True)

# --- 3. 核心輔助函式 ---

@st.cache_data(ttl=3600)  # 設定快取，一小時內相同的 Product Code 不重複請求 API
def get_product_definition(p_code):
    """
    透過 Product Code 查詢該器材的官方分類名稱
    """
    if not p_code or p_code == '未知': return "找不到定義"
    try:
        # 串接 FDA Classification API
        class_url = f'https://api.fda.gov/device/classification.json?search=product_code:"{p_code}"'
        resp = requests.get(class_url, timeout=5).json()
        if 'results' in resp:
            return resp['results'][0].get('device_name', '找不到定義')
    except:
        pass
    return "未知"

# --- 4. 主查詢函式 ---
def run_query(kn, k1, k2, app, lmt):
    """
    執行 OpenFDA API 查詢並處理結果
    kn: 510(k) 號碼, k1/k2: 產品關鍵字, app: 申請廠商, lmt: 限制筆數
    """
    # 判斷查詢邏輯：若有提供號碼則以號碼為主，否則組合複合條件
    if kn:
        q = f'k_number:"{kn}"'
    else:
        query_parts = []
        
        # 1. 廠商欄位搜尋：移除引號並加上 * 實作模糊搜尋
        if app.strip():
            clean_app = app.strip().replace('"', '')
            query_parts.append(f'applicant:{clean_app}*')
        
        # 2. 產品主要關鍵字：bipola* 模式可搜尋到 Bipolar
        if k1.strip():
            clean_k1 = k1.strip().replace('"', '')
            query_parts.append(f'device_name:{clean_k1}*')
        
        # 3. 產品次要關鍵字
        if k2.strip():
            clean_k2 = k2.strip().replace('"', '')
            query_parts.append(f'device_name:{clean_k2}*')
        
        # 將所有條件用 AND 邏輯串接
        q = "+AND+".join(query_parts)

    # 防呆機制：若無任何條件則不執行
    if not q: 
        return st.error("請至少輸入一個搜尋條件 (號碼、廠商或產品關鍵字)")
    
    # 組合完整 OpenFDA API 網址
    url = f'https://api.fda.gov/device/510k.json?search={q}&limit={lmt}'
    
    # 使用 Session 保持連線並設定 User-Agent 避免被擋
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    with st.spinner('正在根據篩選條件檢索 FDA 資料庫...'):
        try:
            resp = session.get(url)
            # 若狀態碼非 200 代表查無資料或 API 異常
            if resp.status_code != 200: 
                return st.warning("找不到相符的查詢結果，請確認輸入內容是否正確。")
            
            raw_data = resp.json().get('results', [])
            processed_results = []

            # 遍歷原始資料進行二次加工
            for r in raw_data:
                k = r.get('k_number')
                # 根據號碼規則預測 PDF 存放路徑
                pdf = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{k[1:3]}/{k}.pdf"
                
                # 檢查 PDF 檔案是否存在
                try:
                    is_ok = session.head(pdf, timeout=2).status_code == 200
                except:
                    is_ok = False
                
                # 獲取產品定義與美化日期格式
                p_code = r.get('product_code', '')
                eng_def = get_product_definition(p_code)
                raw_date = r.get('decision_date', '')
                formatted_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else raw_date

                r['is_ok'] = is_ok
                r['pdf_url'] = pdf
                r['product_desc'] = eng_def
                r['formatted_date'] = formatted_date
                processed_results.append(r)

            # 排序：將有 PDF 的結果排在最前面
            processed_results.sort(key=lambda x: x['is_ok'], reverse=True)

            st.success(f"搜尋完成：共 {len(processed_results)} 筆資料")

            # 渲染結果卡片
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

        except Exception as e:
            st.error(f"連線發生錯誤：{e}")

# --- 5. 側邊欄設定 (使用者輸入介面) ---
with st.sidebar:
    st.header("搜尋參數設定")
    
    # 1. 號碼查詢區
    st.markdown('<span class="custom-label">1. 依 510(k) 號碼查詢 (完整號碼)</span>', unsafe_allow_html=True)
    k_num = st.text_input("hid_1", placeholder="例如: K231234").strip().upper()
    
    # 區塊間距
    st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)
    
    # 2. 複合查詢區
    st.markdown('<span class="custom-label">2. 複合篩選條件 (支援模糊比對)</span>', unsafe_allow_html=True)
    
    st.markdown('<span class="custom-label">申請廠商 (Applicant)</span>', unsafe_allow_html=True)
    app_name = st.text_input("hid_2", placeholder="例如: Medtronic")
    
    st.markdown('<span class="custom-label">產品主要關鍵字</span>', unsafe_allow_html=True)
    kw1 = st.text_input("hid_3", placeholder="例如: Bipolar")
    
    st.markdown('<span class="custom-label">產品次要關鍵字</span>', unsafe_allow_html=True)
    kw2 = st.text_input("hid_4", placeholder="選填")
    
    # 按鈕與滑桿區間距
    st.markdown('<div style="margin-top:25px;"></div>', unsafe_allow_html=True)
    limit = st.slider("抓取筆數", min_value=10, max_value=100, value=50, step=10)
    submit = st.button("啟動查詢", use_container_width=True, type="primary")

# 當按下查詢按鈕時觸發
if submit:
    run_query(k_num, kw1, kw2, app_name, limit)
