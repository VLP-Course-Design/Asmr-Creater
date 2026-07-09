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
from src.vision.pipeline import image_to_scene   # 视觉线产出(待建)
from src.common import validate_scene

scene = image_to_scene(image_path)
validate_scene(scene)          # 合流处再校验一次,双保险
# 交给音频层渲染 → wav → 前端播放
```

## 待建

| 文件     | 说明                                            |
| -------- | ----------------------------------------------- |
| `app.py` | Gradio 应用入口。建议先跑通「选样例图→出声」链路 |

## 工程提醒

`pyo` 是本地音频服务器,网页在线播放大概率要先渲染成 wav 再传前端。这条路径早点验证(见 audio/README)。
