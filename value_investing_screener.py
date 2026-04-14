# ==========================================
# 版本：v1.8
# 日期：2026-04-14
# 更新：新增「被動元件」產業主題
# ==========================================
import streamlit as st
import requests
import urllib3
import pandas as pd
import yfinance as yf
import mplfinance as mpf
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
import re
import json

st.set_page_config(page_title="台股價值選股儀表板", page_icon="📈", layout="wide")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 系統記憶體初始化 (Session State) ---
if 'watchlist' not in st.session_state:
    st.session_state['watchlist'] = []

# 統一使用現代瀏覽器的 User-Agent，避免被當成機器人
CHROME_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

# --- 建立 主題/產業 供應鏈資料庫 ---
THEME_CONCEPTS = {
    "👑 世界第一大廠 (長線護城河)": [ # [v1.7 新增] 匯入您的專屬強勢股名單
        '2330', '3711', '3037', '3443', '3529', 
        '2337', '2408', '2344', '3260', '2313', 
        '2367', '2383', '2308', '3017', '3163', 
        '6442', '3105', '6443'
    ],
    "🔋 被動元件 (MLCC/電阻/電感)": ['2327', '2492', '3026', '2478', '6173', '3357', '2472', '3090'],
    "矽智財與IC設計 (ASIC)": ['3661', '3443', '3035', '6643', '3529'],
    "晶圓代工與先進封裝": ['2330', '3711', '2449'],
    "CoWoS 設備": ['3583', '3131', '6187'],
    "散熱模組 (3D VC/水冷)": ['3017', '3324', '2421', '8996'],
    "銅箔基板 (CCL)": ['2383', '6274', '6213'],
    "印刷電路板 (PCB)": ['2368', '3037', '3044', '2313', '2367'],
    "電源供應器": ['2308', '2301', '6412'],
    "伺服器滑軌": ['2059', '6584'],
    "伺服器機殼": ['8210', '6117', '3013'],
    "伺服器組裝代工 (ODM)": ['2382', '3231', '6669', '2376', '2317', '2356'],
    "矽光子與CPO": ['3081', '3363', '3163', '6442'],
    "🚀 低軌衛星與網通 (LEO)": ['3491', '6285', '2314', '5388', '3380', '3062']
}

# --- 資料抓取與輔助區塊 ---
@st.cache_data(ttl=3600)
def get_twse_stock_data():
    headers = {'User-Agent': CHROME_UA}
    for i in range(10):
        target_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/exchangeReport/BWIBBU_d?response=json&date={target_date}"
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data['stat'] == 'OK':
                    df = pd.DataFrame(data['data'], columns=data['fields'])
                    return df
        except Exception:
            pass
    st.error("連續 10 天都找不到交易資料，可能是證交所網站維護中。")
    return None

@st.cache_data(ttl=86400)
def get_twse_company_profile():
    url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    try:
        response = requests.get(url, verify=False, timeout=10)
        if response.status_code == 200:
            return pd.DataFrame(response.json())
    except Exception as e:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=86400)
def get_company_business_summary_zh(stock_id):
    url = f"https://tw.stock.yahoo.com/quote/{stock_id}/profile"
    headers = {'User-Agent': CHROME_UA}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        match = re.search(r'"businessSummary":"((?:[^"\\]|\\.)*)"', res.text)
        if match:
            return json.loads(f'"{match.group(1)}"')
    except Exception:
        pass
    return None

def translate_to_zh_tw(text):
    if not text or text == '目前無此公司的詳細業務資料。': return text
    url = "https://translate.googleapis.com/translate_a/single"
    params = {"client": "gtx", "sl": "auto", "tl": "zh-TW", "dt": "t", "q": text}
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            result = response.json()
            return "".join([sentence[0] for sentence in result[0] if sentence[0]])
    except Exception:
        pass
    return text

def get_google_news(stock_id, stock_name):
    query = f"{stock_id} {stock_name}"
    url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    news_list = []
    headers = {'User-Agent': CHROME_UA}
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            for item in root.findall('.//channel/item')[:5]:
                title = item.find('title').text
                link = item.find('link').text
                pub_date_str = item.find('pubDate').text
                try:
                    dt = parsedate_to_datetime(pub_date_str)
                    dt_tw = dt + timedelta(hours=8)
                    formatted_date = dt_tw.strftime('%Y-%m-%d %H:%M')
                except:
                    formatted_date = pub_date_str
                news_list.append({"title": title, "link": link, "date": formatted_date})
    except Exception:
        pass
    return news_list

