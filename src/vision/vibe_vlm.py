# -*- coding: utf-8 -*-
"""视觉层 - 氛围分析：调用 VLM 输出 global_vibe 字典。

角色 A（视觉-氛围）维护此文件。
v2: 新增 targeted retry —— 缺字段时换 prompt 专门追要。
v6: scene_type 按分层词表取值；suggested_entities 只保留视觉锚点词典内的实体。
v7: 对齐音频层权威规范——scene_type 走 contracts/playback_proposal/scene_type_vocabulary.json(424 值)，none/other_* 兜底，
    scene_group 查表生成；实体收敛到 contracts/anchor_dictionary.json(87 锚点)。
"""

from __future__ import annotations

import ast
import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from openai import OpenAI

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_MODEL = os.environ.get("VLM_MODEL", "minicpm-v:8b")

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "configs" / "prompts.yaml"
SCENE_VOCAB_PATH = REPO_ROOT / "contracts" / "playback_proposal" / "scene_type_vocabulary.json"
ANCHOR_DICT_PATH = REPO_ROOT / "contracts" / "anchor_dictionary.json"

# mood 词表对齐 2.3：neutral/calm/cozy/cheerful/lively/majestic/mysterious/melancholic/tense/eerie（无 gloomy）
VALID_MOOD = {"neutral", "calm", "cozy", "cheerful", "lively", "majestic", "mysterious", "melancholic", "tense", "eerie"}
VALID_WARMTH = {"warm", "neutral", "cool"}
VALID_NOISE = {"white", "pink", "brown"}
VALID_TOD = {"dawn", "morning", "noon", "afternoon", "dusk", "night"}

_MOOD_FALLBACK = {
    "serene": "calm", "peaceful": "calm", "quiet": "calm", "tranquil": "calm",
    "relaxed": "calm", "soothing": "calm", "relaxing": "calm",
    "cool": "calm",
    "happy": "cheerful", "joyful": "cheerful", "bright": "cheerful", "upbeat": "cheerful",
    "sad": "melancholic", "sorrow": "melancholic", "nostalgic": "melancholic",
    "lonely": "melancholic", "depressed": "melancholic",
    "busy": "lively", "energetic": "lively", "vibrant": "lively", "crowded": "lively",
    "dark": "melancholic", "dreary": "melancholic", "somber": "melancholic", "overcast": "melancholic",
    "boring": "neutral",
    "intimate": "cozy", "warm_mood": "cozy", "comfortable": "cozy",
    "spooky": "eerie", "uncanny": "eerie", "creepy": "eerie",
    "frightening": "eerie", "scary": "eerie",
    "anxious": "tense", "stressful": "tense", "nervous": "tense", "unhappy": "melancholic", "miserable": "melancholic",
    "gloomy": "melancholic", "dark_mood": "melancholic",
    "majestic": "majestic", "grand": "majestic", "壮丽": "majestic",
    "mysterious": "mysterious", "mystic": "mysterious", "神秘": "mysterious",
    # Chinese mood fallbacks
    "平静": "calm", "宁静": "calm", "安静": "calm",
    "温馨": "cozy", "温暖": "cozy", "舒适": "cozy",
    "热闹": "lively", "活跃": "lively", "繁忙": "lively",
    "紧张": "tense", "压抑": "tense",
    "阴暗": "melancholic", "沉闷": "melancholic", "阴郁": "melancholic",
    "忧伤": "melancholic", "怀旧": "melancholic", "悲伤": "melancholic",
    "诡异": "eerie", "阴森": "eerie", "不安": "eerie",
    "愉快": "cheerful", "欢乐": "cheerful", "开心": "cheerful",
}
_WARMTH_FALLBACK = {
    "yellow": "warm", "orange": "warm", "reddish": "warm",
    "blue": "cool", "gray": "cool", "bluish": "cool", "cold": "cool",
}
_NOISE_FALLBACK = {
    "bright_noise": "white", "neutral_noise": "pink", "dark_noise": "brown",
    "green": "pink", "blue": "white", "red": "brown", "grey": "pink",
}
_TOD_FALLBACK = {
    "sunrise": "dawn", "sunset": "dusk", "evening": "dusk",
    "midday": "noon", "daytime": "afternoon",
    "unknown": "afternoon", "twilight": "dusk", "day": "afternoon",
    "indeterminate": "afternoon",
    "nighttime": "night", "daytime": "afternoon",
    # Chinese fallbacks
    "黎明": "dawn", "早晨": "morning", "上午": "morning",
    "正午": "noon", "中午": "noon", "下午": "afternoon",
    "傍晚": "dusk", "黄昏": "dusk", "夜晚": "night", "夜间": "night", "晚上": "night",
    "not determinable": "afternoon", "unclear": "afternoon", "unspecified": "afternoon",
}


