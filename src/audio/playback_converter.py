#!/usr/bin/env python3
"""Convert one visual-analysis JSON record into mono and optional binaural plans."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "configs" / "playback"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "playback"


class ConversionError(ValueError):
    """Raised when the visual record or project configuration is invalid."""


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise ConversionError(f"找不到文件: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConversionError(f"JSON格式错误 {path}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def stable_seed(record_id: str, explicit_seed: int | None) -> int:
    if explicit_seed is not None:
        return explicit_seed
    digest = hashlib.sha256(record_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def unwrap_record(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ConversionError("输入JSON顶层必须是对象")
    if "example_record" in document:
        record = document["example_record"]
    else:
        record = document
    if not isinstance(record, dict):
        raise ConversionError("example_record必须是对象")
    return record


def validate_bbox(bbox: Any, anchor_index: int) -> None:
    if not isinstance(bbox, dict) or bbox.get("format") != "xyxy":
        raise ConversionError(f"trigger_anchors[{anchor_index}].bbox_norm.format必须为xyxy")
    keys = ("x_min", "y_min", "x_max", "y_max")
    try:
        values = [float(bbox[key]) for key in keys]
    except (KeyError, TypeError, ValueError) as exc:
        raise ConversionError(f"trigger_anchors[{anchor_index}].bbox_norm缺少合法坐标") from exc
    x_min, y_min, x_max, y_max = values
    if not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values):
        raise ConversionError(f"trigger_anchors[{anchor_index}]坐标必须在[0,1]")
    if not x_min < x_max or not y_min < y_max:
        raise ConversionError(f"trigger_anchors[{anchor_index}]必须满足x_min<x_max且y_min<y_max")


def validate_record(record: dict[str, Any], allowed_anchors: set[str]) -> None:
    required = ("schema_version", "id", "image", "global_vibe", "trigger_anchors")
    missing = [key for key in required if key not in record]
    if missing:
        raise ConversionError(f"视觉记录缺少字段: {', '.join(missing)}")
    if record["schema_version"] != "2.3":
        raise ConversionError("本演示项目只接受schema_version=2.3")
    if not isinstance(record["id"], str) or not record["id"]:
        raise ConversionError("id必须是非空字符串")
    vibe = record["global_vibe"]
    if not isinstance(vibe, dict):
        raise ConversionError("global_vibe必须是对象")
    for key in ("scene_type", "secondary_scene_types", "scene_group", "mood", "warmth", "time_of_day", "brightness"):
        if key not in vibe:
            raise ConversionError(f"global_vibe缺少字段: {key}")
    brightness = float(vibe["brightness"])
    if not math.isfinite(brightness) or not 0.0 <= brightness <= 1.0:
        raise ConversionError("global_vibe.brightness必须在[0,1]")
    anchors = record["trigger_anchors"]
    if not isinstance(anchors, list):
        raise ConversionError("trigger_anchors必须是数组")
    for index, anchor in enumerate(anchors):
        if not isinstance(anchor, dict):
            raise ConversionError(f"trigger_anchors[{index}]必须是对象")
        anchor_id = anchor.get("anchor_id")
        if anchor_id not in allowed_anchors:
            raise ConversionError(f"trigger_anchors[{index}].anchor_id不在2.3受控词表: {anchor_id}")
        confidence = anchor.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
            raise ConversionError(f"trigger_anchors[{index}].confidence必须在[0,1]")
        validate_bbox(anchor.get("bbox_norm"), index)


def load_mapping_config(config_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    settings = load_json(config_dir / "decision_settings.json")
    scene_profiles = load_json(config_dir / "scene_audio_profiles.json")
    manifest = load_json(config_dir / "audio_manifest.json")
    visual_spec_path = (PROJECT_ROOT / settings["visual_spec_path"]).resolve()
    visual_spec = load_json(visual_spec_path)
    return settings, scene_profiles, manifest, visual_spec


def build_anchor_mapping(visual_spec: dict[str, Any]) -> tuple[set[str], dict[str, list[dict[str, Any]]]]:
    allowed = set(visual_spec["enum_definitions"]["initial_visual_anchor_id"])
    by_anchor: dict[str, list[dict[str, Any]]] = {}
    for mapping in visual_spec["anchor_sound_mapping_reference"]["mappings"]:
        for anchor_id, strength in mapping["anchors"].items():
            candidate = {
                "sound_id": mapping["sound_id"],
                "strength": strength,
                "mode_hint": mapping["mode"],
                "sleep_safety": mapping["sleep_safety"],
            }
            by_anchor.setdefault(anchor_id, []).append(candidate)
    return allowed, by_anchor


def asset_index(manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for asset in manifest.get("assets", []):
        result.setdefault(asset["sound_id"], []).append(asset)
    return result


def pick_asset(sound_id: str, role: str, assets: dict[str, list[dict[str, Any]]], rng: random.Random) -> dict[str, Any]:
    matching = [asset for asset in assets.get(sound_id, []) if asset.get("role") == role]
    if not matching:
        raise ConversionError(f"audio_manifest.json缺少素材: sound_id={sound_id}, role={role}")
    matching.sort(key=lambda item: item["asset_id"])
    return matching[rng.randrange(len(matching))]


def pick_asset_pool(sound_id: str, role: str, assets: dict[str, list[dict[str, Any]]]) -> list[str]:
    matching = sorted(
        asset["asset_id"] for asset in assets.get(sound_id, []) if asset.get("role") == role
    )
    if not matching:
        raise ConversionError(f"audio_manifest.json缺少素材池: sound_id={sound_id}, role={role}")
    return matching


def mix_modifiers(vibe: dict[str, Any]) -> list[str]:
    return [
        f"mood:{vibe['mood']}",
        f"warmth:{vibe['warmth']}",
        f"time_of_day:{vibe['time_of_day']}",
        f"brightness:{float(vibe['brightness']):.2f}",
    ]


def lowpass_from_brightness(brightness: float) -> int:
    return round(6500 + brightness * 9500)


def build_ambient_layers(
    record: dict[str, Any],
    scene_profiles: dict[str, Any],
    assets: dict[str, list[dict[str, Any]]],
    rng: random.Random,
    mono: bool,
) -> tuple[list[dict[str, Any]], str]:
    vibe = record["global_vibe"]
    scene_type = vibe["scene_type"]
    group = vibe["scene_group"]
    profile = scene_profiles.get("scene_types", {}).get(scene_type)
    source = f"scene_type:{scene_type}"
    if profile is None:
        profile = scene_profiles.get("scene_groups", {}).get(group)
        source = f"scene_group:{group}"
    if profile is None:
        profile = scene_profiles["fallbacks"]["silence"]
        source = "fallback:silence"
    sound_id = profile.get("primary_sound_id")
    if sound_id is None:
        return [], source
    asset = pick_asset(sound_id, "ambient", assets, rng)
    loop = asset.get("loop", {})
    if not loop.get("enabled") or not loop.get("seamless_verified"):
        raise ConversionError(f"环境循环素材未验证: {asset['asset_id']}")
    layer: dict[str, Any] = {
        "layer_id": "ambient_primary",
        "role": "primary",
        "sound_id": sound_id,
        "asset_id": asset["asset_id"],
        "mode": "loop",
        "gain_db": float(profile.get("gain_db", -18.0)),
        "lowpass_hz": lowpass_from_brightness(float(vibe["brightness"])),
        "fade_in_ms": 2500,
        "fade_out_ms": 3000,
        "loop_crossfade_ms": int(loop.get("crossfade_ms", 2500)),
    }
    if mono:
        layer["channel_mode"] = "mono"
    else:
        layer["spatial"] = {
            "render_mode": "diffuse_stereo_bed",
            "azimuth_width_deg": 100.0,
            "rear_diffusion": 0.18,
            "head_locked": True,
        }
    return [layer], source


def mode_role(mode_hint: str) -> tuple[str, str]:
    if mode_hint.startswith("loop"):
        return "texture", "intermittent_texture"
    if "texture" in mode_hint:
        return "texture", "intermittent_texture"
    return "trigger", "random_trigger"


def gain_for_candidate(role: str, safety: str) -> float:
    gain = -28.0 if role == "texture" else -30.0
    if safety == "medium":
        gain -= 2.0
    elif safety == "cautious":
        gain -= 5.0
    return gain


def schedule_for_candidate(role: str, mode_hint: str, safety: str) -> dict[str, Any]:
    if role == "texture":
        min_interval, max_interval, probability = 24.0, 55.0, 0.45
    else:
        min_interval, max_interval, probability = 35.0, 90.0, 0.35
    if "long_interval" in mode_hint:
        min_interval, max_interval = 60.0, 150.0
    if "very_long_interval" in mode_hint:
        min_interval, max_interval = 90.0, 240.0
    if "low_probability" in mode_hint:
        probability *= 0.55
    if "very_low_probability" in mode_hint:
        probability *= 0.35
    if safety == "medium":
        probability *= 0.8
    elif safety == "cautious":
        probability *= 0.5
    return {
        "min_interval_s": round(min_interval, 2),
        "max_interval_s": round(max_interval, 2),
        "probability": round(clamp(probability, 0.0, 1.0), 3),
        "selection": "shuffle_no_repeat",
        "max_simultaneous": 1,
    }


def collect_foreground_candidates(
    record: dict[str, Any],
    mapping_by_anchor: dict[str, list[dict[str, Any]]],
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    strength_values = settings["strength_values"]
    safety_values = settings["sleep_safety_values"]
    threshold = float(settings["foreground_candidate_score_threshold"])
    candidates: list[dict[str, Any]] = []
    for anchor_index, anchor in enumerate(record["trigger_anchors"]):
        for mapping in mapping_by_anchor.get(anchor["anchor_id"], []):
            score = (
                float(anchor["confidence"])
                * float(strength_values[mapping["strength"]])
                * float(safety_values[mapping["sleep_safety"]])
            )
            if score < threshold:
                continue
            role, mode = mode_role(mapping["mode_hint"])
            candidates.append(
                {
                    "source_anchor_index": anchor_index,
                    "anchor": anchor,
                    "sound_id": mapping["sound_id"],
                    "strength": mapping["strength"],
                    "sleep_safety": mapping["sleep_safety"],
                    "mode_hint": mapping["mode_hint"],
                    "role": role,
                    "mode": mode,
                    "score": score,
                }
            )
    candidates.sort(key=lambda item: (-item["score"], item["source_anchor_index"], item["sound_id"]))
    selected: list[dict[str, Any]] = []
    used_sounds: set[str] = set()
    for candidate in candidates:
        if candidate["sound_id"] in used_sounds:
            continue
        selected.append(candidate)
        used_sounds.add(candidate["sound_id"])
        if len(selected) >= int(settings["max_foreground_layers"]):
            break
    return selected


def build_foreground_layer(
    candidate: dict[str, Any],
    assets: dict[str, list[dict[str, Any]]],
    brightness: float,
    mono: bool,
    settings: dict[str, Any],
    layer_index: int,
) -> dict[str, Any]:
    pool = pick_asset_pool(candidate["sound_id"], candidate["role"], assets)
    layer: dict[str, Any] = {
        "layer_id": f"foreground_{candidate['sound_id']}_{layer_index}",
        "role": candidate["role"],
        "sound_id": candidate["sound_id"],
        "asset_pool": pool,
        "mode": candidate["mode"],
        "gain_db": gain_for_candidate(candidate["role"], candidate["sleep_safety"]),
        "lowpass_hz": min(lowpass_from_brightness(brightness), 12000),
        "schedule": schedule_for_candidate(
            candidate["role"], candidate["mode_hint"], candidate["sleep_safety"]
        ),
        "source_anchor_index": candidate["source_anchor_index"],
    }
    if mono:
        layer["channel_mode"] = "mono"
    else:
        layer["spatial"] = spatial_parameters(candidate, settings, layer_index)
    return layer


def evaluate_spatial_gate(candidates: list[dict[str, Any]], settings: dict[str, Any]) -> dict[str, Any]:
    policy = settings["spatial_gate"]
    threshold = float(policy["uncertainty_threshold"])
    max_spread = float(policy["max_region_spread"])
    reasons: list[dict[str, Any]] = []
    if len(candidates) < int(policy["minimum_spatial_candidate_count"]):
        reasons.append({"code": "NO_SPATIAL_CANDIDATES"})
    observed: list[float] = []
    for candidate in candidates:
        index = candidate["source_anchor_index"]
        depth = candidate["anchor"].get("depth_hint")
        if not isinstance(depth, dict):
            reasons.append({"code": "DEPTH_HINT_MISSING", "source_anchor_index": index})
            continue
        if depth.get("type") != "relative_monocular":
            reasons.append({"code": "DEPTH_TYPE_UNSUPPORTED", "source_anchor_index": index})
        if depth.get("class") == "unknown":
            reasons.append({"code": "DEPTH_CLASS_UNKNOWN", "source_anchor_index": index})
        try:
            uncertainty = float(depth["uncertainty"])
            spread = float(depth["region_spread"])
            value = float(depth["value"])
        except (KeyError, TypeError, ValueError):
            reasons.append({"code": "INVALID_SPATIAL_INPUT", "source_anchor_index": index})
            continue
        if not all(math.isfinite(item) and 0.0 <= item <= 1.0 for item in (uncertainty, spread, value)):
            reasons.append({"code": "INVALID_SPATIAL_INPUT", "source_anchor_index": index})
            continue
        observed.append(uncertainty)
        if uncertainty >= threshold:
            reasons.append(
                {
                    "code": "DEPTH_UNCERTAINTY_NOT_BELOW_THRESHOLD",
                    "source_anchor_index": index,
                    "observed": uncertainty,
                    "required": f"< {threshold}",
                }
            )
        if spread > max_spread:
            reasons.append(
                {
                    "code": "DEPTH_REGION_SPREAD_TOO_HIGH",
                    "source_anchor_index": index,
                    "observed": spread,
                    "required": f"<= {max_spread}",
                }
            )
    return {
        "passed": not reasons,
        "policy_version": policy["policy_version"],
        "uncertainty_threshold": threshold,
        "comparison": "strict_less_than",
        "max_region_spread": max_spread,
        "candidate_count": len(candidates),
        "evaluated_anchor_indices": [candidate["source_anchor_index"] for candidate in candidates],
        "maximum_observed_uncertainty": max(observed) if observed else None,
        "failure_reasons": reasons,
    }


def spatial_parameters(candidate: dict[str, Any], settings: dict[str, Any], layer_index: int) -> dict[str, Any]:
    anchor = candidate["anchor"]
    bbox = anchor["bbox_norm"]
    depth = anchor["depth_hint"]
    center_x = (float(bbox["x_min"]) + float(bbox["x_max"])) / 2.0
    center_y = (float(bbox["y_min"]) + float(bbox["y_max"])) / 2.0
    area = (float(bbox["x_max"]) - float(bbox["x_min"])) * (
        float(bbox["y_max"]) - float(bbox["y_min"])
    )
    relative_depth = float(depth["value"])
    azimuth = clamp((center_x - 0.5) * 120.0, -60.0, 60.0)
    elevation = clamp((0.5 - center_y) * 30.0, -15.0, 15.0)
    distance = clamp(1.0 + 11.0 * (relative_depth**1.3), 1.0, 15.0)
    distance_gain = clamp(-6.0 * math.log10(distance), -7.0, 0.0)
    distance_lowpass = round(clamp(16000.0 - 700.0 * distance, 6500.0, 16000.0))
    reverb_send = clamp(0.08 + 0.025 * distance, 0.08, 0.38)
    motion_enabled = anchor["anchor_id"] in set(settings["motion_anchor_ids"])
    if motion_enabled:
        motion = {
            "mode": "seeded_micro_motion",
            "seed_offset": 101 + layer_index,
            "azimuth_range_deg": 3.0,
            "elevation_range_deg": 1.0,
            "distance_range_ratio": 0.04,
            "period_s": 42.0,
            "smoothing_ms": 1500,
        }
    else:
        motion = {
            "mode": "static",
            "seed_offset": 101 + layer_index,
            "azimuth_range_deg": 0.0,
            "elevation_range_deg": 0.0,
            "distance_range_ratio": 0.0,
            "period_s": 42.0,
            "smoothing_ms": 1500,
        }
    return {
        "render_mode": "point_source_hrtf",
        "base_position": {
            "azimuth_deg": round(azimuth, 3),
            "elevation_deg": round(elevation, 3),
            "virtual_distance_m": round(distance, 3),
        },
        "visual_evidence": {
            "center_x": round(center_x, 4),
            "center_y": round(center_y, 4),
            "bbox_area": round(area, 6),
            "relative_depth": relative_depth,
            "depth_uncertainty": float(depth["uncertainty"]),
            "size_prior_used": False,
            "size_prior_version": None,
        },
        "source_width": round(clamp(math.sqrt(area), 0.05, 0.35), 3),
        "distance_gain_db": round(distance_gain, 3),
        "distance_lowpass_hz": distance_lowpass,
        "reverb_send": round(reverb_send, 3),
        "motion": motion,
    }


def build_mono_plan(
    record: dict[str, Any],
    seed: int,
    duration_s: float | None,
    settings: dict[str, Any],
    scene_profiles: dict[str, Any],
    assets: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    gate: dict[str, Any],
) -> dict[str, Any]:
    rng = random.Random(seed)
    ambient, ambient_source = build_ambient_layers(record, scene_profiles, assets, rng, mono=True)
    foreground = [
        build_foreground_layer(candidate, assets, float(record["global_vibe"]["brightness"]), True, settings, index)
        for index, candidate in enumerate(candidates)
    ]
    if gate["passed"]:
        fallback_result = "not_required"
        failure_reasons: list[dict[str, Any]] = []
    else:
        fallback_result = "failed"
        failure_reasons = gate["failure_reasons"]
    return {
        "schema_version": "2.0-mono",
        "plan_id": f"plan_{record['id']}_mono",
        "source_record_id": record["id"],
        "seed": seed,
        "duration_s": duration_s,
        "render": {
            "mode": "mono_center",
            "output_channels": 1,
            "spatialization": "disabled",
            "downmix_policy": "equal_power",
            "channel_interpretation": "speakers",
        },
        "fallback": {
            "from": "2.0-binaural",
            "policy_version": gate["policy_version"],
            "result": fallback_result,
            "uncertainty_threshold": gate["uncertainty_threshold"],
            "comparison": gate["comparison"],
            "max_region_spread": gate["max_region_spread"],
            "candidate_count": gate["candidate_count"],
            "evaluated_anchor_indices": gate["evaluated_anchor_indices"],
            "failure_reasons": failure_reasons,
        },
        "layers": {"ambient": ambient, "noise_bed": None, "foreground": foreground},
        "master": {
            "output_channels": 1,
            "gain_db": -2.0,
            "limiter_threshold_db": -1.0,
            "fade_in_ms": 2500,
            "fade_out_ms": 3000,
            "max_foreground_simultaneous": 1,
        },
        "decision_trace": {
            "primary_ambient_from": ambient_source,
            "foreground_from": [
                f"trigger_anchor:{item['anchor']['anchor_id']}:{item['source_anchor_index']}" for item in candidates
            ],
            "render_mode_from": "always_generate_mono_first",
            "mix_modifiers": mix_modifiers(record["global_vibe"]),
        },
    }


def build_binaural_plan(
    record: dict[str, Any],
    seed: int,
    duration_s: float | None,
    settings: dict[str, Any],
    scene_profiles: dict[str, Any],
    assets: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    gate: dict[str, Any],
) -> dict[str, Any]:
    if not gate["passed"]:
        raise ConversionError("空间门控未通过，不能生成双耳计划")
    rng = random.Random(seed)
    ambient, ambient_source = build_ambient_layers(record, scene_profiles, assets, rng, mono=False)
    foreground = [
        build_foreground_layer(candidate, assets, float(record["global_vibe"]["brightness"]), False, settings, index)
        for index, candidate in enumerate(candidates)
    ]
    return {
        "schema_version": "2.0-binaural",
        "plan_id": f"plan_{record['id']}_binaural",
        "source_record_id": record["id"],
        "seed": seed,
        "duration_s": duration_s,
        "render": {
            "mode": "binaural_hrtf",
            "output_channels": 2,
            "headphone_required": True,
            "listener_pose": {
                "position": [0.0, 0.0, 0.0],
                "forward": [0.0, 0.0, -1.0],
                "up": [0.0, 1.0, 0.0],
            },
            "coordinate_system": "right_handed_y_up_listener_relative",
            "hrtf_profile": "renderer_default_v1",
            "distance_model": "inverse",
            "reference_distance_m": 1.0,
            "max_distance_m": 15.0,
            "rolloff_factor": 0.55,
        },
        "quality_gate": {
            "result": "passed",
            "policy_version": gate["policy_version"],
            "uncertainty_threshold": gate["uncertainty_threshold"],
            "comparison": gate["comparison"],
            "max_region_spread": gate["max_region_spread"],
            "candidate_count": gate["candidate_count"],
            "evaluated_anchor_indices": gate["evaluated_anchor_indices"],
            "maximum_observed_uncertainty": gate["maximum_observed_uncertainty"],
            "fallback_plan_version": "2.0-mono",
        },
        "layers": {"ambient": ambient, "noise_bed": None, "foreground": foreground},
        "master": {
            "output_channels": 2,
            "gain_db": -2.0,
            "limiter_threshold_db": -1.0,
            "fade_in_ms": 2500,
            "fade_out_ms": 3000,
            "max_foreground_simultaneous": 1,
            "spatial_parameter_smoothing_ms": 800,
        },
        "decision_trace": {
            "primary_ambient_from": ambient_source,
            "foreground_from": [
                f"trigger_anchor:{item['anchor']['anchor_id']}:{item['source_anchor_index']}" for item in candidates
            ],
            "spatial_mode_from": f"all_spatial_candidates_passed:{gate['policy_version']}",
            "mix_modifiers": mix_modifiers(record["global_vibe"]),
        },
    }


def convert(
    input_path: Path,
    output_dir: Path,
    config_dir: Path,
    explicit_seed: int | None,
    duration_s: float | None,
) -> dict[str, Any]:
    settings, scene_profiles, manifest, visual_spec = load_mapping_config(config_dir)
    allowed_anchors, mapping_by_anchor = build_anchor_mapping(visual_spec)
    record = unwrap_record(load_json(input_path))
    validate_record(record, allowed_anchors)
    seed = stable_seed(record["id"], explicit_seed)
    assets = asset_index(manifest)
    candidates = collect_foreground_candidates(record, mapping_by_anchor, settings)
    gate = evaluate_spatial_gate(candidates, settings)
    mono = build_mono_plan(record, seed, duration_s, settings, scene_profiles, assets, candidates, gate)
    output_dir.mkdir(parents=True, exist_ok=True)
    mono_path = output_dir / f"{record['id']}.mono.playback-plan.json"
    write_json(mono_path, mono)
    report: dict[str, Any] = {
        "source_record_id": record["id"],
        "mono_plan": str(mono_path.resolve()),
        "spatial_gate_passed": gate["passed"],
        "binaural_plan": None,
        "spatial_gate": gate,
    }
    if gate["passed"]:
        binaural = build_binaural_plan(
            record, seed, duration_s, settings, scene_profiles, assets, candidates, gate
        )
        binaural_path = output_dir / f"{record['id']}.binaural.playback-plan.json"
        write_json(binaural_path, binaural)
        report["binaural_plan"] = str(binaural_path.resolve())
    report_path = output_dir / f"{record['id']}.conversion-report.json"
    write_json(report_path, report)
    report["conversion_report"] = str(report_path.resolve())
    return report


def parse_duration(value: str) -> float | None:
    if value.lower() in {"null", "none", "infinite"}:
        return None
    duration = float(value)
    if duration <= 0:
        raise argparse.ArgumentTypeError("duration必须大于0或使用null")
    return duration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将一条视觉层JSON转换为单声道及可选双耳播放计划")
    parser.add_argument("input", type=Path, help="视觉记录JSON；可以是裸记录或包含example_record的说明对象")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="输出目录")
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR, help="配置目录")
    parser.add_argument("--seed", type=int, default=None, help="显式随机种子；默认从记录id稳定生成")
    parser.add_argument("--duration", type=parse_duration, default=1800.0, help="播放秒数或null，默认1800")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = convert(
            input_path=args.input.resolve(),
            output_dir=args.output_dir.resolve(),
            config_dir=args.config_dir.resolve(),
            explicit_seed=args.seed,
            duration_s=args.duration,
        )
    except ConversionError as exc:
        print(f"转换失败: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
