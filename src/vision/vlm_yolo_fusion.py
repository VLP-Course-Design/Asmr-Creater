"""
vlm_yolo_fusion.py

步骤 2 核心流水线：VLM 数据加载、YOLO 检测、结构化融合输出。
功能：
- 解析 VLM 模块输出的成功与失败 JSONL 文件。
- 驱动图像预处理 + YOLO 适配器执行目标检测。
- 将 VLM 语义实体与 YOLO 物理检测框进行空间匹配。
- 生成符合 Scene Contract (contracts/scene_contract.schema.json) 的最终 JSONL。

用法：
    python -m src.vision.vlm_yolo_fusion \
        --image_dir ./data/Train \
        --vlm_success ./outputs/global_vibe_results.jsonl \
        --vlm_failed ./outputs/global_vibe_failed.jsonl \
        --output ./final_structured_results.jsonl
"""

import json
import os
import argparse
import warnings
from typing import List, Dict, Any, Optional, Tuple

# 支持作为模块导入和直接执行 (python -m)
try:
    from .base import BaseDetector
    from .yolo import YoloDetector
    from .preprocess import get_image_files, batch_load_images
except ImportError:
    import sys
    from pathlib import Path as _Path
    _REPO_ROOT = _Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_REPO_ROOT / "src"))
    from vision.base import BaseDetector
    from vision.yolo import YoloDetector
    from vision.preprocess import get_image_files, batch_load_images




def load_jsonl(jsonl_path: str) -> List[Dict[str, Any]]:
    """
    读取并校验 JSONL 格式文件，返回字典列表。

    根据任务规格，每条记录必须包含 image, path, global_vibe, suggested_entities
    四个字段。缺少任一字段会触发警告但仍保留（兼容容错）。

    自动跳过空行与无法解析的损坏行。
    """
    if not os.path.exists(jsonl_path):
        warnings.warn(f"VLM 数据源文件不存在: {jsonl_path}")
        return []

    data = []
    required_fields = ["image", "path", "global_vibe", "suggested_entities"]

    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                # 校验必需字段
                missing = [f for f in required_fields if f not in record]
                if missing:
                    warnings.warn(
                        f"{jsonl_path} 第 {line_num} 行缺少字段 {missing}，"
                        f"当前包含: {list(record.keys())}"
                    )
                data.append(record)
            except json.JSONDecodeError:
                warnings.warn(
                    f"VLM JSONL 文件第 {line_num} 行存在无法解析的畸形行，已自动跳过。"
                )
                continue
    return data


def _match_entity_to_yolo(
    entity_name: str,
    yolo_detections: List[Any]
) -> Tuple[Optional[int], Optional[Any]]:
    """
    将 VLM 实体名称与 YOLO 检测结果 (Detection 对象) 进行字符串模糊匹配。

    匹配策略（由简到繁）：
        1. 精确匹配（忽略大小写）
        2. 包含关系匹配
        3. 单复数形式匹配（VLM 复数 → YOLO 单数）
        4. 单复数形式匹配（YOLO 复数 → VLM 单数）

    Args:
        entity_name: VLM 给出的实体名称
        yolo_detections: Detection 对象列表

    Returns:
        (detection_index, Detection) 或 (None, None)
    """
    entity_lower = entity_name.lower().strip()
    if not entity_lower:
        return None, None

    # 策略1：精确匹配（忽略大小写）
    for i, det in enumerate(yolo_detections):
        if det.name.lower() == entity_lower:
            return i, det

    # 策略2：包含关系匹配
    for i, det in enumerate(yolo_detections):
        label_lower = det.name.lower()
        if entity_lower in label_lower or label_lower in entity_lower:
            return i, det

    # 策略3：VLM 复数 → YOLO 单数
    if entity_lower.endswith('s'):
        singular = entity_lower[:-1]
        for i, det in enumerate(yolo_detections):
            if det.name.lower() == singular:
                return i, det

    # 策略4：YOLO 复数 → VLM 单数
    for i, det in enumerate(yolo_detections):
        label_lower = det.name.lower()
        if label_lower.endswith('s'):
            label_singular = label_lower[:-1]
            if entity_lower == label_singular:
                return i, det

    return None, None


