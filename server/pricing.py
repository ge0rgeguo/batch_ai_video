"""
视频生成积分定价规则
"""
from typing import Optional


# 模型与时长对应的积分定价
PRICING = {
    "sora-2": {10: 10, 15: 15},
    "sora-2-pro": {10: 50, 15: 75, 25: 100},
}


def get_unit_cost(model: str, duration: int) -> int:
    """获取单个视频的积分消耗
    
    Args:
        model: 模型名称，如 "sora-2" 或 "sora-2-pro"
        duration: 视频时长（秒），如 10, 15, 25
    
    Returns:
        积分消耗（正整数）
    """
    return PRICING.get(model, {}).get(duration, 15)  # 默认15分（兜底）

