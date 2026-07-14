# -*- coding: utf-8 -*-
"""批量推理：全部图片 → global_vibe → 输出 JSONL。

用法:
    python -m src.vision.batch_vibe
    python -m src.vision.batch_vibe --resume   # 断点续传
    python -m src.vision.batch_vibe --limit 50 # 只跑前 50 张测试
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

# 让 Python 能找到 src/
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.vision.vibe_vlm import get_global_vibe

logger = logging.getLogger(__name__)

# ── 配置 ────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT.parent / "data"       # D:\Projects\nlp\data
OUTPUT_DIR = REPO_ROOT / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "global_vibe_results.jsonl"
FAILED_FILE = OUTPUT_DIR / "global_vibe_failed.jsonl"
CHECKPOINT_EVERY = 50  # 每 N 张存盘一次


def find_images(data_dir: Path) -> list[Path]:
    """收集所有图片路径，按文件名排序。"""
    images = []
    for sub in ["Train", "Val"]:
        folder = data_dir / sub
        if folder.exists():
            images.extend(sorted(folder.glob("*.jpg")))
    return images


def load_completed(output_path: Path) -> set[str]:
    """读取已有结果，返回已完成的图片名集合（用于断点续传）。"""
    if not output_path.exists():
        return set()
    completed = set()
    with output_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    record = json.loads(line)
                    if "image" in record:
                        completed.add(record["image"])
                except json.JSONDecodeError:
                    continue
    return completed


def append_result(path: Path, record: dict) -> None:
    """追加一行 JSON 到文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_batch(
    images: list[Path],
    output_path: Path,
    failed_path: Path,
    limit: Optional[int] = None,
    resume: bool = False,
) -> None:
    """主循环：逐张处理，断点续传，异常保护。"""
    # 断点续传：跳过已完成的
    completed = load_completed(output_path) if resume else set()
    pending = [img for img in images if img.name not in completed]

    if limit:
        pending = pending[:limit]

    if completed:
        print(f"断点续传: {len(completed)} 张已完成，剩余 {len(pending)} 张")
    else:
        print(f"共 {len(pending)} 张图片待处理")

    total = len(pending)
    ok = 0
    fail = 0
    start_time = time.time()

    for i, img in enumerate(pending):
        elapsed = time.time() - start_time
        eta = (elapsed / max(i, 1)) * (total - i) if i > 0 else 0

        try:
            vibe = get_global_vibe(str(img))
            suggested = vibe.pop("suggested_entities", [])
            record = {
                "image": img.name,
                "path": str(img.relative_to(REPO_ROOT.parent)),
                "global_vibe": vibe,
                "suggested_entities": suggested,
            }
            append_result(output_path, record)
            ok += 1
            status = "OK"
        except Exception as e:
            fail_record = {
                "image": img.name,
                "path": str(img.relative_to(REPO_ROOT.parent)),
                "error": str(e),
            }
            append_result(failed_path, fail_record)
            fail += 1
            status = f"FAIL: {e}"

        # 进度打印
        if (i + 1) % 10 == 0 or status.startswith("FAIL"):
            pct = (i + 1) / total * 100
            eta_str = f"{eta/60:.0f}min" if eta > 60 else f"{eta:.0f}s"
            print(f"[{i+1}/{total}] {pct:.0f}%  OK={ok} FAIL={fail}  ETA:{eta_str}  {img.name} {status}")

        # 每 N 张存盘提示
        if (i + 1) % CHECKPOINT_EVERY == 0:
            print(f"  --- checkpoint saved ({ok+min(fail,0)} records) ---")

    # 最终统计
    total_time = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"完成！总计 {total} 张")
    print(f"  成功: {ok}  ({ok/total*100:.1f}%)" if total > 0 else "  成功: 0")
    print(f"  失败: {fail} ({fail/total*100:.1f}%)" if total > 0 else "  失败: 0")
    print(f"  耗时: {total_time/60:.1f} 分钟 ({total_time/total:.1f}s/张)" if total > 0 else "  耗时: 0")
    print(f"  成功结果: {output_path}")
    if fail > 0:
        print(f"  失败记录: {failed_path}")
        print(f"  重试: python -m src.vision.batch_vibe --retry-failed")


# ── 入口 ────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="批量 VLM 氛围推理")
    parser.add_argument("--resume", action="store_true", help="断点续传，跳过已处理的图片")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 张（测试用）")
    parser.add_argument("--retry-failed", action="store_true", help="重试之前失败的图片")
    args = parser.parse_args()

    images = find_images(DATA_ROOT)
    if not images:
        print(f"未找到图片！请确认数据集路径: {DATA_ROOT}")
        sys.exit(1)

    print(f"找到 {len(images)} 张图片 (Train + Val)")

    if args.retry_failed:
        if not FAILED_FILE.exists():
            print("没有失败记录文件。")
            sys.exit(0)
        # 从失败记录中提取路径
        with FAILED_FILE.open(encoding="utf-8") as f:
            failed_paths = [REPO_ROOT.parent / json.loads(line)["path"] for line in f if line.strip()]
        # 清空旧的失败文件
        FAILED_FILE.write_text("", encoding="utf-8")
        run_batch(failed_paths, OUTPUT_FILE, FAILED_FILE, resume=False)
    else:
        run_batch(images, OUTPUT_FILE, FAILED_FILE, limit=args.limit, resume=args.resume)