# ASMR Creater — 从图像生成空间化 ASMR 白噪音

> 一张图 → 视觉特征 → 结构化中间表示(JSON) → 音频控制参数 → 一路混好的空间化声音流

本项目是「视觉与自然语言处理」课程设计,目标是构建一条**端到端的单向映射链**:输入一张图片,系统理解画面的氛围与内容,自动生成一段"听起来确实是从这张图里长出来的" ASMR / 白噪音声景,并支持基础的 2D 空间音频(物体在画面左边,声音就偏左耳)。

## 核心理念

整个系统的本质是一条可插拔的映射链。视觉语言大模型(VLM)负责**理解与氛围**,YOLO / 几何负责**定位与空间**,DSP 负责**发声**,三者通过一份固定的 JSON 契约解耦,可以并行开发、随意替换底层模型。

```
┌──────────┐   ┌─────────────────────────┐   ┌──────────────────────────┐
│  输入图像 │──▶│ 视觉层                   │──▶│ 音频层                   │
└──────────┘   │ · 预处理 (Pillow)        │   │ · 参数映射               │
               │ · 全局氛围 (VLM)          │   │ · DSP 底噪 (pyo)         │
               │ · 实体检测 (YOLO)         │   │ · 离散音效触发           │
               │ · 空间坐标映射            │   │ · 2D 声像平移            │
               └───────────┬─────────────┘   │ · 多轨混流               │
                           │                  └──────────────────────────┘
                           ▼
                    结构化 JSON 契约
```

## JSON 契约

视觉层与音频层之间的中间格式(接口先行,一旦定死即可并行开发):

```json
{
  "global_vibe": {
    "scene_type": "bedroom",
    "mood": "calm",
    "brightness": 0.28,
    "warmth": "cool",
    "base_noise": "brown",
    "time_of_day": "night"
  },
  "entities": [
    {"name": "cat", "state": "sleeping", "x": 0.22, "depth": "near", "conf": 0.91},
    {"name": "window", "state": "rainy", "x": 0.80, "depth": "far", "conf": 0.75}
  ]
}
```

- `x`:归一化横坐标(0=最左,1=最右),驱动声像平移
- `depth`:MVP 阶段用边界框面积粗估(框大=近)
- `state`:承接"睡觉的猫 → 呼噜声"等亮点,主要由 VLM 填充

## 运行模式

1. **离线批处理模式**(课程刚需):把整个数据集过一遍 VLM,产出一份结构化描述数据集。
2. **在线 Demo 模式**:用户传一张图 → 实时跑通管线 → 出声音。

## MVP 功能范围

**已纳入 MVP:**

- 上传 / 选择单张图片作为输入
- 视觉层输出干净的结构化 JSON(全局氛围 + 实体 + 位置)
- 用 VLM + prompt engineering 为数据集批量生成多维度描述
- DSP 实时生成无缝循环底噪(白 / 粉红 / 棕噪音,随明暗变化)
- 5~8 类常见物体触发对应离散音效(翻书、瓷杯、键盘、鸟鸣、猫呼噜、风、水声…)
- 基础 2D 声像平移
- 极简 Web UI:上传 → 显示识别结果 → 播放 / 暂停 → 每条音轨音量滑块
- 基础评估

**架构预留、暂不实现:**

- 开放词汇检测(YOLO-World / Grounding DINO)
- 单目深度(Depth Anything V2)驱动的距离衰减 + 低通 + 混响
- TTS / AI 人声旁白、空灵哼唱
- 情感分析 + 马尔可夫状态机概率触发
- OpenAL / HRTF 专业 3D 空间音频

## 技术栈

| 层     | 组件                                                        |
| ------ | ----------------------------------------------------------- |
| 视觉   | Pillow、免费 VLM(Qwen2.5-VL / 智谱 GLM-4V / 通义千问-VL)、YOLOv10/v11-Nano(COCO 80 类) |
| 音频   | `pyo`(实时 DSP 底噪 + 混流)、CC0 素材库                    |
| UI     | Gradio 或 Flask                                             |

## 目录结构

```
.
├── docs/                     # 项目文档
│   ├── MVP_guide.md          # MVP 实现指南(路线图、分工、模块拆解)
│   ├── json_contract.md      # 🔒 视觉↔音频 契约说明(v1.0,接口先行,已冻结)
│   ├── playback/             # 音频决策层 v2.x 提案的格式说明与素材规范(见下方说明)
│   └── 可能的项目方向.pdf
├── contracts/                # 视觉↔音频 中间数据契约(接口本身)
│   ├── scene_contract.schema.json   # 🔒 JSON Schema 正式定义(v1.0,程序据此校验)
│   ├── examples/             # 手写样例数据(音频线现在就能开工)
│   └── playback_proposal/    # 视觉记录 2.3 + 场景/锚点词表(提案阶段,未并入 v1.0)
├── src/                      # 源码,按层解耦
│   ├── common/               #   契约加载与校验(两层共用)
│   ├── vision/               #   图 → JSON(Pillow + VLM + YOLO)
│   ├── audio/                #   JSON → 声音(pyo DSP + 触发 + 声像 + 混流)
│   │   └── playback_converter.py  # 视觉记录 2.3 → 播放计划 JSON(v2.x 提案转换器)
│   └── ui/                   #   集成 + Gradio Web 界面
├── sounds/                   # 素材库(见「素材库规范」)
│   ├── ambient/  triggers/   #   底噪备用 / 离散音效
│   ├── trigger_map.json      #   标签 → 素材目录 映射表
│   └── metadata.csv          #   素材元数据(版权/来源)
├── configs/                  # 各层运行配置
│   └── playback/             #   播放计划决策阈值、场景音配置、素材 Manifest
├── scripts/
│   ├── validate_examples.py  # 校验所有样例是否符合契约
│   ├── run_playback_demo.ps1 # 一键跑通播放计划转换器 demo
│   └── test_playback_converter.py  # 转换器单元测试
├── img_dataset/              # 图像数据集(未纳入版本控制,见下方说明)
│   └── Train/
├── requirements.txt
└── README.md
```

