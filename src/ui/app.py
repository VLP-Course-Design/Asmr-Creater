# -*- coding: utf-8 -*-
"""ASMR Creater 后端 —— 同时托管 UI 页面 + /infer 接口。

/infer 完整管线:
    1. VLM 氛围分析 (vision.vibe_vlm.get_global_vibe) → global_vibe
    2. YOLO 目标检测 (vision.yolo.YoloDetector)         → Detection[]
    3. 视觉记录 v2.3 (vision.visual_record)              → trigger_anchors + bbox_norm
       (正式契约见 contracts/scene_contract.schema.json；v1.0 仅由
        vision.vlm_yolo_fusion 提供离线批处理/旧样例兼容)

另外还托管:
    - /sounds/<path>       素材库静态文件(wav、trigger_map.json、桥接表)
    - /sounds/manifest     现场扫描 triggers/ambient 各文件夹下的真实 wav 清单
    - /api/anchor_sound_map 87 视觉锚点 → 66 sound_id 的强度映射(供前端挑素材)

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

from common.contract import validate_visual_record_v23, SchemaValidationError
from vision.preprocess import load_and_preprocess_image
from vision.visual_record import build_visual_record_v23
from audio.playback_converter import (
    load_mapping_config, build_anchor_mapping, build_plans, ConversionError,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=str(REPO / "src" / "ui" / "web"), static_url_path="")
SCHEMA_VERSION = "2.3"

SOUNDS_DIR = REPO / "sounds"
PLAYBACK_CONFIG_DIR = REPO / "configs" / "playback"

# ── YOLO 检测器(启动时加载一次，所有请求复用） ──────────
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

    这里的默认值保留历史输入形状（scene_type="unknown" 等）；
    build_visual_record_v23() 内部的 normalize_scene_type/_normalize_mood 等函数
    会把它们归一化到 v2.3 受控词表（如 unknown → none），不需要在这里改。
    """
    try:
        from vision.vibe_vlm import get_global_vibe
        vibe = get_global_vibe(image_path)
        suggested = vibe.pop("suggested_entities", [])
        logger.info("VLM: scene=%s mood=%s entities=%d",
                    vibe.get("scene_type"), vibe.get("mood"), len(suggested))
        return {
            "global_vibe": vibe,
            "suggested_entities": suggested,
            "_vibe_source": "vlm",
        }
    except Exception as e:
        logger.warning("VLM unavailable (%s), using default ambiance", e)
        return {
            "global_vibe": {
                "scene_type": "unknown", "mood": "calm", "brightness": 0.5,
                "warmth": "neutral", "base_noise": "pink", "time_of_day": "afternoon",
            },
            "suggested_entities": [],
            "_vibe_source": "default_fallback",
            "_vibe_error": str(e),
        }


# ── 锚点 → 声音语义映射（懒加载并缓存） ──────────────────
_anchor_sound_map = None
_asset_urls = None
_STRENGTH_ORDER = {"strong": 0, "medium": 1, "weak": 2, "cautious": 3}


def _get_asset_urls() -> dict:
    """asset_id → {url, makeup_db}。

    播放计划里只有 asset_id,播放端靠这张表取文件。makeup_db 是把素材抬到统一
    响度基准所需的补偿(见 scripts/gen_audio_manifest.py):素材库是批量下载的
    原始文件、没做响度归一化,而计划里的 gain_db 是按「素材已整理到 -24 LUFS」
    定的,不补偿的话最终信号只有约 -63 dBFS,基本听不见。
    """
    global _asset_urls
    if _asset_urls is None:
        _, _, manifest, _ = load_mapping_config(PLAYBACK_CONFIG_DIR)
        _asset_urls = {
            a["asset_id"]: {
                "url": a["path"],
                "makeup_db": (a.get("loudness") or {}).get("makeup_db", 0.0),
            }
            for a in manifest.get("assets", [])
        }
    return _asset_urls


def _get_anchor_sound_map() -> dict:
    """{anchor_id: [{sound_id, strength}, ...]}，按 strength 降序。

    复用 audio.playback_converter 已经写好、测试过的解析逻辑（load_mapping_config /
    build_anchor_mapping），不重新解析 recommended_structured_record_example.json。
    """
    global _anchor_sound_map
    if _anchor_sound_map is None:
        _, _, _, spec = load_mapping_config(PLAYBACK_CONFIG_DIR)
        _, by_anchor = build_anchor_mapping(spec)
        compact = {}
        for anchor_id, candidates in by_anchor.items():
            ranked = sorted(candidates, key=lambda c: _STRENGTH_ORDER.get(c["strength"], 9))
            compact[anchor_id] = [
                {"sound_id": c["sound_id"], "strength": c["strength"]} for c in ranked
            ]
        _anchor_sound_map = compact
    return _anchor_sound_map


# ── 路由 ──────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/sounds/<path:filename>")
def sounds_static(filename):
    """素材库静态文件：wav 本体、trigger_map.json、v23_sound_id_bridge.json。"""
    return send_from_directory(SOUNDS_DIR, filename)


