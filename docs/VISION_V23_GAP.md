# 视觉层对齐音频层规范 2.3 —— 差距清单（B 部分）

**日期**: 2026-08-17
**契约状态**: v2.3 已获团队正式批准并已迁移为 `contracts/scene_contract.schema.json`；本清单仅保留尚未完成的视觉管线工作。
**依据**: `D:\Projects\nlp\playback\recommended_structured_record_example.json`(视觉记录规范 2.3)、`视觉锚点词典与检测边界.md` v1.0、`scene_type_vocabulary.json` v1.0、`ASMR声音素材库准备与采集规范.md` v1.1

## 已就位（A 完整 + B 骨架）

- `contracts/playback_proposal/scene_type_vocabulary.json` —— 424 值 / 20 组（音频层权威拷贝）
- `contracts/anchor_dictionary.json` —— 87 锚点（从规范 md 提取：type / sound_id / strength / definition）
- `src/vision/vibe_vlm.py` —— scene_type 归一化（none / other_* 兜底）+ scene_group 查表 + 87 锚点过滤
- `configs/prompts.yaml` v6 —— scene_type 词表规则 + 锚点式 suggested_entities（尚未全量验证）
- `scripts/normalize_global_vibe.py` —— 旧 2369 条 → `outputs/global_vibe_v23_aligned.jsonl`（2.3 形状；A 完整，B 为保守映射回填）

## 还没做（需要新管线 / 模型，逐项）

| # | 缺口 | 现状 | 需要 |
|---|------|------|------|
| 1 | 87 锚点检测 | YOLO 只出 COCO 80 类，产不出 `visible_bird` / `hands_on_keyboard_typing` | 开放词汇检测（YOLO-World / Grounding DINO）或专用检测器；输出 `bbox_norm`(xyxy, EXIF 修正后归一化 [0,1]) |
| 2 | EXIF 方向 | `src/vision/preprocess.py` 未转正 | 喂检测前 `ImageOps.exif_transpose`（测试报告 #12 同源） |
| 3 | brightness 程序化 | 归一化脚本用灰度均值/255 占位 | 与音频层对齐正式公式；新管线由程序算，不进 VLM prompt |
| 4 | depth_hint | 无深度模型 | 单目深度（Depth Anything 类）产出相对深度 + uncertainty + class + region_spread；MVP 可留空 |
| 5 | secondary_scene_types | 旧数据无法回填 | 新 prompt 让 VLM 输出最多 2 个次场景（词表内、不与主场景重复） |
| 6 | 记录格式 / 契约 | ✅ 已完成 | v2.3 已作为正式主契约；v1.0 仅保留兼容适配 |
| 7 | anchor_selection 配置 | 无 | 生成阶段最大数量 / 置信度阈值 / 去重阈值 / 优先级版本化 |
| 8 | 锚点强弱使用 | `anchor_dictionary.json` 已含 strength | 音频决策层处理（弱默认不播、中降概率）；视觉层只需产出锚点 |

## 建议下一步

1. 立项锚点检测管线（模型选型受 CPU 推理约束：YOLO-World vs Grounding DINO）。
2. 用 v6 prompt + 新检测重跑数据，产出正式 2.3 JSONL（含 bbox / 可选 depth_hint）。
