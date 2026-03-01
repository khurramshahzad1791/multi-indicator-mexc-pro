import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time

st.set_page_config(page_title="MEXC PRO Scanner", layout="wide", page_icon="🚀")
st.title("🚀 MEXC PRO Scanner - Best 100x Signals")
st.warning("⚠️ 100x = EXTREME RISK. Max 0.5% risk per trade. Not financial advice.")

# Settings
st.sidebar.header("Settings")
symbols = ["BTC/USDT:USDT","ETH/USDT:USDT","SOL/USDT:USDT","XRP/USDT:USDT","DOGE/USDT:USDT","PEPE/USDT:USDT","SHIB/USDT:USDT","SUI/USDT:USDT","TON/USDT:USDT","BNB/USDT:USDT","ADA/USDT:USDT","LINK/USDT:USDT","AVAX/USDT:USDT","TRX/USDT:USDT","WIF/USDT:USDT","GOLD/XAUT:USDT"]
tf_options = {"5m":"5m","15m":"15m","30m":"30m","1h":"1h","4h":"4h","Daily":"1d","Weekly":"1w"}
tf_display = st.sidebar.selectbox("Timeframe", list(tf_options.keys()), index=3)
tf = tf_options[tf_display]
a1_mode = st.sidebar.checkbox("A1 Setups Only (Highest Probability)", value=True)
refresh_sec = st.sidebar.slider("Refresh every (seconds)", 20, 60, 30)

# Functions (same powerful VSI logic)
def get_data(ex, sym, timeframe, limit=200):
    ohlcv = ex.fetch_ohlcv(sym, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['ts','o','h','l','c','v'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms')
    return df

def calculate_indicators(df):
    df = df.copy()
    df['ema9'] = df['c'].ewm(span=9).mean()
    df['ema21'] = df['c'].ewm(span=21).mean()
    df['ema200'] = df['c'].ewm(span=200).mean()
    df['vol_avg'] = df['v'].rolling(20).mean()
    df['vol_surge'] = (df['v'] > df['vol_avg'] * (3.5 if a1_mode else 2.5)) & (df['v'] > df['v'].shift())
    delta = df['c'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + gain/loss))
    macd = df['c'].ewm(span=12).mean() - df['c'].ewm(span=26).mean()
    df['macd_hist'] = macd - macd.ewm(span=9).mean()
    bb_mid = df['c'].rolling(20).mean()
    bb_std = df['c'].rolling(20).std()
    df['bb_width'] = (bb_mid + 2*bb_std - (bb_mid - 2*bb_std)) / bb_mid
    df['bb_exp'] = df['bb_width'] > df['bb_width'].rolling(20).mean()
    # SuperTrend
    hl2 = (df['h'] + df['l'])/2
    tr = pd.concat([df['h']-df['l'], (df['h']-df['c'].shift()).abs(), (df['l']-df['c'].shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(10).mean()
    df['upper'] = hl2 + 3*atr
    df['lower'] = hl2 - 3*atr
    df['trend'] = True
    for i in range(1, len(df)):
        if df['c'].iloc[i] > df['upper'].iloc[i-1]: df.loc[df.index[i],'trend'] = True
        elif df['c'].iloc[i] < df['lower'].iloc[i-1]: df.loc[df.index[i],'trend'] = False
        else: df.loc[df.index[i],'trend'] = df['trend'].iloc[i-1]
    df['st'] = np.where(df['trend'], df['lower'], df['upper'])
    return df

def get_signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    cond_long = last['vol_surge'] and last['ema9']>last['ema21'] and prev['ema9']<=prev['ema21'] and last['trend'] and last['rsi']>(58 if a1_mode else 55) and last['macd_hist']>0 and last['bb_exp'] and last['c']>last['ema200']
    cond_short = last['vol_surge'] and last['ema9']<last['ema21'] and prev['ema9']>=prev['ema21'] and not last['trend'] and last['rsi']<(42 if a1_mode else 45) and last['macd_hist']<0 and last['bb_exp'] and last['c']<last['ema200']
    if cond_long: return "A1 LONG" if a1_mode else "LONG", "#00FF00", last['c']
    if cond_short: return "A1 SHORT" if a1_mode else "SHORT", "#FF0000", last['c']
    return "WAIT", "#AAAAAA", last['c']

exchange = ccxt.mexc({'enableRateLimit': True})
results = {}
hot = []

progress = st.progress(0)
for i, sym in enumerate(symbols):
    try:
        df = get_data(exchange, sym, tf)
        df = calculate_indicators(df)
        sig, col, price = get_signal(df)
        results[sym] = {"price":price, "sig":sig, "col":col}
        if sig != "WAIT":
            hot.append((sym.replace("/USDT:USDT",""), sig, col, price))
    except:
        pass
    progress.progress(int((i+1)/len(symbols)*100))

# HOT SIGNALS
st.subheader("🔥 Hot Signals (Ready to Trade Now)")
if hot:
    cols = st.columns(len(hot))
    for idx, (s, sig, colr, pr) in enumerate(hot):
        with cols[idx]:
            st.markdown(f"<h3 style='color:{colr};text-align:center'>{s}<br>{sig}</h3>", unsafe_allow_html=True)
            st.metric("", f"${pr:,.4f}")
else:
    st.info("No hot signals right now — waiting for strong volume surge.")

# ALL PAIRS TABLE
st.subheader("All Pairs Scanner")
data = [{"Coin": k.replace("/USDT:USDT",""), "Price": f"${v['price']:,.4f}", "Signal": f"<span style='color:{v['col']};font-weight:bold'>{v['sig']}</span>"} for k,v in results.items()]
st.markdown(pd.DataFrame(data).to_html(escape=False, index=False), unsafe_allow_html=True)

# DETAILED CHART
st.subheader("📊 Tap a coin below for full chart + levels")
selected = st.selectbox("Select Coin", [k.replace("/USDT:USDT","") for k in symbols])
full_sym = selected + "/USDT:USDT"

if full_sym in results:
    df = get_data(exchange, full_sym, tf)
    df = calculate_indicators(df)
    sig, col, price = get_signal(df)
    fig = go.Figure(data=[go.Candlestick(x=df['ts'][-100:], open=df['o'][-100:], high=df['h'][-100:], low=df['l'][-100:], close=df['c'][-100:])])
    fig.add_trace(go.Scatter(x=df['ts'][-100:], y=df['ema9'][-100:], name="EMA9", line=dict(color="lime")))
    fig.add_trace(go.Scatter(x=df['ts'][-100:], y=df['ema21'][-100:], name="EMA21", line=dict(color="red")))
    fig.add_trace(go.Scatter(x=df['ts'][-100:], y=df['st'][-100:], name="SuperTrend", line=dict(color="purple", width=3)))
    fig.update_layout(title=f"{selected} {tf_display} — {sig}", height=500)
    st.plotly_chart(fig, use_container_width=True)

    if sig != "WAIT":
        sl = price * (1 - 0.004) if "LONG" in sig else price * (1 + 0.004)
        tp1 = price * (1 + 0.01) if "LONG" in sig else price * (1 - 0.01)
        tp2 = price * (1 + 0.02) if "LONG" in sig else price * (1 - 0.02)
        st.success(f"**ENTRY NOW** | **SL**: {sl:,.4f} | **TP1 (50%)**: {tp1:,.4f} | **TP2**: {tp2:,.4f}")

st.caption(f"Last update: {datetime.now().strftime('%H:%M:%S')} • Auto-refresh {refresh_sec}s • A1 = strictest high-probability only")
time.sleep(refresh_sec)
st.rerun()
