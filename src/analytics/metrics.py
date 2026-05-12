"""
绩效分析模块

功能：
- 计算 CAGR（年化复合增长率）
- 计算 Sharpe Ratio 和 Sortino Ratio
- 计算最大回撤
- 计算 Calmar Ratio
- 计算换手率（对小资金账户监控交易成本至关重要）
"""

import logging
from typing import Optional, Tuple

import pandas as pd
import numpy as np

logger: logging.Logger = logging.getLogger(__name__)


def calculate_cagr(
    cumulative_return: float,
    days: int,
) -> float:
    """
    计算年化复合增长率 (CAGR)。
    
    Args:
        cumulative_return: 累计收益率（如 0.5 表示 50%）
        days: 交易日数
    
    Returns:
        年化收益率
    """
    if days <= 0:
        return 0.0
    
    years = days / 252  # 假设每年252个交易日
    
    if cumulative_return <= -1:
        return -1.0  # 亏损100%的情况
    
    cagr = (1 + cumulative_return) ** (1 / years) - 1
    
    return cagr


def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """
    计算夏普比率 (Sharpe Ratio)。
    
    Args:
        returns: 收益率Series
        risk_free_rate: 年化无风险利率
        periods_per_year: 每年交易天数（默认252）
    
    Returns:
        夏普比率
    """
    # 过滤掉 NaN 值
    returns = returns.dropna()
    
    if len(returns) == 0:
        return 0.0
    
    # 计算年化收益率和年化波动率
    annual_return = returns.mean() * periods_per_year
    annual_volatility = returns.std() * np.sqrt(periods_per_year)
    
    # 避免除以零
    if annual_volatility == 0:
        return 0.0
    
    sharpe = (annual_return - risk_free_rate) / annual_volatility
    
    return sharpe


def calculate_sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
    target_return: float = 0.0,
) -> float:
    """
    计算索提诺比率 (Sortino Ratio)。
    
    Sortino Ratio 使用下行波动率而不是总波动率。
    
    Args:
        returns: 收益率Series
        risk_free_rate: 年化无风险利率
        periods_per_year: 每年交易天数
        target_return: 目标收益率（低于此收益视为损失）
    
    Returns:
        索提诺比率
    """
    returns = returns.dropna()
    
    if len(returns) == 0:
        return 0.0
    
    # 计算年化收益率
    annual_return = returns.mean() * periods_per_year
    
    # 计算下行偏差（只考虑低于目标收益的部分）
    downside_returns = returns[returns < target_return]
    
    if len(downside_returns) == 0:
        # 没有下行收益，所有收益都是好的
        return np.inf if annual_return > risk_free_rate else 0.0
    
    downside_std = downside_returns.std() * np.sqrt(periods_per_year)
    
    if downside_std == 0:
        return 0.0
    
    sortino = (annual_return - risk_free_rate) / downside_std
    
    return sortino


def calculate_max_drawdown(
    cumulative_returns: pd.Series,
) -> Tuple[float, str, str]:
    """
    计算最大回撤。
    
    Args:
        cumulative_returns: 累计收益率Series
    
    Returns:
        (最大回撤值, 开始日期, 结束日期)
    """
    if len(cumulative_returns) == 0:
        return 0.0, "", ""
    
    # 计算历史最高点
    running_max = cumulative_returns.cummax()
    
    # 计算回撤
    drawdown = cumulative_returns - running_max
    
    # 找到最大回撤
    max_dd_idx = drawdown.idxmin()
    max_dd = drawdown.loc[max_dd_idx]
    
    # 找到回撤开始的日期（峰值点）
    peak_idx = running_max.loc[:max_dd_idx].idxmax()
    
    # 获取日期（如果是DatetimeIndex）
    if isinstance(cumulative_returns.index, pd.DatetimeIndex):
        peak_date = peak_idx.strftime("%Y-%m-%d") if hasattr(peak_idx, "strftime") else str(peak_idx)
        trough_date = max_dd_idx.strftime("%Y-%m-%d") if hasattr(max_dd_idx, "strftime") else str(max_dd_idx)
    else:
        peak_date = str(peak_idx)
        trough_date = str(max_dd_idx)
    
    return abs(max_dd), peak_date, trough_date


def calculate_calmar_ratio(
    cagr: float,
    max_drawdown: float,
) -> float:
    """
    计算 Calmar Ratio。
    
    Calmar Ratio = 年化收益率 / 最大回撤
    
    Args:
        cagr: 年化收益率
        max_drawdown: 最大回撤（正数表示回撤幅度）
    
    Returns:
        Calmar Ratio
    """
    if max_drawdown == 0:
        return 0.0
    
    return cagr / max_drawdown


def calculate_turnover(
    trades: pd.Series,
    portfolio_value: pd.Series,
) -> float:
    """
    计算换手率（对小资金账户监控交易成本至关重要）。
    
    Args:
        trades: 每日交易价值Series
        portfolio_value: 每日组合价值Series
    
    Returns:
        平均年化换手率
    """
    if len(trades) == 0 or len(portfolio_value) == 0:
        return 0.0
    
    # 日换手率 = 交易价值 / 组合价值
    daily_turnover = trades / portfolio_value
    
    # 平均日换手率
    avg_daily_turnover = daily_turnover.mean()
    
    # 年化换手率（假设252个交易日）
    annual_turnover = avg_daily_turnover * 252
    
    logger.info(f"年化换手率: {annual_turnover*100:.2f}%")
    
    return annual_turnover


