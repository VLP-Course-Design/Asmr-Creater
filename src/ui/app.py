# -*- coding: utf-8 -*-
"""ASMR Creater 后端 —— 同时托管 UI 页面 + /infer 接口。"""

from __future__ import annotations
import json, logging, os, sys, tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("VLM_MODEL", "qwen2.5-vl:7b")

from common.contract import validate_scene
from vision.vibe_vlm import get_global_vibe

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=str(REPO / "src" / "ui" / "web"), static_url_path="")
SCHEMA_VERSION = "1.0"

def _entities_from_suggested(suggested: list) -> list[dict]:
    entities = []
    n = len(suggested)
    for i, item in enumerate(suggested):
        if not isinstance(item, dict): continue
        name = item.get("name", "")
        if not name: continue
        entities.append({"name": name, "state": item.get("state", ""),
            "x": (i + 0.5) / max(n, 1), "depth": "mid", "conf": 0.6, "source": "vlm"})
    return entities

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/infer", methods=["POST"])
def infer():
    if "image" not in request.files:
        return jsonify({"error": "missing image field"}), 400
    f = request.files["image"]
    if f.filename == "": return jsonify({"error": "empty filename"}), 400
    suffix = Path(f.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = Path(tmp.name)
    try:
        logger.info("Analyzing: %s", f.filename)
        vibe = get_global_vibe(tmp_path)
        suggested = vibe.pop("suggested_entities", [])
        entities = _entities_from_suggested(suggested)
        scene = {"schema_version": SCHEMA_VERSION,
            "image": {"id": Path(f.filename).stem, "path": f.filename},
            "global_vibe": vibe, "entities": entities}
        try: validate_scene(scene)
        except Exception as e: logger.warning("Contract: %s", e)
        logger.info("OK: scene=%s mood=%s entities=%d",
                    vibe.get("scene_type"), vibe.get("mood"), len(entities))
        return jsonify(scene)
    except Exception as e:
        logger.exception("Inference failed")
        return jsonify({"error": str(e)}), 500
    finally:
        try: tmp_path.unlink()
        except Exception: pass

@app.route("/health")
def health():
    return jsonify({"status": "ok", "model": os.environ.get("VLM_MODEL", "?")})

if __name__ == "__main__":
    print(f"ASMR Creater backend | Model: {os.environ.get('VLM_MODEL', '?')}")
    print("http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
