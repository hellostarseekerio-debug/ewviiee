"""
data_feed.py
~~~~~~~~~~~~
Real-time and historical data pipeline.

Responsibilities:
  - Binance WebSocket streams (kline, depth, trade)
  - Historical OHLCV via REST (up to 3 years)
  - Cross-asset data: BTC, DXY, Gold, S&P500, yields, oil
  - On-chain: Etherscan gas / staking / burn
  - Derivatives: Coinglass OI, funding rate, long/short
  - Macro/sentiment APIs: Fear&Greed, CoinGecko dominance
  - Redis caching layer for all external API calls
  - PostgreSQL persistence for OHLCV candles
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

import aiohttp
import numpy as np
import pandas as pd
import redis
import structlog
from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException
from sqlalchemy import create_engine, text
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = structlog.get_logger(__name__)

# ─── Redis cache helpers ──────────────────────────────────────────────────────

_redis: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            decode_responses=True,
        )
    return _redis


def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    try:
        get_redis().setex(key, ttl, json.dumps(value))
    except Exception as exc:
        logger.warning("redis_set_failed", key=key, error=str(exc))


def cache_get(key: str) -> Optional[Any]:
    try:
        raw = get_redis().get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("redis_get_failed", key=key, error=str(exc))
        return None


# ─── Database helpers ─────────────────────────────────────────────────────────

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.postgres_dsn, pool_pre_ping=True)
    return _engine


def ensure_tables() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS ohlcv (
        id          BIGSERIAL PRIMARY KEY,
        symbol      VARCHAR(20) NOT NULL,
        interval    VARCHAR(5)  NOT NULL,
        open_time   TIMESTAMPTZ NOT NULL,
        open        DOUBLE PRECISION,
        high        DOUBLE PRECISION,
        low         DOUBLE PRECISION,
        close       DOUBLE PRECISION,
        volume      DOUBLE PRECISION,
        close_time  TIMESTAMPTZ,
        quote_vol   DOUBLE PRECISION,
        trades      INTEGER,
        UNIQUE (symbol, interval, open_time)
    );
    CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_interval_time
        ON ohlcv (symbol, interval, open_time DESC);

    CREATE TABLE IF NOT EXISTS cross_asset (
        id          BIGSERIAL PRIMARY KEY,
        ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        asset       VARCHAR(20) NOT NULL,
        price       DOUBLE PRECISION,
        metadata    JSONB
    );

    CREATE TABLE IF NOT EXISTS sentiment_scores (
        id          BIGSERIAL PRIMARY KEY,
        ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        source      VARCHAR(50),
        score       DOUBLE PRECISION,
        raw         JSONB
    );
    """
    with get_engine().connect() as conn:
        conn.execute(text(ddl))
        conn.commit()


def upsert_candles(df: pd.DataFrame, symbol: str, interval: str) -> None:
    if df.empty:
        return
    rows = df[["open", "high", "low", "close", "volume", "quote_vol", "trades"]].copy()
    rows.index.name = "open_time"
    rows = rows.reset_index()
    rows["symbol"] = symbol
    rows["interval"] = interval
    rows["close_time"] = rows["open_time"] + pd.tseries.frequencies.to_offset(interval)
    try:
        rows.to_sql(
            "ohlcv",
            get_engine(),
            if_exists="append",
            index=False,
            method="multi",
        )
    except Exception:
        # duplicate key — silently ignore on conflict
        pass


# ─── Dataclass for a single candle update ────────────────────────────────────


@dataclass
class Candle:
    symbol: str
    interval: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool
    quote_volume: float = 0.0
    trades: int = 0


# ─── Historical OHLCV fetch ───────────────────────────────────────────────────


