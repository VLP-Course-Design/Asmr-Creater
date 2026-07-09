# 视觉↔音频中间数据契约(Scene Contract）v1.0

> **本文档是全项目最重要的一张纸。** 它是视觉层与音频层之间唯一的接口。
> 一旦冻结,三条开发线(视觉 / 音频 / 素材)即可完全并行,各自 mock 对方、随意替换底层模型互不影响。
>
> - **机器可读的正式定义**:[`contracts/scene_contract.schema.json`](../contracts/scene_contract.schema.json)(JSON Schema draft-07,程序据此校验)
> - **可直接使用的样例**:[`contracts/examples/`](../contracts/examples/)(5 份手写样例,音频线现在就能开工)
> - **校验方式**:`python scripts/validate_examples.py`

**契约状态:🔒 已冻结(v1.0,2026-07-09)。** 任何字段的增删改都必须走本文末尾的「变更流程」,不得私自修改。

---

## 0. 一句话理解

视觉层看完一张图,吐出**一个 JSON 对象**;音频层只读这个对象发声。两边约好的就是这个对象长什么样。

```
一张图 ──[视觉层]──▶  Scene Contract JSON  ──[音频层]──▶  一路混好的声音
                         ▲ 本文档定义的就是它
```

音频层**从第一天起就用手写的样例 JSON 独立开发**,完全不等视觉层。最后集成只是把手写样例换成视觉层真实产出。

---

## 1. 顶层结构

```json
{
  "schema_version": "1.0",
  "image":       { ... },   // 可选,溯源信息,音频层可整段忽略
  "global_vibe": { ... },   // 必填,全局氛围 → 底噪基调
  "entities":    [ ... ]    // 必填,可为空数组 → 离散音效 + 声像
}
```

| 顶层字段         | 必填 | 谁负责填          | 谁消费          | 作用                         |
| ---------------- | ---- | ----------------- | --------------- | ---------------------------- |
| `schema_version` | ✅   | 视觉层            | 双方            | 契约版本号,防止版本错配     |
| `image`          | ❌   | 视觉层            | 批处理/UI/评估  | 溯源;**音频层不需要**       |
| `global_vibe`    | ✅   | 主要 VLM          | 音频层(底噪)  | 全局氛围决定底噪基调         |
| `entities`       | ✅   | YOLO + VLM 融合   | 音频层(音效)  | 可发声实体 → 触发音效 + 声像 |

> **给音频线的话**:你只需要 `global_vibe` 和 `entities` 两个字段就能把整条音频链跑通。`image` 与 `schema_version` 读不读都行。

---

## 2. `global_vibe` —— 全局氛围(底噪的灵魂)

主要由 VLM 一次性输出。音频层据此选底噪类型、定音量、调滤波。

| 字段          | 类型   | 取值范围 / 词表                                                        | 音频层怎么用                                                     |
| ------------- | ------ | --------------------------------------------------------------------- | --------------------------------------------------------------- |
| `scene_type`  | string | 自由字符串(如 `bedroom` `cafe` `forest` `beach` `office`)           | 仅日志/调试;**不硬依赖**,便于未来扩展                          |
| `mood`        | string | `calm` `cozy` `lively` `tense` `gloomy` `melancholic` `eerie` `cheerful` | 微调音效密度与整体感觉                                           |
| `brightness`  | number | `0.0 ~ 1.0`(0=最暗)                                                  | **线性驱动**底噪音量 + 低通截止频率:越暗→越低沉、越轻          |
| `warmth`      | string | `warm` `neutral` `cool`                                                | 影响滤波音色:暖→高频衰减更多更柔,冷→保留更多高频               |
| `base_noise`  | string | `white` `pink` `brown`                                                 | 直接映射 pyo 的 `WhiteNoise` / `PinkNoise` / `BrownNoise`       |
| `time_of_day` | string | `dawn` `morning` `noon` `afternoon` `dusk` `night`                     | 与 `brightness` 协同修饰音色                                     |

**受控词表的约定(重要,给视觉线)**:`mood` / `warmth` / `base_noise` / `time_of_day` 四个字段**只能从上表词表里取值**,不能自创。请在 VLM 的 prompt 里用 few-shot 把词表钉死,否则音频层会拿到不认识的枚举值而报错。`scene_type` 是唯一允许自由发挥的字段。

**底噪选型经验参考**(视觉线填 `base_noise` 时可参考,非强制):

- `brown`(棕噪音,最低沉)→ 夜晚、卧室、雨、深海、压抑/宁静场景
- `pink`(粉噪音,均衡)→ 白天室内、咖啡馆、森林、多数中性场景
- `white`(白噪音,最亮)→ 明亮、电器、瀑布、嘈杂/高频场景

---

## 3. `entities[]` —— 可发声实体(音效 + 空间)

一个数组,每个元素是画面里一个「有发声潜力」的实体。**可以是空数组**(纯氛围图,只出底噪)。

