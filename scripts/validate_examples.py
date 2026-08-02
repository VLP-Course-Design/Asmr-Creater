"""校验 contracts/examples/ 下所有手写样例是否符合 Scene Contract。

用法(仓库根目录下):
    python scripts/validate_examples.py

CI / 提交前跑一下,确保样例与 schema 永远一致。
"""

from __future__ import annotations

import sys
from pathlib import Path

# Windows 控制台默认 GBK,无法输出 emoji;强制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # 老版本 Python 或非常规流
    pass

# 让脚本能直接 import src 包(无需安装)
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from common import SchemaValidationError, list_examples, load_scene  # noqa: E402


def main() -> int:
    examples = list_examples()
    if not examples:
        print("⚠️  contracts/examples/ 下没有找到任何 .json 样例。")
        return 1

    failed = 0
    for path in examples:
        try:
            load_scene(path)  # 默认顺手校验
            print(f"✅ {path.name}")
        except SchemaValidationError as exc:
            failed += 1
            print(f"❌ {path.name}\n     {exc}")
        except Exception as exc:  # JSON 解析等其他错误
            failed += 1
            print(f"❌ {path.name}(读取失败)\n     {exc}")

    total = len(examples)
    print(f"\n{'—' * 40}")
    if failed:
        print(f"共 {total} 份,{failed} 份未通过。")
        return 1
    print(f"共 {total} 份,全部通过契约校验。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
