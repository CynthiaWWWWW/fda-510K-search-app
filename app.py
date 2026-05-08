"""
FDA 510(k) 查詢工具
===================
連線 OpenFDA 資料庫，依欄位精確篩選 510(k) 醫療器材清關資訊。

Author  : (your name)
Version : 2.0.0
"""

# `annotations` 讓型別提示可以用字串形式延遲解析，
# 避免循環引用問題，並相容舊版 Python 的 list[...] 語法。
from __future__ import annotations

import logging
# dataclass 讓資料類別的定義更簡潔，自動產生 __init__、__repr__ 等方法。
# field 用於需要更細緻控制預設值的欄位（目前備而不用）。
from dataclasses import dataclass, field
from typing import Optional

import requests
import streamlit as st


# ---------------------------------------------------------------------------
# 常數
# ---------------------------------------------------------------------------
# 集中管理所有「魔法數字」與 URL，往後只需修改這一區塊，
# 不必在程式各處搜尋散落的字串。

PAGE_TITLE = "FDA 510(k) 查詢器"   # 瀏覽器分頁標題
PAGE_ICON  = "🩺"                   # 分頁 favicon

# OpenFDA REST API 端點
OPENFDA_510K_URL  = "https://api.fda.gov/device/510k.json"
OPENFDA_CLASS_URL = "https://api.fda.gov/device/classification.json"

# FDA AccessData 網站：PDF 下載與官方說明頁面
ACCESSDATA_BASE_URL = "https://www.accessdata.fda.gov"
PDF_BASE_URL        = f"{ACCESSDATA_BASE_URL}/cdrh_docs/pdf"   # PDF 路徑前綴
PMN_DETAIL_URL      = f"{ACCESSDATA_BASE_URL}/scripts/cdrh/cfdocs/cfPMN/pmn.cfm"

CACHE_TTL_SECONDS    = 3_600   # product code 定義快取時間：1 小時
REQUEST_TIMEOUT      = 5       # 一般 API 請求的逾時秒數
PDF_HEAD_TIMEOUT     = 2       # 檢查 PDF 是否存在用的 HEAD 請求逾時（需更快）
DEFAULT_HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FDA510k-Viewer/2.0)"}
# ↑ 部分伺服器會封鎖沒有 User-Agent 的請求，設定後可避免被拒絕

# 結果卡片的左邊框顏色：綠色表示 PDF 可用，黃色表示無 PDF
COLOR_SUCCESS = "#28a745"
COLOR_WARNING = "#ffc107"

# 設定 logging，WARNING 等級以上才會輸出，避免 Streamlit 介面出現雜訊
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)   # 使用模組名稱作為 logger 名稱，方便追蹤來源


# ---------------------------------------------------------------------------
# 資料類別
# ---------------------------------------------------------------------------
# 使用 dataclass 代替裸字典（dict），好處：
#   1. 欄位有明確型別，IDE 可補全與靜態檢查
#   2. 避免 KeyError，預設值更清晰
#   3. 資料與相關行為（property）可以放在同一個類別裡

@dataclass
class SearchParams:
    """使用者透過側邊欄輸入的搜尋條件，傳入查詢函式使用。"""
    k_number:  str = ""    # 510(k) 號碼，例如 "K231234"；若填寫則優先以此查詢
    applicant: str = ""    # 申請廠商名稱，使用前綴模糊匹配
    keyword1:  str = ""    # 產品主要關鍵字，對應 device_name 欄位
    keyword2:  str = ""    # 產品次要關鍵字（選填），與 keyword1 以 AND 連接
    limit:     int = 30    # 最多回傳筆數，上限為 100（OpenFDA 限制）


@dataclass
class DeviceResult:
    """
    單筆 510(k) 查詢結果。

    原始 API 回傳的 dict 經過正規化後封裝在此，
    並透過 property 提供 UI 渲染所需的衍生欄位。
    """
    # --- 來自 API 的核心欄位 ---
    k_number:      str          # 510(k) 申請號碼，例如 "K231234"
    device_name:   str          # 設備英文名稱
    applicant:     str          # 申請廠商名稱
    product_code:  str          # 三碼 FDA 產品分類代碼，例如 "GZA"
    decision_date: str          # 審查決定日期，已格式化為 YYYY-MM-DD
    pdf_url:       str          # 510(k) Summary PDF 的完整下載網址

    # --- 後處理欄位（有預設值，因為需要額外 API 呼叫才能取得）---
    pdf_available: bool = False  # HEAD request 確認 PDF 是否實際存在
    product_desc:  str  = "未知" # 從 classification 端點查到的設備定義名稱

    @property
    def status_color(self) -> str:
        """依 PDF 可用狀態回傳對應的 CSS 顏色碼，供卡片左邊框使用。"""
        return COLOR_SUCCESS if self.pdf_available else COLOR_WARNING

    @property
    def status_label(self) -> str:
        """依 PDF 可用狀態回傳人類可讀的狀態標籤文字。"""
        return "✅ PDF 已就緒" if self.pdf_available else "⚠️ 無 Summary"

    @property
    def pmn_url(self) -> str:
        """組合 FDA 官方 PMN 說明頁面的完整網址。"""
        return f"{PMN_DETAIL_URL}?ID={self.k_number}"


