# vision —— 视觉层（第二人负责模块）

**职责**: 一张图 → 一份符合 [Scene Contract](../../docs/json_contract.md) 的 JSON。**只产出 JSON,绝不碰音频代码。**

> 视觉层由两名成员协作完成：
> - **第一人**（氛围分析）：`vibe_vlm.py`、`batch_vibe.py` — 调用 VLM 输出 `global_vibe`
> - **第二人**（预处理/检测/融合）：`preprocess.py`、`base.py`、`yolo.py`、`vlm_yolo_fusion.py` — 本文档重点说明

---

## 数据流向

```
图片目录 (data/Train/*.jpg)
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│  preprocess.py  (步骤 1)                                  │
│  get_image_files() → batch_load_images()                 │
│  输出: [{'image_yolo': (640,640,3),                      │
│          'image_vlm': (224,224,3),                       │
│          'scale', 'pad_left', 'pad_top', ...}]            │
└────────────┬─────────────────────────────────────────────┘
             │ 内存数组 (杜绝重复读盘)
             ▼
┌──────────────────────────────────────────────────────────┐
│  yolo.py  (步骤 3)                                        │
│  YoloDetector.detect(preprocessed_data)                  │
│  输出: [{'image_path', 'detections': [Detection, ...]}]   │
│  内部: letterbox 坐标 → 原始空间坐标 → 归一化             │
└────────────┬─────────────────────────────────────────────┘
             │                    ┌─────────────────────┐
             │                    │ VLM JSONL 数据       │
             │                    │ (第三人产出)         │
             │                    │ global_vibe_results  │
             │                    │ global_vibe_failed   │
             │                    └──────────┬──────────┘
             │                               │
             ▼                               ▼
┌──────────────────────────────────────────────────────────┐
│  vlm_yolo_fusion.py  (步骤 4 + 步骤 5)                   │
│  load_jsonl() → process_batch() → merge_structured_payload()
│  输出: final_structured_results.jsonl                     │
│  格式: {schema_version, image, global_vibe, entities[]}   │
│  校验: src.common.validate_scene()                        │
└──────────────────────────────────────────────────────────┘
```

---

## 模块详解（第二人交付）

### 1. `preprocess.py` — 图像预处理

**对应任务**: 子任务 1

**核心函数**:

| 函数 | 功能 |
|------|------|
| `get_image_files(root_dir, recursive=True)` | 递归扫描目录，返回 `.jpg/.jpeg/.png` 路径列表（按字母排序） |
| `letterbox(img, target_size, fill_color)` | **保边缩放**：等比缩放至目标尺寸，灰边填充剩余区域。返回 `(resized, scale, (new_w,new_h), (pad_left,pad_top))` |
| `load_and_preprocess_image(path, target_size_yolo, target_size_vlm)` | 单张图像加载：BGR→RGB、Letterbox 640×640、VLM 简单缩放 224×224。返回包含 `image_yolo` 和 `image_vlm` 两个内存数组的字典 |
| `batch_load_images(paths, ...)` | 批量预处理入口，支持进度显示、错误跳过、可选落盘保存 |

**关键设计决策**:

- **内存流复用**: 返回 `image_yolo` (np.ndarray) 给下游 YOLO 直接消费，**杜绝重复读取磁盘**。2000+ 张图片场景下节省大量 I/O 时间。
- **Letterbox 而非拉伸**: 使用等比例缩放 + 灰边填充，防止图像变形导致 YOLO 检测精度下降。
- **双尺寸输出**: 同时产出 640×640 (YOLO) 和 224×224 (VLM 预留)，一次预处理满足两种模型需求。
- **错误隔离**: `load_and_preprocess_image()` 对异常返回 `None`，`batch_load_images()` 自动跳过失败图片，不中断整批处理。

**参数规格**（符合 YOLOv11 标准）:

| 参数 | 值 | 说明 |
|------|-----|------|
| YOLO target_size | `(640, 640)` | YOLOv11 标准输入尺寸 |
| VLM target_size | `(224, 224)` | 常见 VLM 输入尺寸（预留） |
| 填充颜色 | `(114, 114, 114)` | 灰色（ultralytics 默认） |
| 支持格式 | `.jpg`, `.jpeg`, `.png` | 大小写不敏感 |

