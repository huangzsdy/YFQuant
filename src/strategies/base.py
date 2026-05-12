"""
策略库基础模块

提供策略基类和通用功能。
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple

import pandas as pd
import numpy as np


class BaseStrategy(ABC):
    """
    策略基类
    
    所有策略都应该继承此类并实现以下方法：
    - generate_signals(): 生成交易信号
    - get_parameters(): 获取策略参数
    """
    
    def __init__(
        self,
        name: str = "BaseStrategy",
        rebalance_freq: str = "daily",
    ) -> None:
        """
        初始化策略。
        
        Args:
            name: 策略名称
            rebalance_freq: 调仓频率 ('daily', 'weekly', 'monthly')
        """
        self.name = name
        self.rebalance_freq = rebalance_freq
    
    @abstractmethod
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
        pass
    
    def get_parameters(self) -> dict:
        """
        获取策略参数。
        
        Returns:
            参数字典
        """
        return {"name": self.name, "rebalance_freq": self.rebalance_freq}
    
    def _apply_rebalance_freq(
        self,
        signals: pd.Series,
        dates: pd.Series,
        freq: str,
    ) -> pd.Series:
        """
        应用调仓频率限制。
        
        Args:
            signals: 原始信号
            dates: 日期Series
            freq: 频率 ('daily', 'weekly', 'monthly')
        
        Returns:
            应用频率限制后的信号
        """
        result = signals.copy()
        
        if freq == "daily":
            # 每日都可调仓
            return result
        
        # 创建频率掩码
        if freq == "weekly":
            # 每周最后一个交易日
            mask = dates.dt.dayofweek == 4  # Friday
        elif freq == "monthly":
            # 每月最后一个交易日
            mask = dates.dt.is_month_end
        else:
            return result
        
        # 非调仓日保持之前的信号
        result[~mask] = np.nan
        result = result.ffill().fillna(0)
        
        return result
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.get_parameters()})"


def calculate_sma(prices: pd.Series, window: int) -> pd.Series:
    """
    计算简单移动平均线。
    
    Args:
        prices: 价格序列
        window: 窗口大小
    
    Returns:
        SMA序列
    """
    return prices.rolling(window=window, min_periods=window).mean()


def calculate_rsi(prices: pd.Series, window: int = 14) -> pd.Series:
    """
    计算相对强弱指数 (RSI)。
    
    Args:
        prices: 价格序列
        window: RSI周期
    
    Returns:
        RSI序列
    """
    delta = prices.diff()
    
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    avg_gain = gain.rolling(window=window, min_periods=window).mean()
    avg_loss = loss.rolling(window=window, min_periods=window).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.inf)
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_momentum(prices: pd.Series, period: int = 12) -> pd.Series:
    """
    计算动量指标。
    
    Args:
        prices: 价格序列
        period: 回顾期（月数）
    
    Returns:
        动量序列（百分比变化）
    """
    return prices.pct_change(period)