# --- 數據處理區塊 ---
def clean_and_filter_data(df, max_pe, min_yield, max_pb, ignore_fundamentals=False):
    if df is None or df.empty: return None
    target_columns = {'證券代號': '代號', '證券名稱': '名稱', '本益比': '本益比', '殖利率(%)': '殖利率(%)', '股價淨值比': '股價淨值比'}
    try:
        clean_df = df[list(target_columns.keys())].rename(columns=target_columns)
    except KeyError:
        return None
        
    for col in ['本益比', '殖利率(%)', '股價淨值比']:
        clean_df[col] = clean_df[col].replace('-', '0').str.replace(',', '').astype(float)
        
    if ignore_fundamentals:
        return clean_df.sort_values(by='代號')
        
    condition1 = (clean_df['本益比'] > 0) & (clean_df['本益比'] <= max_pe)
    condition2 = (clean_df['殖利率(%)'] >= min_yield)
    condition3 = (clean_df['股價淨值比'] <= max_pb)
    
    return clean_df[condition1 & condition2 & condition3].sort_values(by='殖利率(%)', ascending=False)

@st.cache_data(ttl=300)
def apply_technical_filters(df, req_20ma, req_5d_high, req_macd, req_rsi):
    if df is None or df.empty: return df
    
    stock_ids = df['代號'].tolist()
    if len(stock_ids) > 50:
        st.warning("⚠️ 技術分析單次最高限制 50 檔進行運算。目前僅分析前 50 檔。")
        stock_ids = stock_ids[:50]
        df = df.head(50)

    tickers = [f"{sid}.TW" for sid in stock_ids]
    try:
        data = yf.download(tickers, period="3mo", progress=False, group_by="ticker")
    except Exception as e:
        return df

    if data.empty: return pd.DataFrame()

    passed_stocks = []
    is_multi = isinstance(data.columns, pd.MultiIndex)

    for sid in stock_ids:
        ticker = f"{sid}.TW"
        try:
            if is_multi:
                if ticker not in data.columns.levels[0]: continue
                s_close = data[ticker]['Close'].dropna()
                s_high = data[ticker]['High'].dropna()
            else:
                s_close = data['Close'].dropna()
                s_high = data['High'].dropna()

            if len(s_close) < 30: continue

            latest_close = s_close.iloc[-1]
            pass_all = True

            if req_20ma:
                ma20 = s_close.rolling(20).mean().iloc[-1]
                if latest_close < ma20: pass_all = False
                
            if pass_all and req_5d_high:
                if latest_close < s_close.iloc[-5:].max(): pass_all = False
                
            if pass_all and req_macd:
                macd = s_close.ewm(span=12, adjust=False).mean() - s_close.ewm(span=26, adjust=False).mean()
                if (macd - macd.ewm(span=9, adjust=False).mean()).iloc[-1] <= 0: pass_all = False
                
            if pass_all and req_rsi:
                delta = s_close.diff()
                rs = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean() / (-1 * delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean())
                if (100 - (100 / (1 + rs))).iloc[-1] <= 50: pass_all = False

            if pass_all: passed_stocks.append(sid)
        except Exception:
            continue
    return df[df['代號'].isin(passed_stocks)]

@st.cache_data(ttl=600)
def get_stock_history_cached(ticker):
    stock = yf.Ticker(ticker)
    return stock.history(period="6mo")