# ---------------------------------------------------------------------------
# API 層
# ---------------------------------------------------------------------------
# 此區塊只負責「取得與轉換資料」，不涉及任何 UI 邏輯。
# 未來若要換成非同步框架（asyncio/httpx），只需改動此區塊。

def _build_session() -> requests.Session:
    """
    建立並回傳一個設定好 Header 的 HTTP Session 物件。

    使用 Session 的好處：同一查詢批次內的多個請求可複用 TCP 連線，
    減少握手開銷，並統一帶上 User-Agent。
    """
    session = requests.Session()
    session.headers.update(DEFAULT_HTTP_HEADERS)
    return session


def _build_query(params: SearchParams) -> Optional[str]:
    """
    依搜尋參數組裝 OpenFDA Lucene 查詢字串。

    查詢優先級：
      1. 若提供 k_number，直接精確比對，忽略其他條件。
      2. 否則將廠商、主關鍵字、次關鍵字以 AND 串接進行複合篩選。

    Returns
    -------
    str | None
        可用的 query 字串；若無任何有效條件則回傳 None。
    """
    # 優先以 k_number 精確查詢：加上雙引號避免 OpenFDA 做全文分詞
    if params.k_number:
        return f'k_number:"{params.k_number}"'

    # 複合篩選：逐一檢查各欄位，有值才加入條件串列
    parts: list[str] = []

    if params.applicant:
        # chr(34) == '"'，移除使用者輸入中可能夾帶的雙引號，防止查詢語法錯誤
        # 末尾加 * 啟用前綴模糊匹配（prefix query）
        parts.append(f'applicant:{params.applicant.replace(chr(34), "")}*')

    if params.keyword1:
        parts.append(f'device_name:{params.keyword1.replace(chr(34), "")}*')

    if params.keyword2:
        # 次要關鍵字同樣比對 device_name，兩者以 AND 限縮結果
        parts.append(f'device_name:{params.keyword2.replace(chr(34), "")}*')

    # OpenFDA 使用 +AND+ 作為布林 AND 運算子（URL 安全格式）
    return "+AND+".join(parts) if parts else None


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def fetch_product_definition(product_code: str) -> str:
    """
    查詢 OpenFDA classification 端點，取得 product code 的官方設備定義名稱。

    此函式以 @st.cache_data 裝飾，相同 product_code 在快取 TTL 內
    只會發出一次 HTTP 請求，避免對同一代碼重複查詢。

    Parameters
    ----------
    product_code : str
        三碼 FDA product code，例如 "GZA"。

    Returns
    -------
    str
        英文設備定義名稱（device_name）；查無資料或發生錯誤時回傳 "未知"。
    """
    # 防衛性檢查：避免對空值或無效代碼發出無意義的網路請求
    if not product_code or product_code == "未知":
        return "未知"

    try:
        url  = f'{OPENFDA_CLASS_URL}?search=product_code:"{product_code}"'
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()  # 4xx/5xx 狀態碼會拋出 HTTPError

        results = resp.json().get("results", [])
        if results:
            # 取第一筆結果的 device_name，通常一個 product_code 對應一種設備分類
            return results[0].get("device_name", "未知")

    except requests.RequestException as exc:
        # 查詢定義失敗不影響主流程，僅記錄警告後繼續
        logger.warning("fetch_product_definition failed for %s: %s", product_code, exc)

    return "未知"


def _check_pdf_availability(session: requests.Session, pdf_url: str) -> bool:
    """
    以 HTTP HEAD 請求確認指定 URL 的 PDF 檔案是否實際存在。

    使用 HEAD 而非 GET，是因為 HEAD 只取回 HTTP Header，
    不下載檔案本體，節省頻寬並加快速度。

    Parameters
    ----------
    session  : requests.Session  已設定 Header 的 Session 物件。
    pdf_url  : str               要檢查的 PDF 完整 URL。

    Returns
    -------
    bool
        伺服器回應 200 OK 時為 True，否則（404、逾時、連線錯誤）為 False。
    """
    try:
        resp = session.head(pdf_url, timeout=PDF_HEAD_TIMEOUT)
        return resp.status_code == 200
    except requests.RequestException:
        # 任何連線異常都視為「不可用」，不拋出例外以免中斷整批查詢
        return False


