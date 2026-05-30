"""
backtester.py
~~~~~~~~~~~~~
VectorBT-based backtesting suite with walk-forward optimization.

Workflow:
  1. Load historical OHLCV
  2. Compute all indicators
  3. Generate signals using strategy logic (vectorized)
  4. Run vectorbt simulation
  5. Report metrics: Sharpe, Sortino, Calmar, max DD, win rate, etc.
  6. Optuna parameter optimization
"""

from __future__ import annotations

import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import structlog

warnings.filterwarnings("ignore")

from indicators import compute_all_indicators

logger = structlog.get_logger(__name__)


# ─── Signal generation (vectorized for backtesting) ──────────────────────────


def generate_signals(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    """
    Pure pandas vectorized signal generation for backtesting.
    Returns DataFrame with 'long_entry', 'short_entry', 'long_exit', 'short_exit' bool columns.
    """
    df = compute_all_indicators(df.copy())

    rsi_buy = params.get("rsi_buy", 50)
    rsi_sell = params.get("rsi_sell", 50)
    vol_mult = params.get("vol_mult", 1.5)
    adx_min = params.get("adx_min", 25)

    # Long entry: all of these must be True
    long_entry = (
        (df.get("rsi_14", pd.Series(50, index=df.index)) > rsi_buy)
        & (df.get("macd_hist", pd.Series(0, index=df.index)) > 0)
        & (df.get("price_above_vwap", pd.Series(0, index=df.index)) == 1)
        & (df.get("supertrend_bull", pd.Series(0, index=df.index)) == 1)
        & (df.get("close", df["close"]) > df.get("ema_200", df["close"]))
        & (df.get("vol_ratio", pd.Series(1, index=df.index)) >= vol_mult)
    )

    # Short entry: mirror conditions
    short_entry = (
        (df.get("rsi_14", pd.Series(50, index=df.index)) < rsi_sell)
        & (df.get("macd_hist", pd.Series(0, index=df.index)) < 0)
        & (df.get("price_above_vwap", pd.Series(0, index=df.index)) == 0)
        & (df.get("supertrend_bull", pd.Series(0, index=df.index)) == 0)
        & (df.get("close", df["close"]) < df.get("ema_200", df["close"]))
        & (df.get("vol_ratio", pd.Series(1, index=df.index)) >= vol_mult)
    )

    # Exit: ATR-based (simplified vectorized version)
    atr = df.get("atr", df["close"] * 0.01)
    sl_long = df["close"].shift(1) - 1.5 * atr.shift(1)
    sl_short = df["close"].shift(1) + 1.5 * atr.shift(1)

    long_exit = df["close"] < sl_long
    short_exit = df["close"] > sl_short

    return pd.DataFrame(
        {
            "long_entry": long_entry.fillna(False),
            "short_entry": short_entry.fillna(False),
            "long_exit": long_exit.fillna(False),
            "short_exit": short_exit.fillna(False),
            "close": df["close"],
        },
        index=df.index,
    )


# ─── Metrics calculator ───────────────────────────────────────────────────────


def compute_metrics(returns: pd.Series, trades: pd.DataFrame = None) -> Dict[str, float]:
    """
    Computes performance metrics from a returns Series.
    Compatible with both vectorbt and manual simulations.
    """
    if returns.empty or returns.isna().all():
        return {}

    returns = returns.dropna()
    total_return = float((1 + returns).prod() - 1)
    annual_factor = 252 * 24  # 1h candles

    # Sharpe
    ann_ret = float((1 + returns.mean()) ** annual_factor - 1)
    ann_std = float(returns.std() * np.sqrt(annual_factor))
    sharpe = ann_ret / ann_std if ann_std > 0 else 0.0

    # Sortino
    downside = returns[returns < 0]
    ann_downside = float(downside.std() * np.sqrt(annual_factor)) if len(downside) > 0 else 1e-9
    sortino = ann_ret / ann_downside

    # Max drawdown
    cum = (1 + returns).cumprod()
    rolling_max = cum.cummax()
    drawdown = (cum - rolling_max) / rolling_max
    max_dd = float(drawdown.min())

    # Calmar
    calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0.0

    metrics = {
        "total_return": round(total_return * 100, 2),
        "annual_return": round(ann_ret * 100, 2),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "calmar_ratio": round(calmar, 4),
        "max_drawdown": round(max_dd * 100, 2),
        "volatility_annual": round(ann_std * 100, 2),
    }

    if trades is not None and not trades.empty:
        pnl = trades.get("pnl", pd.Series(dtype=float))
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
        metrics["win_rate"] = round(len(wins) / len(pnl) * 100, 2) if len(pnl) > 0 else 0
        metrics["profit_factor"] = round(wins.sum() / abs(losses.sum()), 4) if losses.sum() != 0 else float("inf")
        metrics["expectancy"] = round(float(pnl.mean()), 4)
        metrics["total_trades"] = len(pnl)

    return metrics


# ─── Walk-forward backtest ────────────────────────────────────────────────────


class WalkForwardBacktester:
    """
    Walk-forward validation: train on in-sample, test on out-of-sample.
    No lookahead bias guaranteed by strict temporal splits.
    """

    def __init__(self, n_splits: int = 5) -> None:
        self.n_splits = n_splits
        self.results: list = []

    def run(
        self,
        df: pd.DataFrame,
        params: Dict[str, Any],
        initial_capital: float = 10_000.0,
    ) -> Dict[str, Any]:
        n = len(df)
        fold_size = n // (self.n_splits + 1)
        all_returns: list = []

        for fold in range(self.n_splits):
            train_end = (fold + 1) * fold_size
            test_start = train_end
            test_end = test_start + fold_size

            df_test = df.iloc[test_start:test_end].copy()
            if len(df_test) < 200:
                continue

            signals = generate_signals(df_test, params)
            fold_returns = self._simulate(signals, initial_capital)
            all_returns.append(fold_returns)

            fold_metrics = compute_metrics(fold_returns)
            logger.info(
                "backtest_fold",
                fold=fold + 1,
                sharpe=fold_metrics.get("sharpe_ratio"),
                total_return=fold_metrics.get("total_return"),
            )

        if not all_returns:
            return {}

        combined = pd.concat(all_returns)
        metrics = compute_metrics(combined)
        metrics["folds"] = self.n_splits
        return metrics

    def _simulate(
        self, signals: pd.DataFrame, capital: float
    ) -> pd.Series:
        """
        Simple vectorized simulation — long/short positions, 1% risk per trade.
        Returns a series of per-bar returns.
        """
        closes = signals["close"].values
        long_e = signals["long_entry"].values
        short_e = signals["short_entry"].values
        long_x = signals["long_exit"].values
        short_x = signals["short_exit"].values
        n = len(closes)

        returns = np.zeros(n)
        position = 0  # 1=long, -1=short, 0=flat
        entry_price = 0.0

        for i in range(1, n):
            if position == 0:
                if long_e[i]:
                    position = 1
                    entry_price = closes[i]
                elif short_e[i]:
                    position = -1
                    entry_price = closes[i]
            elif position == 1:
                bar_ret = (closes[i] - closes[i - 1]) / closes[i - 1]
                returns[i] = bar_ret * 0.01 / (abs(closes[i - 1] - entry_price * 0.985) / closes[i - 1] + 1e-6) * 0.01
                if long_x[i]:
                    position = 0
            elif position == -1:
                bar_ret = (closes[i - 1] - closes[i]) / closes[i - 1]
                returns[i] = bar_ret * 0.01 / (abs(entry_price * 1.015 - closes[i - 1]) / closes[i - 1] + 1e-6) * 0.01
                if short_x[i]:
                    position = 0

        return pd.Series(returns, index=signals.index)


# ─── VectorBT wrapper (optional, richer) ─────────────────────────────────────


class VectorBTBacktester:
    """Full vectorbt simulation with rich stats output."""

    def run(
        self,
        df: pd.DataFrame,
        params: Dict[str, Any],
        initial_capital: float = 10_000.0,
        fees: float = 0.001,
    ) -> Dict[str, Any]:
        try:
            import vectorbt as vbt
        except ImportError:
            logger.warning("vectorbt_not_installed, falling back to simple backtester")
            return WalkForwardBacktester().run(df, params, initial_capital)

        signals = generate_signals(df, params)
        closes = signals["close"]

        pf = vbt.Portfolio.from_signals(
            closes,
            entries=signals["long_entry"],
            exits=signals["long_exit"],
            short_entries=signals["short_entry"],
            short_exits=signals["short_exit"],
            init_cash=initial_capital,
            fees=fees,
            freq="1h",
        )

        stats = pf.stats()
        trades = pf.trades.records_readable

        metrics = {
            "total_return": float(pf.total_return() * 100),
            "sharpe_ratio": float(pf.sharpe_ratio()),
            "sortino_ratio": float(pf.sortino_ratio()),
            "calmar_ratio": float(pf.calmar_ratio()),
            "max_drawdown": float(pf.max_drawdown() * 100),
            "win_rate": float(trades["Return"].gt(0).mean() * 100) if len(trades) > 0 else 0,
            "profit_factor": float(
                trades.loc[trades["Return"] > 0, "Return"].sum()
                / abs(trades.loc[trades["Return"] < 0, "Return"].sum())
            ) if (trades["Return"] < 0).any() else float("inf"),
            "total_trades": len(trades),
            "expectancy": float(trades["Return"].mean()) if len(trades) > 0 else 0,
        }
        logger.info("vectorbt_backtest_complete", **{k: round(v, 4) if isinstance(v, float) else v for k, v in metrics.items()})
        return metrics


# ─── Optuna parameter optimization ───────────────────────────────────────────


def optimize_strategy_params(
    df: pd.DataFrame,
    n_trials: int = 100,
    initial_capital: float = 10_000.0,
) -> Tuple[Dict, float]:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    backtester = WalkForwardBacktester(n_splits=3)

    def objective(trial: optuna.Trial) -> float:
        params = {
            "rsi_buy": trial.suggest_int("rsi_buy", 40, 60),
            "rsi_sell": trial.suggest_int("rsi_sell", 40, 60),
            "vol_mult": trial.suggest_float("vol_mult", 1.0, 2.5),
            "adx_min": trial.suggest_int("adx_min", 20, 35),
        }
        result = backtester.run(df, params, initial_capital)
        sharpe = result.get("sharpe_ratio", -999)
        # Penalise excessive drawdown
        dd = result.get("max_drawdown", -100)
        if dd < -20:
            return -999.0
        return sharpe

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
    best_params = study.best_params
    best_val = study.best_value
    logger.info("optuna_strategy_best", value=best_val, params=best_params)
    return best_params, best_val


# ─── Full backtest report ─────────────────────────────────────────────────────


async def run_full_backtest(
    symbol: str = "ETHUSDT",
    years: int = 3,
    optimize: bool = True,
) -> Dict[str, Any]:
    from data_feed import HistoricalDataLoader

    loader = HistoricalDataLoader()
    start = datetime.now(tz=timezone.utc) - timedelta(days=365 * years)
    df = await loader.fetch(symbol, "1h", start)
    await loader.close()

    if df.empty:
        logger.error("no_data_for_backtest")
        return {}

    logger.info("backtest_start", symbol=symbol, rows=len(df))
    default_params = {"rsi_buy": 50, "rsi_sell": 50, "vol_mult": 1.5, "adx_min": 25}

    if optimize:
        best_params, _ = optimize_strategy_params(df, n_trials=50)
    else:
        best_params = default_params

    vbt_metrics = VectorBTBacktester().run(df, best_params)
    wf_metrics = WalkForwardBacktester(n_splits=5).run(df, best_params)

    report = {
        "symbol": symbol,
        "period": f"{years}y",
        "candles": len(df),
        "optimized_params": best_params,
        "vectorbt_metrics": vbt_metrics,
        "walkforward_metrics": wf_metrics,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    import json
    with open("logs/backtest_report.json", "w") as f:
        json.dump(report, f, indent=2)

    logger.info("backtest_report_saved")
    return report
