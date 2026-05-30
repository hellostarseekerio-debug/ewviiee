"""
indicators.py
~~~~~~~~~~~~~
Complete technical indicator library.

All indicators operate on a pandas DataFrame with columns:
  open, high, low, close, volume

Returns the same DataFrame with new indicator columns appended.
No external TA-Lib C library required — implemented via pandas-ta
and pure-numpy where needed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta as ta
import structlog
from scipy.signal import argrelextrema

logger = structlog.get_logger(__name__)


# ─── Utilities ────────────────────────────────────────────────────────────────


def _validate(df: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing columns: {missing}")


def safe_div(a: pd.Series, b: pd.Series, fill: float = 0.0) -> pd.Series:
    return a.div(b.replace(0, np.nan)).fillna(fill)


# ─── Trend indicators ─────────────────────────────────────────────────────────


def add_ema(df: pd.DataFrame, periods: list[int] = [9, 21, 50, 100, 200]) -> pd.DataFrame:
    for p in periods:
        df[f"ema_{p}"] = ta.ema(df["close"], length=p)
    return df


def add_sma(df: pd.DataFrame, periods: list[int] = [20, 50, 200]) -> pd.DataFrame:
    for p in periods:
        df[f"sma_{p}"] = ta.sma(df["close"], length=p)
    # Golden / death cross signals
    if "sma_50" in df.columns and "sma_200" in df.columns:
        df["golden_cross"] = (df["sma_50"] > df["sma_200"]).astype(int)
        df["sma50_cross_up"] = (
            (df["sma_50"] > df["sma_200"]) & (df["sma_50"].shift(1) <= df["sma_200"].shift(1))
        ).astype(int)
    return df



def add_adx(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    adx = ta.adx(df["high"], df["low"], df["close"], length=length)
    df["adx"] = adx[f"ADX_{length}"]
    df["di_plus"] = adx[f"DMP_{length}"]
    df["di_minus"] = adx[f"DMN_{length}"]
    df["trend_strong"] = (df["adx"] > 25).astype(int)
    return df


def add_parabolic_sar(df: pd.DataFrame) -> pd.DataFrame:
    psar = ta.psar(df["high"], df["low"], df["close"])
    df["psar"] = psar.get("PSARl_0.02_0.2", psar.get("PSARs_0.02_0.2"))
    df["psar_bull"] = (~psar["PSARl_0.02_0.2"].isna()).astype(int)
    return df


def add_ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    ich = ta.ichimoku(df["high"], df["low"], df["close"])
    if ich is not None and len(ich) >= 2:
        span = ich[0]
        df["ichi_tenkan"] = span.get("ITS_9")
        df["ichi_kijun"] = span.get("IKS_26")
        df["ichi_senkou_a"] = span.get("ISA_9")
        df["ichi_senkou_b"] = span.get("ISB_26")
        df["ichi_chikou"] = span.get("ICS_26")
        df["ichi_cloud_bull"] = (df["ichi_senkou_a"] > df["ichi_senkou_b"]).astype(int)
        df["ichi_above_cloud"] = (
            df["close"] > df[["ichi_senkou_a", "ichi_senkou_b"]].max(axis=1)
        ).astype(int)
    return df


def add_supertrend(df: pd.DataFrame, atr_mult: float = 3.0, period: int = 10) -> pd.DataFrame:
    st = ta.supertrend(df["high"], df["low"], df["close"], length=period, multiplier=atr_mult)
    col_d = f"SUPERTd_{period}_{atr_mult}"
    col_l = f"SUPERT_{period}_{atr_mult}"
    if col_d in st.columns:
        df["supertrend_dir"] = st[col_d]  # 1 = bullish, -1 = bearish
        df["supertrend"] = st[col_l]
        df["supertrend_bull"] = (df["supertrend_dir"] == 1).astype(int)
    return df


def add_hma(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    df["hma"] = ta.hma(df["close"], length=length)
    df["hma_slope"] = df["hma"].diff()
    return df


def add_vwap(df: pd.DataFrame) -> pd.DataFrame:
    # Session VWAP (resets each day)
    df["vwap"] = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
    df["price_above_vwap"] = (df["close"] > df["vwap"]).astype(int)
    # Anchored VWAP from last 20 candles
    typical = (df["high"] + df["low"] + df["close"]) / 3
    tp_vol = typical * df["volume"]
    rolling_window = 20
    df["avwap_20"] = (
        tp_vol.rolling(rolling_window).sum() / df["volume"].rolling(rolling_window).sum()
    )
    return df


def add_linear_regression_channel(df: pd.DataFrame, length: int = 50) -> pd.DataFrame:
    closes = df["close"].values
    n = len(closes)
    mid = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)

    for i in range(length - 1, n):
        y = closes[i - length + 1 : i + 1]
        x = np.arange(length)
        m, b = np.polyfit(x, y, 1)
        fit = m * x + b
        std = np.std(y - fit)
        mid[i] = fit[-1]
        upper[i] = fit[-1] + 2 * std
        lower[i] = fit[-1] - 2 * std

    df["lr_mid"] = mid
    df["lr_upper"] = upper
    df["lr_lower"] = lower
    return df


# ─── Momentum indicators ──────────────────────────────────────────────────────


def add_rsi(df: pd.DataFrame, periods: list[int] = [7, 14, 21]) -> pd.DataFrame:
    for p in periods:
        df[f"rsi_{p}"] = ta.rsi(df["close"], length=p)
    if "rsi_14" in df.columns:
        df["rsi_overbought"] = (df["rsi_14"] > 70).astype(int)
        df["rsi_oversold"] = (df["rsi_14"] < 30).astype(int)
        df["rsi_cross_50_up"] = (
            (df["rsi_14"] > 50) & (df["rsi_14"].shift(1) <= 50)
        ).astype(int)
    return df


def add_stochrsi(df: pd.DataFrame) -> pd.DataFrame:
    srsi = ta.stochrsi(df["close"])
    if srsi is not None:
        df["stochrsi_k"] = srsi.get("STOCHRSIk_14_14_3_3")
        df["stochrsi_d"] = srsi.get("STOCHRSId_14_14_3_3")
    return df


def add_stochastic(df: pd.DataFrame) -> pd.DataFrame:
    stoch = ta.stoch(df["high"], df["low"], df["close"])
    if stoch is not None:
        df["stoch_k"] = stoch.get("STOCHk_14_3_3")
        df["stoch_d"] = stoch.get("STOCHd_14_3_3")
        df["stoch_oversold"] = (df["stoch_k"] < 20).astype(int)
        df["stoch_overbought"] = (df["stoch_k"] > 80).astype(int)
    return df


def add_cci(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    df["cci"] = ta.cci(df["high"], df["low"], df["close"], length=length)
    return df


def add_williams_r(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    df["williams_r"] = ta.willr(df["high"], df["low"], df["close"], length=length)
    return df


def add_roc(df: pd.DataFrame, length: int = 10) -> pd.DataFrame:
    df["roc"] = ta.roc(df["close"], length=length)
    return df


def add_momentum(df: pd.DataFrame, length: int = 10) -> pd.DataFrame:
    df["momentum"] = ta.mom(df["close"], length=length)
    return df


def add_awesome_oscillator(df: pd.DataFrame) -> pd.DataFrame:
    df["ao"] = ta.ao(df["high"], df["low"])
    df["ao_positive"] = (df["ao"] > 0).astype(int)
    return df


def add_ultimate_oscillator(df: pd.DataFrame) -> pd.DataFrame:
    df["uo"] = ta.uo(df["high"], df["low"], df["close"])
    return df


# ─── Volatility indicators ────────────────────────────────────────────────────


def add_bollinger_bands(df: pd.DataFrame, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    bb = ta.bbands(df["close"], length=length, std=std)
    if bb is not None:
        df["bb_upper"] = bb[f"BBU_{length}_{std}"]
        df["bb_mid"] = bb[f"BBM_{length}_{std}"]
        df["bb_lower"] = bb[f"BBL_{length}_{std}"]
        df["bb_pct_b"] = bb[f"BBP_{length}_{std}"]
        df["bb_bandwidth"] = bb[f"BBB_{length}_{std}"]
        df["bb_squeeze"] = (df["bb_bandwidth"] < df["bb_bandwidth"].rolling(50).quantile(0.2)).astype(int)
    return df


def add_atr(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=length)
    df["atr_pct"] = safe_div(df["atr"], df["close"]) * 100
    return df


def add_keltner_channels(df: pd.DataFrame, length: int = 20, atr_mult: float = 2.0) -> pd.DataFrame:
    kc = ta.kc(df["high"], df["low"], df["close"], length=length, scalar=atr_mult)
    if kc is not None:
        df["kc_upper"] = kc.get(f"KCUe_{length}_{atr_mult}")
        df["kc_mid"] = kc.get(f"KCBe_{length}_{atr_mult}")
        df["kc_lower"] = kc.get(f"KCLe_{length}_{atr_mult}")
    return df


def add_donchian_channels(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    dc = ta.donchian(df["high"], df["low"], lower_length=length, upper_length=length)
    if dc is not None:
        df["dc_upper"] = dc.get(f"DCU_{length}_{length}")
        df["dc_mid"] = dc.get(f"DCM_{length}_{length}")
        df["dc_lower"] = dc.get(f"DCL_{length}_{length}")
    return df


def add_std_bands(df: pd.DataFrame, length: int = 20, mult: float = 2.0) -> pd.DataFrame:
    rolling_std = df["close"].rolling(length).std()
    sma = df["close"].rolling(length).mean()
    df["std_upper"] = sma + mult * rolling_std
    df["std_lower"] = sma - mult * rolling_std
    return df


# ─── Volume indicators ────────────────────────────────────────────────────────


def add_obv(df: pd.DataFrame) -> pd.DataFrame:
    df["obv"] = ta.obv(df["close"], df["volume"])
    df["obv_ema"] = ta.ema(df["obv"], length=20)
    df["obv_trend"] = (df["obv"] > df["obv_ema"]).astype(int)
    return df


def add_mfi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    df["mfi"] = ta.mfi(df["high"], df["low"], df["close"], df["volume"], length=length)
    df["mfi_overbought"] = (df["mfi"] > 80).astype(int)
    df["mfi_oversold"] = (df["mfi"] < 20).astype(int)
    return df


def add_cmf(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    df["cmf"] = ta.cmf(df["high"], df["low"], df["close"], df["volume"], length=length)
    return df


def add_ad_line(df: pd.DataFrame) -> pd.DataFrame:
    df["ad_line"] = ta.ad(df["high"], df["low"], df["close"], df["volume"])
    return df


def add_force_index(df: pd.DataFrame, length: int = 13) -> pd.DataFrame:
    df["force_index"] = ta.efi(df["close"], df["volume"], length=length)
    return df


def add_eom(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    df["eom"] = ta.eom(df["high"], df["low"], df["close"], df["volume"], length=length)
    return df


def add_volume_profile(df: pd.DataFrame, bins: int = 50) -> pd.DataFrame:
    """
    Computes Point of Control (POC), Value Area High (VAH), Value Area Low (VAL)
    using a simple histogram-based volume profile over the full DataFrame.
    """
    prices = df["close"].dropna().values
    volumes = df["volume"].reindex(df["close"].dropna().index).values
    if len(prices) < bins:
        return df

    price_min, price_max = prices.min(), prices.max()
    bin_edges = np.linspace(price_min, price_max, bins + 1)
    bin_indices = np.digitize(prices, bin_edges) - 1
    bin_indices = np.clip(bin_indices, 0, bins - 1)
    bin_volumes = np.zeros(bins)
    for i, vi in zip(bin_indices, volumes):
        bin_volumes[i] += vi

    poc_bin = int(np.argmax(bin_volumes))
    poc = (bin_edges[poc_bin] + bin_edges[poc_bin + 1]) / 2

    # Value Area = 70% of total volume around POC
    total_vol = bin_volumes.sum()
    target = total_vol * 0.70
    accumulated = bin_volumes[poc_bin]
    lo, hi = poc_bin, poc_bin
    while accumulated < target and (lo > 0 or hi < bins - 1):
        extend_up = bin_volumes[hi + 1] if hi + 1 < bins else 0
        extend_dn = bin_volumes[lo - 1] if lo > 0 else 0
        if extend_up >= extend_dn:
            hi = min(hi + 1, bins - 1)
            accumulated += bin_volumes[hi]
        else:
            lo = max(lo - 1, 0)
            accumulated += bin_volumes[lo]

    df["vp_poc"] = poc
    df["vp_vah"] = (bin_edges[hi] + bin_edges[hi + 1]) / 2
    df["vp_val"] = (bin_edges[lo] + bin_edges[lo + 1]) / 2
    return df


def add_volume_spike(df: pd.DataFrame, period: int = 20, multiplier: float = 1.5) -> pd.DataFrame:
    df["vol_ma"] = df["volume"].rolling(period).mean()
    df["vol_spike"] = (df["volume"] > df["vol_ma"] * multiplier).astype(int)
    df["vol_ratio"] = safe_div(df["volume"], df["vol_ma"])
    return df


# ─── Market structure ─────────────────────────────────────────────────────────


def add_pivot_points(df: pd.DataFrame) -> pd.DataFrame:
    """Classic pivot points using previous bar's H/L/C."""
    prev_h = df["high"].shift(1)
    prev_l = df["low"].shift(1)
    prev_c = df["close"].shift(1)
    df["pp"] = (prev_h + prev_l + prev_c) / 3
    df["r1"] = 2 * df["pp"] - prev_l
    df["s1"] = 2 * df["pp"] - prev_h
    df["r2"] = df["pp"] + (prev_h - prev_l)
    df["s2"] = df["pp"] - (prev_h - prev_l)
    df["r3"] = prev_h + 2 * (df["pp"] - prev_l)
    df["s3"] = prev_l - 2 * (prev_h - df["pp"])
    return df


