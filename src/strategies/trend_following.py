"""
趋势跟踪策略（移动平均线）

策略逻辑：
- 长期均线：200 日 SMA
- 价格 > 均线 -> 做多
- 价格 < 均线 -> 平仓
- 每日或每周调仓
"""

from typing import Optional, Tuple

import pandas as pd
import numpy as np

from .base import BaseStrategy, calculate_sma


class TrendFollowingMA(BaseStrategy):
    """
    趋势跟踪策略（移动平均线）
    
    信号生成规则：
    - 价格 > 200 日均线 -> 做多 (signal=1)
    - 价格 < 200 日均线 -> 平仓 (signal=0)
    - 支持自定义均线周期和调仓频率
    """
    
    def __init__(
        self,
        ma_window: int = 200,
        rebalance_freq: str = "daily",
    ) -> None:
        """
        初始化趋势跟踪策略。
        
        Args:
            ma_window: 移动平均线窗口（默认200）
            rebalance_freq: 调仓频率 ('daily', 'weekly')
        """
        super().__init__(name="TrendFollowingMA", rebalance_freq=rebalance_freq)
        self.ma_window = ma_window
    
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
        
        # 计算移动平均线
        sma = calculate_sma(prices, self.ma_window)
        
        # 生成信号：价格 > 均线 -> 1, 否则 -> 0
        signal = (prices > sma).astype(int)
        
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
            "ma_window": self.ma_window,
        }