| 字段     | 必填 | 类型     | 取值范围                    | 说明                                                                       |
| -------- | ---- | -------- | --------------------------- | -------------------------------------------------------------------------- |
| `name`   | ✅   | string   | 小写标签                    | YOLO 认得的用 COCO 标签(`cat`/`cup`/`book`);VLM 补充的用自由词(`wind_chime`) |
| `state`  | ❌   | string   | 自由字符串                  | VLM 填,承接「睡觉的猫→呼噜声」。缺省=默认状态                              |
| `x`      | ✅   | number   | `0.0 ~ 1.0`                 | 实体中心归一化横坐标(0=最左,1=最右)→ **声像平移**                       |
| `depth`  | ✅   | string   | `near` `mid` `far`          | 远近。MVP 用边界框面积粗估(框大=near)→ 音量衰减                          |
| `conf`   | ✅   | number   | `0.0 ~ 1.0`                 | 置信度。见下方约定                                                          |
| `bbox`   | ❌   | number[] | `[x1,y1,x2,y2]` 均归一化    | 左上+右下,可选。供 UI 画框;音频层通常只用 `x`                            |
| `source` | ❌   | string   | `yolo` `vlm` `fused`        | 该实体的来源,支持融合与未来开放词汇分支追溯                              |

**`conf` 的约定**:

- YOLO 检出的实体 → 填 YOLO 的检测置信度。
- 纯 VLM 提及、YOLO 认不出的实体(如香薰机)→ 约定填 `0.5`,并把 `source` 标为 `vlm`。
- 音频层可用 `conf` 设触发阈值或调音效音量(置信度低→音量小)。

**`name` 与素材库的衔接**:`name` 是音频层查 [`sounds/trigger_map.json`](../sounds/trigger_map.json) 的 key。视觉线产出的标签必须和素材线维护的映射表 key 对齐(都用小写单数)。这是三条线唯一需要额外对齐的词表,请素材线维护一份「已支持标签清单」。

---

## 4. 各线的开工方式(接口先行的意义）

| 线       | 现在就能做什么                                                                 | 依赖谁 |
| -------- | ------------------------------------------------------------------------------ | ------ |
| **音频线** | 拿 `contracts/examples/*.json` 当输入,把 DSP 底噪 + 音效触发 + 声像 + 混流跑通 | 不等任何人 |
| **视觉线** | 让 VLM+YOLO 产出符合本契约的 JSON,用 `scripts/validate_examples.py` 自检     | 不等任何人 |
| **素材线** | 按 `entities[].name` 词表备素材、填 `trigger_map.json` 与 `metadata.csv`      | 不等任何人 |
| **集成期** | 把音频线的手写样例换成视觉线的真实产出,一行代码的事                          | 三线合流 |

只要各线产出/消费的 JSON 都过 schema 校验,集成就几乎无摩擦。

---

## 5. 完整样例(带注释说明)

一间夜晚的卧室,窗边在下雨,一只猫在左侧睡觉:

```json
{
  "schema_version": "1.0",
  "image": { "id": "42", "path": "img_dataset/Train/42.jpg", "width": 1024, "height": 768 },
  "global_vibe": {
    "scene_type": "bedroom",
    "mood": "calm",
    "brightness": 0.28,
    "warmth": "cool",
    "base_noise": "brown",
    "time_of_day": "night"
  },
  "entities": [
    { "name": "cat",    "state": "sleeping", "x": 0.22, "depth": "near", "conf": 0.91, "source": "yolo" },
    { "name": "window", "state": "rainy",    "x": 0.80, "depth": "far",  "conf": 0.75, "source": "fused" }
  ]
}
```

音频层读到它会:出棕噪音底噪(夜/暗→低沉、音量小)→ 左耳偏近处播猫呼噜、右耳远处播雨声。

更多样例见 [`contracts/examples/`](../contracts/examples/),覆盖空实体、多实体、不同底噪等情况。

---

## 6. 变更流程(冻结后如何改)

契约已冻结。若确需改动:

1. 先在群里同步,三条线负责人确认影响。
2. 同时改 `scene_contract.schema.json`(正式定义)与本文档(说明),两者永远一致。
3. 破坏性改动(删字段 / 改语义 / 收窄枚举)→ 升主版本(`1.0`→`2.0`);向后兼容的新增可选字段 → 升次版本(`1.0`→`1.1`)。
4. 在下方 CHANGELOG 记一笔。
5. 跑 `python scripts/validate_examples.py` 确认所有样例仍通过。

### CHANGELOG

- **v1.0(2026-07-09)** —— 初始冻结。在 README/MVP_guide 原始 schema 基础上,新增 `schema_version`、可选 `image` 溯源、`entities[].bbox`/`source`,并把 `mood`/`warmth`/`base_noise`/`time_of_day`/`depth` 收敛为受控枚举。
