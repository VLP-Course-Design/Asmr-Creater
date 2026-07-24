"""
yolo.py —— YOLO 检测器适配器实现

封装 ultralytics 官方库。使用 yolo11n.pt 轻量模型，运行在 CPU 设备，
输出 COCO 80 类检测结果，并自动计算空间方位与距离。

关键设计：
    - 接收 preprocess.batch_load_images() 输出的内存数组（image_yolo），
      直接在内存中推理，杜绝重复读取磁盘。
    - 将 YOLO 在 letterbox 图像上的输出 bbox 映射回原始图像空间，
      确保空间坐标计算正确。
    - 每个检测结果以 Detection dataclass 输出，坐标归一化至 [0,1]。
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple

from ultralytics import YOLO

from .base import BaseDetector
from .detector import Detection


# ─── distance → depth 枚举映射 ───
_DISTANCE_TO_DEPTH = {
    "near": "near",
    "medium": "mid",
    "far": "far",
}


class YoloDetector(BaseDetector):
    """
    YOLO 检测器适配器。

    封装 ultralytics YOLO 模型，提供统一的 detect 接口。
    默认使用 'yolo11n.pt' 权重，运行在 CPU 设备。
    每个检测结果以 Detection dataclass 输出（归一化坐标）。
    """

    # COCO 80 类名称列表（按索引顺序）
    COCO_CLASSES = [
        'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck',
        'boat', 'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench',
        'bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra',
        'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
        'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove',
        'skateboard', 'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup',
        'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange',
        'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
        'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
        'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
        'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier',
        'toothbrush'
    ]

    def __init__(
        self,
        model_name: str = 'yolo11n.pt',
        device: str = 'cpu',
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        img_size: int = 640
    ):
        """
        初始化 YOLO 检测器。

        Args:
            model_name: 模型权重文件名或路径
            device: 推理设备，'cpu' 或 'cuda'，MVP 阶段强制 'cpu'
            conf_threshold: 置信度阈值 (0.25)
            iou_threshold: NMS IoU 阈值 (0.45)
            img_size: 推理图像尺寸 (640)
        """
        self.model_name = model_name
        self.device = device
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.img_size = img_size

        try:
            self.model = YOLO(model_name)
            print(f"[YoloDetector] 模型加载成功: {model_name}, device={device}")
        except Exception as e:
            raise RuntimeError(f"YOLO 模型加载失败: {e}")

    def detect(self, preprocessed_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对预处理后的图像数据执行批量目标检测。

        YOLO 在 letterbox 图像上推理 → bbox 映射回原始空间 →
        坐标归一化 → 产出 Detection 对象列表。

        Args:
            preprocessed_data: preprocess.batch_load_images 返回的列表

        Returns:
            检测结果列表，每张图包含:
            {
                "image_path": str,
                "original_width": int,
                "original_height": int,
                "detections": List[Detection],    # Detection 对象列表
                "error": Optional[str]
            }
        """
        results = []

        for item in preprocessed_data:
            image_yolo = item.get('image_yolo')
            path = item.get('path', '')
            original_w = item.get('original_width', 640)
            original_h = item.get('original_height', 640)
            scale = item.get('scale', 1.0)
            pad_left = item.get('pad_left', 0)
            pad_top = item.get('pad_top', 0)

            try:
                yolo_results = self.model(
                    image_yolo,
                    imgsz=self.img_size,
                    conf=self.conf_threshold,
                    iou=self.iou_threshold,
                    device=self.device,
                    verbose=False
                )

                detections = []
                for r in yolo_results:
                    if r.boxes is None:
                        continue

                    boxes = r.boxes.xyxy.cpu().numpy()
                    confs = r.boxes.conf.cpu().numpy()
                    cls_ids = r.boxes.cls.cpu().numpy().astype(int)

                    for box, conf, cls_id in zip(boxes, confs, cls_ids):
                        x1_lb, y1_lb, x2_lb, y2_lb = box

                        # ── 坐标映射：letterbox 空间 → 原始图像空间 ──
                        orig_x1 = max(0.0, min(float(original_w),
                                       (x1_lb - pad_left) / scale))
                        orig_y1 = max(0.0, min(float(original_h),
                                       (y1_lb - pad_top) / scale))
                        orig_x2 = max(0.0, min(float(original_w),
                                       (x2_lb - pad_left) / scale))
                        orig_y2 = max(0.0, min(float(original_h),
                                       (y2_lb - pad_top) / scale))

                        # ── 归一化 ──
                        norm_x1 = orig_x1 / original_w
                        norm_y1 = orig_y1 / original_h
                        norm_x2 = orig_x2 / original_w
                        norm_y2 = orig_y2 / original_h
                        center_x_norm = (norm_x1 + norm_x2) / 2.0

                        # ── 计算空间方位 ──
                        label = self.COCO_CLASSES[cls_id] \
                            if cls_id < len(self.COCO_CLASSES) \
                            else f"class_{cls_id}"

                        distance_cat = self._compute_distance(
                            [orig_x1, orig_y1, orig_x2, orig_y2],
                            original_w, original_h
                        )
                        depth = _DISTANCE_TO_DEPTH.get(distance_cat, "mid")

                        # ── 创建 Detection 对象（归一化坐标）──
                        detections.append(Detection(
                            name=label,
                            x=float(center_x_norm),
                            depth=depth,
                            conf=float(conf),
                            bbox=[float(norm_x1), float(norm_y1),
                                  float(norm_x2), float(norm_y2)],
                            source="yolo"
                        ))

                results.append({
                    "image_path": path,
                    "original_width": original_w,
                    "original_height": original_h,
                    "error": None,
                    "detections": detections
                })

            except Exception as e:
                results.append({
                    "image_path": path,
                    "original_width": original_w,
                    "original_height": original_h,
                    "error": f"推理异常: {str(e)}",
                    "detections": []
                })

        return results

    def get_supported_classes(self) -> List[str]:
        """返回 COCO 80 类名称列表"""
        return self.COCO_CLASSES.copy()

    # ── 静态工具方法（保留 categorical 输出，供调试/可视化使用）──

    @staticmethod
    def _compute_horizontal(center_x: float, image_width: int) -> str:
        """根据中心点 X 坐标计算水平方位。"""
        if image_width <= 0:
            return "center"
        ratio = center_x / image_width
        if ratio < 0.33:
            return "left"
        elif ratio > 0.67:
            return "right"
        else:
            return "center"

    @staticmethod
    def _compute_distance(bbox, image_width: int, image_height: int) -> str:
        """根据 bbox 面积占比估算距离。"""
        x1, y1, x2, y2 = bbox
        box_area = (x2 - x1) * (y2 - y1)
        image_area = image_width * image_height
        if image_area <= 0:
            return "medium"
        area_ratio = box_area / image_area

        if area_ratio > 0.25:
            return "near"
        elif area_ratio > 0.08:
            return "medium"
        else:
            return "far"
