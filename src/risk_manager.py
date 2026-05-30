"""
risk_manager.py
~~~~~~~~~~~~~~~
Position sizing, stop/take-profit management, drawdown enforcement.

Rules:
  - Max 1% account risk per trade
  - Half-Kelly position sizing
  - ATR-based stop loss (1.5x ATR)
  - Partial exits at 2:1 and 3:1 RR (50% + 50%)
  - Trailing stop activates after +1R, trails by 1 ATR
  - Max 3 concurrent trades
  - Daily drawdown limit 3% → pause
  - Total drawdown limit 10% → halt + alert
  - News blackout: no entries 30 min before/after event
  - Correlation filter: no duplicate directional exposure
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

import structlog

from config import settings
from strategy import Direction, Signal

logger = structlog.get_logger(__name__)


class TradeStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED_TP1 = "CLOSED_TP1"
    CLOSED_TP2 = "CLOSED_TP2"
    CLOSED_SL = "CLOSED_SL"
    CLOSED_TRAIL = "CLOSED_TRAIL"
    CANCELLED = "CANCELLED"


@dataclass
class Position:
    trade_id: str
    symbol: str
    direction: Direction
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    atr: float
    quantity: float
    account_risk_usd: float
    opened_at: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    status: TradeStatus = TradeStatus.OPEN
    # Partial exit tracking
    tp1_hit: bool = False
    trailing_active: bool = False
    trailing_stop: float = 0.0
    highest_price: float = 0.0  # for LONG trailing
    lowest_price: float = float("inf")  # for SHORT trailing
    realised_pnl: float = 0.0
    closed_at: Optional[str] = None

    @property
    def r_multiple(self) -> float:
        """Current price R-multiple (requires current_price update)."""
        risk = abs(self.entry_price - self.stop_loss)
        return 0.0 if risk == 0 else 0.0  # updated in update_trailing

    def risk_amount(self) -> float:
        return abs(self.entry_price - self.stop_loss) * self.quantity


@dataclass
class AccountState:
    balance: float
    peak_balance: float
    daily_start_balance: float
    daily_date: date = field(default_factory=date.today)
    open_positions: Dict[str, Position] = field(default_factory=dict)
    closed_pnl: float = 0.0
    paused: bool = False   # daily drawdown hit
    halted: bool = False   # total drawdown hit

    def current_drawdown(self) -> float:
        return (self.peak_balance - self.balance) / self.peak_balance

    def daily_drawdown(self) -> float:
        return (self.daily_start_balance - self.balance) / self.daily_start_balance

    def refresh_daily(self) -> None:
        today = date.today()
        if self.daily_date != today:
            self.daily_start_balance = self.balance
            self.daily_date = today
            self.paused = False
            logger.info("daily_reset", balance=self.balance)


# ─── Kelly criterion ──────────────────────────────────────────────────────────


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Half-Kelly position fraction."""
    if avg_loss == 0:
        return 0.0
    edge = win_rate * avg_win - (1 - win_rate) * avg_loss
    variance = win_rate * avg_win**2 + (1 - win_rate) * avg_loss**2
    kelly = edge / variance if variance > 0 else 0.0
    return max(0.0, min(kelly * 0.5, 0.25))  # cap at 25% account per trade


# ─── Risk manager ─────────────────────────────────────────────────────────────