def _fuzzy_match(value, valid_set: set, fallback: dict, field_name: str) -> str:
    # VLM sometimes outputs lists like ["calm"] instead of "calm"
    if isinstance(value, list):
        value = value[0] if value else ""
    if isinstance(value, (int, float)):
        value = str(value)
    value = str(value).strip().lower()
    # If VLM concatenates multiple values, take the first word
    if " " in value:
        value = value.split()[0]
        logger.warning("%s: multi-word value, using first word '%s'", field_name, value)
    if value in valid_set:
        return value
    if value in fallback:
        resolved = fallback[value]
        logger.warning("%s: '%s' -> '%s'", field_name, value, resolved)
        return resolved
    # Final safety net: default to safe value instead of failing
    default_map = {"mood": "calm", "warmth": "neutral", "base_noise": "pink", "time_of_day": "afternoon"}
    safe = default_map.get(field_name, list(valid_set)[0])
    logger.warning("%s: '%s' not recognized, defaulting to '%s'", field_name, value, safe)
    return safe


def _load_prompts() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config not found: {CONFIG_PATH}")
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_scene_vocab() -> Dict[str, List[str]]:
    """读取场景受控词表 contracts/playback_proposal/scene_type_vocabulary.json（音频层 v1.0）。

    Returns:
        大类 -> 叶子场景值列表 的映射。
    """
    with SCENE_VOCAB_PATH.open(encoding="utf-8") as f:
        return json.load(f)["groups"]


def _load_anchor_dictionary() -> Dict[str, Dict[str, Any]]:
    """读取视觉锚点词典 contracts/anchor_dictionary.json（音频层 v1.0，87 个锚点）。

    Returns:
        anchor_id -> {type, sound_id, strength, definition} 的映射。
    """
    with ANCHOR_DICT_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return {a["anchor_id"]: a for a in data["anchors"]}


SCENE_VOCAB = _load_scene_vocab()
SCENE_TYPES = {s for types in SCENE_VOCAB.values() for s in types}
SCENE_GROUP_BY_SCENE = {s: g for g, vals in SCENE_VOCAB.items() for s in vals}
ANCHOR_DICT = _load_anchor_dictionary()
ANCHOR_IDS = set(ANCHOR_DICT.keys())

_NON_SCENE_KEYWORDS = [
    # 没有稳定物理环境的图片 -> scene_type=none
    "meme", "screenshot", "document", "slides", "code_editor", "interface",
    "product_shot", "portrait", "selfie", "macro", "close_up", "still_life",
    "poster", "chart", "graph", "book_page", "screen", "cartoon", "drawing",
    "none", "empty", "microshot", "micro",
]

_SCENE_SYNONYMS = {
    # 常见自由词 -> 词表内最接近的叶子场景（或 other_* / none）
    "coffee_shop": "cafe",
    "diner": "restaurant",
    "pub": "bar",
    "class": "classroom",
    "gymnasium": "gym",
    "fitness_center": "gym",
    "store": "retail_store",
    "shop": "retail_store",
    "mall": "shopping_mall",
    "city": "cityscape",
    "building": "building_exterior",
    "buildings": "building_exterior",
    "room": "living_room",
    "home": "living_room",
    "indoor": "other_indoor",
    "outdoor": "other_outdoor",
    "outdoors": "other_outdoor",
    "nature": "other_natural",
    "natural": "other_natural",
    "landscape": "other_natural",
    "water": "lake",
    "gallery": "art_gallery",
    "square": "public_square",
    "night": "none",
    "dusk": "none",
    "dawn": "none",
    "clouds": "cloudscape",
    "cloud": "cloudscape",
    "tree": "forest",
    "trees": "forest",
    "brick_wall": "building_exterior",
    "field": "farmland",
    "terraced_field": "farmland",
    "dining": "dining_room",
    "school": "classroom",
    "university": "university_building",
    "airport": "airport_terminal",
    "station": "train_station",
    "train": "train_station",
    "subway": "metro_station",
    "bus": "bus_station",
    "creek": "stream",
    "snow": "snowfield",
    "yard": "garden",
    "forests": "forest",
    "terrace_fields": "farmland",
    "sky_sunset": "sky",
    "wall": "building_exterior",
    "plate": "dining_room",
}