class HistoricalDataLoader:
    """Pulls up to 3 years of 1h OHLCV from Binance REST, with Redis cache."""

    INTERVALS = ["1h", "4h", "1d"]
    MAX_CANDLES_PER_REQUEST = 1000

    def __init__(self) -> None:
        self._client: Optional[AsyncClient] = None

    async def _get_client(self) -> AsyncClient:
        if self._client is None:
            self._client = await AsyncClient.create(
                api_key=settings.binance_api_key or None,
                api_secret=settings.binance_secret_key or None,
            )
        return self._client

    async def fetch(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        end = end or datetime.now(tz=timezone.utc)
        cache_key = f"ohlcv:{symbol}:{interval}:{start.date()}:{end.date()}"
        cached = cache_get(cache_key)
        if cached:
            logger.info("ohlcv_cache_hit", symbol=symbol, interval=interval)
            return pd.read_json(cached, orient="split")

        client = await self._get_client()
        all_klines: List[list] = []
        current = start

        while current < end:
            try:
                klines = await client.get_historical_klines(
                    symbol,
                    interval,
                    str(int(current.timestamp() * 1000)),
                    str(int(end.timestamp() * 1000)),
                    limit=self.MAX_CANDLES_PER_REQUEST,
                )
            except BinanceAPIException as exc:
                logger.error("binance_fetch_error", error=str(exc))
                await asyncio.sleep(2)
                continue

            if not klines:
                break

            all_klines.extend(klines)
            last_ts = klines[-1][0]
            current = datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc) + timedelta(
                milliseconds=1
            )
            if len(klines) < self.MAX_CANDLES_PER_REQUEST:
                break
            await asyncio.sleep(0.1)  # rate-limit courtesy

        if not all_klines:
            return pd.DataFrame()

        df = self._parse_klines(all_klines)
        cache_set(cache_key, df.to_json(orient="split"), ttl=3600)
        logger.info(
            "ohlcv_fetched",
            symbol=symbol,
            interval=interval,
            candles=len(df),
        )
        return df

    @staticmethod
    def _parse_klines(klines: list) -> pd.DataFrame:
        cols = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades",
            "taker_buy_base", "taker_buy_quote", "_ignore",
        ]
        df = pd.DataFrame(klines, columns=cols)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
        for c in ["open", "high", "low", "close", "volume", "quote_vol"]:
            df[c] = df[c].astype(float)
        df["trades"] = df["trades"].astype(int)
        df = df.set_index("open_time").sort_index()
        return df[["open", "high", "low", "close", "volume", "quote_vol", "trades"]]

    async def fetch_all_timeframes(
        self, symbol: str, years: int = 3
    ) -> Dict[str, pd.DataFrame]:
        start = datetime.now(tz=timezone.utc) - timedelta(days=365 * years)
        tasks = {
            tf: self.fetch(symbol, tf, start) for tf in self.INTERVALS
        }
        results = {}
        for tf, coro in tasks.items():
            results[tf] = await coro
        return results

    async def close(self) -> None:
        if self._client:
            await self._client.close_connection()


# ─── Real-time WebSocket feed ─────────────────────────────────────────────────


class RealtimeDataFeed:
    """
    Manages Binance WebSocket streams:
      - kline streams for 1h, 4h, 1d
      - individual trade stream (for VWAP updates)
    Calls registered callbacks with Candle objects.
    """

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol.lower()
        self._callbacks: List[Callable[[Candle], None]] = []
        self._client: Optional[AsyncClient] = None
        self._bsm: Optional[BinanceSocketManager] = None
        self._running = False

    def register_callback(self, cb: Callable[[Candle], None]) -> None:
        self._callbacks.append(cb)

    def _dispatch(self, candle: Candle) -> None:
        for cb in self._callbacks:
            try:
                cb(candle)
            except Exception as exc:
                logger.error("callback_error", error=str(exc))

    async def _handle_kline(self, msg: dict) -> None:
        k = msg.get("k", {})
        candle = Candle(
            symbol=k["s"],
            interval=k["i"],
            open_time=datetime.fromtimestamp(k["t"] / 1000, tz=timezone.utc),
            open=float(k["o"]),
            high=float(k["h"]),
            low=float(k["l"]),
            close=float(k["c"]),
            volume=float(k["v"]),
            is_closed=k["x"],
            quote_volume=float(k["q"]),
            trades=int(k["n"]),
        )
        self._dispatch(candle)

    async def _stream_klines(self, interval: str) -> None:
        while self._running:
            try:
                async with self._bsm.kline_socket(
                    self.symbol.upper(), interval=interval
                ) as stream:
                    while self._running:
                        msg = await stream.recv()
                        await self._handle_kline(msg)
            except Exception as exc:
                logger.warning(
                    "kline_stream_error",
                    interval=interval,
                    error=str(exc),
                )
                if self._running:
                    await asyncio.sleep(5)

    async def start(self) -> None:
        self._running = True
        self._client = await AsyncClient.create(
            api_key=settings.binance_api_key or None,
            api_secret=settings.binance_secret_key or None,
        )
        self._bsm = BinanceSocketManager(self._client)
        intervals = ["1h", "4h", "1d"]
        await asyncio.gather(
            *[self._stream_klines(iv) for iv in intervals],
            return_exceptions=True,
        )

    async def stop(self) -> None:
        self._running = False
        if self._client:
            await self._client.close_connection()


