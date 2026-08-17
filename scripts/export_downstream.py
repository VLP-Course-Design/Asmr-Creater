# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""导出第二人给下游的文件，并做播放计划 / 视觉记录契约校验。

有图片目录时：读 handover 或旧 VLM JSONL，跑预处理+YOLO，写出全量 JSONL。
无图片时：写出已校验的格式样例（供音频先对接），并提示全量命令。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from common.contract import validate_visual_record_v23
from vision.detector import Detection
from vision.preprocess import get_image_files
from vision.vlm_yolo_fusion import merge_structured_payload, process_batch
from vision.visual_record import process_batch_v23
from audio.playback_converter import build_anchor_mapping, load_mapping_config, validate_record

OUT_DIR = REPO / "outputs" / "downstream"


def _validate_v23_list(records: list) -> None:
    _, _, _, spec = load_mapping_config(REPO / "configs" / "playback")
    allowed, _ = build_anchor_mapping(spec)
    for rec in records:
        validate_visual_record_v23(rec)
        validate_record(rec, allowed)
        vibe = rec["global_vibe"]
        assert "base_noise" not in vibe
        for anchor in rec["trigger_anchors"]:
            box = anchor["bbox_norm"]
            assert box["x_min"] < box["x_max"] and box["y_min"] < box["y_max"]
            assert "depth_hint" not in anchor


def _write_jsonl(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def export_samples() -> None:
    """无数据集时：3 条带框样例，格式与全量文件相同。"""
    yolo = {
        "image_path": "img_dataset/Train/1014.jpg",
        "original_width": 800,
        "original_height": 600,
        "brightness": 0.41,
        "error": None,
        "detections": [
            Detection(name="bird", x=0.20, depth="far", conf=0.88,
                      bbox=[0.10, 0.10, 0.30, 0.25]),
            Detection(name="cat", x=0.55, depth="near", conf=0.93,
                      bbox=[0.40, 0.30, 0.70, 0.90]),
        ],
    }
    handover = {
        "schema_version": "2.3",
        "id": "1014",
        "image": {"path": "data/Train/1014.jpg", "width": 800, "height": 600},
        "global_vibe": {
            "scene_type": "forest",
            "secondary_scene_types": ["stream"],
            "scene_group": "forest_vegetation",
            "mood": "calm",
            "warmth": "cool",
            "time_of_day": "afternoon",
            "brightness": 0.99,
        },
        "trigger_anchors": [
            {"anchor_id": "visible_bird", "confidence": 0.5, "source": "vlm_legacy"},
            {"anchor_id": "relaxed_or_sleeping_cat", "confidence": 0.5,
             "source": "vlm_legacy", "state_note": "sleeping"},
        ],
    }
    v1 = process_batch([yolo], [handover], [])
    v23 = process_batch_v23([yolo], [handover])
    _validate_v23_list(v23)

    _write_jsonl(OUT_DIR / "final_structured_results.sample.jsonl", v1)
    _write_jsonl(OUT_DIR / "visual_analysis.sample.jsonl", v23)
    print(f"样例已写入 {OUT_DIR}")
    print(f"  UI  v1.0 : {OUT_DIR / 'final_structured_results.sample.jsonl'}")
    print(f"  音频 v2.3: {OUT_DIR / 'visual_analysis.sample.jsonl'}")


def export_full(image_dir: Path, vlm_jsonl: Path) -> None:
    from vision.yolo import YoloDetector
    from vision.vlm_yolo_fusion import detect_images_chunked, load_jsonl

    vlm = load_jsonl(str(vlm_jsonl))
    paths = get_image_files(str(image_dir), recursive=True)
    if not paths:
        raise SystemExit(f"图片目录为空: {image_dir}")
    detector = YoloDetector(model_name="yolo11n.pt", device="cpu")
    yolo_results = detect_images_chunked(paths, detector, chunk_size=32)
    v1 = process_batch(yolo_results, vlm, [])
    v23 = process_batch_v23(yolo_results, vlm)
    _validate_v23_list(v23)
    _write_jsonl(OUT_DIR / "final_structured_results.jsonl", v1)
    _write_jsonl(OUT_DIR / "visual_analysis.jsonl", v23)
    print(f"全量已写入 {OUT_DIR}  v1.0={len(v1)}  v2.3={len(v23)}")


def main() -> None:
    image_dir = REPO / "img_dataset"
    if not image_dir.exists():
        image_dir = REPO / "data"
    vlm = REPO / "handover_v23" / "global_vibe_v23_aligned.jsonl"
    if image_dir.exists() and get_image_files(str(image_dir)):
        if not vlm.exists():
            raise SystemExit(f"找不到 VLM JSONL: {vlm}")
        export_full(image_dir, vlm)
    else:
        print("未找到 img_dataset/ 或 data/ 下的图片，先导出已校验样例。")
        print("全量命令（有图之后）:")
        print(
            "  python -m src.vision.vlm_yolo_fusion "
            "--image_dir ./img_dataset/Train "
            "--vlm_success ./handover_v23/global_vibe_v23_aligned.jsonl "
            "--output ./outputs/downstream/final_structured_results.jsonl "
            "--v23_output ./outputs/downstream/visual_analysis.jsonl"
        )
        export_samples()


if __name__ == "__main__":
    main()
