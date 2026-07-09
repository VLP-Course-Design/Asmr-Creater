"""参数解析:把 Scene Contract 翻译成音频控制参数。

MVP 用连续线性映射(比 if-else 高级、比状态机简单)。这里先给出数据结构
与映射骨架,具体 DSP 数值由音频线在接 pyo 时标定。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

# base_noise 字符串 → pyo 噪声类名,音频线接 pyo 时用
NOISE_CLASS = {"white": "WhiteNoise", "pink": "PinkNoise", "brown": "BrownNoise"}


@dataclass
class BedParams:
    """底噪控制参数。"""

    noise_type: str      # white / pink / brown
    volume: float        # 0~1,主要由 brightness 驱动
    lowpass_hz: float    # 低通截止频率,越暗越低


@dataclass
class TriggerParams:
    """单个离散音效的控制参数。"""

    name: str
    pan: float           # 0(左)~1(右),来自 entity.x
    gain: float          # 0~1,受 depth 与 conf 影响
    state: str = ""


def map_bed(global_vibe: Dict[str, Any]) -> BedParams:
    """global_vibe → 底噪参数。数值区间待音频线用听感标定。"""
    brightness = float(global_vibe["brightness"])
    return BedParams(
        noise_type=global_vibe["base_noise"],
        # 越亮音量略大;区间保守,避免刺耳。TODO: 听感标定
        volume=0.25 + 0.35 * brightness,
        # 越暗低通越低沉。TODO: 听感标定
        lowpass_hz=400 + 6000 * brightness,
    )


def map_triggers(entities: List[Dict[str, Any]]) -> List[TriggerParams]:
    """entities → 每个可发声实体的音效参数。"""
    depth_gain = {"near": 1.0, "mid": 0.7, "far": 0.45}
    out: List[TriggerParams] = []
    for e in entities:
        gain = depth_gain.get(e["depth"], 0.7) * (0.5 + 0.5 * float(e["conf"]))
        out.append(
            TriggerParams(
                name=e["name"],
                pan=float(e["x"]),
                gain=gain,
                state=e.get("state", ""),
            )
        )
    return out
