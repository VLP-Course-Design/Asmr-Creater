# ASMR Creater — 从图像生成空间化 ASMR 白噪音
Test

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
│   ├── json_contract.md      # 🔒 视觉↔音频 契约说明(接口先行,已冻结)
│   └── 可能的项目方向.pdf
├── contracts/                # 视觉↔音频 中间数据契约(接口本身)
│   ├── scene_contract.schema.json   # JSON Schema 正式定义(程序据此校验)
│   └── examples/             # 手写样例数据(音频线现在就能开工)
├── src/                      # 源码,按层解耦
│   ├── common/               #   契约加载与校验(两层共用)
│   ├── vision/               #   图 → JSON(Pillow + VLM + YOLO)
│   ├── audio/                #   JSON → 声音(pyo DSP + 触发 + 声像 + 混流)
│   └── ui/                   #   集成 + Gradio Web 界面
├── sounds/                   # 素材库(见「素材库规范」)
│   ├── ambient/  triggers/   #   底噪备用 / 离散音效
│   ├── trigger_map.json      #   标签 → 素材目录 映射表
│   └── metadata.csv          #   素材元数据(版权/来源)
├── scripts/
│   └── validate_examples.py  # 校验所有样例是否符合契约
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