def merge_structured_payload(
    yolo_result: Optional[Dict[str, Any]],
    vlm_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    将 YOLO 检测结果与 VLM 数据合并为符合 Scene Contract 的结构化输出。

    输出格式与 contracts/scene_contract.schema.json 严格对齐。

    Args:
        yolo_result: YoloDetector.detect() 返回值中的单图结果，或 None
        vlm_data: VLM 模块输出的单条结构化字典

    Returns:
        符合 Scene Contract 的结构化字典。

    Raises:
        ValueError: 当 vlm_data 缺少必需字段时抛出
    """
    # 1. 校验 VLM 数据完整性
    required_fields = ["image", "path", "global_vibe", "suggested_entities"]
    for field in required_fields:
        if field not in vlm_data:
            raise ValueError(
                f"VLM 数据缺少必需字段 '{field}'。"
                f"当前包含字段: {list(vlm_data.keys())}"
            )

    if not isinstance(vlm_data["suggested_entities"], list):
        raise ValueError(
            f"suggested_entities 应为列表类型，"
            f"实际为 {type(vlm_data['suggested_entities'])}"
        )

    # 2. 提取 VLM 侧信息
    vlm_image_name = vlm_data.get("image", "")
    global_vibe = vlm_data.get("global_vibe", {})

    # ── global_vibe 空字段兜底 + 额外字段过滤 ──
    # Qwen2.5VL 偶发输出空字符串 scene_type 或额外字段（如 background_color），
    # Schema 有 additionalProperties:false 约束，需在此处统一清理。
    _VIBE_DEFAULTS = {
        "scene_type": "unknown",
        "mood": "calm",
        "brightness": 0.5,
        "warmth": "neutral",
        "base_noise": "pink",
        "time_of_day": "afternoon",
    }
    _ALLOWED_VIBE_KEYS = set(_VIBE_DEFAULTS.keys())

    # 过滤掉 schema 不认识的额外字段
    extra_keys = [k for k in global_vibe if k not in _ALLOWED_VIBE_KEYS]
    for k in extra_keys:
        warnings.warn(
            f"global_vibe 包含未知字段 '{k}'，已移除。图片: {vlm_image_name}"
        )
        del global_vibe[k]

    # 空字段填默认值
    for _field, _default in _VIBE_DEFAULTS.items():
        val = global_vibe.get(_field)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            global_vibe[_field] = _default
            warnings.warn(
                f"global_vibe.{_field} 为空，已使用默认值 '{_default}'。"
                f"图片: {vlm_image_name}"
            )

    # 3. 提取 YOLO 检测列表与图像元信息
    yolo_detections = []
    image_width = 640
    image_height = 480

    if yolo_result and not yolo_result.get("error"):
        yolo_detections = yolo_result.get("detections", [])
        image_width = yolo_result.get("original_width", 640)
        image_height = yolo_result.get("original_height", 480)

    # 4. 构建 entities 数组（符合契约格式）
    entities = []
    matched_yolo_indices = set()

    for vlm_entity in vlm_data["suggested_entities"]:
        # ── VLM 输出格式归一化 ──
        # MiniCPM-V 偶发不规范输出：直接给字符串 "cat" 或嵌套列表 ["cat","dog"]
        # 而非标准 {"name":"cat","state":"sleeping"}，需在此处容错归一化
        if isinstance(vlm_entity, str):
            warnings.warn(
                f"suggested_entities 中出现字符串元素 '{vlm_entity}'，"
                f"已自动转为标准格式。请检查 VLM prompt 约束。"
            )
            vlm_entity = {"name": vlm_entity, "state": ""}
        elif isinstance(vlm_entity, list):
            names = [str(x) for x in vlm_entity if x]
            warnings.warn(
                f"suggested_entities 中出现嵌套列表 {vlm_entity}，"
                f"已合并为单个实体。请检查 VLM prompt 约束。"
            )
            vlm_entity = {"name": ", ".join(names), "state": ""} if names \
                else {"name": "unknown", "state": ""}
        elif not isinstance(vlm_entity, dict):
            warnings.warn(
                f"suggested_entities 中出现非标准类型 {type(vlm_entity).__name__}，"
                f"已跳过该元素。"
            )
            continue

        name = vlm_entity.get("name", "")
        state = vlm_entity.get("state", "")

        # 过滤空 name（VLM 偶发输出空字符串实体名）
        if not name or not name.strip():
            warnings.warn(
                f"suggested_entities 中出现空 name 实体，已跳过。"
                f"图片: {vlm_image_name}"
            )
            continue

        match_idx, matched_det = _match_entity_to_yolo(name, yolo_detections)

        if matched_det is not None and match_idx not in matched_yolo_indices:
            matched_yolo_indices.add(match_idx)
            # YOLO 匹配成功：使用 Detection.to_entity_dict() 直接转换
            entity_dict = matched_det.to_entity_dict(state=state if state else None)
            entities.append(entity_dict)
        else:
            # VLM 提及但 YOLO 不匹配 → 开放词汇预留
            entity_dict = {
                "name": name,
                "x": 0.5,
                "depth": "mid",
                "conf": 0.5,
                "source": "vlm"
            }
            if state:
                entity_dict["state"] = state
            entities.append(entity_dict)

    # 5. 构建 image 溯源信息
    image_id = os.path.splitext(vlm_image_name)[0] if vlm_image_name else ""
    vlm_path = vlm_data.get("path", "")

    # 6. 组装最终输出（严格遵循 Scene Contract）
    return {
        "schema_version": "1.0",
        "image": {
            "id": image_id,
            "path": vlm_path,
            "width": image_width,
            "height": image_height
        },
        "global_vibe": global_vibe,
        "entities": entities
    }


def process_batch(
    yolo_results: List[Dict[str, Any]],
    vlm_success_list: List[Dict[str, Any]],
    vlm_failed_list: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    处理批量 VLM 数据，与 YOLO 结果进行路径匹配与结构化合并。

    Args:
        yolo_results: YoloDetector.detect() 的返回值列表
        vlm_success_list: VLM 成功记录列表
        vlm_failed_list: VLM 失败记录列表

    Returns:
        符合 Scene Contract 的最终输出列表
    """
    # 构建 YOLO 结果索引（按 basename 和规范化路径双键映射）
    # 使用 os.path.normpath 统一 Windows/Linux 路径分隔符
    yolo_map = {}
    for yolo_res in yolo_results:
        img_path = yolo_res.get("image_path", "")
        base_name = os.path.basename(img_path)
        if base_name:
            yolo_map[base_name] = yolo_res
        if img_path:
            yolo_map[os.path.normpath(img_path)] = yolo_res

    final_outputs = []

    # 1. 处理 VLM 成功列表
    for vlm_entry in vlm_success_list:
        vlm_image = vlm_entry.get("image", "")
        vlm_path = os.path.normpath(vlm_entry.get("path", ""))

        # 多策略匹配：文件名 → 路径 basename → 规范化完整路径
        matched_yolo = None
        if vlm_image and vlm_image in yolo_map:
            matched_yolo = yolo_map[vlm_image]
        elif vlm_path:
            vlm_basename = os.path.basename(vlm_path)
            if vlm_basename and vlm_basename in yolo_map:
                matched_yolo = yolo_map[vlm_basename]
            elif vlm_path in yolo_map:
                matched_yolo = yolo_map[vlm_path]

        try:
            merged = merge_structured_payload(matched_yolo, vlm_entry)
            final_outputs.append(merged)
        except ValueError as e:
            # 单条数据损坏不中断整批
            final_outputs.append({
                "schema_version": "1.0",
                "image": {
                    "id": os.path.splitext(vlm_image)[0] if vlm_image else "",
                    "path": vlm_path,
                    "width": 0,
                    "height": 0,
                    "error": f"融合异常: {str(e)}"
                },
                "global_vibe": {},
                "entities": []
            })

    # 2. 处理 VLM 失败列表（保留 error 字段，输出给下游音频层）
    for vlm_entry in vlm_failed_list:
        vlm_image = vlm_entry.get("image", "")
        vlm_path = vlm_entry.get("path", "")
        final_outputs.append({
            "schema_version": "1.0",
            "image": {
                "id": os.path.splitext(vlm_image)[0] if vlm_image else "",
                "path": vlm_path,
                "width": 0,
                "height": 0,
                "error": vlm_entry.get("error", "上游 VLM 模块推理失败")
            },
            "global_vibe": {
                "scene_type": "unknown",
                "mood": "calm",
                "brightness": 0.5,
                "warmth": "neutral",
                "base_noise": "pink",
                "time_of_day": "afternoon"
            },
            "entities": []
        })

    return final_outputs


# ══════════════════════════════════════════════════════════════════════
# 命令行入口
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="VLM 与 YOLO 数据融合流水线 —— 产出符合 Scene Contract 的最终 JSONL"
    )
    parser.add_argument(
        "--vlm_success", type=str, default="global_vibe_results.jsonl",
        help="上游 VLM 模块生成的成功记录 JSONL 文件路径"
    )
    parser.add_argument(
        "--vlm_failed", type=str, default="global_vibe_failed.jsonl",
        help="上游 VLM 模块生成的失败记录 JSONL 文件路径"
    )
    parser.add_argument(
        "--image_dir", type=str, default="./img_dataset",
        help="待进行目标检测的图片目录路径"
    )
    parser.add_argument(
        "--output", type=str, default="final_structured_results.jsonl",
        help="最终融合输出的 JSONL 文件路径"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("【步骤 2 完整流水线】VLM + YOLO 结构化融合")
    print("=" * 60)

    # 1. 读取 VLM 数据
    print("\n[1/4] 正在加载上游 VLM 模块数据...")
    vlm_success = load_jsonl(args.vlm_success)
    vlm_failed = load_jsonl(args.vlm_failed)
    print(f"  VLM 成功记录: {len(vlm_success)} 条")
    print(f"  VLM 失败记录: {len(vlm_failed)} 条")

    # 2. 扫描图片目录
    print("\n[2/4] 正在扫描图片目录...")
    image_paths = get_image_files(args.image_dir, recursive=True)
    print(f"  发现 {len(image_paths)} 张待检测图片")

    if not image_paths:
        print("⚠️ 未找到任何图片，仅进行 VLM 数据转换（所有实体无 YOLO 匹配）。")
        preprocessed = []
    else:
        # 3. 批量预处理 + YOLO 检测
        print("\n[3/4] 正在预处理图片并执行 YOLO 目标检测...")
        preprocessed = batch_load_images(
            image_paths=image_paths,
            target_size_yolo=(640, 640),
            target_size_vlm=(224, 224),
            verbose=True,
            save_dir=None
        )
        print(f"  预处理完成: {len(preprocessed)}/{len(image_paths)} 张")

    # 初始化 YOLO 检测器并推理
    print("  正在初始化 YOLO 检测器 (yolo11n.pt, CPU)...")
    detector = YoloDetector(
        model_name='yolo11n.pt',
        device='cpu',
        conf_threshold=0.25,
        iou_threshold=0.45
    )

    if preprocessed:
        yolo_results = detector.detect(preprocessed)
        print(f"  YOLO 推理完成: {len(yolo_results)} 张")
    else:
        yolo_results = []

    # 4. 数据融合与输出
    print("\n[4/4] 正在融合 VLM 语义与 YOLO 物理空间结果...")
    final_results = process_batch(yolo_results, vlm_success, vlm_failed)

    # 保存结果
    with open(args.output, 'w', encoding='utf-8') as f:
        for entry in final_results:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # 统计摘要
    total_entities = sum(len(e.get("entities", [])) for e in final_results)
    yolo_matched = sum(
        1 for e in final_results
        for ent in e.get("entities", [])
        if ent.get("source") == "yolo"
    )
    vlm_only = sum(
        1 for e in final_results
        for ent in e.get("entities", [])
        if ent.get("source") == "vlm"
    )
    failed_images = sum(1 for e in final_results if "error" in e.get("image", {}))

    print(f"\n{'=' * 60}")
    print(f"✅ 流水线执行完毕！")
    print(f"  输出文件: {args.output}")
    print(f"  处理图片数: {len(final_results)} 张")
    print(f"  融合实体总数: {total_entities}")
    print(f"    - YOLO 匹配成功: {yolo_matched}")
    print(f"    - VLM 提及(开放词汇预留): {vlm_only}")
    print(f"  失败/异常图片: {failed_images}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