def add_fibonacci_levels(df: pd.DataFrame, lookback: int = 100) -> pd.DataFrame:
    """
    Auto-detect major swing high/low in last `lookback` candles,
    then annotate latest Fibonacci retracement levels.
    """
    if len(df) < lookback:
        return df
    window = df.tail(lookback)
    swing_high = window["high"].max()
    swing_low = window["low"].min()
    diff = swing_high - swing_low
    ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618]
    for r in ratios:
        label = str(r).replace(".", "_")
        df[f"fib_{label}"] = swing_high - diff * r
    return df


def add_support_resistance(df: pd.DataFrame, order: int = 5, n_levels: int = 5) -> pd.DataFrame:
    """
    Cluster-based S/R zones using local extrema.
    Adds sr_support_N and sr_resistance_N columns.
    """
    highs = df["high"].values
    lows = df["low"].values
    close = df["close"].values

    high_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
    low_idx = argrelextrema(lows, np.less_equal, order=order)[0]

    resistance_levels = sorted(set(highs[high_idx].tolist()), reverse=True)[:n_levels]
    support_levels = sorted(set(lows[low_idx].tolist()))[:n_levels]

    current_price = close[-1]
    nearby_res = [l for l in resistance_levels if l > current_price][:n_levels]
    nearby_sup = [l for l in support_levels if l < current_price][-n_levels:]

    for i, lvl in enumerate(nearby_res[:n_levels]):
        df[f"sr_resistance_{i+1}"] = lvl
    for i, lvl in enumerate(reversed(nearby_sup[:n_levels])):
        df[f"sr_support_{i+1}"] = lvl
    return df


