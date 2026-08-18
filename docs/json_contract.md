# 视觉↔音频中间数据契约（Scene Contract）v2.3

> 本文档是视觉层与音频层之间的正式接口说明。视觉层产出一条视觉记录，音频层只消费这条记录生成播放计划和声景。
>
> - **机器可读定义**：[contracts/scene_contract.schema.json](../contracts/scene_contract.schema.json)
> - **场景词表**：[contracts/playback_proposal/scene_type_vocabulary.json](../contracts/playback_proposal/scene_type_vocabulary.json)
> - **锚点词典**：[contracts/anchor_dictionary.json](../contracts/anchor_dictionary.json)
> - **播放计划说明**：[docs/playback/](playback/)
> - **校验方式**：`python scripts/validate_examples.py`

**契约状态：🔒 v2.3 已正式批准并生效（2026-08-17）。** 它替代原 v1.0 Scene Contract，后续视觉→音频主流程以 v2.3 为准。v1.0 代码和样例仅作为历史兼容资料，不得作为新视觉记录的输出格式。

---

## 0. 一句话理解

```text
图片 ──[视觉层]──▶ 视觉记录 v2.3 ──[音频决策]──▶ 播放计划 ──[播放端]──▶ 声景
```

视觉层负责环境理解和视觉锚点检测；音频层负责声音映射、调度、安全规则和空间播放。两层不直接调用对方内部模型，只通过本契约通信。

---

## 1. 顶层结构

```json
{
  "schema_version": "2.3",
  "id": "stable_image_id",
  "image": { "path": "data/Train/0.jpg", "width": 1024, "height": 768 },
  "global_vibe": { "...": "..." },
  "trigger_anchors": []
}
```

| 字段 | 必填 | 责任方 | 作用 |
|---|---:|---|---|
| `schema_version` | 是 | 视觉层 | 固定为 `2.3`，防止版本错配 |
| `id` | 是 | 视觉层 | 稳定记录标识，不使用易变化的绝对路径 |
| `image` | 是 | 视觉层 | 正规化图像路径和 EXIF 修正后的尺寸 |
| `global_vibe` | 是 | VLM + 程序 | 环境层、氛围和底噪控制参数 |
| `trigger_anchors` | 是 | 检测/融合管线 | 可支持声音联想的视觉证据及空间信息 |

`image.path` 必须是数据集根目录相对路径，使用正斜杠 `/`，禁止盘符、绝对路径和 `..` 路径穿越。

---

## 2. `global_vibe`：环境层

`global_vibe` 描述画面主导的物理环境和整体氛围，不描述单个物体。

| 字段 | 取值/规则 | 来源 |
|---|---|---|
| `scene_type` | `scene_type_vocabulary.json` 中的 424 个叶子场景值，或 `none`/`other_*` 兜底 | VLM 归一化 |
| `secondary_scene_types` | 同一词表内，最多 2 个；不能与主场景或彼此重复 | VLM 归一化 |
| `scene_group` | 由 `scene_type` 查词表生成的 20 个场景组 | 程序查表，不由 VLM 重复判断 |
| `mood` | `neutral/calm/cozy/cheerful/lively/majestic/mysterious/melancholic/tense/eerie` | VLM 归一化 |
| `warmth` | `warm/neutral/cool` | VLM 归一化 |
| `time_of_day` | `dawn/morning/noon/afternoon/dusk/night` | VLM 归一化 |
| `brightness` | `0.0–1.0` | 程序从图像计算，不由 VLM 输出 |

`scene_type` 判断主导物理环境，不把天气、时段、情绪或显眼物体塞进场景字段。无稳定物理环境的截图、文档、纯人像、微距和孤立物体特写使用 `none`。

---

## 3. `trigger_anchors`：实体证据层

锚点是“可以支持某种声音联想”的可观察视觉证据，不表示声音正在发生，也不直接决定音量或素材。每个 `anchor_id` 必须来自 87 项锚点词典；普通 `person` 不属于锚点。