_COARSE_KEYWORDS = [
    # 有稳定环境但词表无精确匹配 -> other_* 兜底（按关键词归组）
    ("other_indoor", ["room", "indoor", "home", "office", "kitchen", "bed", "hall", "corridor", "interior", "studio", "garage", "house", "apartment", "bathroom", "living", "dining"]),
    ("other_outdoor", ["street", "road", "city", "urban", "outdoor", "plaza", "square", "park", "playground", "building", "campus", "sidewalk", "highway", "market", "stadium", "zoo", "alley"]),
    ("other_transport", ["train", "station", "airport", "metro", "subway", "bus", "car", "vehicle", "railway", "terminal", "port", "airplane", "cabin", "taxi", "ferry"]),
    ("other_natural", ["forest", "mountain", "lake", "river", "ocean", "sea", "beach", "field", "grass", "nature", "desert", "sky", "valley", "hill", "garden", "snow", "cave", "water"]),
]

_GROUP_TO_OTHER = {
    # VLM 偶尔输出大组名 -> 归到对应的 other_*（防御性兜底）
    "natural_terrain": "other_natural", "forest_vegetation": "other_natural",
    "water_coastal": "other_natural", "sky_weather": "other_natural",
    "agriculture_rural": "other_natural",
    "urban_outdoor": "other_outdoor", "events_social": "other_outdoor",
    "animal_facilities": "other_outdoor",
    "transport_outdoor": "other_transport", "transport_indoor": "other_transport",
    "residential_indoor": "other_indoor", "workplace_industrial": "other_indoor",
    "education_research": "other_indoor", "food_hospitality": "other_indoor",
    "retail_personal_service": "other_indoor", "culture_entertainment": "other_indoor",
    "sports_recreation": "other_indoor", "religion_heritage": "other_indoor",
    "healthcare_civic_security": "other_indoor",
    "non_scene": "none",
}

_LEGACY_ENTITY_TO_ANCHOR = {
    # 旧 VLM 自由词 -> 87 锚点词典中最保守的映射（仅限语义明确的）
    # 用于旧数据回填；新数据应由检测器直接产出 anchor_id，不走此表。
    "bird": "visible_bird",
    "birds": "visible_bird",
    "clock": "visible_clock",
    "cup": "single_visible_cup",
    "cups": "single_visible_cup",
    "wind_chime": "visible_wind_chime",
    "kettle": "visible_kettle",
    "keyboard": "visible_keyboard",
    "cat": "relaxed_or_sleeping_cat",
    "stream": "visible_stream_flow",
    "waterfall": "visible_waterfall",
    "fountain": "visible_fountain",
}


def normalize_scene_type(value) -> str:
    """把 VLM 输出的 scene_type 归一化到受控词表 contracts/playback_proposal/scene_type_vocabulary.json 内。

    规则: 列表取首项；小写、空格转下划线；词表内直接返回；
    无稳定环境的词(截图/人像/微距等) -> none；
    常见自由词经 _SCENE_SYNONYMS 映射；仍无法精确归类时按关键词归到
    other_indoor/other_outdoor/other_natural/other_transport；最终兜底 none。
    """
    if isinstance(value, list):
        value = value[0] if value else ""
    value = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if value in SCENE_TYPES:
        return value
    if value in SCENE_VOCAB:
        mapped = _GROUP_TO_OTHER.get(value, "none")
        logger.warning("scene_type: '%s' 是大组名 -> '%s'", value, mapped)
        return mapped
    if any(kw in value for kw in _NON_SCENE_KEYWORDS):
        logger.warning("scene_type: '%s' -> 'none' (non-scene)", value)
        return "none"
    if value in _SCENE_SYNONYMS:
        mapped = _SCENE_SYNONYMS[value]
        logger.warning("scene_type: '%s' -> '%s'", value, mapped)
        return mapped
    for coarse, kws in _COARSE_KEYWORDS:
        if any(kw in value for kw in kws):
            logger.warning("scene_type: '%s' -> '%s' (coarse)", value, coarse)
            return coarse
    logger.warning("scene_type: '%s' not in vocabulary, defaulting to 'none'", value)
    return "none"