def _format_decision_date(raw: str) -> str:
    """
    將 OpenFDA 回傳的 YYYYMMDD 格式日期轉換為人類易讀的 YYYY-MM-DD。

    若格式不符預期（非 8 位純數字），原樣回傳避免資料遺失。
    """
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw  # 格式不明時原樣保留，至少顯示原始值


def _build_pdf_url(k_number: str) -> str:
    """
    依 510(k) 號碼組合 PDF 下載網址。

    FDA 的 PDF 存放路徑規則：
      /cdrh_docs/pdf{YY}/{K_NUMBER}.pdf
    其中 YY 為號碼第 2、3 碼（即年份後兩位），例如 K23xxxx → pdf23/K23xxxx.pdf。
    """
    prefix = k_number[1:3]   # 擷取年份碼，例如 "K231234" → "23"
    return f"{PDF_BASE_URL}{prefix}/{k_number}.pdf"


def fetch_510k_results(params: SearchParams) -> list[DeviceResult]:
    """
    向 OpenFDA 510(k) 端點查詢，並對每筆結果進行後處理，回傳結構化清單。

    後處理步驟（每筆結果）：
      1. 組合 PDF 下載 URL。
      2. 以 HEAD request 確認 PDF 是否可存取。
      3. 查詢 product code 對應的設備定義名稱（有快取）。
      4. 格式化日期。

    最後依「PDF 是否可用」降冪排序，讓可下載的結果排在前面。

    Parameters
    ----------
    params : SearchParams
        使用者搜尋條件。

    Returns
    -------
    list[DeviceResult]
        查詢結果清單；查無資料時回傳空串列。

    Raises
    ------
    ValueError
        未提供任何搜尋條件時拋出，由呼叫端（main）顯示錯誤訊息。
    requests.HTTPError
        API 回傳非 200 且非 404 的狀態碼時拋出。
    """
    # 組裝查詢字串；若無任何條件則提前拋出，避免發出無意義的全量查詢
    query = _build_query(params)
    if not query:
        raise ValueError("至少須填寫一個搜尋條件。")

    url     = f"{OPENFDA_510K_URL}?search={query}&limit={params.limit}"
    session = _build_session()

    resp = session.get(url, timeout=REQUEST_TIMEOUT)

    # OpenFDA 查無資料時回傳 404，這是預期行為，不需視為錯誤
    if resp.status_code == 404:
        return []

    resp.raise_for_status()   # 其他 4xx/5xx 才視為真正的錯誤

    raw_list = resp.json().get("results", [])
    results: list[DeviceResult] = []

    for raw in raw_list:
        k_num   = raw.get("k_number", "N/A")
        pdf_url = _build_pdf_url(k_num)

        results.append(
            DeviceResult(
                k_number      = k_num,
                device_name   = raw.get("device_name", "Unknown"),
                applicant     = raw.get("applicant", "Unknown"),
                product_code  = raw.get("product_code", ""),
                decision_date = _format_decision_date(raw.get("decision_date", "")),
                pdf_url       = pdf_url,
                # 注意：以下兩個欄位需要額外網路請求，是整體速度的主要瓶頸
                pdf_available = _check_pdf_availability(session, pdf_url),
                product_desc  = fetch_product_definition(raw.get("product_code", "")),
            )
        )

    # 將 PDF 可用的結果排到前面，讓使用者優先看到完整資訊
    results.sort(key=lambda r: r.pdf_available, reverse=True)
    return results


# ---------------------------------------------------------------------------
# UI 層
# ---------------------------------------------------------------------------
# 此區塊只負責「畫面渲染」，不包含任何業務邏輯或 API 呼叫。
# 所有 HTML/CSS 字串集中在各自的渲染函式內，便於維護視覺樣式。

