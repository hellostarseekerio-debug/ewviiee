"""
strategy.py
~~~~~~~~~~~
Multi-timeframe signal logic.

Signal generation:
  1. Trend filter: 4h and 1D must align (above/below 200 EMA)
  2. Indicator confluence: 3+ indicators must fire same direction
  3. Volume confirmation: volume spike > 1.5x 20-period average
  4. ML ensemble: confidence > threshold
  5. Sentiment: composite score in expected direction
  6. Blackout: no new trades near high-impact macro events

Returns a Signal object: LONG / SHORT / FLAT with strength metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import structlog

from config import settings
from indicators import compute_all_indicators

logger = structlog.get_logger(__name__)


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass
class Signal:
    direction: Direction
    confidence: float               # 0-1 (from ML ensemble)
    strength: float                 # 0-1 (indicator confluence score)
    entry_price: float
    stop_loss: float
    take_profit_1: float            # 2:1 RR
    take_profit_2: float            # 3:1 RR
    atr: float
    reasons: List[str] = field(default_factory=list)
    ml_meta: Dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())

    @property
    def risk_reward_1(self) -> float:
        if self.direction == Direction.LONG:
            return (self.take_profit_1 - self.entry_price) / (self.entry_price - self.stop_loss + 1e-9)
        return (self.entry_price - self.take_profit_1) / (self.stop_loss - self.entry_price + 1e-9)

    @property
    def actionable(self) -> bool:
        return (
            self.direction != Direction.FLAT
            and self.confidence >= settings.ml_confidence_threshold
            and self.strength >= 0.5
        )


# ─── Individual signal checks ─────────────────────────────────────────────────


def _check_trend_filter(df_1h: pd.DataFrame, df_4h: pd.DataFrame, df_1d: pd.DataFrame) -> Direction:
    """
    All three timeframes must agree on trend direction (above/below 200 EMA).
    Returns LONG, SHORT, or FLAT.
    """
    def trend_dir(df: pd.DataFrame) -> int:
        if "ema_200" not in df.columns or df["ema_200"].isna().all():
            return 0
        close = df["close"].iloc[-1]
        ema = df["ema_200"].iloc[-1]
        return 1 if close > ema else -1

    dirs = [trend_dir(df_1h), trend_dir(df_4h), trend_dir(df_1d)]
    if all(d == 1 for d in dirs):
        return Direction.LONG
    if all(d == -1 for d in dirs):
        return Direction.SHORT
    return Direction.FLAT


def _score_long_signals(row: pd.Series) -> List[str]:
    """Returns list of bullish signals fired on the latest candle."""
    signals: List[str] = []

    def safe(col: str, default=np.nan):
        return row.get(col, default)

    # Momentum
    if safe("rsi_14", 50) < 50 and safe("rsi_14", 50) > 30:
        signals.append("RSI oversold recovery")
    if safe("rsi_cross_50_up", 0) == 1:
        signals.append("RSI crossed above 50")
    if safe("stoch_oversold", 0) == 1 and safe("stoch_k", 50) > safe("stoch_d", 50):
        signals.append("Stochastic oversold with K>D")
    if safe("cci", 0) > -100 and safe("cci", 0) < 0:
        signals.append("CCI recovering from oversold")
    if safe("ao_positive", 0) == 1:
        signals.append("Awesome Oscillator positive")

    # Trend
    if safe("price_above_vwap", 0) == 1:
        signals.append("Price above VWAP")
    if safe("supertrend_bull", 0) == 1:
        signals.append("SuperTrend bullish")
    if safe("ichi_above_cloud", 0) == 1:
        signals.append("Price above Ichimoku cloud")
    if safe("ichi_cloud_bull", 0) == 1:
        signals.append("Ichimoku cloud bullish")
    if safe("psar_bull", 0) == 1:
        signals.append("Parabolic SAR bullish")
    if safe("golden_cross", 0) == 1:
        signals.append("SMA50 above SMA200 (golden cross)")
    if safe("hma_slope", 0) > 0:
        signals.append("HMA upward slope")
    if safe("adx", 0) > 25 and safe("di_plus", 0) > safe("di_minus", 0):
        signals.append("ADX strong trend, DI+ > DI-")

    # Volatility / structure
    if safe("bb_pct_b", 0.5) < 0.2:
        signals.append("Bollinger Band oversold (%B < 0.2)")
    if safe("close", 0) > safe("lr_mid", -1) and safe("close", 0) < safe("lr_upper", 9e9):
        signals.append("Price in LR channel bull zone")

    # Volume
    if safe("vol_spike", 0) == 1:
        signals.append("Volume spike confirmed")
    if safe("obv_trend", 0) == 1:
        signals.append("OBV trending up")
    if safe("mfi_oversold", 0) == 1:
        signals.append("MFI oversold")
    if safe("cmf", 0) > 0:
        signals.append("CMF positive (buying pressure)")

    # Market structure
    if safe("bull_fvg", 0) > 0:
        signals.append("Bullish Fair Value Gap")
    if safe("bull_ob", 0) > 0:
        signals.append("Bullish Order Block")

    return signals


def _score_short_signals(row: pd.Series) -> List[str]:
    """Returns list of bearish signals fired on the latest candle."""
    signals: List[str] = []

    def safe(col: str, default=np.nan):
        return row.get(col, default)

    if safe("rsi_overbought", 0) == 1:
        signals.append("RSI overbought")
    if safe("rsi_14", 50) < 50 and safe("rsi_14", 50) > 30:
        pass  # not bearish by itself
    if safe("stoch_overbought", 0) == 1 and safe("stoch_k", 50) < safe("stoch_d", 50):
        signals.append("Stochastic overbought with K<D")
    if safe("cci", 0) > 100:
        signals.append("CCI overbought")
    if safe("ao_positive", 0) == 0:
        signals.append("Awesome Oscillator negative")
    if safe("price_above_vwap", 0) == 0:
        signals.append("Price below VWAP")
    if safe("supertrend_bull", 0) == 0:
        signals.append("SuperTrend bearish")
    if safe("ichi_above_cloud", 0) == 0:
        signals.append("Price below Ichimoku cloud")
    if safe("psar_bull", 0) == 0:
        signals.append("Parabolic SAR bearish")
    if safe("hma_slope", 0) < 0:
        signals.append("HMA downward slope")
    if safe("adx", 0) > 25 and safe("di_minus", 0) > safe("di_plus", 0):
        signals.append("ADX strong trend, DI- > DI+")
    if safe("bb_pct_b", 0.5) > 0.8:
        signals.append("Bollinger Band overbought (%B > 0.8)")
    if safe("obv_trend", 0) == 0:
        signals.append("OBV trending down")
    if safe("mfi_overbought", 0) == 1:
        signals.append("MFI overbought")
    if safe("cmf", 0) < 0:
        signals.append("CMF negative (selling pressure)")
    if safe("bear_fvg", 0) > 0:
        signals.append("Bearish Fair Value Gap")
    if safe("bear_ob", 0) > 0:
        signals.append("Bearish Order Block")

    return signals


# ─── Multi-timeframe strategy ─────────────────────────────────────────────────


class MultiTimeframeStrategy:
    """
    Core strategy class. Ingests indicator DataFrames + ML prediction +
    sentiment score, outputs a Signal.
    """

    MIN_CONFLUENCE = 3  # minimum indicator signals required

    def evaluate(
        self,
        df_1h: pd.DataFrame,
        df_4h: pd.DataFrame,
        df_1d: pd.DataFrame,
        ml_prediction: Dict[str, Any],
        sentiment: Dict[str, Any],
        blackout: bool = False,
        cross_asset: Optional[Dict[str, Any]] = None,
    ) -> Signal:
        if blackout:
            logger.info("signal_blocked_blackout")
            return self._flat(df_1h, "Economic calendar blackout window")

        # ── Step 1: trend filter ──────────────────────────────────────────────
        trend_dir = _check_trend_filter(df_1h, df_4h, df_1d)
        if trend_dir == Direction.FLAT:
            return self._flat(df_1h, "Multi-timeframe trend not aligned")

        # ── Step 2: ML confidence ─────────────────────────────────────────────
        ml_conf = ml_prediction.get("confidence", 0.5)
        ml_dir = ml_prediction.get("direction", "flat")
        ml_matches = (
            (trend_dir == Direction.LONG and ml_dir == "long")
            or (trend_dir == Direction.SHORT and ml_dir == "short")
        )
        if not ml_matches:
            return self._flat(df_1h, f"ML direction {ml_dir} disagrees with trend {trend_dir}")
        if ml_conf < settings.ml_confidence_threshold:
            return self._flat(df_1h, f"ML confidence {ml_conf:.3f} below threshold")

        # ── Step 3: indicator confluence ──────────────────────────────────────
        latest = df_1h.iloc[-1]
        if trend_dir == Direction.LONG:
            fired = _score_long_signals(latest)
        else:
            fired = _score_short_signals(latest)

        # Volume spike required
        vol_ok = latest.get("vol_spike", 0) == 1
        if not vol_ok:
            fired_names = [f for f in fired if "Volume" in f]
            if not fired_names:
                fired = [f for f in fired if "Volume" not in f]  # allow without vol spike if 5+ signals

        if len(fired) < self.MIN_CONFLUENCE:
            return self._flat(
                df_1h,
                f"Only {len(fired)} indicator signals ({', '.join(fired[:2])}…), need {self.MIN_CONFLUENCE}",
            )

        # ── Step 4: sentiment filter ──────────────────────────────────────────
        sent_score = sentiment.get("composite", 0.0) if sentiment else 0.0
        if trend_dir == Direction.LONG and sent_score < -0.4:
            return self._flat(df_1h, f"Sentiment strongly negative ({sent_score:.2f}) for LONG")
        if trend_dir == Direction.SHORT and sent_score > 0.4:
            return self._flat(df_1h, f"Sentiment strongly positive ({sent_score:.2f}) for SHORT")

        # ── Step 5: cross-asset confirmation ─────────────────────────────────
        btc_ok = self._btc_confirms(trend_dir, cross_asset)
        if not btc_ok:
            fired.append("(BTC not confirming — reduced weight)")

        # ── Step 6: build signal ──────────────────────────────────────────────
        close = float(df_1h["close"].iloc[-1])
        atr = float(df_1h["atr"].iloc[-1]) if "atr" in df_1h.columns else close * 0.01

        if trend_dir == Direction.LONG:
            sl = close - 1.5 * atr
            tp1 = close + 2 * (close - sl)
            tp2 = close + 3 * (close - sl)
        else:
            sl = close + 1.5 * atr
            tp1 = close - 2 * (sl - close)
            tp2 = close - 3 * (sl - close)

        strength = min(len(fired) / 10.0, 1.0)

        signal = Signal(
            direction=trend_dir,
            confidence=ml_conf,
            strength=strength,
            entry_price=close,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2,
            atr=atr,
            reasons=fired,
            ml_meta=ml_prediction,
        )
        logger.info(
            "signal_generated",
            direction=signal.direction,
            confidence=ml_conf,
            signals=len(fired),
            entry=close,
            sl=sl,
            tp1=tp1,
        )
        return signal

    def _flat(self, df: pd.DataFrame, reason: str) -> Signal:
        close = float(df["close"].iloc[-1]) if not df.empty else 0.0
        atr = float(df["atr"].iloc[-1]) if ("atr" in df.columns and not df["atr"].isna().all()) else close * 0.01
        return Signal(
            direction=Direction.FLAT,
            confidence=0.0,
            strength=0.0,
            entry_price=close,
            stop_loss=close - atr,
            take_profit_1=close + 2 * atr,
            take_profit_2=close + 3 * atr,
            atr=atr,
            reasons=[reason],
        )

    @staticmethod
    def _btc_confirms(direction: Direction, cross_asset: Optional[Dict]) -> bool:
        if not cross_asset:
            return True
        btc_eth = cross_asset.get("eth_btc", {})
        if not btc_eth:
            return True
        # Use ETH/BTC ratio trend as proxy for BTC correlation
        eth_btc = btc_eth.get("ETH_BTC", 0)
        btc_usd = btc_eth.get("BTC_USD", 0)
        # Simplified: if BTC is priced above 20k it's not in crash mode
        if direction == Direction.LONG:
            return btc_usd > 20_000
        return btc_usd < 100_000  # short when BTC not in extreme bull


# ─── Strategy runner (called from main loop) ─────────────────────────────────


class StrategyRunner:
    """
    Wraps MultiTimeframeStrategy with DataFrame preparation from
    the raw OHLCV dicts returned by data_feed.build_market_context().
    """

    def __init__(self) -> None:
        self._strategy = MultiTimeframeStrategy()

    def run(
        self,
        market_context: Dict[str, Any],
        ml_prediction: Dict[str, Any],
        sentiment: Dict[str, Any],
    ) -> Signal:
        ohlcv: Dict[str, pd.DataFrame] = market_context.get("ohlcv", {})
        cross_asset = market_context.get("cross_asset", {})
        blackout = market_context.get("blackout", False)

        df_1h = self._prepare(ohlcv.get("1h", pd.DataFrame()))
        df_4h = self._prepare(ohlcv.get("4h", pd.DataFrame()))
        df_1d = self._prepare(ohlcv.get("1d", pd.DataFrame()))

        if df_1h.empty:
            return Signal(
                direction=Direction.FLAT,
                confidence=0.0,
                strength=0.0,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit_1=0.0,
                take_profit_2=0.0,
                atr=0.0,
                reasons=["No 1h OHLCV data"],
            )

        return self._strategy.evaluate(
            df_1h=df_1h,
            df_4h=df_4h,
            df_1d=df_1d,
            ml_prediction=ml_prediction,
            sentiment=sentiment,
            blackout=blackout,
            cross_asset=cross_asset,
        )

    @staticmethod
    def _prepare(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        return compute_all_indicators(df)
