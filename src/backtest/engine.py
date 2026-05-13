"""
回测引擎模块

功能：
- 向量化回测，支持无未来函数偏差
- 交易成本模型（佣金 + 滑点）
- 支持分数股和整数股持仓
- 输出每日组合价值、收益和回撤
"""

import logging
from typing import Optional, Tuple

import pandas as pd
import numpy as np

logger: logging.Logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    向量化回测引擎类
    
    主要功能：
    - 严格使用 shift(1) 避免 look-ahead bias
    - 交易成本模型：$0.005/股佣金 + 0.01%滑点
    - 支持分数股和整数股持仓
    - 生成每日组合价值、收益率和回撤
    """
    
    # 默认交易成本参数
    COMMISSION_PER_SHARE: float = 0.005  # $0.005 per share
    SLIPPAGE_RATE: float = 0.0001  # 0.01% per trade
    
    def __init__(
        self,
        commission_per_share: float = COMMISSION_PER_SHARE,
        slippage_rate: float = SLIPPAGE_RATE,
        initial_capital: float = 10000.0,
        fractional_shares: bool = True,
    ) -> None:
        """
        初始化回测引擎。
        
        Args:
            commission_per_share: 每股佣金（美元）
            slippage_rate: 每笔交易滑点率
            initial_capital: 初始资金
            fractional_shares: 是否允许分数股（True）或只允许整数股（False）
        """
        self.commission_per_share = commission_per_share
        self.slippage_rate = slippage_rate
        self.initial_capital = initial_capital
        self.fractional_shares = fractional_shares
        
        logger.info(
            f"回测引擎初始化: 初始资金=${initial_capital:.2f}, "
            f"佣金=${commission_per_share}/股, 滑点={slippage_rate*100}%, "
            f"分数股={'允许' if fractional_shares else '不允许'}"
        )
    
    def run_backtest(
        self,
        prices: pd.DataFrame,
        signals: pd.Series,
        benchmark_prices: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        """
        运行回测。
        
        Args:
            prices: 价格数据DataFrame，需要包含 'Date' 列和价格列
            signals: 交易信号 Series（1=做多, 0=平仓/做空）
            benchmark_prices: 基准价格Series（用于买入持有对比）
        
        Returns:
            包含每日组合价值、收益率和回撤的DataFrame
        """
        # 合并价格和信号
        df = prices.copy()
        df["Signal"] = signals

        # 确保日期排序
        df = df.sort_values("Date").reset_index(drop=True)

        # 计算每日收益率
        df["Daily_Return"] = df["Close"].pct_change()

        # 使用前一天的信号避免 look-ahead bias
        df["Prev_Signal"] = df["Signal"].shift(1).fillna(0)

        # 计算策略收益（使用前一天信号）
        df["Strategy_Return"] = df["Prev_Signal"] * df["Daily_Return"]

        # 先计算持仓（需要初始资金）
        df = self._calculate_position(df, self.initial_capital)

        # 计算交易成本
        df = self._calculate_transaction_costs(df)

        # 计算组合价值
        df = self._calculate_portfolio_value(df)

        # 计算回撤
        df = self._calculate_drawdown(df)

        # 基准收益（买入持有）
        if benchmark_prices is not None:
            df["Benchmark_Return"] = benchmark_prices.pct_change()
            df["Benchmark_Cumulative"] = (1 + df["Benchmark_Return"]).cumprod() - 1

        # 计算策略累计收益
        df["Strategy_Cumulative"] = (1 + df["Strategy_Return"]).fillna(0).cumprod() - 1

        logger.info(f"回测完成: {len(df)} 个交易日")

        return df
    
    def _calculate_transaction_costs(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算交易成本（佣金 + 滑点）。

        Args:
            df: 包含价格和信号的DataFrame

        Returns:
            包含交易成本的DataFrame
        """
        result_df = df.copy()

        # 检测持仓变化
        result_df["Position_Changed"] = (
            result_df["Signal"] != result_df["Signal"].shift(1)
        ).fillna(False)

        # 上一期的仓位
        result_df["Prev_Signal"] = result_df["Signal"].shift(1).fillna(0)

        # 计算交易价值（使用当天收盘价）
        result_df["Trade_Value"] = 0.0

        # 当 signal 从 0 变为 1（买入）
        buy_mask = (result_df["Signal"] == 1) & (result_df["Prev_Signal"] == 0)
        result_df.loc[buy_mask, "Trade_Value"] = (
            result_df.loc[buy_mask, "Close"] * result_df.loc[buy_mask, "Shares"]
        )

        # 当 signal 从 1 变为 0（卖出）
        sell_mask = (result_df["Signal"] == 0) & (result_df["Prev_Signal"] == 1)
        result_df.loc[sell_mask, "Trade_Value"] = (
            result_df.loc[sell_mask, "Close"] * result_df.loc[sell_mask, "Shares"]
        )

        # 佣金 = 交易股数 *每股佣金（只在买卖时收取）
        result_df["Commission"] = 0.0
        result_df.loc[buy_mask | sell_mask, "Commission"] = (
            result_df.loc[buy_mask | sell_mask, "Shares"] * self.commission_per_share
        )

        # 计算滑点（按交易价值的百分比）
        result_df["Slippage"] = result_df["Trade_Value"] * self.slippage_rate

        # 总交易成本
        result_df["Transaction_Cost"] = result_df["Commission"] + result_df["Slippage"]

        # 将交易成本反映到收益中
        result_df["Net_Return"] = result_df["Strategy_Return"] - (
            result_df["Transaction_Cost"] / (result_df["Close"] * result_df["Shares"]).replace(0, 1)
        )

        return result_df
    
    def _calculate_position(
        self,
        df: pd.DataFrame,
        capital: float,
    ) -> pd.DataFrame:
        """
        计算持仓数量。
        
        Args:
            df: 包含价格和信号的DataFrame
            capital: 可用资金
        
        Returns:
            包含持仓数量的DataFrame
        """
        result_df = df.copy()
        
        # 根据资金和价格计算可买入的股数
        if self.fractional_shares:
            # 允许分数股
            result_df["Shares"] = (capital * result_df["Signal"]) / result_df["Close"]
        else:
            # 只允许整数股（向下取整）
            result_df["Shares"] = np.floor(
                (capital * result_df["Signal"]) / result_df["Close"]
            )
        
        return result_df
    
    def _calculate_portfolio_value(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算每日组合价值。
        
        Args:
            df: 包含收益和成本的DataFrame
        
        Returns:
            包含组合价值的DataFrame
        """
        result_df = df.copy()
        
        # 初始资金
        initial_value = self.initial_capital
        
        # 计算累计收益
        result_df["Cumulative_Return"] = (1 + result_df["Net_Return"]).fillna(1).cumprod()
        result_df["Portfolio_Value"] = initial_value * result_df["Cumulative_Return"]
        
        # 第一天设置为初始资金
        result_df.loc[result_df.index[0], "Portfolio_Value"] = initial_value
        
        return result_df
    
    def _calculate_drawdown(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算回撤。
        
        Args:
            df: 包含组合价值的DataFrame
        
        Returns:
            包含回撤的DataFrame
        """
        result_df = df.copy()
        
        # 历史最高点
        result_df["Peak"] = result_df["Portfolio_Value"].cummax()
        
        # 回撤 = (峰值 - 当前值) / 峰值
        result_df["Drawdown"] = (result_df["Peak"] - result_df["Portfolio_Value"]) / result_df["Peak"]
        
        # 最大回撤
        result_df["Max_Drawdown"] = result_df["Drawdown"].cummax()
        
        return result_df
    
    def calculate_turnover(self, df: pd.DataFrame) -> float:
        """
        计算换手率（用于小资金账户监控交易成本）。
        
        Args:
            df: 回测结果DataFrame
        
        Returns:
            平均日换手率
        """
        if "Trade_Value" not in df.columns or "Portfolio_Value" not in df.columns:
            logger.warning("缺少交易价值或组合价值列，无法计算换手率")
            return 0.0
        
        # 日换手率 = 交易价值 / 组合价值
        daily_turnover = df["Trade_Value"] / df["Portfolio_Value"]
        
        # 平均换手率
        avg_turnover = daily_turnover.mean()
        
        logger.info(f"平均日换手率: {avg_turnover*100:.4f}%")
        
        return avg_turnover


# ============================================================
# 主函数
# ============================================================

def main() -> int:
    """主函数：测试回测引擎"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    
    # 创建测试数据
    dates = pd.date_range("2020-01-01", periods=252, freq="B")
    prices = pd.DataFrame({
        "Date": dates,
        "Close": 100 + np.cumsum(np.random.randn(252) * 2),
    })
    prices["Close"] = prices["Close"].clip(lower=1)  # 确保价格为正
    
    # 简单买入信号
    signals = pd.Series([1 if i % 20 < 10 else 0 for i in range(252)])
    
    # 运行回测
    engine = BacktestEngine(initial_capital=10000)
    results = engine.run_backtest(prices, signals)
    
    print("\n回测结果（前10天）:")
    print(results[["Date", "Close", "Signal", "Portfolio_Value", "Drawdown"]].head(10))
    
    print(f"\n最终组合价值: ${results['Portfolio_Value'].iloc[-1]:.2f}")
    print(f"最大回撤: {results['Max_Drawdown'].iloc[-1]*100:.2f}%")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())