def scene_to_group(scene_type: str) -> str:
    """scene_type -> scene_group（由词表查表生成，不需要 VLM 重复判断）。"""
    return SCENE_GROUP_BY_SCENE.get(scene_type, "none")


def normalize_secondary_scene_types(value, primary=None) -> list:
    """归一化 secondary_scene_types：词表内、去重、去掉主场景、最多 2 个。"""
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        s = normalize_scene_type(v)
        if s == "none" or s == primary or s in out:
            continue
        out.append(s)
    return out[:2]

def filter_anchor_entities(entities) -> List[Dict[str, Any]]:
    """只保留视觉锚点词典(87 个锚点)内的实体。

    - 已是 anchor_id 的直接保留；
    - 旧 VLM 自由词经 _LEGACY_ENTITY_TO_ANCHOR 保守映射；
    - 其余一律丢弃(音频层对词典外实体没有声音语义)。
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(entities, list):
        return out
    for e in entities:
        if not isinstance(e, dict):
            continue
        name = str(e.get("name", "")).strip().lower()
        if name in _LEGACY_ENTITY_TO_ANCHOR:
            name = _LEGACY_ENTITY_TO_ANCHOR[name]
        elif name not in ANCHOR_IDS:
            continue
        item = dict(e)
        item["name"] = name
        if "source" not in item:
            item["source"] = "vlm_legacy"
        out.append(item)
    return out


def _encode_image(image_path: Path, max_size: int = 768) -> str:
    from PIL import Image
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    if max(w, h) > max_size:
        scale = max_size / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        logger.debug("Resized %s: %dx%d -> %dx%d", image_path.name, w, h, new_w, new_h)
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=75)
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{img_b64}"


def _call_vlm(image_path: Path, client: OpenAI, user_prompt: str | None = None) -> str:
    prompts = _load_prompts()
    data_url = _encode_image(image_path)
    text = user_prompt if user_prompt else prompts["global_vibe"]["user"]
    response = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": prompts["global_vibe"]["system"]},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": text},
            ]},
        ],
    )
    return response.choices[0].message.content


def _extract_json(raw: str) -> str:
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if md_match:
        return md_match.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1]
    raise ValueError(f"Cannot extract JSON: {raw[:200]}")


def _repair_json(raw_json: str) -> str:
    raw_json = re.sub(r"//[^\n]*", "", raw_json)
    raw_json = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", raw_json)
    raw_json = re.sub(r"'([a-z_]+)'\s*:", r'"\1":', raw_json)
    raw_json = re.sub(r",\s*([}\]])", r"\1", raw_json)
    return raw_json


def _try_parse(raw_json: str) -> dict:
    repaired = _repair_json(raw_json)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass
    try:
        return ast.literal_eval(repaired)
    except (ValueError, SyntaxError):
        pass
    try:
        return json.loads(re.sub(r"'([^']*)'", r'"\1"', repaired))
    except json.JSONDecodeError:
        pass
    raise ValueError(f"Cannot parse JSON: {raw_json[:200]}")


def _parse_and_validate(raw_json: str) -> Dict[str, Any]:
    data = _try_parse(raw_json)

    # brightness 由程序计算(视觉记录规范 2.3)，不要求 VLM 输出
    required = ["scene_type", "mood", "warmth", "base_noise", "time_of_day"]
    if "suggested_entities" in data:
        data["suggested_entities"] = filter_anchor_entities(data["suggested_entities"])
    missing = [f for f in required if f not in data]
    if missing:
        data["_partial"] = True
        data["_missing_fields"] = missing
        for f in missing:
            data[f] = None

    if data.get("brightness") is not None:
        brightness = float(data["brightness"])
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"brightness out of range: {brightness}")
        data["brightness"] = brightness

    if data.get("mood") is not None:
        data["mood"] = _fuzzy_match(data["mood"], VALID_MOOD, _MOOD_FALLBACK, "mood")
    if data.get("warmth") is not None:
        data["warmth"] = _fuzzy_match(data["warmth"], VALID_WARMTH, _WARMTH_FALLBACK, "warmth")
    if data.get("base_noise") is not None:
        data["base_noise"] = _fuzzy_match(data["base_noise"], VALID_NOISE, _NOISE_FALLBACK, "base_noise")
    if data.get("time_of_day") is not None:
        data["time_of_day"] = _fuzzy_match(data["time_of_day"], VALID_TOD, _TOD_FALLBACK, "time_of_day")
    if data.get("scene_type") is not None:
        data["scene_type"] = normalize_scene_type(data["scene_type"])
    if "secondary_scene_types" in data:
        data["secondary_scene_types"] = normalize_secondary_scene_types(
            data["secondary_scene_types"], data.get("scene_type")
        )

    return data


def _build_targeted_prompt(missing_fields: list[str]) -> str:
    field_specs = {
        "scene_type": "scene_type: 从受控词表选最具体场景；无稳定环境用 none；无法精确归类用 other_*",
        "mood": "mood: 情绪，从 calm/cozy/lively/tense/gloomy/melancholic/eerie/cheerful 中选一个",
        "warmth": "warmth: 冷暖色调，warm/neutral/cool",
        "base_noise": "base_noise: 底噪类型，white/pink/brown",
        "time_of_day": "time_of_day: 时段，dawn/morning/noon/afternoon/dusk/night",
    }
    specs_lines = [field_specs[f] for f in missing_fields if f in field_specs]
    fields_str = ", ".join(missing_fields)
    return (
        f"之前的分析遗漏了以下字段: {fields_str}。\n"
        f"请重新看图，只补充这些字段，输出JSON:\n"
        + "\n".join(specs_lines) + "\n"
        f"只输出JSON，不要其他文字。"
    )


def get_global_vibe(
    image_path: str | Path,
    client: Optional[OpenAI] = None,
    max_retries: int = 2,
) -> Dict[str, Any]:
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    if client is None:
        client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")

    last_error = None
    for attempt in range(max_retries):
        try:
            logger.info("Analyzing %s (%d/%d)", image_path.name, attempt + 1, max_retries)
            raw = _call_vlm(image_path, client)
            raw_json = _extract_json(raw)
            result = _parse_and_validate(raw_json)

            # Targeted retry: 如果缺字段，换 prompt 专门追要
            missing = result.get("_missing_fields", [])
            if missing and attempt < max_retries - 1:
                logger.info("Missing: %s, targeted retry", missing)
                target_prompt = _build_targeted_prompt(missing)
                raw2 = _call_vlm(image_path, client, user_prompt=target_prompt)
                raw_json2 = _extract_json(raw2)
                patch = _try_parse(raw_json2)
                for f in missing:
                    if f in patch and patch[f] is not None:
                        result[f] = patch[f]
                result = _parse_and_validate(json.dumps(result))

            # Strip internal markers before returning
            result.pop("_partial", None)
            result.pop("_missing_fields", None)
            logger.info("Done: scene=%s mood=%s bri=%s",
                        result.get("scene_type"), result.get("mood"), result.get("brightness"))
            return result
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            logger.warning("Attempt %d failed: %s", attempt + 1, e)

    raise ValueError(f"All {max_retries} attempts failed: {last_error}")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if len(sys.argv) < 2:
        train_dir = REPO_ROOT.parent / "data" / "Train"
        if train_dir.exists():
            imgs = sorted(train_dir.glob("*.jpg"))
            img_path = str(imgs[0]) if imgs else None
        else:
            img_path = None
        if not img_path:
            print("Usage: python -m src.vision.vibe_vlm <image_path>")
            sys.exit(1)
    else:
        img_path = sys.argv[1]
    vibe = get_global_vibe(img_path)
    print(json.dumps(vibe, ensure_ascii=False, indent=2))