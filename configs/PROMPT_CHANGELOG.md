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
