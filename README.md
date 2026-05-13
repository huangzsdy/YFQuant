<img src="./doc/yfinance-gh-logo-dark.webp#gh-dark-mode-only" height="100">
<img src="./doc/yfinance-gh-logo-light.webp#gh-light-mode-only" height="100">

# YFQuant - Quantitative Trading Strategy System

**YFQuant** 是一套完整的量化交易策略回测与信号生成系统，基于 Yahoo Finance 数据提供数据获取、策略回测、绩效分析等功能。

---

## 目录 | Table of Contents

- [概述 | Overview](#概述--overview)
- [功能 | Features](#功能--features)
- [安装 | Installation](#安装--installation)
- [快速开始 | Quick Start](#快速开始--quick-start)
- [模块说明 | Module Documentation](#模块说明--module-documentation)
- [配置 | Configuration](#配置--configuration)
- [免责声明 | Disclaimer](#免责声明--disclaimer)

---

## 概述 | Overview

YFQuant 提供完整的量化交易回测框架，主要包括：

- **数据层**：[`src/data/fetcher.py`](src/data/fetcher.py) - 从 Yahoo Finance 和 AkShare 获取历史数据，支持本地缓存和增量更新
- **回测引擎**：[`src/backtest/engine.py`](src/backtest/engine.py) - 向量化回测，无 look-ahead bias，支持交易成本模型
- **策略库**：[`src/strategies/`](src/strategies/) - 包含双动量、趋势跟踪、均值回归等多种低频策略
- **绩效分析**：[`src/analytics/metrics.py`](src/analytics/metrics.py) - 计算 CAGR、夏普比率、最大回撤、换手率等指标
- **Web 看板**：[`streamlit_app.py`](streamlit_app.py) - 交互式回测界面

---

## 功能 | Features

### 1. 数据获取层 (`src/data/fetcher.py`)

- **主数据源**：Yahoo Finance (yfinance)
- **备用数据源**：AkShare（中国市场镜像）
- **自动切换**：yfinance 失败时自动使用 akshare
- **数据清洗**：始终计算并使用 `Adj Close`（调整后价格）
- **本地缓存**：保存到 CSV/Parquet 文件
- **增量更新**：仅获取最新数据

### 2. 回测引擎 (`src/backtest/engine.py`)

- **无未来函数偏差**：严格使用 `shift(1)` 确保信号不泄露未来信息
- **交易成本模型**：
  - 佣金：$0.005/股
  - 滑点：0.01%/交易
- **持仓模式**：支持分数股（小额资金）和整数股
- **输出**：每日组合价值、收益率、回撤

### 3. 策略库 (`src/strategies/`)

| 策略 | 说明 | 调仓频率 |
|------|------|----------|
| `DualMomentumStrategy` | 相对动量（SPY vs TLT 12个月收益）+ 绝对动量（无风险利率）| 月度 |
| `TrendFollowingMA` | 价格 > 200日均线买入，< 均线卖出 | 每日/每周 |
| `MeanReversionRSI` | RSI(14) < 30 买入，> 70 卖出 | 每月 |

### 4. 绩效分析 (`src/analytics/metrics.py`)

- **CAGR**：年化复合增长率
- **Sharpe Ratio**：夏普比率
- **Sortino Ratio**：索提诺比率（只考虑下行波动）
- **Max Drawdown**：最大回撤
- **Calmar Ratio**：CAGR / Max Drawdown
- **Turnover Rate**：年化换手率（对小资金账户至关重要）

### 5. Streamlit 看板 (`streamlit_app.py`)

- 策略下拉选择
- 参数输入（均线周期、RSI 周期等）
- 运行回测按钮
- 权益曲线图（策略 vs 买入持有）
- 绩效指标表格

---

## 安装 | Installation

### 环境要求

- Python 3.8+
- pip 包管理器

### 安装依赖

```bash
pip install yfinance akshare pandas numpy matplotlib streamlit
```

或使用 requirements.txt：

```bash
pip install -r requirements.txt
```

---

## 快速开始 | Quick Start

### 1. 运行 Streamlit 看板

```bash
streamlit run streamlit_app.py
```

浏览器打开 http://localhost:8501

### 2. 使用 Python API

```python
from src.data.fetcher import DataFetcher
from src.backtest.engine import BacktestEngine
from src.strategies import get_strategy
from src.analytics.metrics import calculate_all_metrics

# 获取数据
fetcher = DataFetcher()
data = fetcher.fetch("SPY", "2015-01-01", "2024-01-01")

# 获取策略
strategy = get_strategy("TrendFollowingMA", ma_window=200)

# 生成信号
signals = strategy.generate_signals(data)

# 运行回测
engine = BacktestEngine(initial_capital=10000)
results = engine.run_backtest(data, signals)

# 计算指标
metrics = calculate_all_metrics(
    portfolio_value=results["Portfolio_Value"],
    returns=results["Strategy_Return"],
)
```

### 3. 命令行测试

```bash
# 测试数据获取（需网络）
python -c "import sys; sys.path.insert(0, 'src'); from data.fetcher import DataFetcher; from pathlib import Path; fetcher = DataFetcher(cache_dir=Path('data')); print(fetcher.fetch('SPY', '2020-01-01', '2020-01-31'))"

# 测试回测引擎
python -c "import sys; sys.path.insert(0, 'src'); from backtest.engine import BacktestEngine; import pandas as pd; import numpy as np; dates = pd.date_range('2020-01-01', periods=100, freq='B'); prices = pd.DataFrame({'Date': dates, 'Close': 100 + np.cumsum(np.random.randn(100) * 2)}); prices['Close'] = prices['Close'].clip(lower=1); signals = pd.Series([1 if i % 20 < 10 else 0 for i in range(100)]); engine = BacktestEngine(initial_capital=10000); results = engine.run_backtest(prices, signals); print('回测引擎测试成功!')"

# 测试策略模块
python -c "import sys; sys.path.insert(0, 'src'); from strategies.dual_momentum import DualMomentumStrategy; from strategies.trend_following import TrendFollowingMA; from strategies.mean_reversion import MeanReversionRSI; print('所有策略模块导入成功!')"

# 测试绩效指标
python -c "import sys; sys.path.insert(0, 'src'); from analytics.metrics import calculate_all_metrics; import pandas as pd; import numpy as np; dates = pd.date_range('2020-01-01', periods=252, freq='B'); np.random.seed(42); portfolio_value = pd.Series(10000 * (1 + np.cumsum(np.random.randn(252) * 0.01)), index=dates); returns = portfolio_value.pct_change().fillna(0); trades = pd.Series(np.abs(np.random.randn(252) * 100), index=dates); metrics = calculate_all_metrics(portfolio_value, returns, trades); print('绩效指标计算成功!')"
```

### 4. 运行单元测试

```bash
# 运行YFQuant自带的单元测试（数据获取器）
python -m pytest tests/test_fetcher.py -v --tb=short

# 跳过需要网络的集成测试
python -m pytest tests/ -v -m "not integration"
```

---

## 模块说明 | Module Documentation

### src/data/fetcher.py

数据获取器类。

**主要方法**：

| 方法 | 说明 |
|------|------|
| `fetch()` | 获取数据，优先 yfinance，失败时用 akshare |
| `fetch_multiple()` | 获取多个股票数据 |
| `_load_from_cache()` | 从本地 CSV 加载 |
| `_save_to_cache()` | 保存到本地 CSV |

### src/backtest/engine.py

回测引擎类。

**主要方法**：

| 方法 | 说明 |
|------|------|
| `run_backtest()` | 运行回测，返回每日组合价值 |
| `_calculate_transaction_costs()` | 计算佣金和滑点 |
| `_calculate_drawdown()` | 计算回撤 |
| `calculate_turnover()` | 计算换手率 |

### src/strategies/

策略基类和实现。

**BaseStrategy**:
- `generate_signals()`: 生成交易信号（抽象方法）
- `get_parameters()`: 获取策略参数
- `_apply_rebalance_freq()`: 应用调仓频率限制

**策略实现**:
- `DualMomentumStrategy`: 相对+绝对动量，月度调仓
- `TrendFollowingMA`: 均线趋势跟踪
- `MeanReversionRSI`: RSI 均值回归

### src/analytics/metrics.py

绩效指标计算函数。

| 函数 | 说明 |
|------|------|
| `calculate_cagr()` | 计算年化复合增长率 |
| `calculate_sharpe_ratio()` | 计算夏普比率 |
| `calculate_sortino_ratio()` | 计算索提诺比率 |
| `calculate_max_drawdown()` | 计算最大回撤 |
| `calculate_calmar_ratio()` | 计算 Calmar 比率 |
| `calculate_turnover()` | 计算换手率 |
| `calculate_all_metrics()` | 计算所有指标 |
| `print_metrics()` | 打印指标摘要 |

---

## 配置 | Configuration

### 数据源配置

数据获取器默认优先使用 yfinance，失败时自动切换到 akshare。无需额外配置。

### 回测引擎配置

```python
from src.backtest.engine import BacktestEngine

engine = BacktestEngine(
    commission_per_share=0.005,  # $0.005 per share
    slippage_rate=0.0001,        # 0.01% per trade
    initial_capital=10000.0,     # 初始资金
    fractional_shares=True,      # 允许分数股
)
```

### 策略参数配置

```python
from src.strategies import get_strategy

# 双动量策略
strategy = get_strategy("DualMomentum", 
    momentum_period=12,      # 12个月动量
    risk_free_rate=0.02,    # 2% 无风险利率
)

# 趋势跟踪策略
strategy = get_strategy("TrendFollowingMA",
    ma_window=200,          # 200日均线
)

# 均值回归策略
strategy = get_strategy("MeanReversionRSI",
    rsi_period=14,          # RSI周期
    oversold_threshold=30,  # 超卖阈值
    overbought_threshold=70 # 超买阈值
)
```

---

## 文件结构 | File Structure

```
YFQuant/
├── pyproject.toml              # 项目配置
├── requirements.txt             # Python 依赖
├── streamlit_app.py             # Web 看板
├── README.md                    # 本文件
├── LICENSE.txt                  # Apache License
├── src/
│   ├── __init__.py
│   ├── data/
│   │   └── fetcher.py          # 数据获取层
│   ├── backtest/
│   │   └── engine.py           # 回测引擎
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py             # 策略基类
│   │   ├── dual_momentum.py    # 双动量策略
│   │   ├── trend_following.py  # 趋势跟踪策略
│   │   └── mean_reversion.py   # 均值回归策略
│   └── analytics/
│       └── metrics.py          # 绩效分析
└── tests/
    ├── __init__.py
    └── test_fetcher.py          # 数据获取测试
```

---

## 性能指标说明 | Performance Metrics

| 指标 | 说明 |
|------|------|
| **CAGR** | 年化复合增长率，将累计收益转换为年度收益 |
| **Sharpe Ratio** | 夏普比率 = (年化收益 - 无风险利率) / 年化波动率 |
| **Sortino Ratio** | 索提诺比率，只考虑下行波动率 |
| **Max Drawdown** | 从峰值到谷值的最大损失 |
| **Calmar Ratio** | CAGR / Max Drawdown |
| **Turnover Rate** | 年化换手率，对小资金账户监控交易成本很重要 |
| **Win Rate** | 盈利天数占比 |
| **Profit Factor** | 总盈利 / 总亏损 |

---

## 常见问题 | FAQ

### Q: 数据下载失败怎么办？
A: 检查网络连接。系统会自动尝试 akshare 作为备用源。也可以手动使用 VPN 或代理。

### Q: 如何添加新的策略？
A: 继承 `BaseStrategy` 类，实现 `generate_signals()` 方法，然后在 [`src/strategies/__init__.py`](src/strategies/__init__.py) 中注册。

### Q: 如何处理 A 股数据？
A: 使用 `akshare` 作为数据源，它支持A股的 Sina/Tencent 镜像数据源。

### Q: 换手率有什么作用？
A: 换手率反映交易频繁程度。对于小资金账户，高换手率会导致高交易成本，影响实际收益。

---

## 免责声明 | Disclaimer

> [!IMPORTANT]
> **Yahoo!, Y!Finance, and Yahoo! finance are registered trademarks of Yahoo, Inc.**
>
> yfinance is **not** affiliated, endorsed, or vetted by Yahoo, Inc. It's an open-source tool that uses Yahoo's publicly available APIs, and is intended for research and educational purposes.
>
> **You should refer to Yahoo!'s terms of use** for details on your rights to use the actual data downloaded.
>
> Remember - the Yahoo! finance API is intended for personal use only.

**本项目仅供学习和研究使用，不构成任何投资建议。** 策略回测结果不代表未来实际收益，投资者据此操作风险自担。

---

## 许可证 | License

本项目基于 Apache Software License 发行。详见 [LICENSE.txt](LICENSE.txt)

---

## 致谢 | Credits

- 数据来源：[Yahoo Finance](https://finance.yahoo.com)
- 国际市场数据：[yfinance](https://github.com/ranaroussi/yfinance)
- 中国市场数据：[AkShare](https://github.com/akfamily/akshare)

---

**Ran Aroussi** (original yfinance)  
**YFQuant Contributors** (this project)