def calculate_volatility(
    returns: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """
    计算年化波动率。
    
    Args:
        returns: 收益率Series
        periods_per_year: 每年交易天数
    
    Returns:
        年化波动率
    """
    returns = returns.dropna()
    
    if len(returns) == 0:
        return 0.0
    
    return returns.std() * np.sqrt(periods_per_year)


def calculate_win_rate(returns: pd.Series) -> float:
    """
    计算胜率。
    
    Args:
        returns: 收益率Series
    
    Returns:
        胜率（正收益天数 / 总天数）
    """
    returns = returns.dropna()
    
    if len(returns) == 0:
        return 0.0
    
    win_days = (returns > 0).sum()
    total_days = len(returns)
    
    return win_days / total_days


def calculate_profit_factor(returns: pd.Series) -> float:
    """
    计算盈利因子。
    
    Args:
        returns: 收益率Series
    
    Returns:
        盈利因子（总盈利 / 总亏损）
    """
    returns = returns.dropna()
    
    if len(returns) == 0:
        return 0.0
    
    gross_profit = returns[returns > 0].sum()
    gross_loss = abs(returns[returns < 0].sum())
    
    if gross_loss == 0:
        return np.inf if gross_profit > 0 else 0.0
    
    return gross_profit / gross_loss


def calculate_all_metrics(
    portfolio_value: pd.Series,
    returns: pd.Series,
    trades: Optional[pd.Series] = None,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> dict:
    """
    计算所有绩效指标。
    
    Args:
        portfolio_value: 组合价值Series
        returns: 收益率Series
        trades: 交易价值Series（用于计算换手率）
        risk_free_rate: 年化无风险利率
        periods_per_year: 每年交易天数
    
    Returns:
        包含所有指标的字典
    """
    # 计算累计收益率
    cumulative_return = (portfolio_value.iloc[-1] / portfolio_value.iloc[0]) - 1
    
    # 计算交易天数
    days = len(returns)
    
    # 计算 CAGR
    cagr = calculate_cagr(cumulative_return, days)
    
    # 计算波动率
    volatility = calculate_volatility(returns, periods_per_year)
    
    # 计算 Sharpe Ratio
    sharpe = calculate_sharpe_ratio(returns, risk_free_rate, periods_per_year)
    
    # 计算 Sortino Ratio
    sortino = calculate_sortino_ratio(returns, risk_free_rate, periods_per_year)
    
    # 计算最大回撤
    cumulative_returns_series = (portfolio_value / portfolio_value.iloc[0]) - 1
    max_drawdown, dd_start, dd_end = calculate_max_drawdown(cumulative_returns_series)
    
    # 计算 Calmar Ratio
    calmar = calculate_calmar_ratio(cagr, max_drawdown)
    
    # 计算换手率
    turnover = 0.0
    if trades is not None and len(trades) > 0:
        turnover = calculate_turnover(trades, portfolio_value)
    
    # 计算胜率
    win_rate = calculate_win_rate(returns)
    
    # 计算盈利因子
    profit_factor = calculate_profit_factor(returns)
    
    metrics = {
        "total_return": cumulative_return,
        "cagr": cagr,
        "volatility": volatility,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_drawdown,
        "max_drawdown_start": dd_start,
        "max_drawdown_end": dd_end,
        "calmar_ratio": calmar,
        "turnover_rate": turnover,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_days": days,
        "annual_volatility": volatility,
    }
    
    return metrics


def print_metrics(metrics: dict, strategy_name: str = "Strategy") -> None:
    """
    打印绩效指标摘要。
    
    Args:
        metrics: 指标字典
        strategy_name: 策略名称
    """
    print(f"\n{'='*60}")
    print(f"{strategy_name} 绩效摘要")
    print(f"{'='*60}")
    print(f"{'指标':<25} {'数值':>20}")
    print(f"{'-'*60}")
    print(f"{'总收益率:':<25} {metrics['total_return']*100:>19.2f}%")
    print(f"{'年化收益率 (CAGR):':<25} {metrics['cagr']*100:>19.2f}%")
    print(f"{'年化波动率:':<25} {metrics['volatility']*100:>19.2f}%")
    print(f"{'夏普比率:':<25} {metrics['sharpe_ratio']:>20.2f}")
    print(f"{'索提诺比率:':<25} {metrics['sortino_ratio']:>20.2f}")
    print(f"{'Calmar 比率:':<25} {metrics['calmar_ratio']:>20.2f}")
    print(f"{'最大回撤:':<25} {metrics['max_drawdown']*100:>19.2f}%")
    print(f"{'胜率:':<25} {metrics['win_rate']*100:>19.2f}%")
    print(f"{'盈利因子:':<25} {metrics['profit_factor']:>20.2f}")
    print(f"{'年化换手率:':<25} {metrics['turnover_rate']*100:>19.2f}%")
    print(f"{'-'*60}")
    print(f"{'最大回撤期间:':<25} {metrics['max_drawdown_start']} ~ {metrics['max_drawdown_end']}")
    print(f"{'总交易日数:':<25} {metrics['total_days']:>20}")
    print(f"{'='*60}")


# ============================================================
# 主函数
# ============================================================

def main() -> int:
    """主函数：测试绩效计算"""
    # 创建测试数据
    dates = pd.date_range("2020-01-01", periods=504, freq="B")
    np.random.seed(42)
    
    portfolio_value = pd.Series(
        10000 * (1 + np.cumsum(np.random.randn(504) * 0.01)),
        index=dates,
    )
    returns = portfolio_value.pct_change().fillna(0)
    trades = pd.Series(np.abs(np.random.randn(504) * 100), index=dates)
    
    # 计算所有指标
    metrics = calculate_all_metrics(
        portfolio_value=portfolio_value,
        returns=returns,
        trades=trades,
        risk_free_rate=0.02,
    )
    
    # 打印结果
    print_metrics(metrics, "Test Strategy")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())