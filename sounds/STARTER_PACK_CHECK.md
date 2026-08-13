# 起步素材包验收说明

验收日期：2026-07-22

## 当前交付

- 触发音：14 类，每类 1 个 WAV
- 环境音：5 类，每类 1 个 WAV
- 合计：19 个 WAV，约 109.06 MiB
- 许可：全部 CC0，来源链接与署名信息见 `metadata.csv`
- 人声目录 `triggers/walla/` 保持为空：人声、旁白和 TTS 不在 MVP 范围内

触发音类别：`cat`、`bird`、`dog`、`cup`、`book`、`keyboard`、`clock`、`tv_static`、`window`、`water`、`kettle`、`fire`、`chime`、`espresso`。

环境音类别：`rain`、`forest`、`cafe`、`ocean`、`city`。

## 验收结果

- `metadata.csv` 共 19 条记录，文件路径均存在且没有重复
- 19 个文件均通过 RIFF/WAVE 文件头与数据块检查
- 元数据时长与 WAV 实际时长误差均小于 0.01 秒
- `trigger_map.json` 中除 `walla` 外的每个素材目录均已有起步文件
- 最大文件为 `ambient/rain/rain_ambience_01.wav`，约 17.34 MiB

## 后续工作

这一批是“类型齐全”的起步素材，每类先放 1 个文件，用于尽早打通音频链路。正式丰富素材库时，再为高频类别补到每类 3–5 个轻微变体。