def display_stock_analysis(stock_id, selected_stock_name, company_profile_df):
    ticker = f"{stock_id}.TW"
    tab1, tab2, tab3, tab4 = st.tabs(["📈 K線圖", "🏢 核心業務", "📰 近期新聞", "💡 投資建議"])
    global_df = pd.DataFrame() 

    with tab1:
        with st.spinner(f"正在抓取 {stock_id} 歷史股價..."):
            try:
                df = get_stock_history_cached(ticker)
                global_df = df 
                
                if df.empty:
                    st.warning(f"❌ 找不到代號 {stock_id} 的歷史資料，或遭 Yahoo 暫時阻擋。")
                else:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.droplevel(1)
                        
                    ohlcv_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
                    df_chart = df.dropna(subset=ohlcv_cols)
                    df_chart[ohlcv_cols] = df_chart[ohlcv_cols].astype(float)
                    
                    fig, axlist = mpf.plot(
                        df_chart, type='candle', volume=True, style='yahoo',
                        title=f"{stock_id} K-Line (6 Months)",
                        ylabel='Price', ylabel_lower='Volume',
                        returnfig=True, figsize=(8, 4)
                    )
                    st.pyplot(fig)
            except Exception as e:
                st.error(f"K線圖繪製失敗。錯誤訊息: {e}")
                
    with tab2:
        with st.spinner("正在抓取公司資料..."):
            industry = "無提供分類"
            if not company_profile_df.empty:
                company_info = company_profile_df[company_profile_df['公司代號'] == stock_id]
                if not company_info.empty:
                    industry = company_info.iloc[0].get('產業類別', '無提供分類')
                    
            summary_zh = get_company_business_summary_zh(stock_id)
            if not summary_zh:
                try:
                    english_summary = yf.Ticker(ticker).info.get('longBusinessSummary', '目前無此公司的詳細業務資料。')
                    if english_summary != '目前無此公司的詳細業務資料。':
                        translated_summary = translate_to_zh_tw(english_summary)
                        summary_zh = f"*(🤖 已自動由英文翻譯為中文)*\n\n{translated_summary}"
                    else:
                        summary_zh = english_summary
                except:
                    summary_zh = "無法取得公司簡介"
            
            st.markdown(f"**產業類別：** {industry}")
            st.markdown("**主要經營業務：**")
            st.info(summary_zh)
            
    with tab3:
        with st.spinner("正在抓取近期新聞..."):
            news = get_google_news(stock_id, selected_stock_name)
            if news and len(news) > 0:
                for n in news:
                    st.markdown(f"- **[{n['date']}]** [{n['title']}]({n['link']})")
            else:
                st.write("目前沒有找到近期的相關新聞。")
            
    with tab4:
        if not global_df.empty and len(global_df) >= 20:
            close_price = global_df['Close'].iloc[-1]
            ma20 = global_df['Close'].rolling(window=20).mean().iloc[-1]
            half_year_ago_price = global_df['Close'].iloc[0]
            return_rate = ((close_price - half_year_ago_price) / half_year_ago_price) * 100
            
            if isinstance(close_price, pd.Series): close_price = close_price.iloc[0]
            if isinstance(ma20, pd.Series): ma20 = ma20.iloc[0]
            if isinstance(return_rate, pd.Series): return_rate = return_rate.iloc[0]
            
            st.markdown("### 程式量化判斷與簡易回測")
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("最新收盤價", f"{float(close_price):.2f} 元")
            col_b.metric("20日均線(月線)", f"{float(ma20):.2f} 元")
            col_c.metric("過去半年持有績效", f"{float(return_rate):.2f}%", f"{float(return_rate):.2f}%")
            
            st.markdown("---")
            if close_price > ma20:
                st.success("🟢 **策略判定：建議可分批佈局 (偏多)**\n\n此股票目前股價站上月線，代表短期趨勢偏向多方。")
            else:
                st.warning("🟡 **策略判定：建議觀望，等待買點 (整理中)**\n\n目前股價跌破月線，顯示短期資金正在撤出或處於弱勢整理。")
        else:
            st.warning("⚠️ 歷史股價資料不足或載入失敗，無法計算技術指標投資建議。")


# ==========================================
# 網頁主架構與導覽
# ==========================================
st.title("📈 台股全方位選股與深度分析系統")
st.markdown(f"**系統版本：v1.8 (2026-04-14)** | 資料更新時間：**{datetime.now().strftime('%Y-%m-%d')}** (資料來源：台灣證券交易所)")

st.sidebar.title("🧭 系統導覽")
page = st.sidebar.radio("請選擇操作頁面：", ["🔍 策略選股雷達", "⭐ 我的自選股追蹤"])
st.sidebar.markdown("---")