> **新成员从这里入手**:先读 [docs/json_contract.md](docs/json_contract.md)(唯一接口),再看自己那层的 `src/<层>/README.md`。契约已冻结,三条线(视觉/音频/素材)可即刻并行开工。校验样例:`python scripts/validate_examples.py`。

> **关于数据集**:`img_dataset/`(约 1.7GB,2369+ 张图)体积过大,已通过 `.gitignore` 排除,不纳入 Git 版本控制。请另行获取并放置到该目录下。

## 素材库规范

```
sounds/
  ambient/     # 长循环底噪备用:rain / forest / cafe / ocean / city
  triggers/    # 短音效,按检测标签命名,每类 3~5 个变体
    cat/  cup/  book/  keyboard/  bird/  window/ ...
```

素材优先选用 CC0 / 免版税来源(Freesound、Pixabay、BBC Sound Effects 等),并用一张元数据表记录标签、时长、许可协议与来源 URL。

## 播放计划子系统(音频决策层 v2.x 提案)

音频组在现有 `entities[]`(v1.0 契约)基础上提出了一版更严格的**播放决策层**设计。相关文件已按项目既有分层拆分到 `docs/playback/`、`contracts/playback_proposal/`、`src/audio/playback_converter.py`、`configs/playback/` 与 `scripts/`,尚未接入 `src/audio` 现有 DSP 管线或真实视觉产出,可先并行评审、独立运行。

核心变化:

- **场景闭合词表**:[`scene_type_vocabulary.json`](contracts/playback_proposal/scene_type_vocabulary.json) 把 `global_vibe.scene_type` 从自由字符串收口为 20 个场景大组下的 424 个受控叶子值,禁止模型自创场景标签。
- **视觉锚点词典替代开放实体**:[`视觉锚点词典与检测边界.md`](docs/playback/视觉锚点词典与检测边界.md) 定义 87 个具体、可检测的视觉证据(如 `visible_bird`、`hands_on_keyboard_typing`),而非宽泛物体类别;每个锚点通过 [`recommended_structured_record_example.json`](contracts/playback_proposal/recommended_structured_record_example.json) 中的 `anchor_sound_mapping_reference` 映射到 66 个受控 `sound_id`,不允许自由造词。
- **两级播放计划输出**:转换器读取一条视觉记录(schema 2.3),始终产出确定性的[单声道回退计划](docs/playback/单声道回退播放计划格式说明.md)(`2.0-mono`);只有当所有入选锚点的相对深度质量都通过门控时,才额外产出[双耳 HRTF 空间计划](docs/playback/双耳空间播放计划格式说明.md)(`2.0-binaural`)。
- **素材采集规范**:[`ASMR声音素材库准备与采集规范.md`](docs/playback/ASMR声音素材库准备与采集规范.md) 给出 20 类场景环境音 + 66 类锚点关联声音的采集/格式/响度/授权标准。注意其 66 个 `sound_id` 命名与现有 `sounds/trigger_map.json` 的 17 个标签尚未统一,接入真实素材前需三线对齐。

[`src/audio/playback_converter.py`](src/audio/playback_converter.py) 是可独立运行的转换器,配套 [`scripts/test_playback_converter.py`](scripts/test_playback_converter.py) 与一键 demo 脚本 [`scripts/run_playback_demo.ps1`](scripts/run_playback_demo.ps1),用手写样例记录跑通"视觉记录 → 播放计划 JSON"全流程;当前只生成计划,不读取/合成真实音频字节。详见 [`docs/playback/playback_converter_usage.md`](docs/playback/playback_converter_usage.md)。

[`visual_record.schema.json`](contracts/playback_proposal/visual_record.schema.json) 是从上述规范反推生成的正式 JSON Schema(draft-07),补上了 v2.3 提案原本缺失的机器可校验定义,供视觉线对齐产出格式;已用 `jsonschema` 库自校验通过(含负例测试),尚未接入 `scripts/validate_examples.py`。

## 开发路线图

- **阶段 0 · 地基**:探数据集、选 VLM、迭代 prompt、敲定 JSON schema、搭素材库
- **阶段 1 · 视觉层**:单图 → 干净 JSON(全局氛围 + YOLO + X 坐标)
- **阶段 2 · 音频层**:靠 mock JSON 独立开发 DSP 底噪 + 触发 + 声像 + 混流
- **阶段 3 · 集成 + UI**:接真实 JSON,做 Web 界面,调"图-声匹配感"
- **阶段 4 · 评估 + 报告 + 演示视频**

详见 [docs/MVP_guide.md](docs/MVP_guide.md)。

## 评估维度

- **VLM 描述质量**:验证集人工打分 / 更强 VLM 交叉评审
- **视觉→音频匹配感**:A/B 盲听主观听测(本系统 vs 随机映射 baseline)
- **检测准确率**:小子集手工标注,报 YOLO 命中率 + VLM 场景分类正确率
- **迁移讨论**:抽象画 / 古典画 / 医学影像的跨域表现