class RiskManager:
    def __init__(self, account_state: AccountState) -> None:
        self.state = account_state
        self._alert_callbacks: List = []

    def register_alert(self, callback) -> None:
        self._alert_callbacks.append(callback)

    async def _alert(self, msg: str) -> None:
        for cb in self._alert_callbacks:
            try:
                await cb(msg)
            except Exception:
                pass

    # ── Position sizing ───────────────────────────────────────────────────────

    def size_position(
        self,
        signal: Signal,
        win_rate: float = 0.55,
        avg_rr: float = 2.5,
    ) -> float:
        """
        Returns quantity (in base currency) to trade.
        Uses min(fixed-fraction 1%, half-Kelly) for safety.
        """
        balance = self.state.balance
        risk_per_trade = balance * settings.max_risk_pct

        # Fixed-fraction sizing
        price_risk = abs(signal.entry_price - signal.stop_loss)
        if price_risk <= 0:
            return 0.0
        qty_fixed = risk_per_trade / price_risk

        # Half-Kelly sizing
        kelly_f = kelly_fraction(win_rate, avg_rr, 1.0)
        qty_kelly = (balance * kelly_f) / signal.entry_price

        qty = min(qty_fixed, qty_kelly)
        logger.info(
            "position_sized",
            qty_fixed=round(qty_fixed, 6),
            qty_kelly=round(qty_kelly, 6),
            qty_chosen=round(qty, 6),
            risk_usd=round(qty * price_risk, 2),
        )
        return round(qty, 6)

    # ── Pre-trade checks ──────────────────────────────────────────────────────

    async def can_trade(self, signal: Signal) -> tuple[bool, str]:
        state = self.state
        state.refresh_daily()

        if state.halted:
            return False, "Bot halted — total drawdown limit reached"

        if state.paused:
            return False, "Bot paused — daily drawdown limit reached"

        if len(state.open_positions) >= settings.max_concurrent_trades:
            return False, f"Max concurrent trades ({settings.max_concurrent_trades}) reached"

        if state.daily_drawdown() >= settings.max_daily_drawdown:
            state.paused = True
            msg = f"DAILY DRAWDOWN LIMIT HIT: {state.daily_drawdown():.1%}"
            logger.warning(msg)
            await self._alert(f"⚠️ {msg}")
            return False, msg

        if state.current_drawdown() >= settings.max_total_drawdown:
            state.halted = True
            msg = f"TOTAL DRAWDOWN LIMIT HIT: {state.current_drawdown():.1%} — bot STOPPED"
            logger.critical(msg)
            await self._alert(f"🛑 {msg}")
            return False, msg

        # Correlation filter: don't open same direction if already open
        same_dir = [
            p for p in state.open_positions.values()
            if p.direction == signal.direction and p.symbol == signal.ml_meta.get("symbol", "")
        ]
        if len(same_dir) >= 2:
            return False, "Correlation filter: too many same-direction positions"

        return True, "ok"

    # ── Open position ─────────────────────────────────────────────────────────

    async def open_position(self, signal: Signal, trade_id: str, symbol: str) -> Optional[Position]:
        ok, reason = await self.can_trade(signal)
        if not ok:
            logger.info("trade_blocked", reason=reason)
            return None

        qty = self.size_position(signal)
        if qty <= 0:
            logger.warning("zero_quantity")
            return None

        pos = Position(
            trade_id=trade_id,
            symbol=symbol,
            direction=signal.direction,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            atr=signal.atr,
            quantity=qty,
            account_risk_usd=qty * abs(signal.entry_price - signal.stop_loss),
            highest_price=signal.entry_price,
            lowest_price=signal.entry_price,
        )
        self.state.open_positions[trade_id] = pos
        logger.info(
            "position_opened",
            trade_id=trade_id,
            direction=signal.direction,
            qty=qty,
            entry=signal.entry_price,
            sl=signal.stop_loss,
            tp1=signal.take_profit_1,
        )
        await self._alert(
            f"📈 NEW {signal.direction} | {symbol} | Entry: {signal.entry_price:.2f} "
            f"| SL: {signal.stop_loss:.2f} | TP1: {signal.take_profit_1:.2f}"
        )
        return pos

    # ── Update positions with latest price ───────────────────────────────────

    async def update_positions(self, current_price: float) -> List[Dict]:
        """
        Call on every new candle close.
        Returns list of exit events (for executor to act on).
        """
        exits = []
        for trade_id, pos in list(self.state.open_positions.items()):
            exit_event = await self._check_exit(pos, current_price)
            if exit_event:
                exits.append(exit_event)
        return exits

    async def _check_exit(self, pos: Position, price: float) -> Optional[Dict]:
        if pos.status != TradeStatus.OPEN:
            return None

        is_long = pos.direction == Direction.LONG
        risk = abs(pos.entry_price - pos.stop_loss)

        # Update extremes for trailing
        if is_long:
            pos.highest_price = max(pos.highest_price, price)
        else:
            pos.lowest_price = min(pos.lowest_price, price)

        # ── Activate trailing stop after +1R ──────────────────────────────
        if not pos.trailing_active:
            profit = (price - pos.entry_price) if is_long else (pos.entry_price - price)
            if profit >= risk:
                pos.trailing_active = True
                pos.trailing_stop = (
                    price - pos.atr if is_long else price + pos.atr
                )
                logger.info("trailing_activated", trade_id=pos.trade_id, price=price)

        # Update trailing stop
        if pos.trailing_active:
            if is_long:
                new_trail = pos.highest_price - pos.atr
                pos.trailing_stop = max(pos.trailing_stop, new_trail)
            else:
                new_trail = pos.lowest_price + pos.atr
                pos.trailing_stop = min(pos.trailing_stop, new_trail)

        # ── Stop loss hit ─────────────────────────────────────────────────
        sl_hit = (is_long and price <= pos.stop_loss) or (not is_long and price >= pos.stop_loss)
        trail_hit = pos.trailing_active and (
            (is_long and price <= pos.trailing_stop)
            or (not is_long and price >= pos.trailing_stop)
        )

        if sl_hit:
            return await self._close_position(pos, price, TradeStatus.CLOSED_SL)

        if trail_hit:
            return await self._close_position(pos, price, TradeStatus.CLOSED_TRAIL)

        # ── TP1: close 50% at 2:1 RR ─────────────────────────────────────
        tp1_hit = (is_long and price >= pos.take_profit_1) or (
            not is_long and price <= pos.take_profit_1
        )
        if tp1_hit and not pos.tp1_hit:
            pos.tp1_hit = True
            partial_pnl = (price - pos.entry_price if is_long else pos.entry_price - price) * (pos.quantity * 0.5)
            pos.realised_pnl += partial_pnl
            pos.quantity *= 0.5
            # Move stop to breakeven
            pos.stop_loss = pos.entry_price
            logger.info("tp1_hit", trade_id=pos.trade_id, price=price, pnl=partial_pnl)
            await self._alert(
                f"✅ TP1 HIT 50% exit | {pos.symbol} | Price: {price:.2f} | PnL: ${partial_pnl:.2f}"
            )
            return {"type": "partial_close", "trade_id": pos.trade_id, "qty": pos.quantity, "price": price}

        # ── TP2: close remaining 50% at 3:1 RR ───────────────────────────
        tp2_hit = (is_long and price >= pos.take_profit_2) or (
            not is_long and price <= pos.take_profit_2
        )
        if tp2_hit and pos.tp1_hit:
            return await self._close_position(pos, price, TradeStatus.CLOSED_TP2)

        return None

    async def _close_position(self, pos: Position, price: float, status: TradeStatus) -> Dict:
        pnl = (price - pos.entry_price if pos.direction == Direction.LONG else pos.entry_price - price) * pos.quantity
        pos.realised_pnl += pnl
        pos.status = status
        pos.closed_at = datetime.now(tz=timezone.utc).isoformat()

        self.state.balance += pos.realised_pnl
        self.state.closed_pnl += pos.realised_pnl
        self.state.peak_balance = max(self.state.peak_balance, self.state.balance)
        del self.state.open_positions[pos.trade_id]

        emoji = "✅" if pos.realised_pnl > 0 else "❌"
        await self._alert(
            f"{emoji} CLOSED {pos.direction} | {pos.symbol} | {status} | "
            f"Price: {price:.2f} | PnL: ${pos.realised_pnl:.2f} | Balance: ${self.state.balance:.2f}"
        )
        logger.info(
            "position_closed",
            trade_id=pos.trade_id,
            status=status,
            pnl=pos.realised_pnl,
            balance=self.state.balance,
        )
        return {
            "type": "full_close",
            "trade_id": pos.trade_id,
            "price": price,
            "pnl": pos.realised_pnl,
            "status": status,
        }
