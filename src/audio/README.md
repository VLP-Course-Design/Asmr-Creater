# audio —— 音频合成层

**职责**:一份 [Scene Contract](../../docs/json_contract.md) JSON → 一路混好的双声道声音。**只读 JSON,不关心图是怎么来的。**

## 模块规划(对应 MVP_guide 三-2 的五步)

| 文件          | 步骤           | 说明                                                       | 状态   |
| ------------- | -------------- | ---------------------------------------------------------- | ------ |
| `mapper.py`   | 1 参数解析     | JSON → 音频控制参数(连续线性映射)。已给出骨架            | 骨架   |
| `noise.py`    | 2 底噪生成     | pyo 的 `White/Pink/BrownNoise` + 动态低通滤波              | 待建   |
| `triggers.py` | 3 音效触发     | 查 `trigger_map.json`,`random.choice` 抽变体播放          | 待建   |
| `panner.py`   | 4 空间渲染     | 据 `x` 算左右声道增益(恒定功率 2D 声像平移)              | 待建   |
| `mixer.py`    | 5 多轨混流     | 底噪 + 各音效 → 一路双声道输出;pyo Server 接管声卡        | 待建   |

## 开工方式(重点:你不用等视觉线)

从第一天起就拿手写样例开发:

```python
from src.common import load_example
from src.audio import mapper

scene = load_example("cafe_afternoon_busy")     # 已校验的合法输入
bed = mapper.map_bed(scene["global_vibe"])       # 底噪参数
trigs = mapper.map_triggers(scene["entities"])   # 音效参数列表
# ... 交给 noise / triggers / panner / mixer
```

可用样例见 [`contracts/examples/`](../../contracts/examples/),已覆盖:多实体、空实体(只出底噪)、三种底噪、不同明暗。集成期把 `load_example(...)` 换成视觉线的真实产出即可,别的都不用改。

## playback_converter.py(v2.3 正式契约)

`playback_converter.py` 针对正式 v2.3 视觉记录（场景闭合词表 + 87 个视觉锚点）实现音频决策：输入一条视觉记录，输出单声道/双耳两种播放计划 JSON（声音选型、增益、调度、HRTF 参数等）。它不产生也不读取真实音频字节，更不依赖 `mapper.py` 等其余模块。当前播放计划和测试已跑通；真实 WAV 的加载与试听仍需素材库就绪。用法见 [`docs/playback/playback_converter_usage.md`](../../docs/playback/playback_converter_usage.md)。

## 早点验证的工程点

`pyo` 是本地音频服务器。若 UI 要做成网页在线播放,可能需要把合成结果**渲染成一段 wav** 再传前端(见 MVP_guide 三-4)。这条路径建议第一周就验证。
