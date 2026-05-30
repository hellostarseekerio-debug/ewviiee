# ETH Algorithmic Trading Bot

Professional Ethereum (ETH/USDT) algorithmic trading bot with ML ensemble, 50+ technical indicators, multi-source sentiment, and real-time Streamlit dashboard.

## Architecture

```
/trading-bot
  /src
    config.py          # Pydantic settings from .env
    data_feed.py       # WebSocket OHLCV + all external API collection
    indicators.py      # 50+ technical indicators (pandas-ta)
    sentiment.py       # Twitter/Reddit/News/Macro NLP pipeline
    ml_model.py        # XGBoost + LightGBM + LSTM + RF + meta-learner
    strategy.py        # Multi-timeframe signal logic
    risk_manager.py    # Position sizing, stops, drawdown limits
    executor.py        # Order execution + main trading loop
    backtester.py      # VectorBT walk-forward backtesting
  /dashboard
    app.py             # Streamlit real-time dashboard
  /tests
    test_indicators.py
    test_risk_manager.py
    test_strategy.py
  docker-compose.yml
  Dockerfile
  requirements.txt
  .env.example
```

## Quick Start

### 1. Configure API keys

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required:
- `BINANCE_API_KEY` / `BINANCE_SECRET_KEY` — from Binance account
- `PAPER_TRADING=true` — keep enabled until fully tested

Optional (each degrades gracefully if missing):
- `ETHERSCAN_API_KEY` — on-chain gas/supply data
- `COINGLASS_API_KEY` — derivatives OI/funding
- `NEWSAPI_KEY` — news sentiment
- `CRYPTOPANIC_API_KEY` — crypto news
- `TWITTER_BEARER_TOKEN` — Twitter sentiment
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` — Reddit sentiment
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — trade alerts
- `ALPHA_VANTAGE_API_KEY` — macro data (DXY, Gold, SPX)
- `GLASSNODE_API_KEY` — on-chain analytics
- `WHALEALERT_API_KEY` — whale transaction alerts

### 2. Run with Docker (recommended)

```bash
docker-compose up -d postgres redis
docker-compose up bot dashboard
```

Dashboard available at: http://localhost:8501

### 3. Run locally

```bash
pip install -r requirements.txt

# Train models first (pulls 3 years of data)
cd src && python -c "
import asyncio
from executor import TradingEngine
async def main():
    e = TradingEngine()
    await e.train_models()
asyncio.run(main())
"

# Start the bot
python src/executor.py

# Start the dashboard (separate terminal)
streamlit run dashboard/app.py
```

### 4. Run backtests

```bash
# Full backtest with Optuna optimization
python -c "
import asyncio
from src.backtester import run_full_backtest
asyncio.run(run_full_backtest(optimize=True))
"

# Results saved to logs/backtest_report.json
```

### 5. Run tests

```bash
pytest tests/ -v
```

## Signal Logic

The bot only enters trades when ALL of the following align:

1. **Trend filter**: 1h, 4h, and 1D price must be on same side of 200 EMA
2. **ML confidence**: ensemble model confidence > 72% (configurable)
3. **Indicator confluence**: 3+ technical indicators firing same direction
4. **Volume confirmation**: volume > 1.5x 20-period average
5. **Sentiment**: composite score not strongly opposing the direction
6. **No blackout**: no high-impact macro events within 30 minutes

## Risk Management

| Parameter | Value |
|---|---|
| Max risk per trade | 1% of account |
| Position sizing | Half-Kelly Criterion |
| Stop loss | 1.5x ATR below entry |
| Take profit 1 (50%) | 2:1 Risk-Reward |
| Take profit 2 (50%) | 3:1 Risk-Reward |
| Trailing stop | Activates at +1R, trails 1 ATR |
| Max concurrent trades | 3 |
| Daily drawdown limit | 3% (bot pauses) |
| Total drawdown limit | 10% (bot stops + alerts) |

## ML Models

| Model | Role |
|---|---|
| XGBoost | Binary classification: next candle up/down |
| LightGBM | Regression: 4h price target |
| LSTM (Keras) | Sequence model on 60-candle windows |
| Random Forest | Feature importance + signal weighting |
| Meta-learner (LogReg) | Combines all model outputs → final probability |

Training: 3 years of 1h Binance data, walk-forward validation, weekly retraining. SHAP values for explainability.

## Indicators Implemented

**Trend (10):** EMA 9/21/50/100/200, MACD, ADX+DI, Parabolic SAR, Ichimoku, SuperTrend, HMA, VWAP, Linear Regression Channel

**Momentum (9):** RSI 7/14/21, StochRSI, Stochastic, CCI, Williams %R, ROC, Momentum, Awesome Oscillator, Ultimate Oscillator

**Volatility (5):** Bollinger Bands (+%B, bandwidth), ATR, Keltner Channels, Donchian Channels, Std Deviation Bands

**Volume (8):** OBV, VWAP, MFI, CMF, Volume Profile (POC/VAH/VAL), A/D Line, Force Index, EOM

**Market Structure (7):** Pivot Points, Fibonacci (auto-detect), S/R zones, Fair Value Gaps, Order Blocks, Wyckoff Phase, Elliott Wave (basic)

## Paper Trading (Default)

The bot defaults to `PAPER_TRADING=true`. In paper mode:
- All orders are logged/simulated, no real API calls are made
- Risk management runs identically to live mode
- All metrics and alerts function normally

Set `PAPER_TRADING=false` only after ≥30 days of paper trading with acceptable results.

## Disclaimer

This software is for educational purposes. Algorithmic trading carries significant financial risk. Past performance does not guarantee future results. Never risk money you cannot afford to lose.
