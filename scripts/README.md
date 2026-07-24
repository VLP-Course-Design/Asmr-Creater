# scripts —— 运行与测试脚本

此目录包含 ASMR-Creater 项目的运行、可视化和测试脚本。

---

## 第二人脚本

### `run_vision_pipeline.py` — 预处理 + YOLO 检测演示

**用途**: 演示步骤 1（图像预处理）和步骤 2（YOLO 检测）的完整管线。

**运行**:
```bash
python scripts/run_vision_pipeline.py
```

**流程**:
1. 递归扫描 `IMAGE_DIR`（默认 `./data/Val`）下的所有图片
2. 调用 `batch_load_images()` 批量预处理（Letterbox 640×640 + VLM 224×224）
3. 打印内存中数据结构的元信息
4. （可选）保存处理后的 Letterbox 图片到 `OUTPUT_DIR`
5. （可选）运行 YOLO 检测演示（仅前 3 张，避免耗时过长）

**配置项**（脚本顶部变量）:

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `IMAGE_DIR` | `./data/Val` | 图片目录 |
| `TARGET_SIZE_YOLO` | `(640, 640)` | YOLO 目标尺寸 |
| `TARGET_SIZE_VLM` | `(224, 224)` | VLM 预留尺寸 |
| `SAVE_PROCESSED` | `True` | 是否保存 Letterbox 图片到硬盘 |
| `OUTPUT_DIR` | `./processed_output` | 输出目录 |
| `RUN_YOLO` | `True` | 是否运行 YOLO 检测演示 |

**适用场景**: 人工复核预处理效果、验证 YOLO 模型是否正确加载、检查内存数据流是否完整。

---

### `visualize_stage2.py` — 端到端可视化测试

**用途**: 使用 ultralytics 内置样例图片（`bus.jpg`）跑通完整管线，在图片上绘制检测框、空间位置标签和图例，生成可视化输出。

**运行**:
```bash
python scripts/visualize_stage2.py
```

**流程**:
1. 加载 YOLO 模型（yolo11n.pt, CPU）
2. 对样例图片执行预处理 → YOLO 检测
3. 构造模拟 VLM 数据（含 COCO 实体 + 开放词汇实体）
4. 调用 `merge_structured_payload()` 融合 → 输出 Scene Contract JSON
5. 在原图上绘制:
   - 彩色检测框（不同类别不同颜色）
   - 标签文本：`类别 置信度 | 水平方位 | 距离`
   - 图例：VLM 实体匹配状态（✅ YOLO 匹配 / ❌ 开放词汇预留）
6. 保存 `stage2_visualization_output.jpg`

**模拟 VLM 数据**（内嵌在脚本中）:
```python
"suggested_entities": [
    {"name": "bus", "state": "parked"},        # COCO 类,期望匹配
    {"name": "person", "state": "waiting"},     # COCO 类,期望匹配
    {"name": "car", "state": "driving"},        # COCO 类,期望匹配
    {"name": "traffic light", "state": "green"}, # COCO 类,可能不匹配
    {"name": "香薰机", "state": "static"}        # 开放词汇,必然不匹配
]
```

**适用场景**: 演示答辩视频、可视化验证检测结果、检查 YOLO+VLM 融合逻辑。

---

### `test_vision.py` — 完整功能测试套件

**用途**: 对第二人全部代码进行 7 项自动化测试，覆盖所有核心功能和边界情况。

**运行**:
```bash
python scripts/test_vision.py
```

**测试清单**:

| # | 测试项 | 覆盖内容 |
|---|--------|----------|
| 1 | 预处理管线 | Letterbox 形状验证 (640×640×3)、VLM 缩放 (224×224×3)、字段完整性、scale/padding 正确性 |
| 2 | load_jsonl 字段校验 | 正常数据解析、缺少必需字段警告、空行/损坏行容错 |
| 3 | 实体匹配策略 | 精确匹配、大小写不敏感、复数→单数、无匹配返回 None、Detection 对象属性访问 |
| 4 | merge_structured_payload | Scene Contract 输出格式、YOLO 匹配实体的 x/depth/conf/bbox/source、VLM 实体默认值 |
| 5 | process_batch | 成功条目融合、失败条目保留 error 字段、路径匹配 |
| 6 | Scene Contract Schema 校验 | 输出通过 `contracts/scene_contract.schema.json` 的 JSON Schema 校验 |
| 7 | 坐标映射 | `_compute_horizontal` 阈值 (±0.33/0.67)、`_compute_distance` 阈值 (8%/25%) |

**适用场景**: 修改代码后回归测试、CI/提交前检查、验证功能完整性。

---

## 第一人/基础架构脚本

### `validate_examples.py` — Scene Contract 样例校验

**用途**: 校验 `contracts/examples/` 下所有手写样例是否符合 Schema。

**运行**:
```bash
python scripts/validate_examples.py
```

**适用场景**: 契约变更后验证、CI 检查。

---

## 依赖要求

所有脚本需要以下包（安装命令）:

```bash
pip install opencv-python ultralytics numpy jsonschema pyyaml openai
```

**说明**:
- `opencv-python` — 图像读写与预处理（必需）
- `ultralytics` — YOLO 模型推理（必需）
- `numpy` — 数组运算（必需）
- `jsonschema` — Scene Contract 校验（测试需要）
- `pyyaml` + `openai` — VLM 氛围分析（第一人模块需要，第二人脚本不依赖）

