"""
双动量策略

策略逻辑：
- 相对动量：比较 SPY 与 TLT 的 12 个月收益率
- 绝对动量：与无风险利率比较
- 每月调仓
"""

from typing import Optional, Tuple

import pandas as pd
import numpy as np

from .base import BaseStrategy, calculate_momentum


class DualMomentumStrategy(BaseStrategy):
    """
    双动量策略
    
    信号生成规则：
    - 相对动量：比较 SPY vs TLT 的 12 个月收益
    - 绝对动量：风险资产收益 > 无风险利率
    - 每月末调仓
    """
    
    def __init__(
        self,
        momentum_period: int = 12,  # 月度动量
        risk_free_rate: float = 0.02,  # 年化无风险利率
        rebalance_freq: str = "monthly",
    ) -> None:
        """
        初始化双动量策略。
        
        Args:
            momentum_period: 动量计算周期（月数，默认12）
            risk_free_rate: 年化无风险利率（默认2%）
            rebalance_freq: 调仓频率
        """
        super().__init__(name="DualMomentum", rebalance_freq=rebalance_freq)
        self.momentum_period = momentum_period
        self.risk_free_rate = risk_free_rate
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        **kwargs,
    ) -> pd.Series:
        """
        生成交易信号。
        
        Args:
            data: 包含 SPY 和 TLT 价格的DataFrame
        
        Returns:
            信号Series
        """
        # 获取价格数据
        spy_prices = data["SPY"] if "SPY" in data.columns else data["Close"]
        tlt_prices = data["TLT"] if "TLT" in data.columns else None
        
        if tlt_prices is None:
            raise ValueError("DualMomentumStrategy 需要 SPY 和 TLT 两种资产")
        
        # 计算相对动量（SPY - TLT）
        spy_momentum = calculate_momentum(spy_prices, self.momentum_period)
        tlt_momentum = calculate_momentum(tlt_prices, self.momentum_period)
        relative_momentum = spy_momentum - tlt_momentum
        
        # 计算绝对动量（SPY 收益 vs 无风险利率）
        monthly_rf = (1 + self.risk_free_rate) ** (1/12) - 1
        absolute_momentum = spy_momentum - monthly_rf * self.momentum_period
        
        # 生成信号：SPY 动量 > TLT 动量 且 SPY > 无风险收益
        signal = pd.Series(
            ((relative_momentum > 0) & (absolute_momentum > 0)).astype(int),
            index=data.index,
        )
        
        # 应用调仓频率
        if "Date" in data.columns:
            signal = self._apply_rebalance_freq(
                signal,
                data["Date"] if pd.api.types.is_datetime64_any_dtype(data["Date"]) else pd.to_datetime(data["Date"]),
                self.rebalance_freq,
            )
        else:
            signal = self._apply_rebalance_freq(
                signal,
                pd.to_datetime(data.index),
                self.rebalance_freq,
            )
        
        return signal.fillna(0).astype(int)
    
    def get_parameters(self) -> dict:
        """获取策略参数"""
        return {
            **super().get_parameters(),
            "momentum_period": self.momentum_period,
            "risk_free_rate": self.risk_free_rate,
        }