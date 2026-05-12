"""
策略库导出模块
"""

from .base import BaseStrategy, calculate_sma, calculate_rsi, calculate_momentum
from .dual_momentum import DualMomentumStrategy
from .trend_following import TrendFollowingMA
from .mean_reversion import MeanReversionRSI

# 策略映射表
STRATEGIES = {
    "DualMomentum": DualMomentumStrategy,
    "TrendFollowingMA": TrendFollowingMA,
    "MeanReversionRSI": MeanReversionRSI,
}


def get_strategy(name: str, **kwargs) -> BaseStrategy:
    """
    获取策略实例。
    
    Args:
        name: 策略名称
        **kwargs: 策略参数
    
    Returns:
        策略实例
    """
    if name not in STRATEGIES:
        raise ValueError(f"未知的策略: {name}，可用策略: {list(STRATEGIES.keys())}")
    
    return STRATEGIES[name](**kwargs)


__all__ = [
    "BaseStrategy",
    "DualMomentumStrategy",
    "TrendFollowingMA",
    "MeanReversionRSI",
    "calculate_sma",
    "calculate_rsi",
    "calculate_momentum",
    "get_strategy",
    "STRATEGIES",
]