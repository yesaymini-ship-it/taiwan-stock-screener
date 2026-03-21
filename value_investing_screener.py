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

# ==========================================
# 網頁版選股系統 (使用 Streamlit)
# ==========================================

st.set_page_config(page_title="台股價值選股儀表板", page_icon="📈", layout="wide")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 資料抓取與輔助區塊 ---

@st.cache_data(ttl=3600)
def get_twse_stock_data():
    """從台灣證券交易所抓取基本面數據"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
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
        print(f"取得公司資料失敗: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=86400)
def get_company_business_summary_zh(stock_id):
    url = f"https://tw.stock.yahoo.com/quote/{stock_id}/profile"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        match = re.search(r'"businessSummary":"((?:[^"\\]|\\.)*)"', res.text)
        if match:
            return json.loads(f'"{match.group(1)}"')
    except Exception:
        pass
    return None

def translate_to_zh_tw(text):
    if not text or text == '目前無此公司的詳細業務資料。':
        return text
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
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
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

# --- 數據處理區塊 (基本面 + 技術面) ---

def clean_and_filter_data(df, max_pe, min_yield, max_pb):
    if df is None or df.empty: return None
    target_columns = {'證券代號': '代號', '證券名稱': '名稱', '本益比': '本益比', '殖利率(%)': '殖利率(%)', '股價淨值比': '股價淨值比'}
    try:
        clean_df = df[list(target_columns.keys())].rename(columns=target_columns)
    except KeyError:
        return None
        
    for col in ['本益比', '殖利率(%)', '股價淨值比']:
        clean_df[col] = clean_df[col].replace('-', '0').str.replace(',', '').astype(float)
        
    condition1 = (clean_df['本益比'] > 0) & (clean_df['本益比'] <= max_pe)
    condition2 = (clean_df['殖利率(%)'] >= min_yield)
    condition3 = (clean_df['股價淨值比'] <= max_pb)
    
    return clean_df[condition1 & condition2 & condition3].sort_values(by='殖利率(%)', ascending=False)

@st.cache_data(ttl=300)
def apply_technical_filters(df, req_20ma, req_5d_high, req_macd, req_rsi):
    """執行技術分析運算"""
    if df is None or df.empty: return df
    
    stock_ids = df['代號'].tolist()
    if len(stock_ids) > 200:
        st.warning("⚠️ 符合基本面的股票過多。為維持連線速度，技術分析僅取前 200 檔進行運算。建議縮緊基本面條件！")
        stock_ids = stock_ids[:200]
        df = df.head(200)

    tickers = [f"{sid}.TW" for sid in stock_ids]
    try:
        # 批次下載歷史股價，group_by="ticker" 可確保資料結構穩定
        data = yf.download(tickers, period="3mo", progress=False, group_by="ticker")
    except Exception as e:
        st.error(f"下載技術線圖資料時發生錯誤: {e}")
        return df

    if data.empty: return pd.DataFrame()

    passed_stocks = []
    is_multi = isinstance(data.columns, pd.MultiIndex)

    for sid in stock_ids:
        ticker = f"{sid}.TW"
        try:
            # 提取單一股票的收盤價與最高價
            if is_multi:
                if ticker not in data.columns.levels[0]: continue
                s_close = data[ticker]['Close'].dropna()
                s_high = data[ticker]['High'].dropna()
            else:
                s_close = data['Close'].dropna()
                s_high = data['High'].dropna()

            if len(s_close) < 30: # 資料太少無法算月線
                continue

            latest_close = s_close.iloc[-1]
            pass_all = True

            # 1. 月線 (20MA) 條件
            if req_20ma:
                ma20 = s_close.rolling(20).mean().iloc[-1]
                if latest_close < ma20:
                    pass_all = False

            # 2. 創 5 日新高條件
            if pass_all and req_5d_high:
                recent_5d_high = s_high.iloc[-5:].max()
                if latest_close < recent_5d_high:
                    pass_all = False

            # 3. MACD 多頭條件 (柱狀圖 > 0)
            if pass_all and req_macd:
                ema12 = s_close.ewm(span=12, adjust=False).mean()
                ema26 = s_close.ewm(span=26, adjust=False).mean()
                macd = ema12 - ema26
                signal = macd.ewm(span=9, adjust=False).mean()
                hist = macd - signal
                if hist.iloc[-1] <= 0:
                    pass_all = False

            # 4. RSI(14) 強勢條件 (> 50)
            if pass_all and req_rsi:
                delta = s_close.diff()
                gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
                loss = -1 * delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                if rsi.iloc[-1] <= 50:
                    pass_all = False

            if pass_all:
                passed_stocks.append(sid)

        except Exception:
            continue

    return df[df['代號'].isin(passed_stocks)]

# ==========================================
# 網頁介面 (UI) 設計區塊
# ==========================================

st.title("📈 台股價值選股與深度分析系統")
st.markdown(f"資料更新時間：**{datetime.now().strftime('%Y-%m-%d')}** (資料來源：台灣證券交易所)")

# --- 側邊欄設定 ---
st.sidebar.header("⚙️ 1. 基本面條件 (尋找好公司)")
max_pe = st.sidebar.slider("本益比 (P/E) 最大值", min_value=5.0, max_value=30.0, value=15.0, step=0.5)
min_yield = st.sidebar.slider("殖利率 (%) 最小值", min_value=0.0, max_value=15.0, value=4.0, step=0.5)
max_pb = st.sidebar.slider("股價淨值比 (P/B) 最大值", min_value=0.5, max_value=5.0, value=1.5, step=0.1)

st.sidebar.markdown("---")
st.sidebar.header("📈 2. 技術面條件 (尋找進場點)")
st.sidebar.caption("提示：啟用此功能會即時分析股票歷史線圖，需要數秒鐘運算時間。")
tech_20ma = st.sidebar.checkbox("股價在月線 (20MA) 之上", help="確保股票處於中長期上漲趨勢")
tech_5d_high = st.sidebar.checkbox("股價創 5 日新高", help="短線買盤強烈，動能強勁")
tech_macd = st.sidebar.checkbox("MACD 柱狀圖大於 0 (多頭)", help="短線趨勢強過長線趨勢")
tech_rsi = st.sidebar.checkbox("RSI (14) 大於 50 (轉強)", help="買方力道大於賣方力道")

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("🎯 符合條件的股票清單")
    st.info("💡 **操作提示：點擊下方表格中的任意一列**，右側將自動顯示詳細分析！")
    
    with st.spinner('正在從證交所下載並運算最新數據...'):
        raw_data = get_twse_stock_data()
        company_profile_df = get_twse_company_profile()
        
    selected_stock_id = ""
    selected_stock_name = ""
    
    if raw_data is not None:
        # 第一層篩選：基本面
        result_df = clean_and_filter_data(raw_data, max_pe, min_yield, max_pb)
        
        # 第二層篩選：技術面 (如果有勾選任何一項)
        if result_df is not None and not result_df.empty:
            if any([tech_20ma, tech_5d_high, tech_macd, tech_rsi]):
                with st.spinner('正在分析歷史線圖與技術指標 (MACD/RSI/MA)...'):
                    result_df = apply_technical_filters(result_df, tech_20ma, tech_5d_high, tech_macd, tech_rsi)

        if result_df is not None and not result_df.empty:
            st.success(f"篩選完成！共找到 **{len(result_df)}** 檔股票符合條件。")
            
            selection_event = st.dataframe(
                result_df,
                use_container_width=True,
                hide_index=True,
                height=600,
                on_select="rerun",
                selection_mode="single-row"
            )
            
            if len(selection_event.selection.rows) > 0:
                selected_idx = selection_event.selection.rows[0]
                selected_stock_id = result_df.iloc[selected_idx]['代號']
                selected_stock_name = result_df.iloc[selected_idx]['名稱']
        else:
            st.warning("目前沒有符合條件的股票，請嘗試在左側放寬標準。")
    else:
        st.error("無法取得證交所資料。")

with col2:
    st.subheader("📊 個股深度分析")
    
    stock_id = st.text_input("目前分析的股票代號 (可手動修改)：", value=selected_stock_id, max_chars=10)
    
    if stock_id:
        with st.spinner(f"正在抓取 {stock_id} 的各項數據與中文新聞..."):
            try:
                ticker = f"{stock_id}.TW"
                stock = yf.Ticker(ticker)
                df = stock.history(period="6mo")
                
                if df.empty:
                    st.error(f"❌ 找不到代號 {stock_id} 的歷史資料。")
                else:
                    ohlcv_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
                    df = df.dropna(subset=ohlcv_cols)
                    df[ohlcv_cols] = df[ohlcv_cols].astype(float)
                    
                    fig, axlist = mpf.plot(
                        df, type='candle', volume=True, style='yahoo',
                        title=f"{stock_id} K-Line (6 Months)",
                        ylabel='Price', ylabel_lower='Volume',
                        returnfig=True, figsize=(8, 4)
                    )
                    st.pyplot(fig)
                    
                    tab1, tab2, tab3 = st.tabs(["🏢 1. 核心業務", "📰 2. 近期新聞", "💡 3. 投資建議"])
                    
                    with tab1:
                        industry = "無提供分類"
                        if not company_profile_df.empty:
                            company_info = company_profile_df[company_profile_df['公司代號'] == stock_id]
                            if not company_info.empty:
                                industry = company_info.iloc[0].get('產業類別', '無提供分類')
                                
                        summary_zh = get_company_business_summary_zh(stock_id)
                        
                        if not summary_zh:
                            info = stock.info
                            english_summary = info.get('longBusinessSummary', '目前無此公司的詳細業務資料。')
                            if english_summary != '目前無此公司的詳細業務資料。':
                                translated_summary = translate_to_zh_tw(english_summary)
                                summary_zh = f"*(🤖 已自動由英文翻譯為中文)*\n\n{translated_summary}"
                            else:
                                summary_zh = english_summary
                        
                        st.markdown(f"**產業類別：** {industry}")
                        st.markdown("**主要經營業務：**")
                        st.info(summary_zh)
                            
                    with tab2:
                        news = get_google_news(stock_id, selected_stock_name)
                        if news and len(news) > 0:
                            for n in news:
                                st.markdown(f"- **[{n['date']}]** [{n['title']}]({n['link']})")
                        else:
                            st.write("目前沒有找到近期的相關新聞。")
                            
                    with tab3:
                        close_price = df['Close'].iloc[-1]
                        ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
                        
                        st.markdown("### 程式量化判斷結果")
                        st.write(f"**最新收盤價：** {close_price:.2f} 元")
                        st.write(f"**20日均線(月線)：** {ma20:.2f} 元")
                        
                        if close_price > ma20:
                            st.success(
                                "🟢 **策略判定：建議可分批佈局 (偏多)**\n\n"
                                "此股票已經通過您左側嚴格的基本面篩選，"
                                "且目前股價 **站上月線**，代表短期趨勢偏向多方。兼具基本面保護與技術面動能，是不錯的觀察標的！"
                            )
                        else:
                            st.warning(
                                "🟡 **策略判定：建議觀望，等待買點 (整理中)**\n\n"
                                "雖然此股票的基本面（殖利率、本益比）優良，"
                                "但目前股價 **跌破月線**，顯示短期資金正在撤出或處於弱勢整理。"
                                "建議加入自選股名單，等待未來帶量突破月線時再行進場，資金運用效率會更好。"
                            )
                        
                        st.caption("免責聲明：以上建議僅依據歷史數據與均線公式自動運算，不構成實際投資建議，投資請審慎評估風險。")
                        
            except Exception as e:
                st.error(f"分析時發生錯誤: {e}")
