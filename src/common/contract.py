# -*- coding: utf-8 -*-
"""Scene Contract 的加载与校验工具 —— 视觉层与音频层共用的唯一真相源。

设计目标:
- 视觉层:产出 JSON 后调用 ``validate_scene`` 自检,确保交给音频层的数据合法。
- 音频层:读入任意 JSON(手写样例或真实产出)前调用 ``validate_scene``,拒绝脏数据。
- 两边都从这里加载同一份 ``contracts/scene_contract.schema.json``,不各写一套校验。

契约本身的字段语义见 docs/json_contract.md。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

# 仓库根目录 = 本文件的上上上级(src/common/contract.py -> 仓库根)
REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "contracts" / "scene_contract.schema.json"
EXAMPLES_DIR = REPO_ROOT / "contracts" / "examples"

# 视觉记录契约 v2.3 正式定义，与 Scene Contract 主 Schema 共用唯一真源。
V23_SCHEMA_PATH = SCHEMA_PATH


class SchemaValidationError(ValueError):
    """场景数据不符合契约时抛出。message 会指明第一个出错的字段路径。"""


@lru_cache(maxsize=1)
def load_contract_schema() -> Dict[str, Any]:
    """加载并缓存 JSON Schema 定义。"""
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def validate_scene(scene: Dict[str, Any]) -> Dict[str, Any]:
    """校验一个场景对象是否符合契约。

    合法则原样返回该对象(方便链式调用);不合法抛 ``SchemaValidationError``。

    需要安装 ``jsonschema``(见 requirements.txt)。若未安装,给出清晰提示。
    """
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - 环境问题
        raise RuntimeError(
            "校验契约需要 jsonschema,请先 `pip install -r requirements.txt`。"
        ) from exc

    schema = load_contract_schema()
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(scene), key=lambda e: e.path)
    if errors:
        first = errors[0]
        location = "/".join(str(p) for p in first.path) or "<根>"
        raise SchemaValidationError(
            f"场景数据不符合契约(共 {len(errors)} 处问题)。首个:字段 [{location}] {first.message}"
        )
    return scene


@lru_cache(maxsize=1)
def load_v23_schema() -> Dict[str, Any]:
    """加载并缓存视觉记录 v2.3 正式 JSON Schema 定义。"""
    with V23_SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def validate_visual_record_v23(record: Dict[str, Any]) -> Dict[str, Any]:
    """校验一条视觉记录是否符合 v2.3 正式契约。

    合法则原样返回该对象;不合法抛 ``SchemaValidationError``。该函数保留旧名称，
    方便视觉管线调用；实际加载与 ``validate_scene`` 相同的正式 Schema。
    """
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - 环境问题
        raise RuntimeError(
            "校验契约需要 jsonschema,请先 `pip install -r requirements.txt`。"
        ) from exc

    schema = load_v23_schema()
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(record), key=lambda e: e.path)
    if errors:
        first = errors[0]
        location = "/".join(str(p) for p in first.path) or "<根>"
        raise SchemaValidationError(
            f"视觉记录不符合 v2.3 契约(共 {len(errors)} 处问题)。首个:字段 [{location}] {first.message}"
        )
    return record


def load_scene(path: str | Path, *, validate: bool = True) -> Dict[str, Any]:
    """从文件读入一个场景 JSON,默认顺手校验。"""
    with Path(path).open(encoding="utf-8") as f:
        scene = json.load(f)
    if validate:
        validate_scene(scene)
    return scene


def list_examples() -> List[Path]:
    """列出 contracts/examples 下所有手写样例路径。"""
    return sorted(EXAMPLES_DIR.glob("*.json"))


def load_example(name: str, *, validate: bool = True) -> Dict[str, Any]:
    """按名字加载手写样例,``name`` 可带或不带 .json 后缀。

    音频层开发期常用:``scene = load_example("bedroom_night_cat")``。
    """
    stem = name[:-5] if name.endswith(".json") else name
    return load_scene(EXAMPLES_DIR / f"{stem}.json", validate=validate)
