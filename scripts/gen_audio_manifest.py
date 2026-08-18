# -*- coding: utf-8 -*-
"""由真实素材库生成 configs/playback/audio_manifest.json。

除了登记 asset_id / sound_id / role / path，还实测每个文件的响度并算出
「响度补偿」makeup_db。

为什么需要 makeup_db
--------------------
采集规范 §6.3 明确区分两个概念:
  1. 素材响度 —— 文件自身的测量结果，用来让素材库内部有一致基准;
  2. 播放增益 gain_db —— 播放计划叠加在素材上的相对增益。
并且写明「播放增益只有在素材已按统一响度基准整理后才有可比性」。

播放计划里的 gain_db(环境床 -18~-22、前景 -28~-40)正是按「素材已整理到
约 -24 LUFS-I」这个前提定的。但 sounds/ 下的素材是从 Freesound 批量下载的
原始文件，没做过响度归一化，实测中位 RMS 环境音约 -41 dBFS、触发音约 -32 dBFS。
直接套用计划增益会让最终信号掉到约 -63 dBFS —— 已接近听阈，且推子和系统音量
都救不回来。

这里不改动 WAV 本体(不可逆，且 wav 不入库无法回滚)，而是把实测值和补偿量
写进 Manifest，由播放端在计划增益之外叠加，等价于规范要求的「先把素材整理到
统一基准，再谈播放增益」。

用法:
    python scripts/gen_audio_manifest.py
素材线往 sounds/ 补文件后重跑即可。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from audio.playback_converter import mode_role  # noqa: E402

SOUNDS = REPO / "sounds"
CONFIG = REPO / "configs" / "playback"

# 统一响度基准。规范 §5.1 给的是 -24 LUFS-I;这里用 RMS 近似
# (真正的 LUFS 需要 K 加权 + 门限，本项目暂无该依赖)，因此标注为 rms 而非 lufs，
# 不假装测的是 LUFS。
TARGET_RMS_DBFS = -24.0
# 真峰值上限:规范要求环境床 ≤ -2 dBTP、触发音 ≤ -3 dBTP，取更严的 -3 留余量
PEAK_CEILING_DBFS = -3.0
# 补偿量的安全区间。上限防止把极安静素材的噪底一起抬起来，下限防止过度压低
MAKEUP_MIN_DB, MAKEUP_MAX_DB = -12.0, 30.0


def measure(path: Path) -> tuple[float, float]:
    """返回 (RMS dBFS, 峰值 dBFS)。"""
    data, _ = sf.read(str(path), dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if data.size == 0:
        return -120.0, -120.0
    rms = float(np.sqrt(np.mean(np.square(data))))
    peak = float(np.max(np.abs(data)))
    to_db = lambda x: 20.0 * math.log10(max(x, 1e-12))
    return to_db(rms), to_db(peak)


def makeup_for(rms_db: float, peak_db: float) -> float:
    """把素材抬到统一基准所需的增益，同时不让真峰值越过上限。"""
    want = TARGET_RMS_DBFS - rms_db
    peak_allow = PEAK_CEILING_DBFS - peak_db
    return round(max(MAKEUP_MIN_DB, min(MAKEUP_MAX_DB, want, peak_allow)), 2)


def _loudness(rms_db: float, peak_db: float) -> dict:
    mk = makeup_for(rms_db, peak_db)
    post = rms_db + mk
    out = {"rms_dbfs": round(rms_db, 2), "peak_dbfs": round(peak_db, 2),
           "makeup_db": mk, "target_rms_dbfs": TARGET_RMS_DBFS}
    if post < TARGET_RMS_DBFS - 6.0:
        # 素材本身太安静,补到上限仍达不到基准。继续加增益只会把底噪一起抬起来,
        # 正确做法是重新挑素材(见 sounds/fs_collect.py 的 runners_up 备选)。
        out["under_level"] = True
        out["post_makeup_rms_dbfs"] = round(post, 2)
    return out


def collect() -> list[dict]:
    registry = json.loads((SOUNDS / "v23_registry.json").read_text(encoding="utf-8"))
    assets: list[dict] = []

    def add(sid: str, meta: dict, folder: Path, role: str, prefix: str, loopable: bool):
        for i, wav in enumerate(sorted(folder.glob("*.wav")), 1):
            rms_db, peak_db = measure(wav)
            assets.append({
                "asset_id": f"{prefix}_{sid}_{i:02d}",
                "sound_id": sid,
                "role": role,
                "path": f"/sounds/{'ambient' if prefix == 'amb' else 'triggers'}/{sid}/{wav.name}",
                "loop": {"enabled": loopable, "seamless_verified": False,
                         "crossfade_ms": 2500 if loopable else 0},
                "loudness": _loudness(rms_db, peak_db),
            })

    for sid, meta in sorted(registry["triggers"].items()):
        # role 必须用 playback_converter 自己的词汇，否则素材池取不到
        add(sid, meta, SOUNDS / "triggers" / sid, mode_role(meta.get("mode", ""))[0],
            "trg", meta["role"] == "loop")
    for sid, meta in sorted(registry["ambient"].items()):
        add(sid, meta, SOUNDS / "ambient" / sid, "ambient", "amb", True)
    return assets


def main() -> None:
    assets = collect()
    manifest = {
        "library_version": "1.1",
        "_comment": ("由 scripts/gen_audio_manifest.py 从 sounds/ 下的真实文件生成。"
                     "role 用 playback_converter 的词汇(ambient/texture/trigger)。"
                     "path 是给播放端直接取用的 URL。"),
        "_loudness": (f"loudness.makeup_db 是把素材抬到统一基准({TARGET_RMS_DBFS} dBFS RMS)"
                      f"所需的增益，播放端应在计划的 gain_db 之外叠加它。"
                      f"rms/peak 为实测值;真峰值不越过 {PEAK_CEILING_DBFS} dBFS。"
                      "注:用 RMS 近似 LUFS，项目暂无 K 加权计量依赖。"),
        "_seamless_verified": ("全部为 false:素材是程序批量下载的，无缝循环只能靠人耳试听确认"
                               "(采集规范 §11)。试听通过后逐条改 true，并把 decision_settings.json"
                               " 的 allow_unverified_loops 关掉。"),
        "assets": assets,
    }
    (CONFIG / "audio_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    by_role: dict[str, list[float]] = {}
    for a in assets:
        by_role.setdefault(a["role"], []).append(a["loudness"]["makeup_db"])
    print(f"写出 {CONFIG/'audio_manifest.json'} —— {len(assets)} 条")
    for role, ms in sorted(by_role.items()):
        print(f"  {role:9s} n={len(ms):3d}  makeup 中位 {float(np.median(ms)):+.1f} dB "
              f"(范围 {min(ms):+.1f}~{max(ms):+.1f})")


if __name__ == "__main__":
    main()
