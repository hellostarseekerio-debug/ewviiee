"""Unit tests for indicator computation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from indicators import compute_all_indicators, get_feature_columns


def make_ohlcv(n: int = 300) -> pd.DataFrame:
    np.random.seed(42)
    closes = 2000 + np.cumsum(np.random.randn(n) * 20)
    opens = closes + np.random.randn(n) * 5
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(n) * 10)
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(n) * 10)
    volumes = np.abs(np.random.randn(n) * 1e6 + 5e6)
    idx = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=idx,
    )


def test_compute_all_indicators_runs():
    df = make_ohlcv(300)
    result = compute_all_indicators(df)
    assert len(result) == 300
    assert "ema_9" in result.columns
    assert "ema_200" in result.columns
    assert "rsi_14" in result.columns
    assert "bb_upper" in result.columns
    assert "atr" in result.columns
    assert "obv" in result.columns
    assert "vwap" in result.columns


def test_feature_columns_are_numeric():
    df = make_ohlcv(300)
    result = compute_all_indicators(df)
    cols = get_feature_columns(result)
    assert len(cols) > 50
    for c in cols:
        assert result[c].dtype in [np.float64, np.float32, np.int64, np.int32]


def test_no_future_leak():
    """Indicators should only use past data — no lookahead."""
    df = make_ohlcv(300)
    result1 = compute_all_indicators(df.copy())
    # Modify last 50 rows prices
    df2 = df.copy()
    df2.loc[df2.index[-50:], "close"] *= 2.0
    result2 = compute_all_indicators(df2)
    # First 200 rows should be identical (no future data leaking back)
    for col in ["ema_9", "rsi_14"]:
        if col in result1.columns and col in result2.columns:
            pd.testing.assert_series_equal(
                result1[col].iloc[:200], result2[col].iloc[:200], check_names=False
            )


def test_volume_profile():
    df = make_ohlcv(300)
    result = compute_all_indicators(df)
    assert "vp_poc" in result.columns
    assert float(result["vp_poc"].iloc[-1]) > 0


def test_fibonacci_levels():
    df = make_ohlcv(300)
    result = compute_all_indicators(df)
    assert "fib_0_618" in result.columns
    assert "fib_0_0" in result.columns


def test_fair_value_gaps():
    df = make_ohlcv(300)
    result = compute_all_indicators(df)
    assert "bull_fvg" in result.columns
    assert "bear_fvg" in result.columns
