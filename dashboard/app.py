"""
dashboard/app.py
~~~~~~~~~~~~~~~~
Real-time Streamlit dashboard.

Panels:
  - Live price chart with all indicators overlaid
  - ML confidence + signal panel
  - Sentiment gauges
  - Open positions + P&L table
  - Cross-asset heatmap
  - Backtest metrics summary
  - Trade journal

Run: streamlit run dashboard/app.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import settings

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ETH Trading Bot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .metric-card {background:#1a1a2e;border-radius:8px;padding:12px;margin:4px;}
    .positive {color:#00ff88;}
    .negative {color:#ff4444;}
    .neutral  {color:#aaaaaa;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Bot Config")
    symbol = st.selectbox("Symbol", ["ETHUSDT", "BTCUSDT"], index=0)
    timeframe = st.selectbox("Chart Timeframe", ["1h", "4h", "1d"], index=0)
    auto_refresh = st.checkbox("Auto-refresh (60s)", value=True)
    refresh_btn = st.button("Refresh Now")

    st.markdown("---")
    st.markdown("**Risk Settings**")
    st.markdown(f"Max risk / trade: `{settings.max_risk_pct*100:.1f}%`")
    st.markdown(f"Daily DD limit: `{settings.max_daily_drawdown*100:.1f}%`")
    st.markdown(f"Total DD limit: `{settings.max_total_drawdown*100:.1f}%`")
    st.markdown(f"Max trades: `{settings.max_concurrent_trades}`")
    st.markdown(f"ML threshold: `{settings.ml_confidence_threshold}`")
    st.markdown(f"Paper trading: `{settings.paper_trading}`")

# ─── Data loaders ─────────────────────────────────────────────────────────────


@st.cache_data(ttl=60)
def load_ohlcv(sym: str, tf: str) -> pd.DataFrame:
    """Pull recent OHLCV synchronously via requests (dashboard is sync)."""
    import requests

    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": sym, "interval": tf, "limit": 500}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        cols = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades",
            "taker_base", "taker_quote", "_",
        ]
        df = pd.DataFrame(resp.json(), columns=cols)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        for c in ["open", "high", "low", "close", "volume", "quote_vol"]:
            df[c] = df[c].astype(float)
        df["trades"] = df["trades"].astype(int)
        return df.set_index("open_time")
    except Exception as exc:
        st.warning(f"OHLCV fetch failed: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def load_indicators(sym: str, tf: str) -> pd.DataFrame:
    df = load_ohlcv(sym, tf)
    if df.empty:
        return df
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from indicators import compute_all_indicators
        return compute_all_indicators(df)
    except Exception as exc:
        st.warning(f"Indicator computation failed: {exc}")
        return df


@st.cache_data(ttl=30)
def load_cross_asset() -> Dict:
    import requests
    try:
        fg = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5).json()
        fear_greed = int(fg["data"][0]["value"])
        label = fg["data"][0]["value_classification"]
    except Exception:
        fear_greed, label = 50, "Neutral"

    try:
        cg = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin,ethereum", "vs_currencies": "usd"},
            timeout=5,
        ).json()
        btc = cg.get("bitcoin", {}).get("usd", 0)
        eth = cg.get("ethereum", {}).get("usd", 0)
    except Exception:
        btc, eth = 0, 0

    try:
        dom = requests.get("https://api.coingecko.com/api/v3/global", timeout=5).json()
        btc_dom = dom["data"]["market_cap_percentage"].get("btc", 0)
    except Exception:
        btc_dom = 0

    return {
        "fear_greed": fear_greed,
        "fear_greed_label": label,
        "btc_usd": btc,
        "eth_usd": eth,
        "btc_dominance": btc_dom,
    }


def load_trade_journal() -> List[Dict]:
    path = Path(__file__).parent.parent / "logs" / "trades.jsonl"
    if not path.exists():
        return []
    trades = []
    try:
        with open(path) as f:
            for line in f:
                trades.append(json.loads(line.strip()))
    except Exception:
        pass
    return trades


def load_backtest_report() -> Dict:
    path = Path(__file__).parent.parent / "logs" / "backtest_report.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


# ─── Chart builders ───────────────────────────────────────────────────────────


def make_candlestick_chart(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.60, 0.20, 0.20],
        subplot_titles=["Price + Indicators", "Volume", "RSI"],
    )

    # ── Candlesticks ──────────────────────────────────────────────────────────
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"], high=df["high"],
            low=df["low"], close=df["close"],
            name="Price", showlegend=False,
        ),
        row=1, col=1,
    )

    # ── EMAs ─────────────────────────────────────────────────────────────────
    ema_colors = {9: "#ff9900", 21: "#00bfff", 50: "#ff69b4", 200: "#ffffff"}
    for p, color in ema_colors.items():
        col = f"ema_{p}"
        if col in df.columns:
            fig.add_trace(
                go.Scatter(x=df.index, y=df[col], name=f"EMA{p}",
                           line=dict(color=color, width=1), opacity=0.8),
                row=1, col=1,
            )

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    for col, dash in [("bb_upper", "dot"), ("bb_mid", "solid"), ("bb_lower", "dot")]:
        if col in df.columns:
            fig.add_trace(
                go.Scatter(x=df.index, y=df[col], name=col,
                           line=dict(color="#888888", width=1, dash=dash), opacity=0.5),
                row=1, col=1,
            )

    # ── VWAP ─────────────────────────────────────────────────────────────────
    if "vwap" in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df["vwap"], name="VWAP",
                       line=dict(color="#ffff00", width=1.5, dash="dash")),
            row=1, col=1,
        )

    # ── SuperTrend ────────────────────────────────────────────────────────────
    if "supertrend" in df.columns and "supertrend_dir" in df.columns:
        bull = df[df["supertrend_dir"] == 1]
        bear = df[df["supertrend_dir"] == -1]
        fig.add_trace(
            go.Scatter(x=bull.index, y=bull["supertrend"], mode="markers",
                       marker=dict(color="green", size=3), name="ST Bull"),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(x=bear.index, y=bear["supertrend"], mode="markers",
                       marker=dict(color="red", size=3), name="ST Bear"),
            row=1, col=1,
        )

    # ── Volume ────────────────────────────────────────────────────────────────
    colors = ["green" if c >= o else "red" for o, c in zip(df["open"], df["close"])]
    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], name="Volume",
               marker_color=colors, opacity=0.7, showlegend=False),
        row=2, col=1,
    )
    if "vol_ma" in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df["vol_ma"], name="Vol MA",
                       line=dict(color="orange", width=1)),
            row=2, col=1,
        )

    # ── RSI ───────────────────────────────────────────────────────────────────
    if "rsi_14" in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df["rsi_14"], name="RSI(14)",
                       line=dict(color="#ff69b4", width=1.5)),
            row=3, col=1,
        )
        fig.add_hline(y=70, line=dict(color="red", dash="dot", width=1), row=3, col=1)
        fig.add_hline(y=30, line=dict(color="green", dash="dot", width=1), row=3, col=1)
        fig.add_hline(y=50, line=dict(color="gray", dash="dot", width=1), row=3, col=1)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0d0d0d",
        plot_bgcolor="#0d0d0d",
        height=800,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02, x=0, font=dict(size=10)),
        margin=dict(l=50, r=20, t=40, b=20),
    )
    return fig


def make_sentiment_gauge(score: float, title: str = "Sentiment") -> go.Figure:
    color = "green" if score > 0.2 else ("red" if score < -0.2 else "gray")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score * 100,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": title, "font": {"size": 14}},
        gauge={
            "axis": {"range": [-100, 100]},
            "bar": {"color": color},
            "steps": [
                {"range": [-100, -20], "color": "#2d0000"},
                {"range": [-20, 20], "color": "#1a1a1a"},
                {"range": [20, 100], "color": "#002d00"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 2},
                "thickness": 0.75,
                "value": score * 100,
            },
        },
    ))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0d0d0d",
        height=200,
        margin=dict(l=10, r=10, t=30, b=10),
    )
    return fig


# ─── Main layout ──────────────────────────────────────────────────────────────


def main() -> None:
    st.title("📈 ETH Algorithmic Trading Bot — Live Dashboard")

    if auto_refresh:
        time.sleep(0)  # placeholder; real refresh via st.rerun below
        st_autorefresh = st.empty()

    cross = load_cross_asset()
    df = load_indicators(symbol, timeframe)

    # ── Top KPIs ─────────────────────────────────────────────────────────────
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        eth_price = cross.get("eth_usd", 0)
        st.metric("ETH/USDT", f"${eth_price:,.2f}")
    with col2:
        st.metric("BTC/USDT", f"${cross.get('btc_usd', 0):,.2f}")
    with col3:
        st.metric("BTC Dominance", f"{cross.get('btc_dominance', 0):.1f}%")
    with col4:
        fg = cross.get("fear_greed", 50)
        st.metric("Fear & Greed", f"{fg} — {cross.get('fear_greed_label', '')}")
    with col5:
        if not df.empty and "rsi_14" in df.columns:
            rsi = df["rsi_14"].iloc[-1]
            st.metric("RSI (14)", f"{rsi:.1f}", delta=f"{rsi - df['rsi_14'].iloc[-2]:.2f}" if len(df) > 1 else None)
    with col6:
        if not df.empty and "atr" in df.columns:
            atr = df["atr"].iloc[-1]
            st.metric("ATR", f"${atr:.2f}")

    st.markdown("---")

    # ── Main chart ────────────────────────────────────────────────────────────
    col_chart, col_signals = st.columns([3, 1])
    with col_chart:
        st.subheader(f"{symbol} — {timeframe}")
        if not df.empty:
            fig = make_candlestick_chart(df.tail(200))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No chart data available")

    with col_signals:
        st.subheader("Indicators")
        if not df.empty:
            latest = df.iloc[-1]
            indicators_status = {
                "EMA 9>21": latest.get("ema_9", 0) > latest.get("ema_21", 0),
                "EMA 21>50": latest.get("ema_21", 0) > latest.get("ema_50", 0),
                "Above EMA200": latest.get("close", 0) > latest.get("ema_200", 0),
                "RSI > 50": latest.get("rsi_14", 50) > 50,
                "Above VWAP": latest.get("price_above_vwap", 0) == 1,
                "SuperTrend Bull": latest.get("supertrend_bull", 0) == 1,
                "Volume Spike": latest.get("vol_spike", 0) == 1,
                "ADX Strong": latest.get("adx", 0) > 25,
                "OBV Trend Up": latest.get("obv_trend", 0) == 1,
                "CMF > 0": latest.get("cmf", 0) > 0,
                "BB %B < 0.5": latest.get("bb_pct_b", 0.5) < 0.5,
            }
            bull_count = sum(1 for v in indicators_status.values() if v)
            bear_count = len(indicators_status) - bull_count
            st.markdown(f"**Bullish: {bull_count} / Bearish: {bear_count}**")
            for name, is_bull in indicators_status.items():
                icon = "🟢" if is_bull else "🔴"
                st.markdown(f"{icon} {name}")

        st.markdown("---")
        st.subheader("ML Prediction")
        ml_path = Path(__file__).parent.parent / "models" / "ensemble.pkl"
        if ml_path.exists():
            st.success("Model loaded ✓")
            # Show last prediction if cached
            try:
                import redis
                r = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
                pred_raw = r.get("latest_prediction")
                if pred_raw:
                    pred = json.loads(pred_raw)
                    conf = pred.get("confidence", 0)
                    direction = pred.get("direction", "—")
                    color = "green" if direction == "long" else "red"
                    st.markdown(f"Direction: **:{color}[{direction.upper()}]**")
                    st.progress(conf, text=f"Confidence: {conf:.1%}")
            except Exception:
                st.info("No live prediction cached")
        else:
            st.warning("Model not trained yet")

    st.markdown("---")

    # ── Sentiment row ─────────────────────────────────────────────────────────
    st.subheader("Sentiment Scores")
    sent_cols = st.columns(5)
    sent_data = {
        "Composite": 0.0,
        "Twitter": 0.0,
        "Reddit": 0.0,
        "News": 0.0,
        "Macro News": 0.0,
    }
    # Try to load from Redis cache
    try:
        import redis
        r = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
        raw = r.get("latest_sentiment")
        if raw:
            s = json.loads(raw)
            sent_data = {
                "Composite": s.get("composite", 0),
                "Twitter": s.get("components", {}).get("twitter", 0),
                "Reddit": s.get("components", {}).get("reddit", 0),
                "News": s.get("components", {}).get("news", 0),
                "Macro News": s.get("components", {}).get("macro_news", 0),
            }
    except Exception:
        pass

    for col, (name, score) in zip(sent_cols, sent_data.items()):
        with col:
            fig = make_sentiment_gauge(score or 0.0, name)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ── Cross-asset heatmap ───────────────────────────────────────────────────
    st.subheader("Cross-Asset Correlations (placeholder)")
    with st.expander("Correlation Matrix"):
        corr_data = {
            "ETH": [1.0, 0.85, -0.32, -0.15, 0.42],
            "BTC": [0.85, 1.0, -0.28, -0.12, 0.38],
            "DXY": [-0.32, -0.28, 1.0, 0.65, -0.21],
            "SPX": [-0.15, -0.12, 0.65, 1.0, -0.18],
            "GOLD": [0.42, 0.38, -0.21, -0.18, 1.0],
        }
        corr_df = pd.DataFrame(corr_data, index=["ETH", "BTC", "DXY", "SPX", "GOLD"])
        fig_hm = go.Figure(go.Heatmap(
            z=corr_df.values,
            x=corr_df.columns.tolist(),
            y=corr_df.index.tolist(),
            colorscale="RdBu",
            zmin=-1, zmax=1,
            text=corr_df.round(2).values,
            texttemplate="%{text}",
        ))
        fig_hm.update_layout(template="plotly_dark", height=300, margin=dict(l=40, r=20, t=20, b=40))
        st.plotly_chart(fig_hm, use_container_width=True)

    # ── Trade journal ─────────────────────────────────────────────────────────
    st.subheader("Trade Journal")
    trades = load_trade_journal()
    if trades:
        df_trades = pd.DataFrame(trades)
        st.dataframe(df_trades, use_container_width=True)
    else:
        st.info("No trades yet")

    # ── Backtest report ───────────────────────────────────────────────────────
    st.subheader("Backtest Report")
    report = load_backtest_report()
    if report:
        m = report.get("vectorbt_metrics", report.get("walkforward_metrics", {}))
        bc1, bc2, bc3, bc4, bc5 = st.columns(5)
        bc1.metric("Sharpe Ratio", m.get("sharpe_ratio", "—"))
        bc2.metric("Sortino", m.get("sortino_ratio", "—"))
        bc3.metric("Max DD", f"{m.get('max_drawdown', 0):.1f}%")
        bc4.metric("Win Rate", f"{m.get('win_rate', 0):.1f}%")
        bc5.metric("Profit Factor", m.get("profit_factor", "—"))
    else:
        st.info("Run backtester.py to generate report")

    # ── Auto-refresh ──────────────────────────────────────────────────────────
    if auto_refresh or refresh_btn:
        time.sleep(0.1)
        st.rerun()


if __name__ == "__main__":
    main()
