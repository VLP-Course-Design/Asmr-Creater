#!/usr/bin/env python3
"""素材库覆盖率检查 —— 对照 sounds/v23_registry.json 报告哪些 sound_id 还缺素材。

用法:
    python scripts/check_sounds_coverage.py            # 汇总 + 缺失清单
    python scripts/check_sounds_coverage.py --detail   # 逐条列出已有变体数
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOUNDS = REPO / "sounds"
REGISTRY = SOUNDS / "v23_registry.json"
BRIDGE = SOUNDS / "v23_sound_id_bridge.json"


def variants(folder: str) -> list[str]:
    d = SOUNDS / folder
    return sorted(f.name for f in d.glob("*.wav")) if d.is_dir() else []


def report(section: str, entries: dict, bridge: dict, detail: bool) -> tuple[int, int]:
    print(f"\n{'=' * 62}")
    print(f"{section}({len(entries)} 类)")
    print("=" * 62)

    ready, partial, missing = [], [], []
    for sound_id, meta in sorted(entries.items()):
        have = variants(meta["folder"])
        need = meta["min_variants_mvp"]
        if len(have) >= need:
            ready.append((sound_id, have, need))
        elif have:
            partial.append((sound_id, have, need))
        else:
            missing.append((sound_id, have, need))

    for label, group in (("达标", ready), ("变体不足", partial)):
        if not group:
            continue
        print(f"\n[{label}] {len(group)} 类")
        if detail or label == "变体不足":
            for sound_id, have, need in group:
                print(f"  {sound_id:28s} {len(have)}/{need}  {', '.join(have)}")

    if missing:
        print(f"\n[无素材] {len(missing)} 类")
        by_role: dict[str, list[str]] = {}
        for sound_id, _, _ in missing:
            role = entries[sound_id].get("role", "?")
            by_role.setdefault(role, []).append(sound_id)
        for role, ids in sorted(by_role.items()):
            bridged = [i for i in ids if i in bridge]
            print(f"  · {role}({len(ids)}):")
            print(f"      {', '.join(ids)}")
            if bridged:
                print(f"      其中 {len(bridged)} 类暂由桥接表回退到 v1.0 目录: {', '.join(bridged)}")

    return len(ready), len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 v2.3 素材库覆盖率")
    parser.add_argument("--detail", action="store_true", help="逐条列出已达标类别的变体文件")
    args = parser.parse_args()

    if not REGISTRY.exists():
        print(f"找不到采集清单: {REGISTRY}", file=sys.stderr)
        return 1

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    bridge = json.loads(BRIDGE.read_text(encoding="utf-8"))["map"] if BRIDGE.exists() else {}

    t_ready, t_total = report("触发音 / 锚点关联声音", registry["triggers"], bridge, args.detail)
    a_ready, a_total = report("场景环境音", registry["ambient"], bridge, args.detail)

    print(f"\n{'=' * 62}")
    print(f"合计达标(变体数满足正式 MVP 要求): "
          f"触发音 {t_ready}/{t_total}，环境音 {a_ready}/{a_total}")
    legacy = sum(1 for f in (SOUNDS / "triggers").glob("*/*.wav")) if (SOUNDS / "triggers").is_dir() else 0
    print(f"triggers/ 下现有真实 wav 总数(含 v1.0 旧目录): {legacy}")
    print(f"桥接表暂时代偿的 sound_id: {len(bridge)} 类")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
