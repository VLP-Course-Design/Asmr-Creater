# -*- coding: utf-8 -*-
"""视觉层:一张图 → 一份符合契约的 Scene Contract JSON。

四个步骤(见 docs/MVP_guide.md 三-1):
  1. 预处理 (Pillow)      preprocess.py
  2. 全局氛围 (VLM)       vibe_vlm.py
  3. 实体检测 (YOLO)      yolo.py
  4. 空间坐标映射 + 组装   vlm_yolo_fusion.py

视觉层绝不碰任何音频代码 —— 这是解耦的纪律。产出前用
`src.common.validate_scene` 自检。
"""

import warnings

# ── 预处理模块（无外部依赖，始终可用） ──
from .preprocess import batch_load_images, get_image_files, load_and_preprocess_image, letterbox

# ── 共享数据结构 ──
from .detector import Detection

# ── 检测器接口与 YOLO 实现（ultralytics 为可选运行时依赖）──
from .base import BaseDetector
try:
    from .yolo import YoloDetector
except ImportError as e:
    YoloDetector = None  # type: ignore
    warnings.warn(
        f"YoloDetector 不可用（缺少依赖: {e}）。"
        f"如需检测请安装: pip install ultralytics"
    )

# ── VLM + YOLO 融合管线 ──
from .vlm_yolo_fusion import (
    load_jsonl,
    merge_structured_payload,
    process_batch,
)

# ── 视觉记录 v2.3（当前正式主契约；v1.0 仅保留兼容适配）──
from .visual_record import (
    build_visual_record_v23,
    normalize_upstream_record,
    process_batch_v23,
)
from .anchor_map import detections_to_anchors, map_name_to_anchor

# ── VLM 氛围分析（可选，依赖 ollama + yaml + openai） ──
try:
    from .vibe_vlm import get_global_vibe
except ImportError as e:
    get_global_vibe = None  # type: ignore
    warnings.warn(
        f"vibe_vlm 模块不可用（缺少依赖: {e}），VLM 氛围分析功能暂不可用。"
        f"如需使用请安装: pip install pyyaml openai"
    )

# 定义暴露给外部的模块成员
__all__ = [
    # preprocess
    'batch_load_images',
    'get_image_files',
    'load_and_preprocess_image',
    'letterbox',
    # detector
    'Detection',
    'BaseDetector',
    'YoloDetector',
    # fusion
    'load_jsonl',
    'merge_structured_payload',
    'process_batch',
    # visual record v2.3
    'build_visual_record_v23',
    'normalize_upstream_record',
    'process_batch_v23',
    'detections_to_anchors',
    'map_name_to_anchor',
    # vibe (optional)
    'get_global_vibe',
]
