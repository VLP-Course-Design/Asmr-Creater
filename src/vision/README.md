# vision —— 视觉层

**职责**:一张图 → 一份符合 [Scene Contract](../../docs/json_contract.md) 的 JSON。**只产出 JSON,绝不碰音频代码。**

## 模块规划(对应 MVP_guide 三-1 的四步)

| 文件            | 步骤             | 说明                                                        | 状态   |
| --------------- | ---------------- | ----------------------------------------------------------- | ------ |
| `preprocess.py` | 1 图像预处理     | Pillow 读入、转 RGB、resize;要能批处理整个数据集            | 待建   |
| `vibe_vlm.py`   | 2 全局氛围(VLM) | **课程评分核心**。prompt 让 VLM 直接吐 `global_vibe` JSON    | 待建   |
| `detector.py`   | 3 实体检测(YOLO) | 已给出 `Detector` 抽象接口 + `YoloDetector` 占位            | 骨架   |
| `pipeline.py`   | 4 坐标映射+组装  | 融合 VLM 物体清单与 YOLO 框,算 x/depth,拼成契约 JSON       | 待建   |

## 开工方式

视觉线不等任何人。产出 JSON 后务必自检:

```python
from src.common import validate_scene
validate_scene(scene)   # 不合法会抛异常,别把脏数据交给音频层
```

## 关键纪律

- 受控字段(`mood`/`warmth`/`base_noise`/`time_of_day`/`depth`)只能取词表内的值 —— 在 VLM prompt 里用 few-shot 钉死。
- `entities[].name` 要和 [`sounds/trigger_map.json`](../../sounds/trigger_map.json) 的 key 对齐(小写单数),否则音频层查不到素材。
- 换模型只改对应一个文件,不动契约。prompt 的迭代过程请留版本记录(报告要用)。
