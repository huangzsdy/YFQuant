"""
均值回归策略（RSI）

策略逻辑：
- 周线 RSI(14) < 30 -> 超卖 -> 买入
- 周线 RSI(14) > 70 -> 超买 -> 卖出
- 每月调仓
"""

from typing import Optional, Tuple

import pandas as pd
import numpy as np

from .base import BaseStrategy, calculate_rsi


class MeanReversionRSI(BaseStrategy):
    """
    均值回归策略（RSI）
    
    信号生成规则：
    - RSI(14) < 30 -> 超卖区域 -> 买入 (signal=1)
    - RSI(14) > 70 -> 超买区域 -> 卖出 (signal=0)
    - 周线图表，每月调仓
    """
    
    def __init__(
        self,
        rsi_period: int = 14,
        oversold_threshold: float = 30.0,
        overbought_threshold: float = 70.0,
        rebalance_freq: str = "monthly",
    ) -> None:
        """
        初始化均值回归RSI策略。
        
        Args:
            rsi_period: RSI周期（默认14）
            oversold_threshold: 超卖阈值（默认30）
            overbought_threshold: 超买阈值（默认70）
            rebalance_freq: 调仓频率（默认每月）
        """
        super().__init__(name="MeanReversionRSI", rebalance_freq=rebalance_freq)
        self.rsi_period = rsi_period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        **kwargs,
    ) -> pd.Series:
        """
        生成交易信号。
        
        Args:
            data: 价格数据DataFrame
        
        Returns:
            信号Series（1=做多, 0=平仓）
        """
        # 获取价格
        if "Adj Close" in data.columns:
            prices = data["Adj Close"]
        elif "Close" in data.columns:
            prices = data["Close"]
        elif "close" in data.columns:
            prices = data["close"]
        else:
            raise ValueError("数据中缺少价格列")
        
        # 计算RSI
        rsi = calculate_rsi(prices, self.rsi_period)
        
        # 生成信号
        # RSI < 30 -> 买入 (1)
        # RSI > 70 -> 卖出 (0)
        signal = pd.Series(index=data.index, dtype=int)
        
        # 使用前一天的RSI值避免 look-ahead bias
        rsi_shifted = rsi.shift(1)
        
        signal = ((rsi_shifted < self.oversold_threshold).astype(int))
        
        # 当 RSI > 70 时平仓
        sell_signal = rsi_shifted > self.overbought_threshold
        signal[sell_signal] = 0
        
        # 应用调仓频率
        if "Date" in data.columns:
            dates = data["Date"]
            if not pd.api.types.is_datetime64_any_dtype(dates):
                dates = pd.to_datetime(dates)
        else:
            dates = pd.to_datetime(data.index)
        
        signal = self._apply_rebalance_freq(signal, dates, self.rebalance_freq)
        
        return signal.fillna(0).astype(int)
    
    def get_parameters(self) -> dict:
        """获取策略参数"""
        return {
            **super().get_parameters(),
            "rsi_period": self.rsi_period,
            "oversold_threshold": self.oversold_threshold,
            "overbought_threshold": self.overbought_threshold,
        }