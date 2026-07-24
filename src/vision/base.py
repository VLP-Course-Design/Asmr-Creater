"""
base.py —— 检测器抽象接口层

定义统一的物体检测器契约。
遵循适配器模式，将具体模型实现与业务逻辑解耦，
便于未来无缝替换为 YOLO-World / Grounding DINO 等开放词汇检测器。

每个检测结果以 detector.Detection dataclass 输出（归一化坐标）。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseDetector(ABC):
    """
    物体检测器抽象基类。

    所有具体检测器（YOLO、Grounding DINO 等）必须实现此接口，
    确保上层调用方无需关心底层模型差异。

    设计约定：
        - detect() 接收 preprocess.batch_load_images() 返回的预处理数据
          （包含 image_yolo 内存数组），直接对内存中的图像进行推理。
        - detections 列表中的每个元素为 detector.Detection dataclass（归一化坐标）。
    """

    @abstractmethod
    def detect(self, preprocessed_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对预处理后的图像数据执行批量物体检测。

        Args:
            preprocessed_data: preprocess.batch_load_images 返回的列表，
                每个元素包含 image_yolo, original_width, original_height,
                scale, pad_left, pad_top, path 等字段。

        Returns:
            [
                {
                    "image_path": str,
                    "original_width": int,
                    "original_height": int,
                    "detections": List[Detection],   # detector.Detection 对象
                    "error": Optional[str]
                },
                ...
            ]

        异常处理：
            若某张图片无法处理，应在该条目中标记 error 字段，
            而非中断整个批次。
        """
        pass

    @abstractmethod
    def get_supported_classes(self) -> List[str]:
        """返回当前检测器支持的类别名称列表。"""
        pass