---

### 2. `base.py` — 检测器抽象接口

**对应任务**: 子任务 2（适配器模式）

**核心类**:

| 类 | 角色 |
|----|------|
| `BaseDetector(ABC)` | 抽象基类，定义 `detect(preprocessed_data)` 和 `get_supported_classes()` 两个抽象方法 |

**设计理念**:

- **适配器模式**: 所有检测器实现同一接口。未来替换为 YOLO-World / Grounding DINO 只需新写子类，下游融合管线不改。
- **批量内存推理**: `detect()` 接收预处理模块的内存数组（非文件路径），避免重复 I/O。
- **错误隔离**: 单张图片失败不中断整批，在结果中标记 `error` 字段。

**接口契约**:

```python
class BaseDetector(ABC):
    @abstractmethod
    def detect(self, preprocessed_data: List[Dict]) -> List[Dict]:
        """输入: batch_load_images 返回值
           输出: [{'image_path', 'original_width', 'original_height',
                   'detections': List[Detection], 'error': str|None}]"""
    
    @abstractmethod
    def get_supported_classes(self) -> List[str]:
        """返回支持检测的类别名称列表"""
```

---

### 3. `yolo.py` — YOLO 检测器实现

**对应任务**: 子任务 2 + 子任务 3

**核心类**: `YoloDetector(BaseDetector)`

**初始化参数**（严格按任务规格）:

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `model_name` | `'yolo11n.pt'` | YOLOv11-Nano 轻量模型 |
| `device` | `'cpu'` | **强制 CPU**（确保无 GPU 环境可运行） |
| `conf_threshold` | `0.25` | 置信度阈值 |
| `iou_threshold` | `0.45` | NMS IoU 阈值 |
| `img_size` | `640` | 推理图像尺寸 |

**核心算法 —— 坐标映射**:

这是整个视觉层最关键的数值计算。YOLO 在 640×640 letterbox 图像上推理，输出 bbox 在 letterbox 空间。需映射回原始图像空间才能正确计算空间方位：

```
设 YOLO 输出 bbox 坐标为 (x_lb, y_lb)，预处理参数为 scale, pad_left, pad_top：

原始坐标 = (x_lb - pad_left) / scale
       y_orig = (y_lb - pad_top) / scale

归一化坐标 = x_orig / original_width
```

然后基于原始图像空间计算：
- **水平方位** (`_compute_horizontal`): `center_x / image_width < 0.33 → "left"`, `> 0.67 → "right"`, else `"center"`
- **距离估算** (`_compute_distance`): `box_area / image_area > 0.25 → "near"`, `> 0.08 → "medium"`, else `"far"`

