<img src="./doc/yfinance-gh-logo-dark.webp#gh-dark-mode-only" height="100">
<img src="./doc/yfinance-gh-logo-light.webp#gh-light-mode-only" height="100">

# YFQuant - Quantitative Trading Strategy System

**YFQuant** is a complete quantitative trading strategy backtesting and signal generation system, providing data fetching, strategy backtesting, performance analytics and more based on Yahoo Finance data.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Module Documentation](#module-documentation)
- [Configuration](#configuration)
- [Disclaimer](#disclaimer)

---

## Overview

YFQuant provides a complete quantitative trading backtesting framework:

- **Data Layer**: [`src/data/fetcher.py`](src/data/fetcher.py) - Fetch historical data from Yahoo Finance and AkShare, with local cache and incremental updates
- **Backtest Engine**: [`src/backtest/engine.py`](src/backtest/engine.py) - Vectorized backtesting with no look-ahead bias, supports transaction cost models
- **Strategy Library**: [`src/strategies/`](src/strategies/) - Includes dual momentum, trend following, mean reversion and other low-frequency strategies
- **Performance Analytics**: [`src/analytics/metrics.py`](src/analytics/metrics.py) - Calculate CAGR, Sharpe ratio, max drawdown, turnover rate and more
- **Web Dashboard**: [`streamlit_app.py`](streamlit_app.py) - Interactive backtesting interface

---

## Features

### 1. Data Fetcher (`src/data/fetcher.py`)

- **Primary Source**: Yahoo Finance (yfinance)
- **Fallback Source**: AkShare (China market mirror)
- **Auto-switch**: Automatically uses akshare when yfinance fails
- **Data Cleaning**: Always calculate and use `Adj Close` (adjusted for splits and dividends)
- **Local Cache**: Save to CSV/Parquet files
- **Incremental Update**: Fetch only latest data

### 2. Backtest Engine (`src/backtest/engine.py`)

- **No Look-Ahead Bias**: Strictly use `shift(1)` to prevent signal leakage
- **Transaction Cost Model**:
  - Commission: $0.005 per share
  - Slippage: 0.01% per trade
- **Position Sizing**: Support fractional shares (for small capital) and integer shares
- **Output**: Daily portfolio value, returns, and drawdown

### 3. Strategy Library (`src/strategies/`)

| Strategy | Description | Rebalance Frequency |
|----------|-------------|---------------------|
| `DualMomentumStrategy` | Relative momentum (SPY vs TLT 12-month return) + Absolute momentum (risk-free rate) | Monthly |
| `TrendFollowingMA` | Buy when price > 200-day SMA, sell when < SMA | Daily/Weekly |
| `MeanReversionRSI` | Buy when RSI(14) < 30, sell when RSI > 70 | Monthly |

### 4. Performance Analytics (`src/analytics/metrics.py`)

- **CAGR**: Compound Annual Growth Rate
- **Sharpe Ratio**: Risk-adjusted return
- **Sortino Ratio**: Downside-only volatility adjustment
- **Max Drawdown**: Maximum peak-to-trough decline
- **Calmar Ratio**: CAGR / Max Drawdown
- **Turnover Rate**: Annual turnover (crucial for small capital accounts)

### 5. Streamlit Dashboard (`streamlit_app.py`)

- Strategy dropdown selection
- Parameter inputs (MA window, RSI period, etc.)
- Run backtest button
- Equity curve chart (Strategy vs Buy & Hold)
- Performance metrics table

---

## Installation

### Requirements

- Python 3.8+
- pip package manager

### Install Dependencies

```bash
pip install yfinance akshare pandas numpy matplotlib streamlit
```

Or use requirements.txt:

```bash
pip install -r requirements.txt
```

---

## Quick Start

### 1. Run Streamlit Dashboard

```bash
streamlit run streamlit_app.py
```

Open browser at http://localhost:8501

### 2. Use Python API

```python
from src.data.fetcher import DataFetcher
from src.backtest.engine import BacktestEngine
from src.strategies import get_strategy
from src.analytics.metrics import calculate_all_metrics

# Fetch data
fetcher = DataFetcher()
data = fetcher.fetch("SPY", "2015-01-01", "2024-01-01")

# Get strategy
strategy = get_strategy("TrendFollowingMA", ma_window=200)

# Generate signals
signals = strategy.generate_signals(data)

# Run backtest
engine = BacktestEngine(initial_capital=10000)
results = engine.run_backtest(data, signals)

# Calculate metrics
metrics = calculate_all_metrics(
    portfolio_value=results["Portfolio_Value"],
    returns=results["Strategy_Return"],
)
```

### 3. Command Line Testing

```bash
# Test data fetcher
python -m src.data.fetcher

# Test backtest engine
python -m src.backtest.engine

# Test performance metrics
python -m src.analytics.metrics
```

---

## Module Documentation

### src/data/fetcher.py

Data fetcher class.

**Main Methods**:

| Method | Description |
|--------|-------------|
| `fetch()` | Fetch data, prefer yfinance, fallback to akshare |
| `fetch_multiple()` | Fetch multiple tickers |
| `_load_from_cache()` | Load from local CSV |
| `_save_to_cache()` | Save to local CSV |

### src/backtest/engine.py

Backtest engine class.

**Main Methods**:

| Method | Description |
|--------|-------------|
| `run_backtest()` | Run backtest, return daily portfolio values |
| `_calculate_transaction_costs()` | Calculate commission and slippage |
| `_calculate_drawdown()` | Calculate drawdown |
| `calculate_turnover()` | Calculate turnover rate |

### src/strategies/

Strategy base class and implementations.

**BaseStrategy**:
- `generate_signals()`: Generate trading signals (abstract method)
- `get_parameters()`: Get strategy parameters
- `_apply_rebalance_freq()`: Apply rebalance frequency limit

**Implementations**:
- `DualMomentumStrategy`: Relative + Absolute momentum, monthly rebalance
- `TrendFollowingMA`: MA trend following
- `MeanReversionRSI`: RSI mean reversion

### src/analytics/metrics.py

Performance metric functions.

| Function | Description |
|----------|-------------|
| `calculate_cagr()` | Calculate Compound Annual Growth Rate |
| `calculate_sharpe_ratio()` | Calculate Sharpe Ratio |
| `calculate_sortino_ratio()` | Calculate Sortino Ratio |
| `calculate_max_drawdown()` | Calculate Maximum Drawdown |
| `calculate_calmar_ratio()` | Calculate Calmar Ratio |
| `calculate_turnover()` | Calculate Turnover Rate |
| `calculate_all_metrics()` | Calculate all metrics |
| `print_metrics()` | Print metrics summary |

---

## Configuration

### Data Source Configuration

The data fetcher prioritizes yfinance by default and automatically switches to akshare on failure. No additional configuration needed.

### Backtest Engine Configuration

```python
from src.backtest.engine import BacktestEngine

engine = BacktestEngine(
    commission_per_share=0.005,  # $0.005 per share
    slippage_rate=0.0001,        # 0.01% per trade
    initial_capital=10000.0,     # Initial capital
    fractional_shares=True,       # Allow fractional shares
)
```

### Strategy Parameter Configuration

```python
from src.strategies import get_strategy

# Dual Momentum Strategy
strategy = get_strategy("DualMomentum", 
    momentum_period=12,      # 12-month momentum
    risk_free_rate=0.02,     # 2% risk-free rate
)

# Trend Following Strategy
strategy = get_strategy("TrendFollowingMA",
    ma_window=200,           # 200-day MA
)

# Mean Reversion Strategy
strategy = get_strategy("MeanReversionRSI",
    rsi_period=14,           # RSI period
    oversold_threshold=30,   # Oversold threshold
    overbought_threshold=70  # Overbought threshold
)
```

---

## File Structure

```
YFQuant/
├── pyproject.toml              # Project configuration
├── requirements.txt           # Python dependencies
├── streamlit_app.py            # Web dashboard
├── README.md                  # Bilingual README
├── README_en.md               # English-only README
├── LICENSE.txt                # Apache License
├── src/
│   ├── __init__.py
│   ├── data/
│   │   └── fetcher.py         # Data fetcher
│   ├── backtest/
│   │   └── engine.py          # Backtest engine
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py            # Strategy base class
│   │   ├── dual_momentum.py   # Dual momentum strategy
│   │   ├── trend_following.py # Trend following strategy
│   │   └── mean_reversion.py  # Mean reversion strategy
│   └── analytics/
│       └── metrics.py          # Performance analytics
└── tests/
    ├── __init__.py
    └── test_fetcher.py        # Data fetcher tests
```

---

## Performance Metrics

| Metric | Description |
|--------|-------------|
| **CAGR** | Compound Annual Growth Rate, annualizes cumulative return |
| **Sharpe Ratio** | (Annual Return - Risk-Free Rate) / Annual Volatility |
| **Sortino Ratio** | Similar to Sharpe but only considers downside volatility |
| **Max Drawdown** | Maximum peak-to-trough decline |
| **Calmar Ratio** | CAGR / Max Drawdown |
| **Turnover Rate** | Annual portfolio turnover, important for small capital monitoring |
| **Win Rate** | Percentage of profitable days |
| **Profit Factor** | Gross Profit / Gross Loss |

---

## FAQ

### Q: What to do if data download fails?
A: Check your network connection. The system automatically tries akshare as fallback. You can also use VPN or proxy manually.

### Q: How to add a new strategy?
A: Inherit from `BaseStrategy` class, implement `generate_signals()` method, then register in [`src/strategies/__init__.py`](src/strategies/__init__.py).

### Q: How to handle China A-share data?
A: Use `akshare` as data source, which supports A-shares via Sina/Tencent mirrors.

### Q: What's the purpose of turnover rate?
A: Turnover reflects trading frequency. For small capital accounts, high turnover leads to high transaction costs, affecting actual returns.

---

## Disclaimer

> [!IMPORTANT]
> **Yahoo!, Y!Finance, and Yahoo! finance are registered trademarks of Yahoo, Inc.**
>
> yfinance is **not** affiliated, endorsed, or vetted by Yahoo, Inc. It's an open-source tool that uses Yahoo's publicly available APIs, and is intended for research and educational purposes.
>
> **You should refer to Yahoo!'s terms of use** for details on your rights to use the actual data downloaded.
>
> Remember - the Yahoo! finance API is intended for personal use only.

**This project is for educational and research purposes only. It does not constitute any investment advice.** Backtesting results do not guarantee future performance. Investors bear their own risks.

---

## License

This project is distributed under the Apache Software License. See [LICENSE.txt](LICENSE.txt)

---

## Credits

- Data Source: [Yahoo Finance](https://finance.yahoo.com)
- International Market Data: [yfinance](https://github.com/ranaroussi/yfinance)
- China Market Data: [AkShare](https://github.com/akfamily/akshare)

---

**Ran Aroussi** (original yfinance)  
**YFQuant Contributors** (this project)