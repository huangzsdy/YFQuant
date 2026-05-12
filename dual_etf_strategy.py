"""
SPY 和 TLT 双均线择时策略（含样本外测试）

【风控审计修复版本】
1. Look-ahead bias: 已验证无误 - 使用 shift(1) 避免未来函数
2. 数据复权: 已使用 Adj Close（已复权价格）
3. 交易成本: 添加佣金万分之八 + 滑点 0.01 美元/股
4. 等待期: 添加 200 日预热期，数据不足时不产生交易信号

策略逻辑：
- 读取 SPY 和 TLT 历史数据（Adj Close）
- 计算 SPY 的 200 日简单移动平均线 (SMA)
- 每月最后一个交易日进行调仓
- 预热期（200日）内不产生交易信号
- 调仓规则：
    - 如果 SPY 收盘价 > 200日均线 -> 全仓持有 SPY
    - 否则 -> 全仓持有 TLT
- 交易成本：佣金 0.08%，滑点 0.01 美元/股

样本外测试：
- 训练期（In-Sample）：2015-01-01 ~ 2020-12-31（蓝色）
- 测试期（Out-of-Sample）：2021-01-01 ~ 至今（红色）
"""

import os
import sys
import logging
from pathlib import Path
from typing import Tuple, Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np


# ============================================================
# 配置参数
# ============================================================

# 数据目录
DATA_DIR: Path = Path("data")

# 股票代码
TICKERS: Tuple[str, str] = ("SPY", "TLT")

# 移动平均线参数
SMA_WINDOW: int = 200

# 【风控】预热期：需要至少 200 个交易日的数据才能产生信号
WARMUP_PERIOD: int = SMA_WINDOW

# 【风控】交易成本
COMMISSION_RATE: float = 0.0008  # 佣金万分之八
SLIPPAGE_PER_SHARE: float = 0.01  # 滑点 0.01 美元/股

# 样本外测试划分日期
IN_SAMPLE_END_DATE: str = "2020-12-31"
OUT_OF_SAMPLE_START_DATE: str = "2021-01-01"

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger: logging.Logger = logging.getLogger(__name__)


# ============================================================
# 数据加载和验证函数
# ============================================================

def load_etf_data(ticker: str, data_dir: Path) -> pd.DataFrame:
    """
    加载单个 ETF 的历史数据。
    
    Args:
        ticker: ETF 代码（如 "SPY", "TLT"）
        data_dir: 数据目录路径
    
    Returns:
        包含历史数据的 DataFrame
    
    Raises:
        FileNotFoundError: 当 CSV 文件不存在时
        ValueError: 当数据格式不正确时
    """
    file_path: Path = data_dir / f"{ticker}.csv"
    
    if not file_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {file_path}")
    
    # 读取 CSV 文件
    df: pd.DataFrame = pd.read_csv(file_path, parse_dates=["Date"])
    
    # 按日期排序
    df = df.sort_values("Date").reset_index(drop=True)
    
    # 【风控】数据验证：检查必要列
    required_columns: set = {"Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"}
    missing_columns: set = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"{ticker} 数据缺少必要列: {missing_columns}")
    
    # 【风控】数据验证：检查 NaN 和无穷值
    if df["Adj Close"].isna().any():
        nan_count: int = df["Adj Close"].isna().sum()
        logger.warning(f"{ticker} 数据中存在 {nan_count} 个 NaN 值，将被删除")
        df = df.dropna(subset=["Adj Close"])
    
    if np.isinf(df["Adj Close"]).any():
        inf_count: int = np.isinf(df["Adj Close"]).sum()
        logger.warning(f"{ticker} 数据中存在 {inf_count} 个无穷值，将被删除")
        df = df[~np.isinf(df["Adj Close"])]
    
    logger.info(
        f"已加载 {ticker} 数据: {len(df)} 条记录，"
        f"时间范围: {df['Date'].min().strftime('%Y-%m-%d')} ~ {df['Date'].max().strftime('%Y-%m-%d')}"
    )
    
    return df


