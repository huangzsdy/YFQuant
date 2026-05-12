<img src="./doc/yfinance-gh-logo-dark.webp#gh-dark-mode-only" height="100">
<img src="./doc/yfinance-gh-logo-light.webp#gh-light-mode-only" height="100">

# YFQuant - Dual ETF Trading Strategy System

**YFQuant** 是一个基于 Yahoo Finance 数据的量化交易策略系统，采用 SPY/TLT 双均线择时策略进行自动交易决策。

---

## 📋 目录 | Table of Contents

- [项目概述 | Overview](#项目概述--overview)
- [主要功能 | Features](#主要功能--features)
- [安装指南 | Installation](#安装指南--installation)
- [快速开始 | Quick Start](#快速开始--quick-start)
- [模块说明 | Module Documentation](#模块说明--module-documentation)
- [配置说明 | Configuration](#配置说明--configuration)
- [免责声明 | Disclaimer](#免责声明--disclaimer)

---

## 项目概述 | Overview

YFQuant 是一套完整的量化交易回测与信号生成系统，主要包含：

- **数据下载**：从 Yahoo Finance 获取 SPY（标普500 ETF）和 TLT（20年期国债 ETF）历史数据
- **策略回测**：基于 200 日均线的双均线择时策略，支持样本内/外测试
- **数据库管理**：SQLite 数据库存储和查询功能
- **自动调度**：定时任务自动运行策略并发送邮件通知

---

## 主要功能 | Features

### 1. 数据下载 (`download_data.py`)
- 自动下载 SPY 和 TLT 历史日线数据
- 支持自定义时间范围
- 自动处理 Yahoo Finance API 的 MultiIndex 列名问题
- 数据字段：Date, Open, High, Low, Close, Adj Close, Volume

### 2. 双均线择时策略 (`dual_etf_strategy.py`)
- **策略逻辑**：
  - 计算 SPY 的 200 日简单移动平均线 (SMA)
  - 每月最后一个交易日进行调仓
  - SPY 收盘价 > 200日均线 → 全仓持有 SPY
  - 否则 → 全仓持有 TLT
- **风控措施**：
  - 200 日预热期，数据不足时不产生交易信号
  - 佣金万分之八 + 滑点 0.01 美元/股
  - 使用 `shift(1)` 避免 look-ahead bias
- **回测分析**：
  - 样本内期间：2015-01-01 ~ 2020-12-31
  - 样本外期间：2021-01-01 ~ 至今
  - 性能指标：累计收益、年化收益、最大回撤、夏普比率

### 3. 数据库管理 (`database.py`)
- 创建和管理 `quant.db` SQLite 数据库
- 将 CSV 数据导入数据库表
- 提供日期范围查询功能
- 获取最新交易信号

### 4. 定时调度 (`scheduler.py`)
- 纽约时间下午 6 点自动运行策略
- 保存交易信号到日志文件
- 通过 Gmail SMTP 发送信号邮件

---

## 安装指南 | Installation

### 环境要求
- Python 3.8+
- pip 包管理器

### 安装依赖

```bash
pip install yfinance pandas matplotlib numpy schedule pytz
```

或使用 requirements.txt：

```bash
pip install -r requirements.txt
```

---

## 快速开始 | Quick Start

### 1. 下载数据

```bash
python download_data.py
```

输出示例：
```
2025-05-12 10:30:00 - INFO - ============================================================
2025-05-12 10:30:00 - INFO - SPY 和 TLT 历史数据下载脚本
2025-05-12 10:30:00 - INFO - ============================================================
2025-05-12 10:30:00 - INFO - 下载时间范围: 2015-01-01 至 2025-05-12
2025-05-12 10:30:00 - INFO - 股票列表: ['SPY', 'TLT']
...
2025-05-12 10:30:45 - INFO - SPY 数据已保存至 data/SPY.csv，共 2600 条记录
2025-05-12 10:30:50 - INFO - TLT 数据已保存至 data/TLT.csv，共 2600 条记录
```

### 2. 运行策略回测

```bash
python dual_etf_strategy.py
```

输出示例：
```
============================================================
策略表现摘要（含交易成本）
============================================================
【风控参数】佣金: 0.08%, 滑点: $0.01/股, 预热期: 200日
============================================================

样本内期间 (In-Sample): 2015-01-01 ~ 2020-12-31
--------------------------------------------------------------------------------
指标                         双均线策略                  SPY买入持有
--------------------------------------------------------------------------------
累计收益率:                     45.23%                    55.67%
年化收益率:                     7.85%                     9.12%
最大回撤:                      12.34%                    18.56%
夏普比率:                       0.87                      0.92
--------------------------------------------------------------------------------
```

### 3. 导入数据库（可选）

```bash
python database.py
```

### 4. 配置邮件通知（可选）

编辑 [`scheduler.py`](scheduler.py:37) 中的配置：

```python
GMAIL_USERNAME: str = "your_email@gmail.com"  # 修改为你的 Gmail 地址
GMAIL_APP_PASSWORD: str = "your_app_password"  # 修改为你的 App Password
RECIPIENTS: list = ["recipient@example.com"]  # 修改为收件人邮箱
```

### 5. 启动定时调度（可选）

```bash
python scheduler.py
```

---

## 模块说明 | Module Documentation

### download_data.py

数据下载模块，负责从 Yahoo Finance 获取历史数据。

**主要函数**：

| 函数 | 说明 |
|------|------|
| `ensure_data_directory()` | 确保数据目录存在 |
| `download_ticker_data()` | 下载单个股票数据并保存 CSV |

**配置参数**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `TICKERS` | `["SPY", "TLT"]` | 要下载的股票代码 |
| `START_DATE` | `"2015-01-01"` | 开始日期 |
| `END_DATE` | `date.today()` | 结束日期 |
| `DATA_DIR` | `Path("data")` | 数据存储目录 |

### dual_etf_strategy.py

策略回测模块，实现双均线择时策略。

**主要函数**：

| 函数 | 说明 |
|------|------|
| `load_etf_data()` | 加载 ETF 历史数据 |
| `generate_trading_signals()` | 生成交易信号 |
| `calculate_trade_costs()` | 计算交易成本 |
| `calculate_returns()` | 计算每日收益率 |
| `calculate_performance_metrics()` | 计算性能指标 |
| `plot_performance()` | 绘制收益对比图 |

**配置参数**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SMA_WINDOW` | `200` | 移动平均线窗口 |
| `WARMUP_PERIOD` | `200` | 预热期天数 |
| `COMMISSION_RATE` | `0.0008` | 佣金率（万分之八）|
| `SLIPPAGE_PER_SHARE` | `0.01` | 每股滑点（美元）|

### database.py

数据库管理模块，使用 SQLite 存储数据。

**主要类**：

- `QuantDatabase`: 数据库管理类

**主要方法**：

| 方法 | 说明 |
|------|------|
| `create_table_from_csv()` | 从 CSV 创建数据库表 |
| `import_all_csv()` | 导入所有 CSV 文件 |
| `query_by_date_range()` | 按日期范围查询 |
| `query_signal()` | 查询交易信号 |

### scheduler.py

定时调度模块，自动运行策略并发送邮件。

**主要函数**：

| 函数 | 说明 |
|------|------|
| `run_strategy()` | 运行策略脚本 |
| `get_latest_signal()` | 获取最新信号 |
| `save_signal_log()` | 保存信号日志 |
| `send_signal_email()` | 发送信号邮件 |
| `daily_trading_job()` | 每日交易任务 |

---

## 配置说明 | Configuration

### Gmail SMTP 配置

1. 登录 Gmail 账号
2. 启用"两步验证"
3. 生成"App Password"（不是邮箱密码）
4. 在 [`scheduler.py`](scheduler.py:37) 中配置：

```python
GMAIL_USERNAME = "your_email@gmail.com"
GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"  # 16位App密码
RECIPIENTS = ["recipient1@example.com", "recipient2@example.com"]
```

### 策略参数调整

编辑 [`dual_etf_strategy.py`](dual_etf_strategy.py:40) 中的配置：

```python
# 移动平均线参数
SMA_WINDOW: int = 200  # 可调整为 50, 100, 150 等

# 交易成本
COMMISSION_RATE: float = 0.0008  # 佣金万分之八
SLIPPAGE_PER_SHARE: float = 0.01  # 滑点 0.01 美元

# 回测时间范围
IN_SAMPLE_END_DATE: str = "2020-12-31"
OUT_OF_SAMPLE_START_DATE: str = "2021-01-01"
```

---

## 性能指标说明

| 指标 | 说明 |
|------|------|
| **累计收益率** | 策略总收益相对于初始资金的比例 |
| **年化收益率** | 将累计收益转换为年度收益率 |
| **最大回撤** | 从最高点到最低点的最大损失 |
| **夏普比率** | 风险调整后的收益（收益/波动）|
| **总交易次数** | 回测期间的总交易数 |
| **总交易成本** | 佣金和滑点的总成本 |

---

## 文件结构

```
YFQuant/
├── download_data.py      # 数据下载脚本
├── dual_etf_strategy.py   # 策略回测脚本
├── database.py            # 数据库管理脚本
├── scheduler.py           # 定时调度脚本
├── requirements.txt       # Python 依赖
├── data/                  # 数据存储目录
│   ├── SPY.csv           # SPY 历史数据
│   ├── TLT.csv           # TLT 历史数据
│   └── backtest_results.csv  # 回测结果
├── log/                   # 日志目录
│   └── signal_*.txt      # 信号日志
└── quant.db               # SQLite 数据库
```

---

## 常见问题

### Q: 数据下载失败怎么办？
A: 检查网络连接和 Yahoo Finance API 状态。也可以尝试增加 `timeout` 参数或重试。

### Q: 如何添加新的 ETF？
A: 修改 [`download_data.py`](download_data.py:26) 中的 `TICKERS` 列表和 [`dual_etf_strategy.py`](dual_etf_strategy.py:45) 中的配置。

### Q: 回测结果保存在哪里？
A: 回测结果保存在 `data/backtest_results.csv`。

### Q: 如何关闭邮件通知？
A: 将 [`scheduler.py`](scheduler.py:401) 中的 `send_signal_email()` 调用注释掉，或将 `GMAIL_USERNAME` 保持为默认值。

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
- 行情库：[yfinance](https://github.com/ranaroussi/yfinance)

---

**Ran Aroussi** (original yfinance)
**YFQuant Contributors** (this project)
