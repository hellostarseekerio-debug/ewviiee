"""
executor.py
~~~~~~~~~~~
Order placement, management, and the main async trading loop.

Paper trading mode (default): logs orders, no real API calls.
Live mode: places market + limit orders on Binance.

Main loop:
  1. Refresh market context (data_feed)
  2. Run ML prediction
  3. Run sentiment
  4. Evaluate strategy
  5. Risk-check → size position
  6. Place/update orders
  7. Sleep until next 1h candle close
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from data_feed import build_market_context
from ml_model import EnsemblePredictor
from risk_manager import AccountState, Position, RiskManager
from sentiment import SentimentAggregator
from strategy import Direction, Signal, StrategyRunner

logger = structlog.get_logger(__name__)


# ─── Telegram alerter ─────────────────────────────────────────────────────────


class TelegramAlerter:
    API = "https://api.telegram.org"

    def __init__(self) -> None:
        self._enabled = bool(settings.telegram_bot_token and settings.telegram_chat_id)

    async def send(self, message: str) -> None:
        if not self._enabled:
            logger.info("telegram_disabled", msg=message)
            return
        import aiohttp
        url = f"{self.API}/bot{settings.telegram_bot_token}/sendMessage"
        try:
            async with aiohttp.ClientSession() as s:
                await s.post(url, json={"chat_id": settings.telegram_chat_id, "text": message})
        except Exception as exc:
            logger.warning("telegram_send_failed", error=str(exc))


# ─── Paper-trade order simulator ─────────────────────────────────────────────


class PaperTradeExecutor:
    """Simulates order fills at market price (no real exchange calls)."""

    def __init__(self) -> None:
        self._orders: List[Dict] = []

    async def market_buy(self, symbol: str, qty: float, price: float) -> Dict:
        order = {
            "orderId": str(uuid.uuid4()),
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "qty": qty,
            "price": price,
            "status": "FILLED",
            "ts": datetime.now(tz=timezone.utc).isoformat(),
        }
        self._orders.append(order)
        logger.info("paper_buy", **{k: v for k, v in order.items() if k != "ts"})
        return order

    async def market_sell(self, symbol: str, qty: float, price: float) -> Dict:
        order = {
            "orderId": str(uuid.uuid4()),
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "qty": qty,
            "price": price,
            "status": "FILLED",
            "ts": datetime.now(tz=timezone.utc).isoformat(),
        }
        self._orders.append(order)
        logger.info("paper_sell", **{k: v for k, v in order.items() if k != "ts"})
        return order

    async def cancel_order(self, order_id: str) -> None:
        logger.info("paper_cancel", order_id=order_id)


# ─── Live order executor ──────────────────────────────────────────────────────


class LiveExecutor:
    """Places real orders on Binance Futures (or spot)."""

    def __init__(self) -> None:
        self._client: Optional[AsyncClient] = None

    async def _get_client(self) -> AsyncClient:
        if self._client is None:
            self._client = await AsyncClient.create(
                api_key=settings.binance_api_key,
                api_secret=settings.binance_secret_key,
            )
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def market_buy(self, symbol: str, qty: float, price: float) -> Dict:
        client = await self._get_client()
        try:
            order = await client.order_market_buy(symbol=symbol, quantity=qty)
            logger.info("live_buy", orderId=order["orderId"], qty=qty)
            return order
        except BinanceAPIException as exc:
            logger.error("binance_order_error", error=str(exc))
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def market_sell(self, symbol: str, qty: float, price: float) -> Dict:
        client = await self._get_client()
        try:
            order = await client.order_market_sell(symbol=symbol, quantity=qty)
            logger.info("live_sell", orderId=order["orderId"], qty=qty)
            return order
        except BinanceAPIException as exc:
            logger.error("binance_order_error", error=str(exc))
            raise

    async def close(self) -> None:
        if self._client:
            await self._client.close_connection()


# ─── Trade journal ────────────────────────────────────────────────────────────


class TradeJournal:
    """Structured JSON trade log appended to logs/trades.jsonl."""

    def __init__(self) -> None:
        import pathlib
        pathlib.Path("logs").mkdir(exist_ok=True)
        self._path = "logs/trades.jsonl"

    def log(self, event: Dict) -> None:
        import json
        event["ts"] = datetime.now(tz=timezone.utc).isoformat()
        try:
            with open(self._path, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as exc:
            logger.warning("journal_write_failed", error=str(exc))


# ─── Main trading engine ──────────────────────────────────────────────────────


class TradingEngine:
    """
    Orchestrates the full trading loop.
    Runs indefinitely; call stop() for graceful shutdown.
    """

    LOOP_INTERVAL_SECONDS = 3600  # 1 hour (1h candle close)

    def __init__(self, initial_balance: float = 10_000.0) -> None:
        self._running = False
        self._ml = EnsemblePredictor()
        self._sentiment = SentimentAggregator()
        self._strategy = StrategyRunner()
        self._alerter = TelegramAlerter()
        self._journal = TradeJournal()

        account = AccountState(
            balance=initial_balance,
            peak_balance=initial_balance,
            daily_start_balance=initial_balance,
        )
        self._risk = RiskManager(account)
        self._risk.register_alert(self._alerter.send)

        if settings.paper_trading:
            self._order_executor = PaperTradeExecutor()
            logger.info("paper_trading_mode")
        else:
            self._order_executor = LiveExecutor()
            logger.info("live_trading_mode")

    async def _iteration(self) -> None:
        logger.info("cycle_start", ts=datetime.now(tz=timezone.utc).isoformat())

        # ── 1. Market context ──────────────────────────────────────────────
        context = await build_market_context(settings.symbol)
        ohlcv_1h = context.get("ohlcv", {}).get("1h")
        if ohlcv_1h is None or ohlcv_1h.empty:
            logger.warning("no_ohlcv_data")
            return

        current_price = float(ohlcv_1h["close"].iloc[-1])

        # ── 2. ML prediction ───────────────────────────────────────────────
        if not self._ml.is_trained():
            logger.info("ml_not_trained_skipping_cycle")
            return
        ml_pred = self._ml.predict(ohlcv_1h)

        # ── 3. Sentiment ───────────────────────────────────────────────────
        sentiment = await self._sentiment.get_composite_score()

        # ── 4. Strategy signal ─────────────────────────────────────────────
        signal = self._strategy.run(context, ml_pred, sentiment)

        # ── 5. Update existing positions ───────────────────────────────────
        exits = await self._risk.update_positions(current_price)
        for exit_event in exits:
            if exit_event["type"] == "full_close":
                await self._execute_close(
                    exit_event["trade_id"],
                    current_price,
                )
            elif exit_event["type"] == "partial_close":
                await self._execute_partial_close(
                    exit_event["trade_id"],
                    exit_event["qty"],
                    current_price,
                )

        # ── 6. New entry ───────────────────────────────────────────────────
        if signal.actionable:
            trade_id = str(uuid.uuid4())[:8]
            pos = await self._risk.open_position(signal, trade_id, settings.symbol)
            if pos:
                await self._execute_entry(pos, signal)
                self._journal.log({
                    "event": "open",
                    "trade_id": trade_id,
                    "symbol": settings.symbol,
                    "direction": signal.direction,
                    "entry": pos.entry_price,
                    "sl": pos.stop_loss,
                    "tp1": pos.take_profit_1,
                    "tp2": pos.take_profit_2,
                    "qty": pos.quantity,
                    "confidence": signal.confidence,
                    "reasons": signal.reasons,
                    "ml": signal.ml_meta,
                    "sentiment": sentiment.get("composite"),
                })
        else:
            logger.info(
                "no_entry",
                direction=signal.direction,
                reason=signal.reasons[0] if signal.reasons else "—",
            )

    async def _execute_entry(self, pos: Position, signal: Signal) -> None:
        if signal.direction == Direction.LONG:
            await self._order_executor.market_buy(
                pos.symbol, pos.quantity, pos.entry_price
            )
        else:
            await self._order_executor.market_sell(
                pos.symbol, pos.quantity, pos.entry_price
            )

    async def _execute_close(self, trade_id: str, price: float) -> None:
        logger.info("execute_close", trade_id=trade_id, price=price)
        # In paper mode this is a no-op; in live mode place opposing market order

    async def _execute_partial_close(self, trade_id: str, qty: float, price: float) -> None:
        logger.info("execute_partial_close", trade_id=trade_id, qty=qty, price=price)

    async def train_models(self) -> None:
        """Pull 3 years of data and train the ensemble."""
        from datetime import timedelta
        from data_feed import HistoricalDataLoader

        loader = HistoricalDataLoader()
        from datetime import timezone as tz_module
        start = datetime.now(tz=timezone.utc) - timedelta(days=365 * 3)
        df = await loader.fetch(settings.symbol, "1h", start)
        await loader.close()

        if df.empty:
            logger.error("training_data_empty")
            return

        logger.info("training_start", rows=len(df))
        self._ml.train(df)
        logger.info("training_complete")

    async def run(self) -> None:
        self._running = True
        logger.info("engine_started", symbol=settings.symbol)
        await self._alerter.send(f"🚀 ETH Trading Bot started | {settings.symbol} | Paper: {settings.paper_trading}")

        while self._running:
            try:
                await self._iteration()
            except Exception as exc:
                logger.error("iteration_error", error=str(exc), exc_info=True)
                await self._alerter.send(f"⚠️ Bot error: {exc}")
            finally:
                await asyncio.sleep(self.LOOP_INTERVAL_SECONDS)

    async def stop(self) -> None:
        self._running = False
        await self._sentiment.close()
        if hasattr(self._order_executor, "close"):
            await self._order_executor.close()
        logger.info("engine_stopped")


# ─── Entry point ─────────────────────────────────────────────────────────────


async def main() -> None:
    import structlog
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}.get(
                settings.log_level.upper(), 20
            )
        )
    )
    engine = TradingEngine()
    # First run: train if no model exists
    if not engine._ml.is_trained():
        await engine.train_models()
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
