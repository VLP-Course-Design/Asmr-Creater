# common —— 公共模块

视觉层与音频层共用的东西放这里。目前只有一件核心资产:**契约的加载与校验**。

## `contract.py`

封装了对 [`contracts/scene_contract.schema.json`](../../contracts/scene_contract.schema.json) 的加载与 JSON Schema 校验,两层都从这里进出数据,避免各写一套校验逻辑。

```python
from src.common import validate_scene, load_example, list_examples

# 音频线:直接拿手写样例开工
scene = load_example("bedroom_night_cat")   # 已顺手校验
mixer.render(scene["global_vibe"], scene["entities"])

# 视觉线:产出 JSON 后自检再交付
validate_scene(my_generated_scene)           # 不合法会抛 SchemaValidationError
```

| 函数                    | 用途                                             |
| ----------------------- | ------------------------------------------------ |
| `validate_scene(scene)` | 校验一个场景对象,合法返回自身,否则抛异常       |
| `load_scene(path)`      | 从文件读 JSON,默认顺手校验                       |
| `load_example(name)`    | 按名加载 `contracts/examples/` 里的手写样例      |
| `list_examples()`       | 列出所有手写样例路径                             |
| `load_contract_schema()`| 加载 schema 本身(一般不用直接调用)             |

依赖 `jsonschema`(见根目录 `requirements.txt`)。
