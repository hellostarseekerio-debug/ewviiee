"""Unit tests for strategy signal logic."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from strategy import Direction, MultiTimeframeStrategy, _check_trend_filter


def make_trending_df(n: int = 300, trend: str = "up") -> pd.DataFrame:
    """Make a DataFrame that looks like a strong uptrend or downtrend."""
    np.random.seed(0)
    if trend == "up":
        closes = 1500 + np.arange(n) * 5 + np.random.randn(n) * 10
    else:
        closes = 3000 - np.arange(n) * 5 + np.random.randn(n) * 10
    opens = closes + np.random.randn(n) * 2
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(n) * 5)
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(n) * 5)
    vols = np.abs(np.random.randn(n) * 1e6 + 5e6)
    idx = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=idx,
    )


def test_trend_filter_uptrend():
    from indicators import compute_all_indicators

    df_up = compute_all_indicators(make_trending_df(300, "up"))
    direction = _check_trend_filter(df_up, df_up, df_up)
    assert direction == Direction.LONG


def test_trend_filter_downtrend():
    from indicators import compute_all_indicators

    df_dn = compute_all_indicators(make_trending_df(300, "down"))
    direction = _check_trend_filter(df_dn, df_dn, df_dn)
    assert direction == Direction.SHORT


def test_strategy_returns_flat_no_ml():
    from indicators import compute_all_indicators

    df = compute_all_indicators(make_trending_df(300, "up"))
    strat = MultiTimeframeStrategy()
    # ML confidence below threshold → FLAT
    ml_pred = {"confidence": 0.50, "direction": "long"}
    signal = strat.evaluate(
        df_1h=df, df_4h=df, df_1d=df,
        ml_prediction=ml_pred,
        sentiment={"composite": 0.3},
    )
    assert signal.direction == Direction.FLAT


def test_strategy_blackout_returns_flat():
    from indicators import compute_all_indicators

    df = compute_all_indicators(make_trending_df(300, "up"))
    strat = MultiTimeframeStrategy()
    ml_pred = {"confidence": 0.85, "direction": "long"}
    signal = strat.evaluate(
        df_1h=df, df_4h=df, df_1d=df,
        ml_prediction=ml_pred,
        sentiment={"composite": 0.5},
        blackout=True,
    )
    assert signal.direction == Direction.FLAT
    assert "blackout" in signal.reasons[0].lower()


def test_signal_has_valid_rr():
    from indicators import compute_all_indicators

    df = compute_all_indicators(make_trending_df(300, "up"))
    strat = MultiTimeframeStrategy()
    # Force enough signals by using high confidence and good sentiment
    ml_pred = {"confidence": 0.90, "direction": "long"}
    signal = strat.evaluate(
        df_1h=df, df_4h=df, df_1d=df,
        ml_prediction=ml_pred,
        sentiment={"composite": 0.5},
    )
    if signal.direction != Direction.FLAT:
        # TP1 should be at least 1.5:1 RR
        assert signal.risk_reward_1 >= 1.5
        assert signal.stop_loss < signal.entry_price  # long: SL below entry
        assert signal.take_profit_1 > signal.entry_price  # TP above entry
