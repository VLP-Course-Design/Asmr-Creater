# -*- coding: utf-8 -*-
"""把旧 global_vibe_results.jsonl 对齐到音频层「视觉记录规范 2.3」。

A(环境层): scene_type 归一化到 contracts/scene_type_vocabulary.json(424 值，none/other_* 兜底)，
           scene_group 由词表查表生成；brightness 由程序从图片计算(规范要求，不用 VLM 估计)。
B(实体层): suggested_entities 收敛到 contracts/anchor_dictionary.json 的 87 个锚点 id
           (旧自由词经保守映射，source=vlm_legacy，无 bbox——bbox/depth 需新检测管线产出)。

用法:
    python scripts/normalize_global_vibe.py
    python scripts/normalize_global_vibe.py --input outputs/global_vibe_results.jsonl --output outputs/global_vibe_v23_aligned.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

# 让 Python 能找到 src/
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.vision.vibe_vlm import (
    ANCHOR_IDS,
    SCENE_TYPES,
    filter_anchor_entities,
    normalize_scene_type,
    normalize_secondary_scene_types,
    scene_to_group,
)


def compute_brightness(image_path: Path) -> float:
    """程序计算亮度：灰度均值/255（0~1）。公式待与音频层对齐。"""
    img = Image.open(image_path)
    img.draft("L", (64, 64))  # JPEG 低分辨率解码，加快批量处理
    img = img.convert("L")
    img.thumbnail((64, 64))  # thumbnail 原地修改并返回 None，勿赋值
    px = list(img.getdata())
    return sum(px) / (len(px) * 255.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="旧 VLM 结果对齐到视觉记录规范 2.3")
    parser.add_argument("--input", default=str(REPO_ROOT / "outputs" / "global_vibe_results.jsonl"))
    parser.add_argument("--output", default=str(REPO_ROOT / "outputs" / "global_vibe_v23_aligned.jsonl"))
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    if not in_path.exists():
        print(f"输入文件不存在: {in_path}")
        sys.exit(1)

    scene_counter: Counter = Counter()
    group_counter: Counter = Counter()
    anchor_counter: Counter = Counter()
    n_total = 0
    n_img_missing = 0
    records = []

    with in_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            n_total += 1

            gv_old = rec.get("global_vibe", {})
            scene_type = normalize_scene_type(gv_old.get("scene_type"))
            scene_counter[scene_type] += 1
            group = scene_to_group(scene_type)
            group_counter[group] += 1

            img_path = Path(str(rec.get("path", "")))
            width = height = 0
            brightness = 0.5
            full_img = REPO_ROOT.parent / img_path
            if full_img.exists():
                try:
                    with Image.open(full_img) as im:
                        width, height = im.size
                    brightness = compute_brightness(full_img)
                except Exception:
                    n_img_missing += 1
            else:
                n_img_missing += 1

            anchors = filter_anchor_entities(rec.get("suggested_entities", []))
            trigger_anchors = []
            for a in anchors:
                aid = a["name"]
                anchor_counter[aid] += 1
                item = {
                    "anchor_id": aid,
                    "confidence": 0.5,
                    "source": a.get("source", "vlm_legacy"),
                }
                # 旧数据无 bbox/depth_hint：需新检测管线产出（见 docs/VISION_V23_GAP.md）
                if a.get("state"):
                    item["state_note"] = a["state"]
                trigger_anchors.append(item)

            record = {
                "schema_version": "2.3",
                "id": str(rec.get("image", "")).rsplit(".", 1)[0],
                "image": {
                    "path": str(rec.get("path", "")),
                    "width": width,
                    "height": height,
                },
                "global_vibe": {
                    "scene_type": scene_type,
                    "secondary_scene_types": normalize_secondary_scene_types(gv_old.get("secondary_scene_types", []), scene_type),
                    "scene_group": group,
                    "mood": gv_old.get("mood"),
                    "warmth": gv_old.get("warmth"),
                    "time_of_day": gv_old.get("time_of_day"),
                    "brightness": round(brightness, 3),
                },
                "trigger_anchors": trigger_anchors,
            }
            records.append(record)

    # 硬校验：scene_type 必须在 424 词表内，锚点必须在 87 锚点词典内
    bad_scene = {r["global_vibe"]["scene_type"] for r in records} - SCENE_TYPES
    bad_anchor = {a["anchor_id"] for r in records for a in r["trigger_anchors"]} - ANCHOR_IDS
    if bad_scene or bad_anchor:
        print(f"校验未通过: 越界场景 {bad_scene}，越界锚点 {bad_anchor}")
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"总记录数: {n_total} | 图片缺失/读取失败: {n_img_missing}")
    print(f"scene_type 种类: {len(scene_counter)} | none 数量: {scene_counter.get('none', 0)} | other_* 合计: {sum(v for k, v in scene_counter.items() if k.startswith('other_'))}")
    print(f"scene_group 种类: {len(group_counter)}")
    print(f"触发锚点总数: {sum(anchor_counter.values())} | 锚点种类: {len(anchor_counter)}")
    print(f"输出文件: {out_path}")
    print("\nscene_type 分布 (top 12):")
    for k, v in scene_counter.most_common(12):
        print(f"  {v:5d}  {k}")
    print("\n锚点分布 (全部):")
    for k, v in anchor_counter.most_common():
        print(f"  {v:5d}  {k}")


if __name__ == "__main__":
    main()