def _apply_global_styles() -> None:
    """
    向 Streamlit 注入全域 CSS 樣式表。

    將樣式集中在此函式，避免 CSS 字串散落在各個渲染函式之間，
    也方便日後切換主題或進行設計調整。
    """
    st.markdown(
        """
        <style>
        /* ── 頁面標題區 ── */
        .main-title {
            font-size: 28px; font-weight: 800; color: #1E1E1E;
            text-align: center; margin-bottom: 6px;
        }
        .info-text {
            font-size: 15px; color: #888;
            text-align: center; margin-bottom: 20px;
        }

        /* ── 查詢結果卡片 ── */
        .result-card {
            border-left: 6px solid #ccc;   /* 顏色由 Python 動態覆寫 */
            padding: 16px 18px;
            background: #f8f9fa;
            border-radius: 10px;
            margin-bottom: 15px;
            box-shadow: 2px 2px 6px rgba(0,0,0,0.06);
        }
        /* 卡片左上角的序號標籤 */
        .index-badge {
            background: #4a4a4a; color: #fff;
            padding: 3px 10px; border-radius: 6px;
            font-size: 0.85em; font-weight: 700;
            letter-spacing: 1px; margin-right: 10px;
        }
        /* product code 的等寬字體標籤 */
        .code-label {
            background: #e9ecef; color: #495057;
            padding: 2px 6px; border-radius: 4px;
            font-family: monospace; font-weight: 700; margin-right: 6px;
        }

        /* ── 側邊欄自訂標籤 ── */
        /* Streamlit 原生 label 會造成間距不一致，統一隱藏後用 custom-label 取代 */
        [data-testid="stSidebar"] label { display: none; }
        .custom-label {
            font-size: 0.9rem; color: #31333F;
            display: block; margin-top: 10px; margin-bottom: 3px;
        }
        /* 側邊欄 h2 加粗 */
        [data-testid="stSidebar"] h2 {
            font-size: 1.1rem !important; font-weight: 700 !important;
            margin-bottom: 8px !important;
        }
        /* 收緊側邊欄元件間的垂直間距 */
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.4rem !important; }
        /* 移除 text_input 預設的底部 margin，保持側邊欄緊湊 */
        div.stTextInput { margin-bottom: 0 !important; }
        /* 側邊欄分隔線 */
        .sidebar-divider { margin: 1rem 0; border: 0; border-top: 1px solid #ddd; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_page_header() -> None:
    """渲染頁面頂部的標題與副標題。"""
    st.markdown(
        '<div class="main-title">🩺 FDA 510(k) 查詢工具</div>'
        '<div class="info-text">連線 OpenFDA 資料庫 · 精確欄位篩選</div>',
        unsafe_allow_html=True,
    )


def _render_result_card(index: int, result: DeviceResult) -> None:
    """
    將單筆 DeviceResult 渲染為 HTML 卡片並輸出到頁面。

    Parameters
    ----------
    index  : int           卡片的顯示序號（從 1 開始）。
    result : DeviceResult  已處理完畢的查詢結果資料。
    """
    # 只有 PDF 存在時才產生下載連結 HTML；否則空字串，讓 flex 容器自然收縮
    pdf_link_html = (
        f'<a href="{result.pdf_url}" target="_blank" '
        f'style="color:#d9534f;text-decoration:none;font-weight:600;">📄 下載 PDF</a>'
        if result.pdf_available else ""
    )

    # 卡片 HTML：左邊框顏色、狀態標籤顏色皆由 DeviceResult 的 property 提供，
    # 保持 UI 邏輯與資料邏輯的分離。
    html = f"""
    <div class="result-card" style="border-left-color:{result.status_color};">

        <!-- 卡片標頭：序號 + 510(k) 號碼（左）、狀態標籤（右） -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <div>
                <span class="index-badge">{index:02d}</span>
                <span style="font-size:1.15em;font-weight:800;color:#111;">
                    510(k) 號碼：{result.k_number}
                </span>
            </div>
            <span style="color:{result.status_color};font-weight:700;background:#fff;
                         padding:2px 10px;border-radius:20px;
                         border:1px solid {result.status_color};font-size:0.82em;">
                {result.status_label}
            </span>
        </div>

        <!-- 卡片主體：各欄位資訊 -->
        <div style="margin-bottom:6px;"><b>判定日期：</b>{result.decision_date}</div>
        <div style="margin-bottom:6px;">
            <b>產品代碼與分類：</b>
            <span class="code-label">{result.product_code}</span>
            <span style="color:#555;">{result.product_desc}</span>
        </div>
        <div style="margin-bottom:6px;"><b>設備名稱：</b>{result.device_name}</div>
        <div style="margin-bottom:12px;"><b>申請廠商：</b>{result.applicant}</div>

        <!-- 卡片底部連結列 -->
        <div style="display:flex;gap:16px;">
            <a href="{result.pmn_url}" target="_blank"
               style="color:#007bff;text-decoration:none;font-weight:600;">🌐 官方資訊</a>
            {pdf_link_html}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def _render_sidebar() -> tuple[SearchParams, bool]:
    """
    渲染側邊欄的搜尋表單，收集使用者輸入後打包為 SearchParams 回傳。

    自訂 HTML label（custom-label）取代 Streamlit 原生 label，
    目的是消除不同 widget 之間的預設間距差異，維持視覺一致性。

    Returns
    -------
    (SearchParams, bool)
        - SearchParams：使用者填入的搜尋條件。
        - bool：True 表示使用者點擊了「啟動查詢」按鈕。
    """
    with st.sidebar:
        st.header("搜尋參數設定")

        # ── 區塊 1：精確查詢 ──
        st.markdown('<span class="custom-label">1. 依 510(k) 號碼查詢</span>', unsafe_allow_html=True)
        # .upper() 自動轉大寫，讓使用者不必在意大小寫輸入
        k_number = st.text_input("k_number_input", placeholder="例如：K231234").strip().upper()

        # ── 區塊 2：複合篩選 ──
        st.markdown('<div style="margin-top:18px;"></div>', unsafe_allow_html=True)
        st.markdown('<span class="custom-label">2. 複合篩選條件（模糊查詢）</span>', unsafe_allow_html=True)

        st.markdown('<span class="custom-label">申請廠商</span>', unsafe_allow_html=True)
        applicant = st.text_input("applicant_input", placeholder="例如：Medtronic").strip()

        st.markdown('<span class="custom-label">產品主要關鍵字</span>', unsafe_allow_html=True)
        keyword1 = st.text_input("keyword1_input", placeholder="例如：Bipolar").strip()

        st.markdown('<span class="custom-label">產品次要關鍵字（選填）</span>', unsafe_allow_html=True)
        keyword2 = st.text_input("keyword2_input", placeholder="選填").strip()

        # ── 分隔線 ──
        st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

        # ── 筆數控制 ──
        st.markdown('<span class="custom-label">抓取筆數上限</span>', unsafe_allow_html=True)
        limit = st.slider("limit_slider", min_value=10, max_value=100, value=30, step=10)

        # 查詢觸發按鈕；use_container_width=True 讓按鈕撐滿側邊欄寬度
        submitted = st.button("啟動查詢", use_container_width=True, type="primary")

    # 將各欄位組裝為資料類別，與 UI 邏輯解耦
    params = SearchParams(
        k_number  = k_number,
        applicant = applicant,
        keyword1  = keyword1,
        keyword2  = keyword2,
        limit     = limit,
    )
    return params, submitted


# ---------------------------------------------------------------------------
# 主程式進入點
# ---------------------------------------------------------------------------

def main() -> None:
    """
    應用程式主函式，負責組合 UI 與 API 兩層的執行流程：

    1. 設定頁面基本屬性（標題、圖示、版面）。
    2. 注入全域樣式並渲染頁面標頭。
    3. 渲染側邊欄，取得使用者輸入。
    4. 使用者送出後呼叫 API 層查詢資料。
    5. 依結果渲染卡片，或顯示對應的錯誤訊息。
    """
    # Streamlit 規定 set_page_config 必須是第一個 st.* 呼叫
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")
    _apply_global_styles()
    _render_page_header()

    # 渲染側邊欄並等待使用者輸入；未送出前直接結束此次渲染循環
    params, submitted = _render_sidebar()
    if not submitted:
        return

    # ── 呼叫 API 層，針對不同例外類型給予適切的錯誤提示 ──
    try:
        with st.spinner("正在根據篩選條件檢索 FDA 資料庫…"):
            results = fetch_510k_results(params)

    except ValueError as exc:
        # 使用者輸入問題（例如未填任何條件）→ 顯示錯誤並停止
        st.error(f"輸入錯誤：{exc}")
        return

    except requests.HTTPError as exc:
        # API 回傳非預期的 HTTP 狀態碼 → 提示可能是查詢內容問題
        st.warning(f"API 回傳異常（{exc.response.status_code}），請確認輸入內容是否正確。")
        return

    except requests.RequestException as exc:
        # 網路層錯誤（DNS、連線逾時等）→ 顯示技術性錯誤訊息
        st.error(f"網路連線錯誤：{exc}")
        return

    # ── 渲染查詢結果 ──
    if not results:
        # 查詢成功但無資料（API 回傳 404）→ 顯示友善提示
        st.warning("找不到相符的查詢結果，請確認輸入內容是否正確。")
        return

    st.success(f"搜尋完成：共 {len(results)} 筆資料")

    # enumerate 從 1 開始計數，對應卡片上顯示的序號
    for idx, result in enumerate(results, start=1):
        _render_result_card(idx, result)


# 確保只有直接執行此檔案時才啟動應用程式；
# 被其他模組 import 時不會自動執行（雖然 Streamlit 通常直接執行，這是好習慣）
if __name__ == "__main__":
    main()
