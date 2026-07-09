"""视觉层:一张图 → 一份符合契约的 Scene Contract JSON。

四个步骤(见 docs/MVP_guide.md 三-1):
  1. 预处理 (Pillow)      preprocess.py
  2. 全局氛围 (VLM)       vibe_vlm.py
  3. 实体检测 (YOLO)      detector.py
  4. 空间坐标映射 + 组装   pipeline.py

视觉层绝不碰任何音频代码 —— 这是解耦的纪律。产出前用
`src.common.validate_scene` 自检。
"""
