"""COCO / VLM 自由词 → 视觉记录 v2.3 `anchor_id` 映射。

音频决策层只认 87 项受控锚点，不再消费 COCO 类名或 `suggested_entities`。
本模块只做「可见证据 → 锚点」的保守映射：证据不足时宁可不输出，
也不把普通 person、未在睡觉的猫、无雨的伞等强行写成锚点。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# 静态物体：看见即可成立（中/弱证据，由音频层决定是否发声）
_STATIC_NAME_TO_ANCHOR: Dict[str, str] = {
    "bird": "visible_bird",
    "keyboard": "visible_keyboard",
    "mouse": "visible_computer_mouse",
    "clock": "visible_clock",
    "cup": "single_visible_cup",
    "refrigerator": "visible_refrigerator_or_freezer",
    "train": "visible_train_or_railway",
    "boat": "boat_hull_at_water",
    "cow": "livestock_in_pasture",
    "sheep": "livestock_in_pasture",
    "horse": "livestock_in_pasture",
    "book": "book_stack_or_bookshelf",
    "kite": "visible_bird",
}

# VLM 自由词（含中文）→ 锚点；仍需有 YOLO 框才写入 v2.3（bbox 必填）
_VLM_NAME_TO_ANCHOR: Dict[str, str] = {
    "wind_chime": "visible_wind_chime",
    "windchime": "visible_wind_chime",
    "chime": "visible_wind_chime",
    "kettle": "visible_kettle",
    "teapot": "visible_kettle",
    "coffee_machine": "operating_coffee_machine",
    "coffeemachine": "operating_coffee_machine",
    "espresso": "operating_coffee_machine",
    "fan": "running_fan",
    "air_conditioner": "visible_air_conditioner",
    "ac": "visible_air_conditioner",
    "washing_machine": "running_washing_machine",
    "record_player": "visible_record_player",
    "turntable": "visible_record_player",
    "radio": "visible_radio_or_tuning_knob",
    "fountain": "visible_fountain",
    "waterfall": "visible_waterfall",
    "frog": "visible_frog",
    "bee": "visible_bee",
    "cricket": "visible_cricket",
    "cicada": "visible_cicada",
    "singing_bowl": "visible_singing_bowl",
    "风铃": "visible_wind_chime",
    "水壶": "visible_kettle",
    "键盘": "visible_keyboard",
    "杯子": "single_visible_cup",
    "鸟": "visible_bird",
    "猫": "relaxed_or_sleeping_cat",
}

_SLEEPING_CAT_STATES = {
    "sleeping", "asleep", "relaxed", "resting", "lying", "curled",
    "睡觉", "睡着", "趴着", "蜷缩", "休息",
}

_WALKING_STATES = {
    "walking", "walk", "striding", "crossing", "走", "行走", "走路",
}

_TYPING_STATES = {
    "typing", "type", "打字",
}

_RAIN_HINTS = {
    "rain", "rainy", "raining", "雨", "下雨",
}

# 交接包里的锚点 id → 给 YOLO 类名补状态，否则猫/人会对不上
_ANCHOR_STATE_HINTS: Dict[str, Tuple[str, str]] = {
    "relaxed_or_sleeping_cat": ("cat", "sleeping"),
    "hands_on_keyboard_typing": ("keyboard", "typing"),
    "walking_person": ("person", "walking"),
    "walking_person_on_snow": ("person", "walking"),
    "umbrella_in_visible_rain": ("umbrella", "rainy"),
}

_VEHICLE_CLASSES = {"car", "bus", "truck", "motorcycle", "bicycle"}

_TABLEWARE_CLASSES = {"fork", "knife", "spoon", "bowl", "wine glass"}


def _norm(name: str) -> str:
    return (name or "").strip().lower().replace("-", "_").replace(" ", "_")


def _state_hits(state: str, vocab: Iterable[str]) -> bool:
    text = (state or "").strip().lower()
    if not text:
        return False
    return any(token in text for token in vocab)


def map_name_to_anchor(
    name: str,
    state: str = "",
    *,
    rain_context: bool = False,
) -> Optional[str]:
    """把单个物体名(+可选状态)映射到 v2.3 anchor_id；无法成立则返回 None。"""
    key = _norm(name)
    if not key:
        return None

    if key in {"cat", "猫"}:
        if _state_hits(state, _SLEEPING_CAT_STATES):
            return "relaxed_or_sleeping_cat"
        return None

    if key in {"person", "people", "human", "man", "woman", "人"}:
        if _state_hits(state, _WALKING_STATES):
            return "walking_person"
        return None

    if key == "keyboard" and _state_hits(state, _TYPING_STATES):
        return "hands_on_keyboard_typing"

    if key == "umbrella" and rain_context:
        return "umbrella_in_visible_rain"

    if key in _STATIC_NAME_TO_ANCHOR:
        return _STATIC_NAME_TO_ANCHOR[key]

    if key in _VLM_NAME_TO_ANCHOR:
        return _VLM_NAME_TO_ANCHOR[key]

    return None


def _bbox_of(det: Any) -> Optional[List[float]]:
    bbox = getattr(det, "bbox", None)
    if not bbox or len(bbox) != 4:
        return None
    x1, y1, x2, y2 = (float(v) for v in bbox)
    if not (0.0 <= x1 <= 1.0 and 0.0 <= y1 <= 1.0 and 0.0 <= x2 <= 1.0 and 0.0 <= y2 <= 1.0):
        x1, y1, x2, y2 = (
            max(0.0, min(1.0, x1)),
            max(0.0, min(1.0, y1)),
            max(0.0, min(1.0, x2)),
            max(0.0, min(1.0, y2)),
        )
    if x1 >= x2 or y1 >= y2:
        return None
    return [x1, y1, x2, y2]


def _iou(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def _union_bbox(boxes: Sequence[Sequence[float]]) -> List[float]:
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def detections_to_anchors(
    detections: Sequence[Any],
    entity_states: Optional[Dict[str, str]] = None,
    suggested_names: Optional[Iterable[str]] = None,
    iou_threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """YOLO Detection 列表 → v2.3 trigger_anchors（无框的 VLM-only 实体直接丢弃）。"""
    states = { _norm(k): v for k, v in (entity_states or {}).items() }
    suggested = { _norm(n) for n in (suggested_names or []) if n }
    for hint_id, (cls, st) in _ANCHOR_STATE_HINTS.items():
        if hint_id in suggested or hint_id in states:
            states.setdefault(cls, st)
    rain_context = any(
        hint in " ".join(list(states.values()) + list(suggested))
        for hint in _RAIN_HINTS
    ) or any(_state_hits(v, _RAIN_HINTS) for v in states.values())

    raw: List[Tuple[str, float, List[float]]] = []
    vehicle_boxes: List[Tuple[float, List[float]]] = []
    tableware_boxes: List[Tuple[float, List[float]]] = []
    cup_boxes: List[Tuple[float, List[float]]] = []
    person_boxes: List[Tuple[float, List[float]]] = []

    for det in detections:
        name = _norm(getattr(det, "name", ""))
        bbox = _bbox_of(det)
        if not name or bbox is None:
            continue
        conf = float(getattr(det, "conf", 0.0))
        state = states.get(name, "")

        if name in _VEHICLE_CLASSES:
            vehicle_boxes.append((conf, bbox))
        if name in _TABLEWARE_CLASSES:
            tableware_boxes.append((conf, bbox))
        if name == "cup":
            cup_boxes.append((conf, bbox))
        if name == "person":
            person_boxes.append((conf, bbox))

        anchor_id = map_name_to_anchor(name, state, rain_context=rain_context)
        if anchor_id is None:
            continue
        raw.append((anchor_id, conf, bbox))

    if len(cup_boxes) >= 2:
        raw = [(a, c, b) for a, c, b in raw if a != "single_visible_cup"]
        boxes = [b for _, b in cup_boxes]
        raw.append((
            "multiple_cups_or_cup_saucer",
            max(c for c, _ in cup_boxes),
            _union_bbox(boxes),
        ))

    if len(vehicle_boxes) >= 2:
        boxes = [b for _, b in vehicle_boxes]
        raw.append((
            "road_vehicle_flow",
            max(c for c, _ in vehicle_boxes),
            _union_bbox(boxes),
        ))

    if len(tableware_boxes) >= 2:
        boxes = [b for _, b in tableware_boxes]
        raw.append((
            "visible_tableware",
            max(c for c, _ in tableware_boxes),
            _union_bbox(boxes),
        ))

    if len(person_boxes) >= 4:
        boxes = [b for _, b in person_boxes]
        raw.append((
            "gathered_crowd",
            max(c for c, _ in person_boxes),
            _union_bbox(boxes),
        ))

    # 同 anchor_id 且 IoU 高的框去重，保留置信度更高者
    kept: List[Tuple[str, float, List[float]]] = []
    for anchor_id, conf, bbox in sorted(raw, key=lambda x: x[1], reverse=True):
        duplicate = False
        for other_id, _, other_bbox in kept:
            if other_id == anchor_id and _iou(bbox, other_bbox) >= iou_threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append((anchor_id, conf, bbox))

    anchors: List[Dict[str, Any]] = []
    for anchor_id, conf, bbox in kept:
        anchors.append({
            "anchor_id": anchor_id,
            "bbox_norm": {
                "format": "xyxy",
                "x_min": round(bbox[0], 4),
                "y_min": round(bbox[1], 4),
                "x_max": round(bbox[2], 4),
                "y_max": round(bbox[3], 4),
            },
            "confidence": round(max(0.0, min(1.0, conf)), 4),
            "source": "yolo",
        })
    return anchors
