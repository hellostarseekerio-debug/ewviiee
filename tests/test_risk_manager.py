"""Unit tests for risk manager logic."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from risk_manager import AccountState, RiskManager
from strategy import Direction, Signal


def make_account(balance: float = 10_000.0) -> AccountState:
    return AccountState(
        balance=balance,
        peak_balance=balance,
        daily_start_balance=balance,
    )


def make_signal(direction: Direction = Direction.LONG, confidence: float = 0.80) -> Signal:
    return Signal(
        direction=direction,
        confidence=confidence,
        strength=0.7,
        entry_price=2000.0,
        stop_loss=1970.0,   # 30 USD risk
        take_profit_1=2060.0,
        take_profit_2=2090.0,
        atr=20.0,
    )


def test_position_sizing():
    rm = RiskManager(make_account(10_000))
    sig = make_signal()
    qty = rm.size_position(sig)
    # Max risk 1% = $100, price risk = $30 → qty ≈ 3.33
    assert qty == pytest.approx(3.333333, abs=0.01)


def test_can_trade_basic():
    rm = RiskManager(make_account())
    sig = make_signal()
    ok, reason = asyncio.run(rm.can_trade(sig))
    assert ok
    assert reason == "ok"


def test_max_concurrent_trades():
    from risk_manager import Position, TradeStatus

    rm = RiskManager(make_account())
    sig = make_signal()
    # Fill up to max
    for i in range(3):
        pos = Position(
            trade_id=str(i), symbol="ETHUSDT", direction=Direction.LONG,
            entry_price=2000, stop_loss=1970, take_profit_1=2060, take_profit_2=2090,
            atr=20, quantity=1.0, account_risk_usd=30.0,
        )
        rm.state.open_positions[str(i)] = pos

    ok, reason = asyncio.run(rm.can_trade(sig))
    assert not ok
    assert "Max concurrent" in reason


def test_daily_drawdown_pause():
    acct = make_account(10_000)
    acct.balance = 9_600  # 4% drawdown > 3% limit
    rm = RiskManager(acct)
    ok, reason = asyncio.run(rm.can_trade(make_signal()))
    assert not ok
    assert "DAILY" in reason.upper()
    assert acct.paused


def test_total_drawdown_halt():
    acct = make_account(10_000)
    acct.balance = 8_900   # 11% drawdown > 10% limit
    rm = RiskManager(acct)
    ok, reason = asyncio.run(rm.can_trade(make_signal()))
    assert not ok
    assert "TOTAL" in reason.upper()
    assert acct.halted


def test_kelly_fraction():
    from risk_manager import kelly_fraction
    f = kelly_fraction(0.55, 2.0, 1.0)
    assert 0 < f < 0.25


def test_tp1_partial_close():
    acct = make_account()
    rm = RiskManager(acct)
    from risk_manager import Position, TradeStatus

    pos = Position(
        trade_id="t1", symbol="ETHUSDT", direction=Direction.LONG,
        entry_price=2000, stop_loss=1970, take_profit_1=2060,
        take_profit_2=2090, atr=20, quantity=2.0, account_risk_usd=60.0,
        highest_price=2000, lowest_price=2000,
    )
    rm.state.open_positions["t1"] = pos

    # Price hits TP1
    exits = asyncio.run(rm.update_positions(2060.0))
    assert len(exits) == 1
    assert exits[0]["type"] == "partial_close"
    assert pos.tp1_hit
    assert pos.quantity == 1.0  # halved
    assert pos.stop_loss == 2000.0  # moved to breakeven


def test_stop_loss_close():
    acct = make_account()
    rm = RiskManager(acct)
    from risk_manager import Position

    pos = Position(
        trade_id="t2", symbol="ETHUSDT", direction=Direction.LONG,
        entry_price=2000, stop_loss=1970, take_profit_1=2060,
        take_profit_2=2090, atr=20, quantity=1.0, account_risk_usd=30.0,
        highest_price=2000, lowest_price=2000,
    )
    rm.state.open_positions["t2"] = pos

    exits = asyncio.run(rm.update_positions(1965.0))  # below SL
    assert len(exits) == 1
    assert exits[0]["type"] == "full_close"
    assert exits[0]["pnl"] < 0
    assert "t2" not in rm.state.open_positions