def validate_data(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """
    验证数据完整性，检查 NaN 和无穷值。
    
    Args:
        df: 待验证的数据
        name: 数据名称（用于日志）
    
    Returns:
        验证后的数据
    """
    initial_len: int = len(df)
    
    # 删除包含 NaN 的行
    nan_mask: pd.Series = df.isna().any(axis=1)
    if nan_mask.any():
        nan_count: int = nan_mask.sum()
        logger.warning(f"{name}: 删除 {nan_count} 行包含 NaN 的数据")
        df = df[~nan_mask]
    
    # 删除包含无穷值的行
    inf_mask: pd.Series = np.isinf(df.select_dtypes(include=[np.number])).any(axis=1)
    if inf_mask.any():
        inf_count: int = inf_mask.sum()
        logger.warning(f"{name}: 删除 {inf_count} 行包含无穷值的数据")
        df = df[~inf_mask]
    
    if len(df) < initial_len:
        logger.info(f"{name}: {initial_len} -> {len(df)} 条记录")
    
    return df.reset_index(drop=True)


def calculate_sma(prices: pd.Series, window: int) -> pd.Series:
    """
    计算简单移动平均线。
    
    Args:
        prices: 价格序列
        window: 移动平均窗口大小
    
    Returns:
        移动平均线序列
    """
    return prices.rolling(window=window, min_periods=window).mean()


# ============================================================
# 策略逻辑
# ============================================================

def generate_trading_signals(spy_data: pd.DataFrame) -> pd.DataFrame:
    """
    生成交易信号。
    
    【风控修复】
    - 根据 SPY 收盘价与 200 日均线的比较结果生成信号
    - 每月末进行调仓决策
    - 只有在预热期（200日）过后才产生有效信号
    
    Args:
        spy_data: SPY 历史数据
    
    Returns:
        包含信号的历史数据
    """
    df: pd.DataFrame = spy_data.copy()
    
    # 计算 200 日简单移动平均线
    df["SMA_200"] = calculate_sma(df["Adj Close"], SMA_WINDOW)
    
    # 判断是否在均线上方
    df["Above_SMA"] = df["Adj Close"] > df["SMA_200"]
    
    # 判断是否为月末（每月最后一个交易日）
    df["Is_Month_End"] = df["Date"].dt.is_month_end
    
    # 生成交易信号：1 = SPY, 0 = TLT
    df["Signal"] = df["Above_SMA"].astype(int)
    
    # 只有月末才改变持仓
    df.loc[~df["Is_Month_End"], "Signal"] = pd.NA
    df["Signal"] = df["Signal"].ffill().fillna(0).astype(int)
    
    # 【风控修复】标记预热期：预热期内（数据不足200日）信号无效
    df["In_Warmup"] = df["SMA_200"].isna()
    df["Valid_Signal"] = ~df["In_Warmup"]
    
    # 预热期后的第一个有效信号
    df["First_Valid_Signal"] = df["Valid_Signal"] & (~df["Valid_Signal"].shift(1).fillna(False))
    
    warmup_count: int = df["In_Warmup"].sum()
    if warmup_count > 0:
        logger.warning(
            f"【风控警告】预热期内有 {warmup_count} 个交易日不产生有效信号，"
            f"这些日期将不计入回测绩效"
        )
    
    return df


def calculate_trade_costs(
    df: pd.DataFrame,
    commission_rate: float = COMMISSION_RATE,
    slippage_per_share: float = SLIPPAGE_PER_SHARE,
) -> pd.DataFrame:
    """
    【风控修复】计算交易成本（佣金 + 滑点）。
    
    Args:
        df: 包含价格和信号的数据
        commission_rate: 佣金率（默认 0.0008 = 万分之八）
        slippage_per_share: 每股滑点金额（默认 0.01 美元）
    
    Returns:
        包含交易成本的数据
    """
    result_df: pd.DataFrame = df.copy()
    
    # 检测持仓变化（前一天 signal vs 今天 signal）
    # Signal 变化意味着需要交易
    result_df["Signal_Changed"] = (result_df["Signal"] != result_df["Signal"].shift(1)).fillna(False)
    
    # 计算交易价格（使用当天收盘价）
    # 买入时用 ask 价格（收盘价 + 滑点），卖出时用 bid 价格（收盘价 - 滑点）
    # 为简化，假设滑点在买卖时都收取
    result_df["Trade_Price"] = result_df["SPY_Price"]
    
    # 【风控】计算滑点成本
    # 当 signal 改变时，每股滑点成本
    # 注意：这里只对 SPY 交易收取滑点（ETF 转换时）
    # 如果只是持有 TLT 不产生交易成本
    result_df["Slippage_Cost"] = 0.0
    
    # 当持仓从 TLT 转为 SPY 时（买入 SPY）
    spy_entry: pd.Series = (result_df["Signal"] == 1) & (result_df["Signal"].shift(1) == 0)
    result_df.loc[spy_entry, "Slippage_Cost"] = slippage_per_share
    
    # 当持仓从 SPY 转为 TLT 时（卖出 SPY，买入 TLT）
    tlt_entry: pd.Series = (result_df["Signal"] == 0) & (result_df["Signal"].shift(1) == 1)
    result_df.loc[tlt_entry, "Slippage_Cost"] = slippage_per_share
    
    # 【风控】计算佣金成本
    # 假设每次交易按交易金额的 commission_rate 收取
    # 这里简化处理：按持仓变化当天的收盘价计算
    result_df["Trade_Value"] = result_df["SPY_Price"]  # 每次交易 1 股（假设）
    result_df["Commission_Cost"] = 0.0
    
    # 有持仓变化时收取佣金
    commission_mask: pd.Series = result_df["Signal_Changed"]
    result_df.loc[commission_mask, "Commission_Cost"] = (
        result_df.loc[commission_mask, "Trade_Value"] * commission_rate
    )
    
    # 总交易成本
    result_df["Total_Trade_Cost"] = result_df["Slippage_Cost"] + result_df["Commission_Cost"]
    
    # 交易成本计入当天收益率（负收益）
    result_df["Trade_Cost_Return"] = -result_df["Total_Trade_Cost"] / result_df["SPY_Price"]
    
    # 统计信息
    total_trades: int = result_df["Signal_Changed"].sum()
    total_costs: float = result_df["Total_Trade_Cost"].sum()
    avg_cost_per_trade: float = total_costs / total_trades if total_trades > 0 else 0
    
    logger.info(f"【成本统计】总交易次数: {total_trades}, 总交易成本: ${total_costs:.4f}, 平均每次: ${avg_cost_per_trade:.4f}")
    
    return result_df


def calculate_returns(data: pd.DataFrame) -> pd.DataFrame:
    """
    计算每日收益率（含交易成本）。
    
    【风控修复】
    - 使用 shift(1) 确保不使用未来数据（Look-ahead bias 已排除）
    - 扣减交易成本
    
    Args:
        data: 包含价格和信号的数据
    
    Returns:
        包含收益率的数据
    """
    df: pd.DataFrame = data.copy()
    
    # 【风控确认】使用 shift(1) 避免 look-ahead bias
    # signal[1] 的变化影响 day[1] 的收益
    
    # 计算每日价格收益率
    df["SPY_Daily_Return"] = df["SPY_Price"].pct_change()
    df["TLT_Daily_Return"] = df["TLT_Price"].pct_change()
    
    # 策略收益率：Signal=1 用 SPY，Signal=0 用 TLT
    # shift(1) 确保使用昨天的信号（今天收盘后才知道信号，用于明天的持仓）
    df["Strategy_Return"] = (
        df["Signal"].shift(1) * df["SPY_Daily_Return"] +
        (1 - df["Signal"].shift(1)) * df["TLT_Daily_Return"]
    )
    
    # SPY 买入持有收益率
    df["SPY_BuyHold_Return"] = df["SPY_Daily_Return"]
    
    # 【风控修复】扣减交易成本
    if "Trade_Cost_Return" in df.columns:
        # 只在有持仓的日子扣减成本（持仓变化当天）
        df["Strategy_Return"] = df["Strategy_Return"].fillna(0) + df["Trade_Cost_Return"].fillna(0)
    
    # 【风控修复】预热期内不产生有效收益
    df.loc[df["In_Warmup"], "Strategy_Return"] = 0.0
    df.loc[df["In_Warmup"], "SPY_BuyHold_Return"] = 0.0
    
    return df


def calculate_cumulative_returns(returns: pd.DataFrame) -> pd.DataFrame:
    """
    计算累计收益率。
    
    Args:
        returns: 包含每日收益率的数据
    
    Returns:
        包含累计收益率的数据
    """
    df: pd.DataFrame = returns.copy()
    
    # 累计收益率 = (1 + r1) * (1 + r2) * ... - 1
    df["Strategy_Cumulative"] = (1 + df["Strategy_Return"]).cumprod() - 1
    df["SPY_BuyHold_Cumulative"] = (1 + df["SPY_BuyHold_Return"]).cumprod() - 1
    
    return df


# ============================================================
# 性能指标计算
# ============================================================

def calculate_annualized_return(cumulative_return: float, days: int) -> float:
    """
    计算年化收益率。
    
    Args:
        cumulative_return: 累计收益率
        days: 交易日数
    
    Returns:
        年化收益率
    """
    if days <= 0:
        return 0.0
    return (1 + cumulative_return) ** (252 / days) - 1


def calculate_max_drawdown(cumulative_returns: pd.Series) -> float:
    """
    计算最大回撤。
    
    Args:
        cumulative_returns: 累计收益率序列
    
    Returns:
        最大回撤（正值表示回撤幅度）
    """
    cummax: pd.Series = cumulative_returns.cummax()
    drawdown: pd.Series = cummax - cumulative_returns
    return drawdown.max()


def calculate_sharpe_ratio(daily_returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """
    计算夏普比率。
    
    Args:
        daily_returns: 每日收益率序列
        risk_free_rate: 年化无风险利率（默认 0）
    
    Returns:
        夏普比率
    """
    # 过滤掉 NaN 值
    returns: np.ndarray = daily_returns.dropna().values
    if len(returns) == 0:
        return 0.0
    
    # 计算年化收益率和年化波动率
    annual_return: float = np.mean(returns) * 252
    annual_volatility: float = np.std(returns, ddof=0) * np.sqrt(252)
    
    # 避免除以零
    if annual_volatility == 0:
        return 0.0
    
    return (annual_return - risk_free_rate) / annual_volatility


def calculate_performance_metrics(
    df: pd.DataFrame,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    计算策略性能指标。
    
    Args:
        df: 包含收益率的数据
        start_date: 可选的开始日期筛选
        end_date: 可选的结束日期筛选
    
    Returns:
        包含各项指标的字典
    """
    # 筛选日期范围
    period_df: pd.DataFrame = df.copy()
    if start_date:
        period_df = period_df[period_df["Date"] >= pd.to_datetime(start_date)]
    if end_date:
        period_df = period_df[period_df["Date"] <= pd.to_datetime(end_date)]
    
    # 【风控修复】只使用有效信号的数据计算绩效
    # 排除预热期的数据
    valid_df: pd.DataFrame = period_df[~period_df["In_Warmup"]].copy()
    
    # 删除包含 NaN 或无穷值的行
    valid_df = valid_df.replace([np.inf, -np.inf], np.nan).dropna()
    
    if len(valid_df) == 0:
        return {
            "days": 0,
            "total_trades": 0,
            "total_costs": 0.0,
            "strategy_return": 0.0,
            "spy_return": 0.0,
            "strategy_annual": 0.0,
            "spy_annual": 0.0,
            "strategy_drawdown": 0.0,
            "spy_drawdown": 0.0,
            "strategy_sharpe": 0.0,
            "spy_sharpe": 0.0,
        }
    
    days: int = len(valid_df)
    
    # 累计收益率
    strategy_cumulative: float = valid_df["Strategy_Cumulative"].iloc[-1]
    spy_cumulative: float = valid_df["SPY_BuyHold_Cumulative"].iloc[-1]
    
    # 年化收益率
    strategy_annual: float = calculate_annualized_return(strategy_cumulative, days)
    spy_annual: float = calculate_annualized_return(spy_cumulative, days)
    
    # 最大回撤
    strategy_drawdown: float = calculate_max_drawdown(valid_df["Strategy_Cumulative"])
    spy_drawdown: float = calculate_max_drawdown(valid_df["SPY_BuyHold_Cumulative"])
    
    # 夏普比率
    strategy_sharpe: float = calculate_sharpe_ratio(valid_df["Strategy_Return"])
    spy_sharpe: float = calculate_sharpe_ratio(valid_df["SPY_BuyHold_Return"])
    
    # 交易统计
    total_trades: int = valid_df["Signal_Changed"].sum() if "Signal_Changed" in valid_df.columns else 0
    total_costs: float = valid_df["Total_Trade_Cost"].sum() if "Total_Trade_Cost" in valid_df.columns else 0.0
    
    return {
        "days": days,
        "total_trades": total_trades,
        "total_costs": total_costs,
        "strategy_return": strategy_cumulative,
        "spy_return": spy_cumulative,
        "strategy_annual": strategy_annual,
        "spy_annual": spy_annual,
        "strategy_drawdown": strategy_drawdown,
        "spy_drawdown": spy_drawdown,
        "strategy_sharpe": strategy_sharpe,
        "spy_sharpe": spy_sharpe,
    }


# ============================================================
# 可视化
# ============================================================

def plot_performance(
    cumulative_returns: pd.DataFrame,
    output_dir: Path,
    in_sample_end: str,
    out_sample_start: str,
) -> None:
    """
    绘制策略累计收益与 SPY 买入持有对比图。
    
    Args:
        cumulative_returns: 包含累计收益率的数据
        output_dir: 图片输出目录
        in_sample_end: 样本内结束日期
        out_sample_start: 样本外开始日期
    """
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(14, 7))
    
    # 转换日期用于绘图
    split_date: pd.Timestamp = pd.to_datetime(out_sample_start)
    
    # 绘制样本内数据（蓝色）
    in_sample: pd.DataFrame = cumulative_returns[
        (cumulative_returns["Date"] <= pd.to_datetime(in_sample_end)) &
        (~cumulative_returns["In_Warmup"])  # 【风控修复】排除预热期
    ]
    if not in_sample.empty:
        ax.plot(
            in_sample["Date"],
            in_sample["Strategy_Cumulative"] * 100,
            label="In-Sample: Dual ETF Strategy",
            linewidth=2,
            color="blue",
        )
        ax.plot(
            in_sample["Date"],
            in_sample["SPY_BuyHold_Cumulative"] * 100,
            label="In-Sample: SPY Buy & Hold",
            linewidth=2,
            color="blue",
            linestyle="--",
            alpha=0.7,
        )
    
    # 绘制样本外数据（红色）
    out_sample: pd.DataFrame = cumulative_returns[
        (cumulative_returns["Date"] >= split_date) &
        (~cumulative_returns["In_Warmup"])  # 【风控修复】排除预热期
    ]
    if not out_sample.empty:
        ax.plot(
            out_sample["Date"],
            out_sample["Strategy_Cumulative"] * 100,
            label="Out-of-Sample: Dual ETF Strategy",
            linewidth=2,
            color="red",
        )
        ax.plot(
            out_sample["Date"],
            out_sample["SPY_BuyHold_Cumulative"] * 100,
            label="Out-of-Sample: SPY Buy & Hold",
            linewidth=2,
            color="red",
            linestyle="--",
            alpha=0.7,
        )
    
    # 绘制分界线
    ax.axvline(
        x=split_date,
        color="black",
        linestyle="--",
        linewidth=2,
        label="In-Sample / Out-of-Sample Split",
    )
    
    # 设置图表标题和标签
    ax.set_title(
        "Dual ETF Strategy vs SPY Buy & Hold\n"
        "(200-Day SMA, In-Sample: Blue, Out-of-Sample: Red, w/ Trading Costs)",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Cumulative Return (%)", fontsize=12)
    ax.legend(loc="upper left", fontsize=9)
    
    # 格式化 x 轴日期
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    plt.xticks(rotation=45)
    
    # 格式化 y 轴为百分比
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    
    # 添加零线
    ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    
    plt.tight_layout()
    
    # 保存图片
    output_path: Path = output_dir / "strategy_performance.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    logger.info(f"性能对比图已保存至: {output_path}")
    
    plt.close()


def print_performance_summary(
    in_sample_metrics: dict,
    out_sample_metrics: dict,
) -> None:
    """
    打印策略表现摘要。
    
    Args:
        in_sample_metrics: 样本内指标
        out_sample_metrics: 样本外指标
    """
    def format_metrics(m: dict, period: str) -> None:
        """格式化打印单个时期的指标"""
        print(f"\n{period}")
        print("-" * 80)
        print(f"{'指标':<20} {'双均线策略':>25} {'SPY买入持有':>25}")
        print("-" * 80)
        print(f"{'累计收益率:':<20} {m['strategy_return']*100:>24.2f}% {m['spy_return']*100:>24.2f}%")
        print(f"{'年化收益率:':<20} {m['strategy_annual']*100:>24.2f}% {m['spy_annual']*100:>24.2f}%")
        print(f"{'最大回撤:':<20} {m['strategy_drawdown']*100:>24.2f}% {m['spy_drawdown']*100:>24.2f}%")
        print(f"{'夏普比率:':<20} {m['strategy_sharpe']:>25.2f} {m['spy_sharpe']:>25.2f}")
        print(f"{'交易日数:':<20} {m['days']:>25}")
        print(f"{'总交易次数:':<20} {m['total_trades']:>25}")
        print(f"{'总交易成本:':<20} ${m['total_costs']:>24.4f}")
        print("-" * 80)
    
    print("\n" + "=" * 80)
    print("策略表现摘要（含交易成本）")
    print("=" * 80)
    print(f"【风控参数】佣金: {COMMISSION_RATE*100:.2f}%, 滑点: ${SLIPPAGE_PER_SHARE:.2f}/股, 预热期: {WARMUP_PERIOD}日")
    print("=" * 80)
    
    format_metrics(in_sample_metrics, f"样本内期间 (In-Sample): 2015-01-01 ~ {IN_SAMPLE_END_DATE}")
    format_metrics(out_sample_metrics, f"样本外期间 (Out-of-Sample): {OUT_OF_SAMPLE_START_DATE} ~ 至今")
    
    # 打印对比总结
    print("\n样本外 vs 样本内 对比:")
    print("-" * 80)
    print(f"{'指标':<20} {'样本外-策略':>20} {'样本内-策略':>20} {'差异':>20}")
    print("-" * 80)
    
    annual_diff: float = (out_sample_metrics['strategy_annual'] - in_sample_metrics['strategy_annual']) * 100
    sharpe_diff: float = out_sample_metrics['strategy_sharpe'] - in_sample_metrics['strategy_sharpe']
    drawdown_diff: float = (out_sample_metrics['strategy_drawdown'] - in_sample_metrics['strategy_drawdown']) * 100
    
    print(f"{'年化收益率 (%):':<20} {out_sample_metrics['strategy_annual']*100:>19.2f}% {in_sample_metrics['strategy_annual']*100:>19.2f}% {annual_diff:>19.2f}%")
    print(f"{'夏普比率:':<20} {out_sample_metrics['strategy_sharpe']:>20.2f} {in_sample_metrics['strategy_sharpe']:>20.2f} {sharpe_diff:>20.2f}")
    print(f"{'最大回撤 (%):':<20} {out_sample_metrics['strategy_drawdown']*100:>19.2f}% {in_sample_metrics['strategy_drawdown']*100:>19.2f}% {drawdown_diff:>19.2f}%")
    print("=" * 80)


# ============================================================
# 主函数
# ============================================================

def main() -> int:
    """
    主函数：运行双均线择时策略。
    
    Returns:
        成功返回 0，失败返回 1
    """
    logger.info("=" * 80)
    logger.info("SPY/TLT 双均线择时策略（含风控审计修复）")
    logger.info(f"【风控】移动平均线窗口: {SMA_WINDOW} 日")
    logger.info(f"【风控】预热期: {WARMUP_PERIOD} 个交易日")
    logger.info(f"【风控】佣金: {COMMISSION_RATE*100:.2f}%, 滑点: ${SLIPPAGE_PER_SHARE:.2f}/股")
    logger.info(f"样本内期间: 2015-01-01 ~ {IN_SAMPLE_END_DATE}")
    logger.info(f"样本外期间: {OUT_OF_SAMPLE_START_DATE} ~ 至今")
    logger.info("=" * 80)
    
    try:
        # 加载数据
        logger.info("正在加载数据...")
        spy_data: pd.DataFrame = load_etf_data(TICKERS[0], DATA_DIR)
        tlt_data: pd.DataFrame = load_etf_data(TICKERS[1], DATA_DIR)
        
        # 合并数据（使用 SPY 的日期作为基准）
        merged_data: pd.DataFrame = spy_data[["Date", "Adj Close"]].copy()
        merged_data = merged_data.rename(columns={"Adj Close": "SPY_Price"})
        
        tlt_prices: pd.Series = tlt_data.set_index("Date")["Adj Close"]
        merged_data["TLT_Price"] = merged_data["Date"].map(
            lambda x: tlt_prices.get(x, pd.NA)
        )
        
        # 合并后只保留两个市场都有数据的日期
        merged_data = merged_data.dropna()
        merged_data = merged_data.reset_index(drop=True)
        
        logger.info(f"合并后数据: {len(merged_data)} 条记录")
        
        # 数据验证
        merged_data = validate_data(merged_data, "合并数据")
        
        # 【风控检查】数据量是否足够
        if len(merged_data) < WARMUP_PERIOD:
            logger.error(
                f"【风控错误】数据量不足：需要至少 {WARMUP_PERIOD} 个交易日，"
                f"实际只有 {len(merged_data)} 个"
            )
            return 1
        
        # 使用 SPY 的价格生成信号
        spy_with_signals: pd.DataFrame = generate_trading_signals(
            pd.DataFrame({
                "Date": merged_data["Date"],
                "Adj Close": merged_data["SPY_Price"]
            })
        )
        
        # 将信号应用到合并数据
        merged_data["Signal"] = spy_with_signals["Signal"].values
        merged_data["SMA_200"] = spy_with_signals["SMA_200"].values
        merged_data["In_Warmup"] = spy_with_signals["In_Warmup"].values
        merged_data["Valid_Signal"] = spy_with_signals["Valid_Signal"].values
        
        # 【风控修复】计算交易成本
        merged_data = calculate_trade_costs(merged_data)
        
        # 计算每日收益率
        merged_data = calculate_returns(merged_data)
        
        # 计算累计收益率
        merged_data = calculate_cumulative_returns(merged_data)
        
        # 最终数据验证
        merged_data = validate_data(merged_data, "最终数据")
        
        # 计算样本内和样本外的性能指标
        in_sample_metrics: dict = calculate_performance_metrics(
            merged_data,
            start_date="2015-01-01",
            end_date=IN_SAMPLE_END_DATE,
        )
        out_sample_metrics: dict = calculate_performance_metrics(
            merged_data,
            start_date=OUT_OF_SAMPLE_START_DATE,
        )
        
        # 打印策略摘要
        print_performance_summary(in_sample_metrics, out_sample_metrics)
        
        # 绘制对比图
        logger.info("正在生成性能对比图...")
        plot_performance(
            merged_data,
            Path("."),
            IN_SAMPLE_END_DATE,
            OUT_OF_SAMPLE_START_DATE,
        )
        
        # 保存回测结果
        output_path: Path = DATA_DIR / "backtest_results.csv"
        merged_data.to_csv(output_path, index=False)
        logger.info(f"回测结果已保存至: {output_path}")
        
        logger.info("=" * 80)
        logger.info("策略回测完成!")
        logger.info("=" * 80)
        
        return 0
        
    except FileNotFoundError as e:
        logger.error(f"数据文件未找到: {e}")
        logger.error("请先运行 download_data.py 下载数据")
        return 1
    except Exception as e:
        logger.error(f"策略回测时发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
