"""实体检测共享数据结构 —— Detection dataclass。

这是检测器与下游管线之间的标准数据格式。坐标均为归一化(0~1)，
字段直接映射 Scene Contract 的 entities[] 元素。

抽象接口见 base.py(BaseDetector),YOLO 实现见 yolo.py(YoloDetector)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Detection:
    """一次检测结果。坐标均为归一化(0~1)。"""

    name: str                        # COCO 标签,小写单数
    x: float                         # 中心归一化横坐标 0~1 (0=最左,1=最右)
    depth: str                       # near / mid / far,由 bbox 面积粗估
    conf: float                      # 检测置信度 0~1
    bbox: List[float] = field(default_factory=list)  # [x1,y1,x2,y2] 归一化
    source: str = "yolo"             # "yolo" | "vlm" | "fused"

    def to_entity_dict(self, state: str | None = None) -> dict:
        """转为 Scene Contract entities[] 元素格式。"""
        result: dict = {
            "name": self.name,
            "x": round(self.x, 4),
            "depth": self.depth,
            "conf": round(self.conf, 4),
            "source": self.source,
        }
        if state:
            result["state"] = state
        if self.bbox:
            result["bbox"] = [round(v, 4) for v in self.bbox]
        return result