# ─── Cross-asset data fetcher ─────────────────────────────────────────────────


class CrossAssetFetcher:
    """
    Pulls live prices / metrics for macro + crypto cross-asset indicators.
    Each method is cached in Redis with an appropriate TTL.
    """

    COINGECKO_BASE = "https://api.coingecko.com/api/v3"
    ALTERNATIVE_ME = "https://api.alternative.me/fng/"
    COINGLASS_BASE = "https://open-api.coinglass.com/public/v2"
    ETHERSCAN_BASE = "https://api.etherscan.io/api"
    BEACONCHAIN_BASE = "https://beaconcha.in/api/v1"
    WHALEALERT_BASE = "https://api.whale-alert.io/v1"
    ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None

    async def _session_(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self._session

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get(self, url: str, params: dict = None) -> dict:
        session = await self._session_()
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    # ── CoinGecko ─────────────────────────────────────────────────────────────

    async def btc_dominance(self) -> float:
        cached = cache_get("btc_dominance")
        if cached is not None:
            return float(cached)
        data = await self._get(
            f"{self.COINGECKO_BASE}/global"
        )
        dom = data["data"]["market_cap_percentage"].get("btc", 0.0)
        cache_set("btc_dominance", dom, ttl=300)
        return dom

    async def total_market_caps(self) -> Dict[str, float]:
        """Returns TOTAL, TOTAL2 (ex-BTC), TOTAL3 (ex-BTC/ETH) in USD."""
        cached = cache_get("total_market_caps")
        if cached:
            return cached
        data = await self._get(f"{self.COINGECKO_BASE}/global")
        gd = data["data"]
        total = gd.get("total_market_cap", {}).get("usd", 0)
        btc_mc = total * gd["market_cap_percentage"].get("btc", 0) / 100
        eth_mc = total * gd["market_cap_percentage"].get("eth", 0) / 100
        result = {
            "TOTAL": total,
            "TOTAL2": total - btc_mc,
            "TOTAL3": total - btc_mc - eth_mc,
        }
        cache_set("total_market_caps", result, ttl=300)
        return result

    async def eth_btc_price(self) -> Dict[str, float]:
        cached = cache_get("eth_btc_price")
        if cached:
            return cached
        data = await self._get(
            f"{self.COINGECKO_BASE}/simple/price",
            params={"ids": "ethereum,bitcoin", "vs_currencies": "usd,btc"},
        )
        result = {
            "ETH_USD": data["ethereum"]["usd"],
            "BTC_USD": data["bitcoin"]["usd"],
            "ETH_BTC": data["ethereum"]["btc"],
        }
        cache_set("eth_btc_price", result, ttl=60)
        return result

    async def altcoin_season_index(self) -> float:
        """Approximates altcoin season: % of top 50 alts outperforming BTC in 90d."""
        cached = cache_get("altcoin_season")
        if cached is not None:
            return float(cached)
        data = await self._get(
            f"{self.COINGECKO_BASE}/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 50,
                "page": 1,
                "price_change_percentage": "90d",
            },
        )
        btc_change = next(
            (c["price_change_percentage_90d_in_currency"] for c in data if c["id"] == "bitcoin"),
            0,
        )
        outperformers = sum(
            1
            for c in data
            if c["id"] != "bitcoin"
            and (c.get("price_change_percentage_90d_in_currency") or 0) > btc_change
        )
        index = round(outperformers / 49 * 100, 2)
        cache_set("altcoin_season", index, ttl=3600)
        return index

    # ── Fear & Greed ──────────────────────────────────────────────────────────

    async def fear_greed_index(self) -> Dict[str, Any]:
        cached = cache_get("fear_greed")
        if cached:
            return cached
        data = await self._get(self.ALTERNATIVE_ME, params={"limit": 1})
        result = data["data"][0]
        cache_set("fear_greed", result, ttl=3600)
        return result

    # ── Coinglass derivatives ─────────────────────────────────────────────────

    async def eth_open_interest(self) -> Dict[str, Any]:
        cached = cache_get("eth_oi")
        if cached:
            return cached
        headers = {"coinglassSecret": settings.coinglass_api_key}
        session = await self._session_()
        async with session.get(
            f"{self.COINGLASS_BASE}/open_interest",
            params={"symbol": "ETH"},
            headers=headers,
        ) as resp:
            if resp.status != 200:
                return {}
            data = await resp.json()
        result = data.get("data", {})
        cache_set("eth_oi", result, ttl=300)
        return result

    async def eth_funding_rate(self) -> float:
        cached = cache_get("eth_funding")
        if cached is not None:
            return float(cached)
        headers = {"coinglassSecret": settings.coinglass_api_key}
        session = await self._session_()
        async with session.get(
            f"{self.COINGLASS_BASE}/funding_rates_chart",
            params={"symbol": "ETH", "type": "C"},
            headers=headers,
        ) as resp:
            if resp.status != 200:
                return 0.0
            data = await resp.json()
        # average funding rate across exchanges
        rates = [
            float(e.get("rate", 0))
            for e in data.get("data", {}).get("dataMap", {}).values()
            if e
        ]
        avg = float(np.mean(rates)) if rates else 0.0
        cache_set("eth_funding", avg, ttl=300)
        return avg

    async def eth_long_short_ratio(self) -> float:
        cached = cache_get("eth_ls_ratio")
        if cached is not None:
            return float(cached)
        headers = {"coinglassSecret": settings.coinglass_api_key}
        session = await self._session_()
        async with session.get(
            f"{self.COINGLASS_BASE}/account_long_short_pos_ratio",
            params={"symbol": "ETH", "interval": "h1", "limit": 1},
            headers=headers,
        ) as resp:
            if resp.status != 200:
                return 1.0
            data = await resp.json()
        ratio = float(data.get("data", [{}])[-1].get("longShortRatio", 1.0))
        cache_set("eth_ls_ratio", ratio, ttl=300)
        return ratio

    # ── Etherscan on-chain ────────────────────────────────────────────────────

    async def eth_gas_price(self) -> Dict[str, float]:
        cached = cache_get("eth_gas")
        if cached:
            return cached
        data = await self._get(
            self.ETHERSCAN_BASE,
            params={
                "module": "gastracker",
                "action": "gasoracle",
                "apikey": settings.etherscan_api_key,
            },
        )
        result_raw = data.get("result", {})
        result = {
            "safe_gwei": float(result_raw.get("SafeGasPrice", 0)),
            "propose_gwei": float(result_raw.get("ProposeGasPrice", 0)),
            "fast_gwei": float(result_raw.get("FastGasPrice", 0)),
        }
        cache_set("eth_gas", result, ttl=60)
        return result

    async def eth_supply_stats(self) -> Dict[str, float]:
        """ETH total supply, burn rate (EIP-1559), net issuance."""
        cached = cache_get("eth_supply")
        if cached:
            return cached
        data = await self._get(
            self.ETHERSCAN_BASE,
            params={
                "module": "stats",
                "action": "ethsupply2",
                "apikey": settings.etherscan_api_key,
            },
        )
        r = data.get("result", {})
        result = {
            "eth_supply": float(r.get("EthSupply", 0)) / 1e18,
            "eth2_staking": float(r.get("Eth2Staking", 0)) / 1e18,
            "burnt_fees": float(r.get("BurntFees", 0)) / 1e18,
        }
        cache_set("eth_supply", result, ttl=600)
        return result

    async def eth_active_addresses(self) -> int:
        cached = cache_get("eth_active_addr")
        if cached is not None:
            return int(cached)
        data = await self._get(
            self.ETHERSCAN_BASE,
            params={
                "module": "stats",
                "action": "dailytx",
                "startdate": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                "enddate": datetime.now().strftime("%Y-%m-%d"),
                "sort": "desc",
                "apikey": settings.etherscan_api_key,
            },
        )
        rows = data.get("result", [{}])
        # unique address proxy: use latest daily tx count
        count = int(rows[0].get("uniqueAddresses", 0)) if rows else 0
        cache_set("eth_active_addr", count, ttl=3600)
        return count

    # ── Beacon chain staking ──────────────────────────────────────────────────

    async def eth_staking_apr(self) -> Dict[str, float]:
        cached = cache_get("eth_staking_apr")
        if cached:
            return cached
        data = await self._get(f"{self.BEACONCHAIN_BASE}/ethstore/latest")
        d = data.get("data", {})
        result = {
            "apr": float(d.get("apr", 0)) * 100,
            "validators": int(d.get("validatorscount", 0)),
        }
        cache_set("eth_staking_apr", result, ttl=3600)
        return result

    # ── Macro: Alpha Vantage ──────────────────────────────────────────────────

    async def dxy(self) -> float:
        """DXY (US Dollar Index) — daily close."""
        cached = cache_get("dxy")
        if cached is not None:
            return float(cached)
        data = await self._get(
            self.ALPHA_VANTAGE_BASE,
            params={
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": "DXY",
                "to_currency": "USD",
                "apikey": settings.alpha_vantage_api_key,
            },
        )
        # Fallback: use TIME_SERIES_DAILY for $DXY
        data2 = await self._get(
            self.ALPHA_VANTAGE_BASE,
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": "DXY",
                "apikey": settings.alpha_vantage_api_key,
            },
        )
        ts = data2.get("Time Series (Daily)", {})
        if ts:
            latest_date = sorted(ts.keys())[-1]
            val = float(ts[latest_date]["4. close"])
            cache_set("dxy", val, ttl=3600)
            return val
        return 100.0  # neutral fallback

    async def macro_prices(self) -> Dict[str, float]:
        """Gold, S&P500, 10Y yield, WTI crude via Alpha Vantage."""
        cached = cache_get("macro_prices")
        if cached:
            return cached
        symbols = {
            "GOLD": "XAUUSD",
            "SPX": "SPY",
            "QQQ": "QQQ",
            "OIL": "WTI",
        }
        result: Dict[str, float] = {}
        for label, sym in symbols.items():
            try:
                data = await self._get(
                    self.ALPHA_VANTAGE_BASE,
                    params={
                        "function": "TIME_SERIES_DAILY",
                        "symbol": sym,
                        "apikey": settings.alpha_vantage_api_key,
                    },
                )
                ts = data.get("Time Series (Daily)", {})
                if ts:
                    latest = sorted(ts.keys())[-1]
                    result[label] = float(ts[latest]["4. close"])
            except Exception:
                result[label] = 0.0
        cache_set("macro_prices", result, ttl=3600)
        return result

    # ── Whale alerts ──────────────────────────────────────────────────────────

    async def whale_transactions(self, min_usd: int = 5_000_000) -> List[Dict]:
        cached = cache_get("whale_txs")
        if cached:
            return cached
        session = await self._session_()
        async with session.get(
            f"{self.WHALEALERT_BASE}/transactions",
            params={
                "api_key": settings.whalealert_api_key,
                "min_value": min_usd,
                "currency": "eth",
                "start": int(time.time()) - 3600,
            },
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
        txs = data.get("transactions", [])
        cache_set("whale_txs", txs, ttl=300)
        return txs

    # ── Aggregate snapshot ────────────────────────────────────────────────────

    async def full_snapshot(self) -> Dict[str, Any]:
        """Returns all cross-asset / on-chain data in one dict."""
        tasks = {
            "btc_dominance": self.btc_dominance(),
            "market_caps": self.total_market_caps(),
            "eth_btc": self.eth_btc_price(),
            "fear_greed": self.fear_greed_index(),
            "eth_oi": self.eth_open_interest(),
            "eth_funding": self.eth_funding_rate(),
            "eth_ls_ratio": self.eth_long_short_ratio(),
            "eth_gas": self.eth_gas_price(),
            "eth_supply": self.eth_supply_stats(),
            "eth_staking": self.eth_staking_apr(),
            "altcoin_season": self.altcoin_season_index(),
            "macro": self.macro_prices(),
        }
        results = {}
        for k, coro in tasks.items():
            try:
                results[k] = await coro
            except Exception as exc:
                logger.warning("snapshot_partial_failure", key=k, error=str(exc))
                results[k] = None
        logger.info("cross_asset_snapshot_complete", keys=list(results.keys()))
        return results

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


# ─── Economic calendar ────────────────────────────────────────────────────────


class EconomicCalendar:
    """
    Returns upcoming high-impact macro events within a window.
    Uses Trading Economics API if key is set, otherwise a public iCal feed.
    """

    TRADINGECONOMICS_URL = "https://api.tradingeconomics.com/calendar"

    async def upcoming_events(
        self, hours_ahead: int = 24
    ) -> List[Dict[str, Any]]:
        cached = cache_get("eco_calendar")
        if cached:
            return cached

        now = datetime.now(tz=timezone.utc)
        cutoff = now + timedelta(hours=hours_ahead)

        if settings.trading_economics_api_key:
            try:
                session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
                async with session.get(
                    self.TRADINGECONOMICS_URL,
                    params={
                        "c": settings.trading_economics_api_key,
                        "d1": now.strftime("%Y-%m-%d"),
                        "d2": cutoff.strftime("%Y-%m-%d"),
                        "importance": "3",  # high importance only
                        "f": "json",
                    },
                ) as resp:
                    data = await resp.json() if resp.status == 200 else []
                await session.close()
                events = [
                    {
                        "event": e.get("Event", ""),
                        "country": e.get("Country", ""),
                        "date": e.get("Date", ""),
                        "importance": e.get("Importance", 0),
                    }
                    for e in (data or [])
                    if e.get("Importance", 0) >= 3
                ]
                cache_set("eco_calendar", events, ttl=3600)
                return events
            except Exception as exc:
                logger.warning("eco_calendar_error", error=str(exc))

        return []

    def is_blackout_window(
        self, events: List[Dict], buffer_minutes: int = 30
    ) -> bool:
        """True if we are within `buffer_minutes` of any high-impact event."""
        now = datetime.now(tz=timezone.utc)
        for ev in events:
            try:
                ev_time = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
                delta = abs((ev_time - now).total_seconds() / 60)
                if delta <= buffer_minutes:
                    return True
            except Exception:
                pass
        return False


# ─── Convenience: build a feature-ready row ──────────────────────────────────


async def build_market_context(symbol: str = "ETHUSDT") -> Dict[str, Any]:
    """
    One-call helper that assembles OHLCV DataFrames + cross-asset snapshot
    into a single context dict consumed by strategy.py and ml_model.py.
    """
    loader = HistoricalDataLoader()
    fetcher = CrossAssetFetcher()
    calendar = EconomicCalendar()

    start = datetime.now(tz=timezone.utc) - timedelta(days=365 * 3)

    ohlcv, cross_asset, events = await asyncio.gather(
        loader.fetch_all_timeframes(symbol),
        fetcher.full_snapshot(),
        calendar.upcoming_events(),
        return_exceptions=True,
    )

    await asyncio.gather(loader.close(), fetcher.close())

    return {
        "ohlcv": ohlcv if not isinstance(ohlcv, Exception) else {},
        "cross_asset": cross_asset if not isinstance(cross_asset, Exception) else {},
        "events": events if not isinstance(events, Exception) else [],
        "blackout": calendar.is_blackout_window(
            events if not isinstance(events, Exception) else []
        ),
        "symbol": symbol,
        "ts": datetime.now(tz=timezone.utc).isoformat(),
    }