@app.route("/sounds/manifest")
def sounds_manifest():
    """现场扫描 sounds/{ambient,triggers}/*/ 下的真实 wav 文件。

    不写死文件名列表：素材线以后往某个文件夹里多放变体，前端下次请求就能感知到，
    不需要改代码。
    """
    def _scan(kind: str) -> dict:
        base = SOUNDS_DIR / kind
        result = {}
        if not base.is_dir():
            return result
        for folder in sorted(p for p in base.iterdir() if p.is_dir()):
            files = sorted(f.name for f in folder.glob("*.wav"))
            if files:
                result[folder.name] = [
                    f"/sounds/{kind}/{folder.name}/{name}" for name in files
                ]
        return result

    return jsonify({"triggers": _scan("triggers"), "ambient": _scan("ambient")})


@app.route("/api/anchor_sound_map")
def anchor_sound_map():
    return jsonify(_get_anchor_sound_map())


@app.route("/api/asset_urls")
def asset_urls():
    return jsonify(_get_asset_urls())


@app.route("/api/plan", methods=["POST"])
def api_plan():
    """一条视觉记录 v2.3 → 播放计划。

    /infer 内部已经会产出计划;这个端点给「不经过图像推理」的调用方用
    (例如页面上的预设样例场景),保证它们走的也是同一套音频决策代码。
    """
    record = request.get_json(silent=True)
    if not isinstance(record, dict):
        return jsonify({"error": "请求体必须是一条视觉记录 JSON"}), 400
    try:
        validate_visual_record_v23(record)
    except SchemaValidationError as e:
        return jsonify({"error": f"视觉记录不符合 v2.3 契约: {e}"}), 422
    try:
        mono, binaural, gate = build_plans(record, PLAYBACK_CONFIG_DIR, duration_s=None)
    except ConversionError as e:
        return jsonify({"error": f"生成播放计划失败: {e}"}), 422
    return jsonify({
        "record": record,
        "plan": binaural or mono,
        "spatial_gate_passed": gate["passed"],
        "asset_urls": _get_asset_urls(),
    })


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
        VLM 氛围 + YOLO 实体检测 → 视觉记录 v2.3(trigger_anchors + bbox_norm)。
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
        vibe_source = vlm_data.pop("_vibe_source", "unknown")
        vibe_error = vlm_data.pop("_vibe_error", None)

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

        # ── 3. 视觉记录 v2.3 ──
        # build_visual_record_v23 只在 yolo_result 没有 error 时才读宽高；这里补一次
        # 浅拷贝清空 error 字段，避免"预处理其实成功、只是 YOLO 推理本身出错"时
        # 白白丢掉本来就拿到的图像尺寸（此规整只在 app.py 做，不改 vision/visual_record.py）。
        yolo_input = yolo_results[0] if yolo_results else None
        if yolo_input and yolo_input.get("error"):
            yolo_input = {**yolo_input, "error": None}

        record = build_visual_record_v23(
            yolo_input,
            {"image": f.filename, "path": str(tmp_path), **vlm_data},
        )
        if record is None:
            return jsonify({"error": "图像预处理失败，无法生成视觉记录"}), 422

        # ── 4. 校验（严格拒绝，不只 warning） ──
        try:
            validate_visual_record_v23(record)
        except SchemaValidationError as e:
            logger.warning("v2.3 contract validation failed: %s", e)
            return jsonify({"error": f"视觉记录不符合 v2.3 契约: {e}"}), 422

        # ── 5. 音频决策:直接调用 playback_converter,不在前端另写一套 ──
        # 声音选型、增益、触发间隔/概率、环境床全部由这里产出;前端只负责执行。
        try:
            mono, binaural, gate = build_plans(record, PLAYBACK_CONFIG_DIR, duration_s=None)
        except ConversionError as e:
            logger.warning("playback plan failed: %s", e)
            return jsonify({"error": f"生成播放计划失败: {e}"}), 422

        plan = binaural or mono
        logger.info(
            "OK: scene=%s anchors=%d -> plan=%s ambient=%s foreground=%d",
            record["global_vibe"].get("scene_type"),
            len(record["trigger_anchors"]),
            plan["schema_version"],
            (plan["layers"]["ambient"][0]["sound_id"] if plan["layers"]["ambient"] else "无"),
            len(plan["layers"]["foreground"]),
        )
        return jsonify({
            "record": record,
            "plan": plan,
            "spatial_gate_passed": gate["passed"],
            "asset_urls": _get_asset_urls(),
            "diagnostics": {
                "vibe_source": vibe_source,
                "vibe_error": vibe_error,
            },
        })

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

    print(f"ASMR Creater backend | VLM: {os.environ.get('VLM_MODEL', '?')} | schema: {SCHEMA_VERSION}")
    print(f"  http://{args.host}:{args.port}")
    print(f"  /                     → UI 页面")
    print(f"  /infer                → POST image → 视觉记录 v2.3 JSON")
    print(f"  /sounds/<path>        → 素材库静态文件")
    print(f"  /sounds/manifest      → 各素材文件夹真实 wav 清单")
    print(f"  /api/anchor_sound_map → 87 锚点 → 66 sound_id 映射")
    print(f"  /health               → 服务状态")
    app.run(host=args.host, port=args.port, debug=False)
