# sounds —— 素材库(一等交付物)

素材库不是「下载一堆 wav 就完事」,它是需要专门维护的一等交付物,**版权要能写进报告**。

## 目录结构

```
sounds/
├── ambient/            # 长循环底噪备用(pyo 实时底噪之外的兜底)
│   ├── rain/  forest/  cafe/  ocean/  city/
├── triggers/           # 短音效,按检测标签命名,每类 3~5 个变体
│   ├── cat/            #   cat_purr_1.wav  cat_meow_1.wav ...
│   ├── bird/  cup/  book/  keyboard/  window/  water/ ...
├── trigger_map.json    # 标签 → 素材目录 映射表(音频层查它)
└── metadata.csv        # 每个文件的元数据(版权/时长/来源,报告直接用)
```

> 空目录不进 Git。每个子目录放了一个 `.gitkeep` 占位,放入真实素材后可删。

## 三件事(素材线的工作)

1. **备素材**:按 [`trigger_map.json`](trigger_map.json) 里的 `folder` 建目录,每类放 **3~5 个微小变体**(音频层 `random.choice` 抽取,提升真实感,低成本高收益)。
2. **维护映射表** [`trigger_map.json`](trigger_map.json):新增一个可发声物体 = 在此登记一行 + 往对应目录放素材。key 用**小写单数**,须与视觉线产出的 `entities[].name` 对齐。
3. **填元数据** [`metadata.csv`](metadata.csv):每个文件记标签、时长、是否可循环、默认音量、**许可协议、来源 URL**。报告的「数据/素材来源」与版权说明直接由它生成。

## 素材来源(优先 CC0 / 免版税)

Freesound(搜索时左侧筛 CC0)、Pixabay、BBC Sound Effects(教育用途)、Adobe Audition 免费包、Zapsplat。**别去百度搜「音效下载」。** 人声 / 旁白 / TTS 全部划到 MVP 外。

## 工作量提示

COCO 80 类里真正常在生活场景出现、又有发声意义的其实就一二十类。先把 `trigger_map.json` 里这十几类的映射和素材备齐,demo 就够惊艳了。别贪多。