```json
{
  "anchor_id": "visible_bird",
  "bbox_norm": { "format": "xyxy", "x_min": 0.72, "y_min": 0.18, "x_max": 0.86, "y_max": 0.34 },
  "confidence": 0.91,
  "source": "yoloe",
  "depth_hint": null
}
```

| 字段 | 规则 |
|---|---|
| `anchor_id` | 87 项锚点词典中的唯一值 |
| `bbox_norm` | EXIF 修正后原图上的归一化 `xyxy` 框，坐标在 `[0,1]` |
| `confidence` | 视觉检测可信度，不得直接换算成音量 |
| `source` | `yoloe`、`yolo_world`、`grounding_dino`、`vlm` 或 `manual` |
| `depth_hint` | 可选的相对单目深度提示；MVP 可为空 |

动作锚点优先于同一证据的静态锚点，强证据优先于弱证据。同一视觉证据不得重复输出互为强弱版本的框。`region_context` 只支持宽环境候选，不按框中心生成点声源 HRTF。

正式锚点由检测管线负责；VLM 的旧自由词映射只能作为弱证据或兼容输入，不能替代正式检测。

---

## 4. 音频层使用边界

音频层将 `scene_type/scene_group` 映射为环境床，将 `anchor_id` 映射为受控 `sound_id`，再生成 `2.0-mono` 或 `2.0-binaural` 播放计划。

- 检测置信度、深度值和框面积参与候选门控或空间参数，不直接控制基础音量。
- 真实素材必须在 Manifest 中可解析；缺失或无法解码时必须报告错误，不得静默用其他声音冒充。
- 只有播放计划明确声明 `noise_bed` 时，才允许生成程序底噪。
- VLM 不可用时可以使用默认氛围，但必须在 UI、日志或演示记录中标记 `default_fallback`，不能计入 VLM 识别质量。
- “完整流程跑通”必须包含视觉记录、播放计划、真实素材加载/解码和实际播放；仅生成 JSON 播放计划只能称为“接口链路跑通”。

播放计划的空间门控和单声道回退规则详见 [单声道回退播放计划格式说明](playback/单声道回退播放计划格式说明.md) 与 [双耳空间播放计划格式说明](playback/双耳空间播放计划格式说明.md)。

---

## 5. 各线当前接口

| 线 | 输入 | 输出 | 验收 |
|---|---|---|---|
| 视觉-氛围 | 图片 | `global_vibe` | 受控词表、默认回退有标记 |
| 视觉-检测 | 图片 + 预处理 | `trigger_anchors` | 87 锚点、EXIF 修正、归一化框 |
| 音频决策 | 一条 v2.3 视觉记录 | 播放计划 | 场景/锚点映射和安全门控 |
| 播放端 | 播放计划 + Manifest | 实际声景 | WAV 可加载、无静默失败、可试听 |

视觉层和音频层可以独立使用手写 v2.3 记录开发，但集成测试必须使用真实视觉记录和真实素材。

---

## 6. 变更流程

任何契约字段、枚举或语义变更必须：

1. 在团队中同步并确认视觉、音频、素材三线影响。
2. 同时修改 `contracts/scene_contract.schema.json` 和本文档。
3. 破坏性改动升主版本；向后兼容的可选字段升次版本。
4. 在下方 CHANGELOG 记录原因、影响和迁移方式。
5. 运行 `python scripts/validate_examples.py`，并补充对应的 v2.3 测试。

### CHANGELOG

- **v2.3（2026-08-17）** —— 团队正式批准视觉记录 2.3 作为主契约。由 v1.0 的 `entities[]` 迁移为 `id/image/global_vibe/trigger_anchors[]`；场景收敛到 424 叶子词表，锚点收敛到 87 项词典，`scene_group` 改为程序查表，`brightness` 改为程序计算，并补充归一化框、检测来源和可选深度提示。
- **v1.0（2026-07-09）** —— 历史冻结版本，保留用于旧样例、旧批处理结果和兼容代码，不再作为新视觉记录输出格式。