if page == "🔍 策略選股雷達":
    st.sidebar.header("⚙️ 1. 基本面條件")
    max_pe = st.sidebar.slider("本益比 (P/E) 最大值", min_value=5.0, max_value=50.0, value=25.0, step=1.0)
    min_yield = st.sidebar.slider("殖利率 (%) 最小值", min_value=0.0, max_value=15.0, value=2.0, step=0.5)
    max_pb = st.sidebar.slider("股價淨值比 (P/B) 最大值", min_value=0.5, max_value=10.0, value=3.0, step=0.1)

    st.sidebar.markdown("---")
    st.sidebar.header("🤖 2. 熱門產業主題")
    selected_themes = st.sidebar.multiselect("選擇產業類別 (可複選，留空代表全市場)", list(THEME_CONCEPTS.keys()))
    
    ignore_fundamentals = False
    if selected_themes:
        st.sidebar.info("💡 提示：『世界第一大廠』或科技龍頭享有較高溢價，建議勾選下方選項忽略傳統本益比限制。")
        ignore_fundamentals = st.sidebar.checkbox("🔓 忽略基本面條件 (直接分析選取標的)", value=True)

    st.sidebar.markdown("---")
    st.sidebar.header("📈 3. 技術面條件")
    tech_20ma = st.sidebar.checkbox("股價在月線 (20MA) 之上")
    tech_5d_high = st.sidebar.checkbox("股價創 5 日新高")
    tech_macd = st.sidebar.checkbox("MACD 柱狀圖大於 0")
    tech_rsi = st.sidebar.checkbox("RSI (14) 大於 50")

    col1, col2 = st.columns([1, 1.4])

    with col1:
        st.subheader("🎯 篩選結果清單")
        
        with st.spinner('下載並運算數據中...'):
            raw_data = get_twse_stock_data()
            company_profile_df = get_twse_company_profile()
            
        selected_stock_id = ""
        selected_stock_name = ""
        
        if raw_data is not None:
            result_df = clean_and_filter_data(raw_data, max_pe, min_yield, max_pb, ignore_fundamentals)
            
            if result_df is not None and not result_df.empty and selected_themes:
                target_stocks = []
                for theme in selected_themes:
                    target_stocks.extend(THEME_CONCEPTS[theme])
                result_df = result_df[result_df['代號'].isin(set(target_stocks))]
                    
            if result_df is not None and not result_df.empty:
                if any([tech_20ma, tech_5d_high, tech_macd, tech_rsi]):
                    with st.spinner('分析歷史線圖與指標...'):
                        result_df = apply_technical_filters(result_df, tech_20ma, tech_5d_high, tech_macd, tech_rsi)

            if result_df is not None and not result_df.empty:
                st.success(f"共找到 **{len(result_df)}** 檔股票。")
                selection_event = st.dataframe(
                    result_df, use_container_width=True, hide_index=True, height=600,
                    on_select="rerun", selection_mode="single-row"
                )
                if len(selection_event.selection.rows) > 0:
                    selected_idx = selection_event.selection.rows[0]
                    selected_stock_id = result_df.iloc[selected_idx]['代號']
                    selected_stock_name = result_df.iloc[selected_idx]['名稱']
            else:
                st.warning("目前沒有符合條件的股票。")

    with col2:
        st.subheader("📊 個股深度分析")
        stock_id = st.text_input("輸入股票代號：", value=selected_stock_id, max_chars=10)
        
        if stock_id:
            btn_col1, btn_col2 = st.columns([1, 2])
            with btn_col1:
                if stock_id not in st.session_state['watchlist']:
                    if st.button(f"⭐ 將 {stock_id} 加入自選", type="primary"):
                        st.session_state['watchlist'].append(stock_id)
                        st.rerun()
                else:
                    if st.button(f"❌ 將 {stock_id} 移出自選"):
                        st.session_state['watchlist'].remove(stock_id)
                        st.rerun()
            display_stock_analysis(stock_id, selected_stock_name, company_profile_df)

elif page == "⭐ 我的自選股追蹤":
    st.subheader("⭐ 我的專屬自選股追蹤庫")
    
    if not st.session_state['watchlist']:
        st.info("📂 您的自選清單目前為空！請前往左側導覽切換至「🔍 策略選股雷達」，在「🤖 2. 熱門產業主題」中選擇「👑 世界第一大廠 (長線護城河)」來挑選標的。")
    else:
        with st.spinner('正在為您的自選股更新今日最新數據...'):
            raw_data = get_twse_stock_data()
            company_profile_df = get_twse_company_profile()
            
        wl_df = pd.DataFrame()
        if raw_data is not None:
            target_columns = {'證券代號': '代號', '證券名稱': '名稱', '本益比': '本益比', '殖利率(%)': '殖利率(%)', '股價淨值比': '股價淨值比'}
            try:
                clean_df = raw_data[list(target_columns.keys())].rename(columns=target_columns)
                for col in ['本益比', '殖利率(%)', '股價淨值比']:
                    clean_df[col] = clean_df[col].replace('-', '0').str.replace(',', '').astype(float)
                wl_df = clean_df[clean_df['代號'].isin(st.session_state['watchlist'])].sort_values(by='代號')
            except Exception as e:
                pass
                
        col1, col2 = st.columns([1, 1.4])
        
        with col1:
            st.write(f"目前共追蹤 **{len(st.session_state['watchlist'])}** 檔股票：")
            if not wl_df.empty:
                selection_event_wl = st.dataframe(
                    wl_df, use_container_width=True, hide_index=True, height=600,
                    on_select="rerun", selection_mode="single-row"
                )
                
                selected_stock_id_wl = ""
                selected_stock_name_wl = ""
                if len(selection_event_wl.selection.rows) > 0:
                    selected_idx = selection_event_wl.selection.rows[0]
                    selected_stock_id_wl = wl_df.iloc[selected_idx]['代號']
                    selected_stock_name_wl = wl_df.iloc[selected_idx]['名稱']
            else:
                st.warning("無法載入自選股最新報價資料。")
                
        with col2:
            if selected_stock_id_wl:
                st.subheader(f"📊 {selected_stock_id_wl} 追蹤分析")
                if st.button(f"❌ 從自選庫中刪除 {selected_stock_id_wl}", type="secondary"):
                    st.session_state['watchlist'].remove(selected_stock_id_wl)
                    st.rerun()
                display_stock_analysis(selected_stock_id_wl, selected_stock_name_wl, company_profile_df)
