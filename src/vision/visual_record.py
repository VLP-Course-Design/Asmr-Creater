"""把第二人检测结果组装为视觉记录 v2.3，供音频播放计划转换器消费。

v1.0 Scene Contract（`entities` / `base_noise` / 框面积估 depth）仍由
`vlm_yolo_fusion.merge_structured_payload` 产出，给现有 UI 使用。
本模块只负责队友在 main 上新增的 playback 输入格式，不改冻结契约 v1.0。

v2.3 纪律（见 contracts/playback_proposal/）：
- brightness 由程序计算，不采用 VLM 估计值
- scene_group 由 scene_type 查表，不让模型填
- 无单目深度时省略 depth_hint，禁止用框面积冒充
- 无合格锚点时 trigger_anchors 为空数组
- image.path 必须是相对路径
"""

from __future__ import annotations

import json
import os
import re
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from .anchor_map import detections_to_anchors


REPO_ROOT = Path(__file__).resolve().parents[2]
VOCAB_PATH = REPO_ROOT / "contracts" / "playback_proposal" / "scene_type_vocabulary.json"

_V23_MOOD = {
    "neutral", "calm", "cozy", "cheerful", "lively",
    "majestic", "mysterious", "melancholic", "tense", "eerie",
}
_MOOD_ALIAS = {
    "gloomy": "melancholic",
    "阴暗": "melancholic",
    "沉闷": "melancholic",
}
_V23_WARMTH = {"cool", "neutral", "warm"}
_V23_TOD = {"morning", "afternoon", "dusk", "night", "dawn", "noon", "unknown"}

_SCENE_ALIAS = {
    "unknown": "none",
    "room": "other_indoor",
    "indoor": "other_indoor",
    "outdoor": "other_outdoor",
    "livingroom": "living_room",
    "study": "study_room",
    "seaside": "beach",
    "seashore": "beach",
    "city": "cityscape",
    "home": "other_indoor",
    "nature": "other_natural",
    "卧室": "bedroom",
    "厨房": "kitchen",
    "咖啡馆": "cafe",
    "咖啡厅": "cafe",
    "森林": "forest",
    "街道": "street",
    "海滩": "beach",
    "办公室": "office",
    "客厅": "living_room",
}


def is_v23_handover_record(raw: Dict[str, Any]) -> bool:
    """识别 VLM 交接包 / PR #7 归一化后的 2.3 形记录。"""
    if not isinstance(raw, dict):
        return False
    if raw.get("schema_version") == "2.3":
        return True
    if "trigger_anchors" in raw and "id" in raw:
        return True
    return isinstance(raw.get("image"), dict)


def normalize_upstream_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    """把旧 VLM JSONL 与 handover v2.3 JSONL 收成融合管线统一输入。

    统一后至少尽量提供: image(文件名), path, id, global_vibe, suggested_entities。
    不臆造缺失的 global_vibe，以免掩盖损坏行。
    """
    if not is_v23_handover_record(raw):
        out = dict(raw)
        if "suggested_entities" not in out and "global_vibe" in out:
            out["suggested_entities"] = []
        return out

    image_obj = raw.get("image") if isinstance(raw.get("image"), dict) else {}
    path = str(image_obj.get("path") or raw.get("path") or "").replace("\\", "/")
    record_id = str(raw.get("id") or "")
    filename = os.path.basename(path) or (f"{record_id}.jpg" if record_id else "unknown.jpg")

    suggested: List[Dict[str, str]] = []
    for anchor in raw.get("trigger_anchors") or []:
        if isinstance(anchor, dict) and anchor.get("anchor_id"):
            suggested.append({
                "name": str(anchor["anchor_id"]),
                "state": str(anchor.get("state_note") or ""),
            })
    for item in raw.get("suggested_entities") or []:
        if isinstance(item, dict) and item.get("name"):
            suggested.append({"name": str(item["name"]), "state": str(item.get("state") or "")})
        elif isinstance(item, str) and item.strip():
            suggested.append({"name": item, "state": ""})

    return {
        "image": filename,
        "path": path,
        "id": record_id or os.path.splitext(filename)[0],
        "global_vibe": dict(raw.get("global_vibe") or {}),
        "suggested_entities": suggested,
        "_handover_width": image_obj.get("width"),
        "_handover_height": image_obj.get("height"),
    }