**输出格式**: 每个检测结果以 [`Detection` dataclass](#共享数据结构) 输出，坐标归一化至 [0,1]。

**静态工具方法**:

| 方法 | 功能 | 阈值 |
|------|------|------|
| `_compute_horizontal(center_x, image_width)` | 水平方位分类 | left: <33%, center: 33-67%, right: >67% |
| `_compute_distance(bbox, image_width, image_height)` | 距离分类 | near: >25%, medium: 8-25%, far: ≤8% |

---

### 4. `vlm_yolo_fusion.py` — 结构化融合管线

**对应任务**: 子任务 4 + 子任务 5

**核心函数**:

| 函数 | 功能 |
|------|------|
| `load_jsonl(jsonl_path)` | 读取并校验 VLM JSONL 文件。校验 `image`, `path`, `global_vibe`, `suggested_entities` 四个必需字段。损坏行自动跳过并警告 |
| `merge_structured_payload(yolo_result, vlm_data)` | 单图融合：YOLO 物理检测 + VLM 语义实体 → Scene Contract JSON |
| `process_batch(yolo_results, vlm_success, vlm_failed)` | 批量融合：路径匹配 → 逐条调用 `merge_structured_payload` |
| `_match_entity_to_yolo(entity_name, yolo_detections)` | 实体名模糊匹配（4 级策略） |

**实体匹配策略**（由简到繁，忽略大小写）:

| 优先级 | 策略 | 示例 |
|--------|------|------|
| 1 | 精确匹配 | `cat` ↔ `cat` |
| 2 | 包含关系 | `dining table` 包含 `table` |
| 3 | VLM 复数 → YOLO 单数 | `cars` → `car` |
| 4 | YOLO 复数 → VLM 单数 | `scissors` 匹配 `scissor` |

**融合输出规则**:

| 匹配结果 | `detected_by_yolo` (→ `source`) | `physical_location` (→ `x`/`depth`) | `conf` |
|----------|-------------------------------|--------------------------------------|--------|
| 匹配成功 | `true` → `"yolo"` | 填入 YOLO 检测的归一化坐标 | YOLO 置信度 |
| 匹配失败 | `false` → `"vlm"` | `null` → `x=0.5, depth="mid"` | `0.5` (约定值) |

**失败条目处理**: VLM 推理失败的图片（来自 `_failed.jsonl`）仍输出到最终 JSONL，`image.error` 字段标记原因，`global_vibe` 给默认值，`entities` 为空数组。确保下游音频层知晓该图片不可用于音频生成。

**命令行入口**:

```bash
python -m src.vision.vlm_yolo_fusion \
    --image_dir ./data/Train \
    --vlm_success ./outputs/global_vibe_results.jsonl \
    --vlm_failed ./outputs/global_vibe_failed.jsonl \
    --output ./final_structured_results.jsonl
```

---

## 共享数据结构

### `Detection` dataclass（`detector.py`）

检测器与下游管线之间的标准数据格式，字段直接映射 Scene Contract 的 `entities[]` 元素：

```python
@dataclass
class Detection:
    name: str          # 标签名,小写单数 (如 "cat")
    x: float           # 归一化横坐标 0~1 (0=最左,1=最右)
    depth: str         # "near" | "mid" | "far"
    conf: float        # 置信度 0~1
    bbox: List[float]  # 归一化 [x1,y1,x2,y2]
    source: str        # "yolo" | "vlm" | "fused"
    
    def to_entity_dict(self, state=None) -> dict:
        """转为 Scene Contract entities[] 元素格式"""
```

---

## 输出格式对照 (Scene Contract v1.0)

融合管线的最终输出与 `contracts/scene_contract.schema.json` 严格对齐：

```json
{
  "schema_version": "1.0",
  "image": {
    "id": "42",
    "path": "data/Train/42.jpg",
    "width": 1024,
    "height": 768
  },
  "global_vibe": {
    "scene_type": "bedroom",
    "mood": "calm",
    "brightness": 0.28,
    "warmth": "cool",
    "base_noise": "brown",
    "time_of_day": "night"
  },
  "entities": [
    {
      "name": "cat",
      "state": "sleeping",
      "x": 0.22,
      "depth": "near",
      "conf": 0.91,
      "bbox": [0.12, 0.20, 0.32, 0.85],
      "source": "yolo"
    },
    {
      "name": "香薰机",
      "state": "diffusing",
      "x": 0.5,
      "depth": "mid",
      "conf": 0.5,
      "source": "vlm"
    }
  ]
}
```

---

## 运行与测试

```bash
# 完整功能测试 (无需真实图像,使用 mock 数据)
python scripts/test_vision.py

# 预处理 + YOLO 演示 (需要真实图片)
python scripts/run_vision_pipeline.py

# 端到端可视化 (使用 ultralytics 内置 bus.jpg)
python scripts/visualize_stage2.py

# 完整融合管线 (需要 VLM JSONL + 图片目录)
python -m src.vision.vlm_yolo_fusion \
    --image_dir ./data/Train \
    --vlm_success ./outputs/global_vibe_results.jsonl \
    --vlm_failed ./outputs/global_vibe_failed.jsonl \
    --output ./final_structured_results.jsonl
```

## 关键纪律

- 受控字段(`mood`/`warmth`/`base_noise`/`time_of_day`/`depth`)只能取词表内的值 —— 在 VLM prompt 里用 few-shot 钉死。
- `entities[].name` 要和 [`sounds/trigger_map.json`](../../sounds/trigger_map.json) 的 key 对齐(小写单数),否则音频层查不到素材。
- 检测器输出统一使用 `Detection` dataclass(归一化坐标)，接口见 `detector.py`。
- 换模型只改对应一个文件，不动契约。prompt 的迭代过程请留版本记录(报告要用)。
- 产出后务必自检：`validate_scene(scene)`，不合法会抛异常。
