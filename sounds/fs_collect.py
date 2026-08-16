#!/usr/bin/env python3
"""
Freesound 素材采集管线 —— 场景白噪音合成器
================================================

三步走：
    python fs_collect.py search                 # 只查询，产出 candidates.json，人工过一遍
    python fs_collect.py auth                   # (可选) OAuth2 授权，拿原始 wav
    python fs_collect.py download               # 下载 + 转 wav + 写 metadata.csv

依赖：
    pip install requests soundfile numpy
    ffmpeg  (只有在走 preview-mp3 回退路径时才需要)

凭据：申请地址 https://freesound.org/apiv2/apply/
    export FREESOUND_TOKEN=xxx          # 必需，用于搜索
    export FREESOUND_CLIENT_ID=xxx      # 仅 OAuth2 下载原始 wav 时需要
    export FREESOUND_CLIENT_SECRET=xxx

关于许可：默认只收 CC0，这样你不需要在成品里附署名清单。
把 LICENSES 改成 ["Creative Commons 0", "Attribution"] 可扩大池子，
但此时 attribution.md 必须随项目一起分发。
"""

import os, sys, json, time, csv, re, subprocess, pathlib, urllib.parse
import requests

# ── 配置 ────────────────────────────────────────────────────────────────
API = "https://freesound.org/apiv2"
TOKEN = os.environ.get("FREESOUND_TOKEN", "")
CLIENT_ID = os.environ.get("FREESOUND_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("FREESOUND_CLIENT_SECRET", "")

LICENSES = ["Creative Commons 0"]          # 放宽可加 "Attribution"
MIN_SAMPLERATE = 22050
# 母版统一采样率。48k 来自 docs/playback/ASMR声音素材库准备与采集规范.md §5.1
# 的强制要求(原脚本写的是 44.1k,与该规范不一致)。
TARGET_SR = 48000
CANDIDATES_PER_QUERY = 15
SLEEP = 1.1                                # 免费 tier 限流，别调低
OUT = pathlib.Path("assets")
SPECS = pathlib.Path("sound_specs.json")
TOKEN_CACHE = pathlib.Path(".fs_oauth.json")

FIELDS = ",".join([
    "id", "name", "url", "license", "username", "duration", "type",
    "samplerate", "channels", "filesize", "download", "previews", "tags",
    "avg_rating", "num_ratings", "num_downloads",
    "loopable", "single_event", "brightness", "sharpness", "loudness",
    "spectral_centroid", "silence_rate", "dynamic_range",
])

LOOP_ROLES = {"bed", "loop"}


# ── 许可证归一化 ────────────────────────────────────────────────────────
# APIv2 的 license 字段返回的是 URL(如 http://creativecommons.org/publicdomain/zero/1.0/),
# 不是 "Creative Commons 0" 这种字符串。不归一化会导致 metadata.csv 里写进 URL、
# 且所有 CC0 素材被误判为「需署名」写进 attribution.md。
def norm_license(lic: str) -> str:
    s = (lic or "").lower()
    if "publicdomain/zero" in s or s == "creative commons 0":
        return "CC0"
    if "by-nc-sa" in s:
        return "CC-BY-NC-SA"
    if "by-nc" in s or "attribution noncommercial" in s:
        return "CC-BY-NC"
    if "by-sa" in s:
        return "CC-BY-SA"
    if "licenses/by" in s or s == "attribution":
        return "CC-BY"
    if "publicdomain/mark" in s:
        return "PDM"
    return lic or "UNKNOWN"


# ── 搜索 ────────────────────────────────────────────────────────────────
def build_filter(spec):
    lic = " OR ".join(f'"{l}"' for l in LICENSES)
    lo, hi = spec["dur"]
    parts = [
        f"license:({lic})",
        f"duration:[{lo} TO {hi}]",
        f"samplerate:[{MIN_SAMPLERATE} TO *]",
    ]
    # 只有 OAuth2 下载才拿得到原始 wav；没授权就别强制 type:wav，
    # 否则池子会小很多，反正回退路径会统一转成 wav。
    if TOKEN_CACHE.exists():
        parts.append("type:(wav OR aiff OR flac)")
    return " ".join(parts)


def search_one(spec):
    """对一个 sound_id 的所有 query 跑搜索，合并去重。"""
    seen, pool = set(), []
    for q in spec["q"]:
        params = {
            "query": q,
            "filter": build_filter(spec),
            "fields": FIELDS,
            "page_size": CANDIDATES_PER_QUERY,
            "sort": "score",
        }
        try:
            r = requests.get(f"{API}/search/", params=params,
                             headers={"Authorization": f"Token {TOKEN}"}, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"    ! {spec['id']} / '{q}' 查询失败: {e}")
            time.sleep(SLEEP)
            continue
        for s in r.json().get("results", []):
            if s["id"] not in seen:
                seen.add(s["id"])
                s["_query"] = q
                pool.append(s)
        time.sleep(SLEEP)
    return pool


def score(s, spec):
    """按助眠场景的实际需求排序，而不是按 Freesound 的相关性。"""
    sc = 0.0
    txt = (s.get("name", "") + " " + " ".join(s.get("tags", []))).lower()

    # 硬性排除词
    for bad in spec.get("avoid", []):
        if bad.lower() in txt:
            sc -= 40
    for bad in ("music", "song", "speech", "voice over", "scream", "loop pack demo"):
        if bad in txt:
            sc -= 20

    # 角色匹配：loop 类看 loopable，trigger 类看 single_event
    loopable = s.get("loopable")
    single = s.get("single_event")
    if spec["role"] in LOOP_ROLES:
        if loopable is True:
            sc += 30
        if single is True:
            sc -= 10
    else:
        if single is True:
            sc += 20

    # 高频抑制 —— 这是整份需求表里出现最多的约束
    bright = s.get("brightness")
    sharp = s.get("sharpness")
    if spec.get("hf_strict"):
        if isinstance(bright, (int, float)):
            sc -= max(0.0, bright - 45) * 0.6
        if isinstance(sharp, (int, float)):
            sc -= max(0.0, sharp - 40) * 0.6

    # 动态范围：床音要平稳，触发音无所谓
    dr = s.get("dynamic_range")
    if spec["role"] in LOOP_ROLES and isinstance(dr, (int, float)):
        sc -= max(0.0, dr - 12) * 0.8

    # 静音占比过高说明素材里大段空白
    sr_ = s.get("silence_rate")
    if isinstance(sr_, (int, float)) and sr_ > 0.5:
        sc -= 15

    # 质量信号
    if s.get("num_ratings", 0) >= 3:
        sc += float(s.get("avg_rating") or 0) * 4
    sc += min(float(s.get("num_downloads") or 0), 5000) / 500.0
    if s.get("channels") == 2:
        sc += 3
    if norm_license(s.get("license")) == "CC0":
        sc += 5

    # 时长贴近推荐区间中点
    lo, hi = spec["dur"]
    mid = (lo + hi) / 2
    d = float(s.get("duration") or 0)
    sc -= abs(d - mid) / max(mid, 1) * 6
    return sc


def cmd_search():
    if not TOKEN:
        sys.exit("请先设置 FREESOUND_TOKEN")
    specs = json.loads(SPECS.read_text(encoding="utf-8"))
    all_specs = [dict(s, category="bed") for s in specs["beds"]] + \
                [dict(s, category="trigger") for s in specs["triggers"]]

    out, missing = {}, []
    for i, spec in enumerate(all_specs, 1):
        print(f"[{i}/{len(all_specs)}] {spec['id']}", flush=True)
        pool = search_one(spec)
        if not pool:
            missing.append(spec["id"])
            print("    ✗ 无候选")
            continue
        pool.sort(key=lambda s: score(s, spec), reverse=True)
        picked = pool[: spec["n"]]
        for s in picked:
            s["_score"] = round(score(s, spec), 2)
        out[spec["id"]] = {"spec": spec, "picked": picked,
                           "runners_up": [{"id": s["id"], "name": s["name"],
                                           "url": s["url"], "duration": s["duration"]}
                                          for s in pool[spec["n"]: spec["n"] + 5]]}
        print(f"    ✓ {len(pool)} 候选 → 选 {len(picked)}: " +
              ", ".join(f"{s['id']}({s['duration']:.1f}s,{s['_score']})" for s in picked))

    pathlib.Path("candidates.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写出 candidates.json —— {len(out)}/{len(all_specs)} 个 sound_id 有结果")
    if missing:
        print("以下需要手工兜底（放宽 dur 或改 query）:")
        for m in missing:
            print("   -", m)


# ── OAuth2 ──────────────────────────────────────────────────────────────
def cmd_auth():
    if not (CLIENT_ID and CLIENT_SECRET):
        sys.exit("需要 FREESOUND_CLIENT_ID / FREESOUND_CLIENT_SECRET")
    url = (f"{API}/oauth2/authorize/?client_id={CLIENT_ID}"
           f"&response_type=code&state=collect")
    print("1. 浏览器打开并授权：\n  ", url)
    print("2. 授权后页面会给你一个 code。")
    code = input("粘贴 code: ").strip()
    r = requests.post(f"{API}/oauth2/access_token/", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code", "code": code}, timeout=30)
    r.raise_for_status()
    tok = r.json()
    tok["_obtained"] = time.time()
    TOKEN_CACHE.write_text(json.dumps(tok))
    print("✓ access_token 已缓存到", TOKEN_CACHE, "(有效期约 24h，过期重跑 auth)")


def access_token():
    if not TOKEN_CACHE.exists():
        return None
    tok = json.loads(TOKEN_CACHE.read_text())
    if time.time() - tok.get("_obtained", 0) > tok.get("expires_in", 86400) - 300:
        print("! access_token 可能已过期，必要时重跑 `python fs_collect.py auth`")
    return tok.get("access_token")


# ── 下载与转码 ──────────────────────────────────────────────────────────
def to_wav(src: pathlib.Path, dst: pathlib.Path):
    """统一转成 TARGET_SR 16-bit wav。

    优先走 soundfile(libsndfile ≥1.1 原生支持 MP3/FLAC/AIFF/OGG),不需要外部
    ffmpeg;只有遇到 libsndfile 读不了的容器(如 m4a)才回退 ffmpeg。
    """
    if src.suffix.lower() == ".wav":
        try:
            import soundfile as sf
            info = sf.info(str(src))
            if info.samplerate == TARGET_SR and info.subtype == "PCM_16":
                src.replace(dst)
                return True
        except Exception:
            pass

    try:
        import soundfile as sf
        import soxr
        data, sr = sf.read(str(src), always_2d=True, dtype="float32")
        if sr != TARGET_SR:
            data = soxr.resample(data, sr, TARGET_SR, quality="HQ")
        sf.write(str(dst), data, TARGET_SR, subtype="PCM_16")
        src.unlink(missing_ok=True)
        return True
    except Exception as e:
        print(f"    · soundfile 解码失败({e}),回退 ffmpeg")

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
           "-ar", str(TARGET_SR), "-sample_fmt", "s16", str(dst)]
    try:
        subprocess.run(cmd, check=True)
        src.unlink(missing_ok=True)
        return True
    except Exception as e:
        print("    ! ffmpeg 转码失败(且未安装 ffmpeg 时属预期):", e)
        return False


def fetch(sound, dest_stem: pathlib.Path, at):
    """优先原始文件（需 OAuth2），否则回退 preview-hq-mp3。"""
    # 临时文件必须和最终 wav 不同名，否则 ffmpeg 会自读自写
    raw_base = dest_stem.parent / (dest_stem.name + "__raw")
    final = dest_stem.with_suffix(".wav")

    if at and sound.get("download"):
        try:
            r = requests.get(sound["download"],
                             headers={"Authorization": f"Bearer {at}"},
                             timeout=180, stream=True)
            if r.status_code == 200:
                raw = raw_base.with_suffix("." + (sound.get("type") or "wav"))
                with open(raw, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
                if to_wav(raw, final):
                    return True, "original"
                # 原始容器解不了(如 m4a,libsndfile 不支持且本机无 ffmpeg)时
                # 不要直接放弃,回退 preview 至少还能拿到素材
                print("    ! 原始文件转码失败，回退 preview")
                raw.unlink(missing_ok=True)
            else:
                print(f"    ! 原始下载 HTTP {r.status_code}，回退 preview")
        except Exception as e:
            print("    ! 原始下载失败，回退 preview:", e)

    prev = (sound.get("previews") or {}).get("preview-hq-mp3")
    if not prev:
        return False, None
    r = requests.get(prev, headers={"Authorization": f"Token {TOKEN}"},
                     timeout=120, stream=True)
    r.raise_for_status()
    mp3 = raw_base.with_suffix(".mp3")
    with open(mp3, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            f.write(chunk)
    return to_wav(mp3, final), "preview-mp3"


def cmd_download():
    if not pathlib.Path("candidates.json").exists():
        sys.exit("先跑 `python fs_collect.py search`")
    cand = json.loads(pathlib.Path("candidates.json").read_text(encoding="utf-8"))
    at = access_token()
    if not at:
        print("! 未授权 OAuth2 —— 将下载 preview-hq-mp3 (~128kbps) 转 wav。")
        print("  要原始 wav 请先跑 `python fs_collect.py auth`\n")

    rows, attribs = [], []
    for sid, entry in cand.items():
        spec = entry["spec"]
        sub = "beds" if spec["category"] == "bed" else "triggers"
        folder = OUT / sub / sid
        folder.mkdir(parents=True, exist_ok=True)

        for n, s in enumerate(entry["picked"], 1):
            stem = folder / f"{sid}_{n:02d}"
            ok, how = fetch(s, stem, at)
            if not ok:
                print(f"  ✗ {sid}_{n:02d} 下载失败")
                continue
            wav = stem.with_suffix(".wav")

            # 实测时长，不用 API 报的
            try:
                import soundfile as sf
                info = sf.info(str(wav))
                dur = round(info.frames / info.samplerate, 3)
            except Exception:
                dur = round(float(s.get("duration") or 0), 3)

            lic = norm_license(s.get("license"))
            rows.append({
                "file": str(wav.relative_to(OUT)).replace("\\", "/"),
                "label": sid,
                "category": spec["role"],
                "duration_sec": dur,
                "loopable": "true" if spec["role"] in LOOP_ROLES else "false",
                "default_volume": spec["vol"],
                "license": lic,
                "source_url": s["url"],
                "notes": f"{s['name']} by {s['username']}"
                         + ("" if how == "original" else " [from hq-mp3 preview]")
                         + (f"; fs_loopable={s.get('loopable')}" if s.get("loopable") is not None else ""),
            })
            if lic != "CC0":
                attribs.append(f"- \"{s['name']}\" by {s['username']} "
                               f"({s['url']}) — {lic} — {s.get('license')}")
            print(f"  ✓ {rows[-1]['file']}  {dur}s  {rows[-1]['license']}  [{how}]")

    OUT.mkdir(exist_ok=True)
    cols = ["file", "label", "category", "duration_sec", "loopable",
            "default_volume", "license", "source_url", "notes"]
    with open(OUT / "metadata.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"\n写出 {OUT/'metadata.csv'} —— {len(rows)} 条")

    if attribs:
        (OUT / "attribution.md").write_text(
            "# 素材署名\n\n本项目使用了以下需署名的素材：\n\n"
            + "\n".join(sorted(set(attribs))) + "\n", encoding="utf-8")
        print(f"写出 {OUT/'attribution.md'} —— {len(set(attribs))} 条需署名，必须随项目分发")


if __name__ == "__main__":
    cmds = {"search": cmd_search, "auth": cmd_auth, "download": cmd_download}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        sys.exit(f"用法: python {sys.argv[0]} {{search|auth|download}}")
    cmds[sys.argv[1]]()
