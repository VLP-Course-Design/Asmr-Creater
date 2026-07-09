"""音频层:一份 Scene Contract JSON → 一路混好的双声道声音。

五个步骤(见 docs/MVP_guide.md 三-2):
  1. 参数解析      mapper.py    JSON → 音频控制参数(连续线性映射)
  2. 底噪生成      noise.py     pyo 的 White/Pink/BrownNoise + 动态滤波
  3. 音效触发      triggers.py  查 trigger_map,随机抽变体播放
  4. 空间渲染      panner.py    据 x 算左右声道增益(恒定功率平移)
  5. 多轨混流      mixer.py     底噪 + 各音效 → 一路双声道输出

音频层从第一天起就靠 contracts/examples/*.json 独立开发,不等视觉层。
"""
