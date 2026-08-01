"""
app.py —— ASMR-Creater 后端推理服务

提供 /infer 端点，接收图片上传，运行视觉层完整管线
（预处理 → YOLO 检测 → Scene Contract JSON），返回给前端 UI。

用法:
    python src/ui/app.py                # 默认端口 5000
    python src/ui/app.py --port 8080    # 自定义端口

前端接入: 将 src/ui/web/index.html 中 CONFIG.BACKEND 设为 true 即可。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

# 确保仓库根在 sys.path 中
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import numpy as np
from src.vision.preprocess import load_and_preprocess_image
from src.vision.yolo import YoloDetector
from src.vision.vlm_yolo_fusion import merge_structured_payload

# ── 全局检测器（启动时加载一次，所有请求复用） ──
_detector: YoloDetector | None = None


def get_detector() -> YoloDetector:
    """懒加载 YOLO 检测器（首次调用时下载模型）。"""
    global _detector
    if _detector is None:
        print("[app] Loading YOLO model (yolo11n.pt, CPU)...")
        _detector = YoloDetector(
            model_name="yolo11n.pt",
            device="cpu",
            conf_threshold=0.25,
            iou_threshold=0.45,
        )
        print("[app] YOLO model ready.")
    return _detector


def image_to_scene(image_bytes: bytes, filename: str = "upload.jpg") -> dict:
    """
    单张图片 → Scene Contract JSON 的完整推理管线。

    流程:
        1. 将 bytes 写入临时文件
        2. 预处理（Letterbox + VLM 缩放）
        3. YOLO 目标检测
        4. 组装 Scene Contract JSON

    Args:
        image_bytes: 上传图片的原始字节
        filename: 原始文件名（用于日志）

    Returns:
        符合 contracts/scene_contract.schema.json 的字典
    """
    # 1. 写入临时文件（OpenCV 需要文件路径读取）
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        # 2. 预处理
        preprocessed = load_and_preprocess_image(
            tmp_path,
            target_size_yolo=(640, 640),
            target_size_vlm=(224, 224),
        )
        if preprocessed is None:
            raise ValueError(f"无法预处理图片: {filename}")

        # 3. YOLO 检测
        detector = get_detector()
        yolo_results = detector.detect([preprocessed])

        # 4. 组装 Scene Contract
        #    单图 demo 模式无 VLM 数据，使用默认 global_vibe
        #    （前端会用自己的 Canvas 分析结果覆盖）
        default_vlm = {
            "image": filename,
            "path": tmp_path,
            "global_vibe": {
                "scene_type": "unknown",
                "mood": "calm",
                "brightness": 0.5,
                "warmth": "neutral",
                "base_noise": "pink",
                "time_of_day": "afternoon",
            },
            "suggested_entities": [],
        }

        scene = merge_structured_payload(
            yolo_results[0] if yolo_results else None,
            default_vlm,
        )

        # 5. 对于 demo 模式，将 YOLO 检测到的所有实体也加入 entities
        #    （因为无 VLM suggested_entities 时 entities 为空）
        if yolo_results and not yolo_results[0].get("error"):
            yolo_dets = yolo_results[0].get("detections", [])
            # 去重：只加尚未在 entities 中的 detection
            existing_names = {e["name"] for e in scene["entities"]}
            for det in yolo_dets:
                if det.name not in existing_names:
                    scene["entities"].append(det.to_entity_dict())
                    existing_names.add(det.name)

        return scene

    finally:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════
# HTTP Server（使用标准库，零额外依赖）
# ═══════════════════════════════════════════════════════════════

from http.server import HTTPServer, BaseHTTPRequestHandler


class InferHandler(BaseHTTPRequestHandler):
    """处理 /infer POST 请求，返回 Scene Contract JSON。"""

    def do_GET(self):
        """GET / → 返回 UI 页面，其他路径返回静态文件。"""
        if self.path == "/" or self.path == "/index.html":
            html_path = REPO_ROOT / "src" / "ui" / "web" / "index.html"
            if html_path.exists():
                content = html_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
        # 其他 GET 请求：返回简单提示
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"ASMR-Creater Backend. POST /infer to upload an image.")

    def do_OPTIONS(self):
        """CORS 预检响应。"""
        self._cors_headers()
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        if self.path != "/infer":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"not found"}')
            return

        try:
            # 读取 multipart/form-data
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._error(400, "需要 multipart/form-data 格式上传图片")
                return

            # 解析 boundary 和 body
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))

            # 简单 multipart 解析（不引入第三方库）
            image_bytes = _parse_multipart(body, content_type)
            if image_bytes is None:
                self._error(400, "无法从请求中提取图片，请使用 file 字段上传")
                return

            # 推理
            scene = image_to_scene(image_bytes)

            # 返回 JSON
            resp = json.dumps(scene, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self._cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        except Exception as e:
            traceback.print_exc()
            self._error(500, str(e))

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _error(self, code: int, msg: str):
        resp = json.dumps({"error": msg}, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def log_message(self, format, *args):
        """简洁日志。"""
        print(f"[app] {args[0]}")


def _parse_multipart(body: bytes, content_type: str) -> bytes | None:
    """
    简单 multipart/form-data 解析，提取第一个文件的内容。
    不引入第三方库，仅处理基本的文件上传场景。
    """
    # 提取 boundary
    import re
    match = re.search(rb'boundary=([^;]+)', content_type.encode() if isinstance(content_type, str) else content_type)
    if not match:
        # Try string match
        match = re.search(r'boundary=([^;]+)', content_type)
        if not match:
            return None
        boundary = b'--' + match.group(1).strip().encode()
    else:
        boundary = b'--' + match.group(1).strip()

    # 按 boundary 分割
    parts = body.split(boundary)
    for part in parts:
        if b'Content-Disposition' not in part:
            continue
        if b'filename=' not in part:
            continue

        # 找到 header 结束位置（双 \r\n\r\n）
        header_end = part.find(b'\r\n\r\n')
        if header_end == -1:
            continue

        # 提取文件内容（去掉尾部 \r\n 和 --）
        content = part[header_end + 4:]
        # 去掉尾部的 \r\n
        content = content.rstrip(b'\r\n')
        if content:
            return content

    return None


def main():
    parser = argparse.ArgumentParser(description="ASMR-Creater 后端推理服务")
    parser.add_argument("--port", type=int, default=5000, help="服务端口 (默认 5000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="监听地址 (默认 127.0.0.1)")
    args = parser.parse_args()

    # 预热模型
    get_detector()

    server = HTTPServer((args.host, args.port), InferHandler)
    print(f"\n{'=' * 50}")
    print(f"  ASMR-Creater 后端推理服务已启动")
    print(f"  地址: http://{args.host}:{args.port}")
    print(f"  端点: POST /infer  (multipart/form-data, file 字段)")
    print(f"  前端: 将 CONFIG.BACKEND 设为 true 即可接入")
    print(f"{'=' * 50}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[app] 服务已停止")
        server.server_close()


if __name__ == "__main__":
    main()
