# -*- coding: utf-8 -*-
"""视觉层 · 氛围分析：调用 VLM 输出 global_vibe 字典。

角色 A（视觉-氛围）维护此文件。
"""

from __future__ import annotations

import ast
import base64
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from openai import OpenAI

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_MODEL = "minicpm-v:8b"

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "configs" / "prompts.yaml"

VALID_MOOD = {"calm", "cozy", "lively", "tense", "gloomy", "melancholic", "eerie", "cheerful"}
VALID_WARMTH = {"warm", "neutral", "cool"}
VALID_NOISE = {"white", "pink", "brown"}
VALID_TOD = {"dawn", "morning", "noon", "afternoon", "dusk", "night"}

_MOOD_FALLBACK = {
    "serene": "calm", "peaceful": "calm", "quiet": "calm", "tranquil": "calm",
    "relaxed": "calm", "soothing": "calm", "neutral": "calm", "relaxing": "calm",
    "cool": "calm",
    "happy": "cheerful", "joyful": "cheerful", "bright": "cheerful", "upbeat": "cheerful",
    "sad": "melancholic", "sorrow": "melancholic", "nostalgic": "melancholic",
    "lonely": "melancholic", "depressed": "melancholic",
    "busy": "lively", "energetic": "lively", "vibrant": "lively", "crowded": "lively",
    "dark": "gloomy", "dreary": "gloomy", "somber": "gloomy", "overcast": "gloomy",
    "boring": "gloomy",
    "intimate": "cozy", "warm_mood": "cozy", "comfortable": "cozy",
    "spooky": "eerie", "uncanny": "eerie", "creepy": "eerie",
    "frightening": "eerie", "scary": "eerie",
    "anxious": "tense", "stressful": "tense", "nervous": "tense",
}
_WARMTH_FALLBACK = {
    "yellow": "warm", "orange": "warm", "reddish": "warm",
    "blue": "cool", "gray": "cool", "bluish": "cool", "cold": "cool",
}
_NOISE_FALLBACK = {"bright_noise": "white", "neutral_noise": "pink", "dark_noise": "brown"}
_TOD_FALLBACK = {
    "sunrise": "dawn", "sunset": "dusk", "evening": "dusk",
    "midday": "noon", "daytime": "afternoon",
    "unknown": "afternoon", "twilight": "dusk",
}


def _fuzzy_match(value: str, valid_set: set, fallback: dict, field_name: str) -> str:
    value = value.strip().lower()
    if value in valid_set:
        return value
    if value in fallback:
        resolved = fallback[value]
        logger.warning("%s: '%s' -> '%s'", field_name, value, resolved)
        return resolved
    raise ValueError(f"{field_name} '{value}' not in {sorted(valid_set)}")


def _load_prompts() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config not found: {CONFIG_PATH}")
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _call_vlm(image_path: Path, client: OpenAI) -> str:
    img_bytes = image_path.read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    ext = image_path.suffix.lower().lstrip(".")
    mime = f"image/{ext}" if ext in ("jpg", "jpeg", "png", "webp") else "image/jpeg"
    data_url = f"data:{mime};base64,{img_b64}"

    prompts = _load_prompts()
    response = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": prompts["global_vibe"]["system"]},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompts["global_vibe"]["user"]},
                ],
            },
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

    required = ["scene_type", "mood", "brightness", "warmth", "base_noise", "time_of_day"]
    missing = [f for f in required if f not in data]
    if missing:
        logger.warning("Missing fields: %s, marking _partial", missing)
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

    return data


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
            logger.info("Done: %s mood=%s bri=%s", result["scene_type"], result.get("mood"), result.get("brightness"))
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