def index_yolo_results(yolo_results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """按文件名 / 去扩展名 id / 规范化路径建立 YOLO 结果索引。"""
    yolo_map: Dict[str, Dict[str, Any]] = {}
    for yolo_res in yolo_results:
        img_path = yolo_res.get("image_path", "")
        base_name = os.path.basename(img_path)
        stem = os.path.splitext(base_name)[0]
        if base_name:
            yolo_map[base_name] = yolo_res
        if stem:
            yolo_map[stem] = yolo_res
        if img_path:
            yolo_map[os.path.normpath(img_path)] = yolo_res
            yolo_map[img_path.replace("\\", "/")] = yolo_res
    return yolo_map


def match_yolo_result(
    yolo_map: Dict[str, Dict[str, Any]],
    vlm_entry: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    path = str(vlm_entry.get("path") or "")
    candidates = [
        vlm_entry.get("image"),
        vlm_entry.get("id"),
        os.path.basename(path),
        os.path.splitext(os.path.basename(path))[0],
        os.path.normpath(path) if path else "",
        path.replace("\\", "/"),
    ]
    for key in candidates:
        if key and key in yolo_map:
            return yolo_map[key]
    return None


def sanitize_record_id(name: str) -> str:
    """生成符合 v2.3 `id` 模式的稳定标识，禁止用绝对路径。"""
    stem = Path(str(name or "")).stem or "record"
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", stem)
    if not cleaned or not re.match(r"[A-Za-z0-9]", cleaned[0]):
        cleaned = "img_" + cleaned
    return cleaned[:128]


def sanitize_relative_path(path: str, fallback_name: str = "unknown.jpg") -> str:
    """去掉盘符/绝对路径/`..`，统一正斜杠。"""
    raw = (path or "").replace("\\", "/").strip()
    if not raw:
        return fallback_name
    parts = [p for p in raw.split("/") if p and p != "."]
    if any(p == ".." for p in parts) or re.match(r"^[A-Za-z]:", raw) or raw.startswith("/"):
        return parts[-1] if parts else fallback_name
    return "/".join(parts) or fallback_name


@lru_cache(maxsize=1)
def _scene_type_to_group() -> Dict[str, str]:
    if not VOCAB_PATH.exists():
        warnings.warn(f"场景词表不存在: {VOCAB_PATH}")
        return {}
    data = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    mapping: Dict[str, str] = {}
    for group, types in (data.get("groups") or {}).items():
        for scene_type in types:
            mapping[scene_type] = group
    return mapping


def normalize_scene_type(raw: str) -> tuple[str, str]:
    """自由 scene_type → (词表叶子类别, scene_group)。无法对齐时回退 none。"""
    key = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    key = _SCENE_ALIAS.get(key, key)
    table = _scene_type_to_group()
    if key in table:
        return key, table[key]
    if key:
        warnings.warn(f"scene_type '{raw}' 不在 v2.3 词表，已回退为 none")
    return "none", table.get("none", "non_scene")


def _normalize_mood(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    value = _MOOD_ALIAS.get(value, value)
    return value if value in _V23_MOOD else "calm"


def _normalize_warmth(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    return value if value in _V23_WARMTH else "neutral"


def _normalize_tod(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    return value if value in _V23_TOD else "unknown"


def _secondary_scene_types(raw: Any, primary: str) -> List[str]:
    if not isinstance(raw, list):
        return []
    table = _scene_type_to_group()
    out: List[str] = []
    for item in raw:
        scene, _ = normalize_scene_type(str(item))
        if scene in table and scene != primary and scene != "none" and scene not in out:
            out.append(scene)
        if len(out) >= 2:
            break
    return out


def _resolve_scene(vibe_in: Dict[str, Any]) -> tuple[str, str]:
    """优先沿用交接包里已对齐的 scene_type/scene_group，不一致再查表。"""
    scene_type, looked_up = normalize_scene_type(str(vibe_in.get("scene_type") or ""))
    given_group = vibe_in.get("scene_group")
    table = _scene_type_to_group()
    if isinstance(given_group, str) and table.get(scene_type) == given_group:
        return scene_type, given_group
    return scene_type, looked_up


def build_visual_record_v23(
    yolo_result: Optional[Dict[str, Any]],
    vlm_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """单图 → 视觉记录 v2.3。缺少合法图像尺寸时返回 None（应写入错误集）。"""
    vlm_data = normalize_upstream_record(vlm_data)
    vibe_in = dict(vlm_data.get("global_vibe") or {})
    suggested = vlm_data.get("suggested_entities") or []
    entity_states: Dict[str, str] = {}
    suggested_names: List[str] = []
    for item in suggested:
        if isinstance(item, dict) and item.get("name"):
            suggested_names.append(str(item["name"]))
            entity_states[str(item["name"])] = str(item.get("state") or "")
        elif isinstance(item, str) and item.strip():
            suggested_names.append(item)

    width = 0
    height = 0
    detections: List[Any] = []
    brightness = None
    if yolo_result and not yolo_result.get("error"):
        width = int(yolo_result.get("original_width") or 0)
        height = int(yolo_result.get("original_height") or 0)
        detections = yolo_result.get("detections") or []
        brightness = yolo_result.get("brightness")

    if width < 1 or height < 1:
        return None

    if brightness is None:
        warnings.warn("缺少程序计算的 brightness，已使用 0.5；请走 preprocess 管线")
        brightness = 0.5
    brightness = float(max(0.0, min(1.0, float(brightness))))

    scene_type, scene_group = _resolve_scene(vibe_in)
    image_name = vlm_data.get("image") or os.path.basename(vlm_data.get("path") or "")
    rel_path = sanitize_relative_path(
        str(vlm_data.get("path") or ""),
        fallback_name=os.path.basename(str(image_name)) or "unknown.jpg",
    )
    record_id = sanitize_record_id(str(vlm_data.get("id") or image_name or rel_path))

    return {
        "schema_version": "2.3",
        "id": record_id,
        "image": {
            "path": rel_path,
            "width": width,
            "height": height,
        },
        "global_vibe": {
            "scene_type": scene_type,
            "secondary_scene_types": _secondary_scene_types(
                vibe_in.get("secondary_scene_types"), scene_type
            ),
            "scene_group": scene_group,
            "mood": _normalize_mood(vibe_in.get("mood")),
            "warmth": _normalize_warmth(vibe_in.get("warmth")),
            "time_of_day": _normalize_tod(vibe_in.get("time_of_day")),
            "brightness": round(brightness, 2),
        },
        "trigger_anchors": detections_to_anchors(
            detections,
            entity_states=entity_states,
            suggested_names=suggested_names,
        ),
    }


def process_batch_v23(
    yolo_results: List[Dict[str, Any]],
    vlm_success_list: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """仅处理 VLM 成功条目。失败图不进入正式 v2.3 JSONL（按规范进错误集）。"""
    yolo_map = index_yolo_results(yolo_results)
    records: List[Dict[str, Any]] = []
    for vlm_entry in vlm_success_list:
        normalized = normalize_upstream_record(vlm_entry)
        matched = match_yolo_result(yolo_map, normalized)
        record = build_visual_record_v23(matched, normalized)
        if record is not None:
            records.append(record)
        else:
            warnings.warn(
                f"无法生成 v2.3 记录（缺少图像尺寸）: "
                f"{normalized.get('image') or normalized.get('path')}"
            )
    return records
