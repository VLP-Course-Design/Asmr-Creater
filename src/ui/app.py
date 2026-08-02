# -*- coding: utf-8 -*-
"""ASMR Creater 后端 —— 同时托管 UI 页面 + /infer 接口。

/infer 完整管线:
    1. VLM 氛围分析 (vision.vibe_vlm.get_global_vibe) → global_vibe
    2. YOLO 目标检测 (vision.yolo.YoloDetector)         → Detection[]
    3. 结构化融合 (vision.vlm_yolo_fusion)               → Scene Contract JSON

启动:
    python src/ui/app.py
    python src/ui/app.py --port 8080
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory

# ── 路径与配置 ────────────────────────────────────────────
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("VLM_MODEL", "qwen2.5-vl:7b")

from common.contract import validate_scene
from vision.preprocess import load_and_preprocess_image
from vision.vlm_yolo_fusion import merge_structured_payload

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=str(REPO / "src" / "ui" / "web"), static_url_path="")
SCHEMA_VERSION = "1.0"

# ── YOLO 检测器（启动时加载一次，所有请求复用） ──────────
_yolo_detector = None


def _get_yolo():
    """懒加载 YOLO 检测器（首次调用时自动下载 yolo11n.pt）。"""
    global _yolo_detector
    if _yolo_detector is None:
        from vision.yolo import YoloDetector
        logger.info("Loading YOLO model (yolo11n.pt, CPU)...")
        _yolo_detector = YoloDetector(
            model_name="yolo11n.pt",
            device="cpu",
            conf_threshold=0.25,
            iou_threshold=0.45,
        )
        logger.info("YOLO model ready.")
    return _yolo_detector


# ── VLM 氛围分析（可选，Ollama 不可用时回退默认值） ──────

def _vlm_or_default(image_path: Path, filename: str) -> dict:
    """
    尝试调用 VLM 获取 global_vibe + suggested_entities。
    若 VLM 不可用则返回中性默认值。
    """
    try:
        from vision.vibe_vlm import get_global_vibe
        vibe = get_global_vibe(image_path)
        suggested = vibe.pop("suggested_entities", [])
        logger.info("VLM: scene=%s mood=%s entities=%d",
                    vibe.get("scene_type"), vibe.get("mood"), len(suggested))
        return {"global_vibe": vibe, "suggested_entities": suggested}
    except Exception as e:
        logger.warning("VLM unavailable (%s), using default ambiance", e)
        return {
            "global_vibe": {
                "scene_type": "unknown", "mood": "calm", "brightness": 0.5,
                "warmth": "neutral", "base_noise": "pink", "time_of_day": "afternoon",
            },
            "suggested_entities": [],
        }


# ── 路由 ──────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/health")
def health():
    yolo_loaded = _yolo_detector is not None
    return jsonify({
        "status": "ok",
        "vlm_model": os.environ.get("VLM_MODEL", "?"),
        "yolo_loaded": yolo_loaded,
    })


@app.route("/infer", methods=["POST"])
def infer():
    """
    完整视觉推理管线:
        VLM 氛围 + YOLO 实体检测 → 结构化融合 → Scene Contract JSON。
    """
    if "image" not in request.files:
        return jsonify({"error": "missing image field"}), 400

    f = request.files["image"]
    if f.filename == "":
        return jsonify({"error": "empty filename"}), 400

    suffix = Path(f.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = Path(tmp.name)

    try:
        # ── 1. VLM 氛围分析 ──
        vlm_data = _vlm_or_default(tmp_path, f.filename)

        # ── 2. YOLO 实体检测 ──
        preprocessed = load_and_preprocess_image(
            str(tmp_path),
            target_size_yolo=(640, 640),
            target_size_vlm=(224, 224),
        )
        yolo_results = []
        if preprocessed is not None:
            detector = _get_yolo()
            yolo_results = detector.detect([preprocessed])

        # ── 3. 结构化融合 ──
        scene = merge_structured_payload(
            yolo_results[0] if yolo_results else None,
            {
                "image": f.filename,
                "path": str(tmp_path),
                **vlm_data,
            },
        )

        # ── 4. Demo 模式兜底：VLM 未 suggest 时，YOLO 检测结果直接入 entities ──
        if yolo_results and not yolo_results[0].get("error"):
            yolo_dets = yolo_results[0].get("detections", [])
            existing_names = {e["name"] for e in scene["entities"]}
            for det in yolo_dets:
                if det.name not in existing_names:
                    scene["entities"].append(det.to_entity_dict())
                    existing_names.add(det.name)

        # ── 5. 校验 ──
        try:
            validate_scene(scene)
        except Exception as e:
            logger.warning("Contract validation: %s", e)

        logger.info(
            "OK: scene=%s entities=%d (YOLO=%d VLM=%d)",
            scene["global_vibe"].get("scene_type"),
            len(scene["entities"]),
            sum(1 for e in scene["entities"] if e.get("source") == "yolo"),
            sum(1 for e in scene["entities"] if e.get("source") == "vlm"),
        )
        return jsonify(scene)

    except Exception as e:
        logger.exception("Inference failed")
        return jsonify({"error": str(e)}), 500

    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ASMR Creater 后端服务")
    parser.add_argument("--port", type=int, default=5000, help="服务端口 (默认 5000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
    args = parser.parse_args()

    print(f"ASMR Creater backend | VLM: {os.environ.get('VLM_MODEL', '?')}")
    print(f"  http://{args.host}:{args.port}")
    print(f"  /      → UI 页面")
    print(f"  /infer → POST image → Scene Contract JSON")
    print(f"  /health → 服务状态")
    app.run(host=args.host, port=args.port, debug=False)
