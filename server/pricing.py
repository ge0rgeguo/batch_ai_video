"""
视频生成积分定价规则
"""
from typing import Optional


# 模型与时长对应的积分定价
PRICING = {
    "sora-2-all": {10: 10, 15: 15},
    "sora-2-pro-all": {10: 50, 15: 75, 25: 100},
}

# veo_3_1 按分辨率定价（时长固定8秒）
VEO_PRICING = {
    "veo_3_1": {"720p": 10, "1080p": 50, "4k": 100},
}


def get_unit_cost(model: str, duration: int, size: str = None) -> int:
    """获取单个视频的积分消耗

    Args:
        model: 模型名称，如 "sora-2-all", "sora-2-pro-all", "veo_3_1"
        duration: 视频时长（秒），如 8, 10, 15, 25
        size: 分辨率，veo_3_1 使用 "720p", "1080p", "4k"

    Returns:
        积分消耗（正整数）
    """
    # veo_3_1 按分辨率定价
    if model in VEO_PRICING:
        return VEO_PRICING[model].get(size, 50)  # 默认1080p价格
    # 其他模型按时长定价
    return PRICING.get(model, {}).get(duration, 15)  # 默认15分（兜底）







