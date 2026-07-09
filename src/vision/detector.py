"""实体检测接口 —— 把「检测器」抽象成可替换的一层。

MVP 用 YOLOv10/v11-Nano(COCO 80 类)。未来换开放词汇检测
(YOLO-World / Grounding DINO)只需新写一个 Detector 子类,
下游 pipeline 不改。这就是 MVP_guide 三-3 说的「抽象成可替换接口」。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class Detection:
    """一次检测结果。坐标均为归一化(0~1)。"""

    name: str                        # COCO 标签,小写单数
    x: float                         # 中心归一化横坐标
    depth: str                       # near / mid / far,由 bbox 面积粗估
    conf: float                      # 检测置信度
    bbox: List[float] = field(default_factory=list)  # [x1,y1,x2,y2] 归一化
    source: str = "yolo"


class Detector(ABC):
    """检测器抽象基类。所有实现产出统一的 Detection 列表。"""

    @abstractmethod
    def detect(self, image) -> List[Detection]:
        """输入一张(已预处理的)图,返回检测列表。"""
        raise NotImplementedError


class YoloDetector(Detector):
    """TODO(视觉线):用 ultralytics 加载 YOLOv11-Nano 实现。

    要点:
      - 只保留生活场景常见、且素材库里有映射的类(见 sounds/trigger_map.json)。
      - depth 用 bbox 面积阈值粗估:大→near,中→mid,小→far。
    """

    def detect(self, image) -> List[Detection]:  # pragma: no cover - 占位
        raise NotImplementedError("YoloDetector 待视觉线实现")
