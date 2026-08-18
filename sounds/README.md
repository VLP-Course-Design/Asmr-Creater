# sounds —— 素材库(一等交付物)

素材库不是「下载一堆 wav 就完事」,它是需要专门维护的一等交付物,**版权要能写进报告**。

## 目录结构

```
sounds/
├── ambient/                    # 长循环环境床
│   ├── rain/ forest/ cafe/ ocean/ city/        # v1.0 旧目录(已有真实素材)
│   └── ocean_coast_bed/ forest_day_bed/ ...    # v2.3 的 20 类场景环境母版
├── triggers/                   # 触发音 / 锚点关联声音
│   ├── cat/ bird/ cup/ book/ keyboard/ ...     # v1.0 旧目录(已有真实素材)
│   └── cat_purr/ bird_chirp/ page_turn/ ...    # v2.3 的 66 类 sound_id
├── trigger_map.json            # v1.0 标签 → 素材目录 映射表
├── v23_sound_id_bridge.json    # 过渡桥接:v2.3 sound_id → v1.0 目录(见下)
├── v23_registry.json           # 🎯 v2.3 采集清单(角色/时长/变体数/对应锚点)
└── metadata.csv                # 每个文件的元数据(版权/时长/来源,报告直接用)
```

> 空目录不进 Git,每个子目录放了 `.gitkeep` 占位,放入真实素材后可删。

## 当前状态:v2.3 素材已补齐，保留兼容桥接

正式视觉/音频流程用 66 个 `sound_id`(`cat_purr`/`bird_chirp`)命名；当前素材库已满足 66 类触发音和 20 类环境音的 MVP 变体要求。历史 v1.0 目录仍保留用于兼容，因此:

- [`v23_sound_id_bridge.json`](v23_sound_id_bridge.json) 仍为历史兼容映射，正式同名目录优先；
- 前端播放时**优先**找与 `sound_id` 同名的目录(如 `triggers/bird_chirp/`),里面一旦有真实 wav 就自动改用它,不再走桥接 —— 素材线补齐素材不需要改任何代码;
- 素材缺失或无法解码时必须报告错误，不得静默用合成音冒充真实素材；桥接表和 v1.0 旧目录待试听验收后再决定清理。

查看当前覆盖率:

```bash
python scripts/check_sounds_coverage.py            # 汇总 + 缺失清单
python scripts/check_sounds_coverage.py --detail   # 逐条列出变体
```

## 三件事(素材线的工作)

1. **按 [`v23_registry.json`](v23_registry.json) 备素材**:它列出了 66 类触发音 + 20 类环境音各自的**角色**(loop/texture/trigger/long_tail_trigger)、**目标时长**、**正式 MVP 最少变体数**、以及**对应哪些视觉锚点**。文件名用 `<sound_id>_<两位变体号>.wav`,放进 `triggers/<sound_id>/` 或 `ambient/<sound_id>/`。
2. **填元数据** [`metadata.csv`](metadata.csv):每个文件记标签、时长、是否可循环、默认音量、**许可协议、来源 URL**。报告的「数据/素材来源」与版权说明直接由它生成。
3. **格式统一**:WAV PCM 48kHz,24-bit 优先。局部点声源(鸟鸣/翻页/脚步)优先**单声道**便于 HRTF 定位;雨/海浪/交通等宽环境声保留**立体声**。详细的录制、转换、响度、验收标准见 [`docs/playback/ASMR声音素材库准备与采集规范.md`](../docs/playback/ASMR声音素材库准备与采集规范.md)。

## 素材来源(优先 CC0 / 免版税)

当前素材元数据记录的条目主要来自 **Freesound 的 CC0 条目**(见 `metadata.csv` 的 `source_url`)，这是最省心的路子。可用渠道与注意事项:

| 渠道 | 注意 |
|---|---|
| [Freesound](https://freesound.org/) | 逐条查许可,**筛 CC0**;CC BY 需履行署名;排除 CC BY-NC |
| [Pixabay](https://pixabay.com/sound-effects/) | 允许使用和修改,但限制把素材本身作为独立文件再分发 |
| [Wikimedia Commons](https://commons.wikimedia.org/) | 每个文件许可不同,不能当作平台统一授权 |
| [Sonniss GDC Bundle](https://sonniss.com/gdc-bundle-license/) | 可在项目中使用和修改,限制原样转售 |

**自行录制**更适合这批室内拟音:键盘、鼠标、翻页、纸张、书写、时钟、风扇、水壶、杯子、餐具、门、布料、扫地、烹饪、脚步、踩雪 —— 手机录即可,后期用 ffmpeg 统一转 48kHz WAV(命令见采集规范 §9.3)。一次室内拟音日能覆盖 20~25 类。

**不要**:视频网站/影视/游戏截取的音轨、来源不明的「免费音效」聚合站、只限个人或非商业用途的素材、含可辨识人声或音乐的环境录音。人声 / 旁白 / TTS 全部划到 MVP 外(`triggers/walla/` 有意留空)。

## 工作量提示

按采集规范的分级:**最小闭环**是 66 类各 1 份(先打通链路);**正式 MVP** 循环类各 2 份、触发类各 3 份(约 170~200 份)才能避免机械重复。建议先按真实数据里锚点出现的频率排优先级,而不是按词表顺序平均用力。
