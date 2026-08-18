# 播放计划转换演示子项目

本项目读取一条视觉层JSON记录（schema 2.3），始终先生成单声道播放计划；当所有实际入选的空间候选锚点都具有合格的相对深度信息时，再额外生成双耳HRTF空间播放计划。

## 1. 当前能力

```text
输入一条视觉记录
  → 校验2.3字段、锚点和边界框
  → 场景映射主环境声
  → 87视觉锚点映射66声音语义
  → 根据置信度×推断强度×助眠安全筛选最多2个前景层
  → 总是输出2.0-mono单声道计划
  → 检查实际入选锚点的depth_hint
      ├─ 全部通过 → 额外输出2.0-binaural计划
      └─ 任一失败 → 不输出双耳计划，并在报告中记录原因
```

默认空间门控：

- 至少有一个实际入选的空间候选；
- 每个候选都有完整 `relative_monocular` 深度；
- `class != unknown`；
- 所有 `uncertainty < 0.35`；
- 所有 `region_spread <= 0.50`。

双耳计划中的实体位置使用框中心，虚拟距离使用相对深度。只有鸟、蜜蜂、行人等少量活动锚点启用受限制的确定性微动；固定设备保持静止。

## 2. 目录结构

本 demo 已按项目既有分层拆分到各自目录,不再是独立子项目:

```text
src/audio/playback_converter.py                转换器源码
configs/playback/                               决策、场景映射和占位Manifest
  decision_settings.json
  scene_audio_profiles.json
  audio_manifest.json
contracts/scene_contract.schema.json             正式视觉记录规范 2.3
contracts/playback_proposal/                    词表与历史提案镜像
  scene_type_vocabulary.json
  recommended_structured_record_example.json
  examples/
    with_depth/                                 带合格深度的模拟视觉记录
    without_depth/                              不带深度的模拟视觉记录
docs/playback/                                  格式说明与采集规范(本文件所在目录)
scripts/
  run_playback_demo.ps1                         一键运行两个示例
  test_playback_converter.py                    单元测试
outputs/playback/                               本地生成的播放计划和报告(已 gitignore,需自行运行生成)
```

## 3. 环境要求

- Windows PowerShell；
- Python 3.10或更高版本；
- 不需要安装第三方Python包。

检查Python：

```powershell
python --version
```

如果系统没有名为 `python` 的命令，可将解释器完整路径临时设置为：

```powershell
$env:PLAYBACK_PYTHON = 'C:\path\to\python.exe'
```

`run_playback_demo.ps1` 会依次查找 `PLAYBACK_PYTHON`、`python` 和 `py`。

## 4. 一键运行

在PowerShell中执行(仓库根目录下):

```powershell
Set-Location '<仓库根目录>'
.\scripts\run_playback_demo.ps1
```

脚本会运行两个输入：

1. `contracts/playback_proposal/examples/with_depth/example_coastal_bird_with_depth.json`
   - 始终生成单声道计划；
   - 深度质量通过，额外生成双耳计划。
2. `contracts/playback_proposal/examples/without_depth/example_study_keyboard_without_depth.json`
   - 生成单声道计划；
   - 因 `DEPTH_HINT_MISSING` 不生成双耳计划。

## 5. 运行自己的输入

在仓库根目录下:

```powershell
python .\src\audio\playback_converter.py `
  'D:\path\to\one_visual_record.json' `
  --output-dir '.\outputs\playback\my_case' `
  --seed 18432 `
  --duration 1800
```

不传 `--config-dir` 时默认读取 `configs/playback/`。输入既可以是裸 `example_record` 对象，也可以是顶层含有 `example_record` 的说明JSON。

无限时长：

```powershell
python .\src\audio\playback_converter.py '.\contracts\playback_proposal\examples\with_depth\example_coastal_bird_with_depth.json' --duration null
```

未提供 `--seed` 时，程序从记录 `id` 生成稳定种子。相同输入、配置和素材Manifest会得到可复现结果。

## 6. 输出文件

每条输入至少输出：

```text
<id>.mono.playback-plan.json
<id>.conversion-report.json
```

空间门控通过时还输出：

```text
<id>.binaural.playback-plan.json
```

转换报告包含是否通过空间门控、评估的锚点下标、最大不确定性以及失败原因。

## 7. 当前素材是占位引用

真实环境音、底噪和触发音尚未准备，所以 `config/audio_manifest.json` 使用占位 `asset_id` 和未来路径。转换器不会打开音频字节，只验证计划所需的素材引用是否能在Manifest中解析。

这意味着：

- 生成的JSON计划可以用于开发、Schema设计和前端调度测试；
- 当前不能真正播放，因为对应WAV文件尚不存在；
- 占位环境素材虽标记 `seamless_verified=true`，只是为了演示计划生成，替换真实文件后必须进行实际循环试听并更新元数据。

加入真实素材时：

1. 把环境音放进项目实际的素材目录(参考 [`sounds/`](../../sounds/) 现有布局,或按需扩展);
2. 把局部触发和纹理放进对应的触发音目录;
3. 更新 `configs/playback/audio_manifest.json` 的 `asset_id`、路径、时长、声道、响度、真峰值、许可证和SHA-256；
4. 删除 `placeholder=true`；
5. 对循环素材实际试听后再设置 `seamless_verified=true`。

> 注意：本 demo 的 66 个 `sound_id` 命名与现有 [`sounds/trigger_map.json`](../../sounds/trigger_map.json) 的标签体系(17 个 key)不是同一套词表,尚未统一,接入真实素材前需要三线先对齐命名方案。

## 8. 配置说明

### `decision_settings.json`

- `visual_spec_path` 指向仓库根目录下的 `contracts/playback_proposal/recommended_structured_record_example.json`，这里只复用 87 锚点与 66 声音映射；视觉记录契约本身以 `contracts/scene_contract.schema.json` 为准；
- 控制候选分数、最多前景层数、深度门限及允许微动的锚点；
- 修改阈值应升级 `config_version` 或 `policy_version`。

### `scene_audio_profiles.json`

当前只覆盖两个模拟场景和安全回退。正式使用前应按 `scene_type_vocabulary.json` 扩充精确场景及20个场景组映射。

### `audio_manifest.json`

登记计划可引用的具体素材。视觉输入和播放计划都不保存真实绝对文件路径。

## 9. 运行测试

```powershell
Set-Location '<仓库根目录>'
python .\scripts\test_playback_converter.py
```

测试验证：

- 有合格深度时生成单声道和双耳两份计划；
- 无深度时只生成单声道计划；
- 回退原因是结构化错误码；
- 双耳输出为2声道，单声道输出为1声道。

## 10. 设计边界

- 本项目生成播放计划，不渲染或合成真实音频。
- 每次都保留单声道计划；双耳计划是可选增强输出。
- 空间门控只检查经过映射、安全和层数预算后实际入选的锚点，无关检测结果不会阻止双耳输出。
- 单张图片只构造前方虚拟声场，不能证明声源位于听者后方。
- 框大小目前只写入视觉证据和声源宽度，不转换为距离；没有可靠实体尺寸先验时，相对距离只来自 `depth_hint.value`。
- `confidence` 不直接控制音量，深度和框面积也不直接控制基础音量。