def add_fair_value_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detects bullish and bearish Fair Value Gaps (FVG / imbalance).
    Bullish FVG: candle[i-2].high < candle[i].low  (gap up)
    Bearish FVG: candle[i-2].low  > candle[i].high (gap down)
    """
    n = len(df)
    bull_fvg = np.zeros(n)
    bear_fvg = np.zeros(n)
    for i in range(2, n):
        if df["low"].iloc[i] > df["high"].iloc[i - 2]:
            bull_fvg[i] = (df["low"].iloc[i] + df["high"].iloc[i - 2]) / 2
        if df["high"].iloc[i] < df["low"].iloc[i - 2]:
            bear_fvg[i] = (df["high"].iloc[i] + df["low"].iloc[i - 2]) / 2
    df["bull_fvg"] = bull_fvg
    df["bear_fvg"] = bear_fvg
    return df


def add_order_blocks(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """
    Identifies the most recent bullish/bearish order blocks.
    Bullish OB: last bearish candle before a strong up-move.
    Bearish OB: last bullish candle before a strong down-move.
    """
    closes = df["close"].values
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)

    bull_ob = np.zeros(n)
    bear_ob = np.zeros(n)

    for i in range(lookback, n - 1):
        # Bullish OB: bearish candle followed by strong up move
        if opens[i] > closes[i]:  # bearish candle
            if closes[i + 1] > highs[i]:  # price breaks above
                bull_ob[i] = lows[i]
        # Bearish OB: bullish candle followed by strong down move
        if closes[i] > opens[i]:  # bullish candle
            if closes[i + 1] < lows[i]:  # price breaks below
                bear_ob[i] = highs[i]

    df["bull_ob"] = bull_ob
    df["bear_ob"] = bear_ob
    return df


def add_wyckoff_phase(df: pd.DataFrame, lookback: int = 50) -> pd.DataFrame:
    """
    Heuristic Wyckoff phase labeling based on price action + volume patterns.
    Phases: Accumulation, Markup, Distribution, Markdown (0-3).
    """
    if len(df) < lookback:
        df["wyckoff_phase"] = 0
        return df

    price_trend = df["close"].diff(lookback)
    vol_trend = df["volume"].diff(lookback)
    sma50 = df["close"].rolling(lookback).mean()

    conditions = [
        # Accumulation: flat price, rising volume
        (price_trend.abs() < df["close"].rolling(lookback).std()) & (vol_trend > 0),
        # Markup: rising price + rising volume
        (price_trend > 0) & (df["close"] > sma50),
        # Distribution: flat/rising price, declining volume
        (price_trend.abs() < df["close"].rolling(lookback).std()) & (vol_trend < 0),
    ]
    choices = [0, 1, 2]
    df["wyckoff_phase"] = np.select(conditions, choices, default=3)  # 3 = Markdown
    return df


# ─── Master function ──────────────────────────────────────────────────────────


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes every indicator and appends columns to df.
    Input: OHLCV DataFrame (index = DatetimeIndex).
    Output: same DataFrame with ~150 new columns.
    """
    _validate(df)
    df = df.copy()

    # Trend
    df = add_ema(df)
    df = add_sma(df)
    df = add_adx(df)
    df = add_parabolic_sar(df)
    df = add_ichimoku(df)
    df = add_supertrend(df)
    df = add_hma(df)
    df = add_vwap(df)
    df = add_linear_regression_channel(df)

    # Momentum
    df = add_rsi(df)
    df = add_stochrsi(df)
    df = add_stochastic(df)
    df = add_cci(df)
    df = add_williams_r(df)
    df = add_roc(df)
    df = add_momentum(df)
    df = add_awesome_oscillator(df)
    df = add_ultimate_oscillator(df)

    # Volatility
    df = add_bollinger_bands(df)
    df = add_atr(df)
    df = add_keltner_channels(df)
    df = add_donchian_channels(df)
    df = add_std_bands(df)

    # Volume
    df = add_obv(df)
    df = add_mfi(df)
    df = add_cmf(df)
    df = add_ad_line(df)
    df = add_force_index(df)
    df = add_eom(df)
    df = add_volume_profile(df)
    df = add_volume_spike(df)

    # Market structure
    df = add_pivot_points(df)
    df = add_fibonacci_levels(df)
    df = add_support_resistance(df)
    df = add_fair_value_gaps(df)
    df = add_order_blocks(df)
    df = add_wyckoff_phase(df)

    logger.info("indicators_computed", columns=len(df.columns), rows=len(df))
    return df


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return all numeric indicator columns (excluding OHLCV base)."""
    base = {"open", "high", "low", "close", "volume", "quote_vol", "trades"}
    return [
        c for c in df.columns
        if c not in base and df[c].dtype in [np.float64, np.float32, np.int64, np.int32, int, float]
    ]
