# ui —— 界面与集成层

**职责**:把视觉层与音频层接起来,套一个极简 Web 界面。这是三线合流的地方。

## 界面要素(MVP_guide 三-4)

- 图片上传 / 从数据集选择
- 显示识别结果(标签 + 边界框)
- 播放 / 暂停按钮
- **每条音轨一个音量滑块**(对应「保留可自行调整各音效」)
- 文字 prompt 输入框:界面留位,但**先禁用**,标注「未来功能」(开放词汇 / 声景 DIY)

## 集成方式

```python
# 批量模式: 视觉管线全量运行 → final_structured_results.jsonl
# python -m src.vision.vlm_yolo_fusion --image_dir ./data ...

# 单图模式: 后端推理服务供 UI 调用
from src.ui.app import image_to_scene
from src.common import validate_scene

scene = image_to_scene(image_bytes)
validate_scene(scene)          # 合流处再校验一次,双保险
# 交给前端 Web Audio 渲染
```

## 已有

| 文件            | 说明                                                                                    |
| --------------- | --------------------------------------------------------------------------------------- |
| `app.py`        | **后端推理服务**。提供 `/infer` 端点(接收图片→返回 Scene Contract JSON)与 `/` 页面服务。零额外依赖(标准库 HTTP 服务)。启动: `python src/ui/app.py --port 5000` |
| `web/index.html`| 沉浸式声景工作台单文件。**功能已跑通**。`CONFIG.BACKEND=true` 时上传图片走后端 `/infer`,后端返回 YOLO 检测结果(entities + bbox)并渲染。详见下方。 |
| `web/samples/`  | 4 张样例图放置目录,缺图自动回退占位框。需要什么图见 `web/samples/README.md`。 |

### 网页端已实现的功能

| 功能     | 现状                                                                                                       |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| **选图** | 加载 `samples/*.jpg` 并叠加检测框;图片缺失自动回退虚线占位框,不报错                                       |
| **上传** | 真实读取文件 → Canvas 缩到 64×64 **真实分析平均亮度与冷暖** → 产出合法 Scene Contract(`brightness`/`warmth`/`base_noise`/`time_of_day`/`mood` 全部由画面算出) |
| **播放** | **Web Audio API 真实合成**:白/粉/棕噪音实时生成 + 低通(`brightness` 驱动)+ 每个实体一条带通噪声轨(音色查 `VOICE` 预设,镜像 `trigger_map.json`)+ `StereoPanner`(`x` 驱动)。音量滑块真控增益,**声像条可拖拽**,有主音量 |
| **校验** | 前端轻量契约校验,镜像 `contracts/scene_contract.schema.json`;非法数据会红条报错 |
| **导出** | 「下载 Scene Contract」按钮导出当前 JSON,方便喂给音频线做联调 |

> 已实测:前端校验器对 `contracts/examples/` 5 份样例与页面内置 4 个场景判定全部通过,非法数据能拦截;三种噪声算法输出均在有效范围无 NaN;303 种亮度×冷暖组合产出的契约 100% 合法。

### 接后端(一行改动)

```js
const CONFIG = { BACKEND:true, ENDPOINT:"/infer" };   // 页面脚本顶部
```
后端 `/infer` 接收 `multipart/form-data` 的 `image` 字段,返回一份 Scene Contract JSON 即可。前端会自动校验、渲染检测框(用 `entities[].bbox`)、重建音轨。

> **注意**:用 `file://` 直接打开时,部分浏览器禁止读取本地图片像素,上传分析会提示改用
> `python -m http.server 8000` 访问。样例场景与播放功能不受影响。

## 后端服务 (`app.py`) 架构

```
浏览器上传图片 ──POST /infer──▶  app.py (HTTP 服务)
                                    │
                                    ├─ load_and_preprocess_image()  # 预处理
                                    ├─ YoloDetector.detect()        # YOLO 推理
                                    └─ image_to_scene()             # 组装 JSON
                                       │
                                       ▼
                                   Scene Contract JSON
                                       │
                                       ▼
                              前端 Web Audio 渲染声景
```

**启动**:
```bash
python src/ui/app.py --port 5000
# 浏览器打开 http://127.0.0.1:5000
# 上传一张图片,YOLO 自动检测物体,Web Audio 实时合成声景
```

**API 契约**:
- `POST /infer`: multipart/form-data, `file` 字段带图片
- 返回: 符合 `contracts/scene_contract.schema.json` 的 JSON
- `GET /`: 返回 UI 页面 (`web/index.html`)

**设计要点**:
- YOLO 模型在启动时加载一次,所有请求复用(避免每次推理重新加载)
- 单图 demo 模式下 global_vibe 使用中性默认值,前端 Canvas 分析可覆盖
- 零额外依赖: HTTP 服务基于标准库 `http.server`,图片解析自实现
- 上传图片写入临时文件,推理完成后自动清理

## 工程提醒

`pyo` 是本地音频服务器,网页在线播放大概率要先渲染成 wav 再传前端。这条路径早点验证(见 audio/README)。
