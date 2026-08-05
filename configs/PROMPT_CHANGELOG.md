# Prompt 迭代记录

## v1 (2026-07-13) — 基础 global_vibe
- **目标**: 稳定输出 6 字段结构化 JSON
- **策略**: system prompt 定角色 + user prompt 内嵌完整受控词表 + few-shot 格式示例
- **问题发现**:
  - VLM 自创词汇 (serene/lonely/frightening 等) → 加模糊回退映射
  - JSON 格式错误 (单引号/反斜杠/尾逗号) → 多策略解析
  - 偶发漏字段 → partial 标记而非填假数据
- **通过率**: ~96%

## v2 (2026-07-13) — 新增 suggested_entities
- **变更**: prompt 增加 suggested_entities 数组字段
- **设计**: 让 VLM 列出有发声潜力的物体及状态,补 YOLO 认不出的物体
## v1 批量结果（已归档）
- 全量 2369 张用 v1 prompt 跑完
- 完整成功率 98.3%，partial 28 张，失败 12 张
- 结果归档为 outputs/global_vibe_results_v1.jsonl
- 保留作为 v2 对比 baseline
## v2 批量结果 (2026-07-14)
- 全量 2369 张用 v2 prompt 跑完
- 完整成功率 99.5% (2357/2369)，零 partial（针对性补缺策略生效）
- 85% 的图片至少识别出一个发声物体 (1999/2357)
- 失败 12 张 → outputs/failed_images/
- v1 vs v2 对比：partial 从 28 降到 0，成功率从 98.3% 升到 99.5%

## v3 (2026-08-04) — 模板空字符串化
- **变更**: 模板中示例值改为空字符串（mood/base_noise 等由示例值改为 ""）
- **动机**: AB 测试验证空字符串分布更合理（见 outputs/test_prompt_A_空字符串.jsonl、test_prompt_B_示例+禁止.jsonl）
- **备注**: 本条目由 prompts.yaml 注释与 outputs 测试文件整理，细节请角色 A 补充

## v4 (2026-08-05) — suggested_entities 增加 x 坐标（已搁置）
- **变更**: suggested_entities 每项增加 x 字段（实体中心水平位置，0.0=最左，1.0=最右）
- **状态**: 已提交后撤回并暂存（stash@{0}），暂不引入 x，故搁置；后续如需可恢复再议

## v5 (2026-08-05) — 强化 suggested_entities 指令，提升实体召回
- **变更**: 指令改为「仔细检查画面、宁多勿少、通常 2~6 个」，新增判定标准与常见漏项提示，示例加至 5 个
- **动机**: v3/qwen 实体召回仅 12.6%，v5 让 qwen 输出更多可发声实体
- **验证**: 20 张同图 AB —— qwen 4/20→12/20（提及 7→29）；100 张随机样本 —— 有实体图片 12.6%→45.0%
- **遗留**: 实体名命中 trigger_map 仍仅约 10%（归一化 + 素材表扩充属音频/素材线）
