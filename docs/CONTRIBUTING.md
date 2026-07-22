# 协作指南

本项目三条线(视觉 / 音频 / 素材)并行开发,靠一份**已冻结的 JSON 契约**解耦。为了不互相踩脚、也不把 `main` 搞乱,请按本文的流程走。

---

## 一分钟上手

```bash
git clone https://github.com/VLP-Course-Design/Asmr-Creater.git
cd Asmr-Creater

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
python scripts/validate_examples.py   # 应全部通过,说明环境 OK
```

数据集 `img_dataset/` 不在仓库里(约 1.7GB),需另行获取后放到该目录下。

**新成员必读顺序**:[json_contract.md](json_contract.md)(唯一接口,先看这个)→ 自己那层的 `src/<层>/README.md` → [MVP_guide.md](MVP_guide.md)(全局路线图)。

---

## 分支模型

`main` 是受保护的稳定分支,**不能直接 push**,所有改动必须走 Pull Request。

| 分支 | 用途 | 示例 |
| --- | --- | --- |
| `main` | 随时可跑的稳定版本,受 Ruleset 保护 | — |
| `feat/*` | 新功能 | `feat/audio-panning`、`feat/vision-preprocess` |
| `fix/*` | 修 bug | `fix/vlm-json-parse` |
| `docs/*` | 只改文档 | `docs/update-contract` |
| `chore/*` | 依赖、配置、脚手架 | `chore/add-ci` |

命名用**小写 + 连字符**,带上所属层次,让人一眼看出归属:`feat/audio-*`、`feat/vision-*`、`feat/sounds-*`、`feat/ui-*`。

---

## 标准工作流

```bash
# 1. 从最新的 main 开分支(每次开新分支前都同步一下)
git checkout main
git pull

git checkout -b feat/audio-panning

# 2. 开发 + 小步提交
git add src/audio/panner.py
git commit -m "feat(audio): 实现恒定功率 2D 声像平移"

# 3. 推到远端(第一次推需要 -u)
git push -u origin feat/audio-panning

# 4. 到 GitHub 开 PR → 等 1 个同学 review → 合并

# 5. 合并后清理
git checkout main
git pull
git branch -d feat/audio-panning
```

> 分支尽量**短命**:一个分支只做一件事,几天内合掉。长期不合的分支冲突会滚雪球。

---

## 提交信息规范

用 [Conventional Commits](https://www.conventionalcommits.org/) 格式,便于生成报告里的开发历程:

```
<类型>(<范围>): <一句话说明>
```

**类型**:`feat` 新功能 / `fix` 修 bug / `docs` 文档 / `refactor` 重构 / `test` 测试 / `chore` 杂务

**范围**:`vision`、`audio`、`sounds`、`ui`、`common`、`contracts`、`docs`

```bash
git commit -m "feat(vision): 补全 preprocess 批处理循环"
git commit -m "fix(audio): 修正 x=0.5 时左右增益不等的问题"
git commit -m "docs(contract): 补充 depth 字段取值说明"
```

说明用中文没问题,但要写**做了什么**,别写"更新"、"修改一下"这种无信息量的话。

---

## Pull Request 规范

**开 PR 前自查:**

- [ ] `python scripts/validate_examples.py` 全部通过
- [ ] 没有提交数据集、音频本体(`.wav/.mp3`)、`.env` 或任何密钥
- [ ] 只改了自己那层的文件(跨层改动见下方「分层纪律」)
- [ ] 已从最新 `main` rebase 或 merge,没有冲突

**PR 描述写清三件事:**

1. **做了什么** —— 一两句话
2. **为什么** —— 对应 MVP_guide 的哪一步 / 解决什么问题
3. **怎么验证** —— reviewer 跑什么命令、听什么效果能确认它work

音频相关的 PR,建议附一段渲染好的 wav 或录屏,否则 reviewer 没法判断效果。

**Review 规则:**

- 需要 **1 个同学 approve** 才能合并
- **不能自己批自己的 PR**(GitHub 强制)
- Review 意见必须全部 resolve 才能合并
- 推了新 commit 后,之前的 approve 会失效,需要重新 review

**合并方式**:推荐 **Squash and merge**,让 `main` 的历史保持一条干净的主线,每个功能一个 commit。

---

## 分层纪律(最重要的一条)

整个项目能并行开发,全靠这条边界:

- **视觉层只产出 JSON,绝不碰音频代码**
- **音频层只读 JSON,不关心图是怎么来的**
- 两层之间**只通过 [`contracts/scene_contract.schema.json`](../contracts/scene_contract.schema.json) 通信**

**契约已冻结。** 如果你觉得必须改契约(加字段、改取值范围),不要直接改:

1. 单独开一个 `docs/change-contract-xxx` 分支,**只改契约相关文件**
2. PR 里说明:为什么必须改、对另一层的影响、旧样例是否还兼容
3. **需要视觉线和音频线都 approve** 才能合并
4. 合并后同步更新 `contracts/examples/` 下的样例和 `docs/json_contract.md`

契约一动,两条线都要返工,所以这道门槛是故意设高的。

---

## 不要提交这些

`.gitignore` 已经挡掉了大部分,但仍需留意:

| 内容 | 原因 | 怎么办 |
| --- | --- | --- |
| `img_dataset/` | 1.7GB,GitHub 扛不住 | 已 ignore,另行分发 |
| `sounds/**/*.wav` 等音频本体 | 体积大、版权复杂 | 已 ignore;**但目录结构、`trigger_map.json`、`metadata.csv` 要提交** |
| API 密钥 / `.env` | **仓库是公开的**,泄露即作废 | 走环境变量,见下 |
| `.venv/`、`__pycache__/` | 环境产物 | 已 ignore |
| 模型权重 `.pt` / `.onnx` | 体积大 | 按需在 `.gitignore` 取消注释 |

**密钥处理规矩**:目前 VLM 走本地 Ollama,不需要密钥。将来如果改用云端 API(智谱 GLM-4V、通义千问-VL 等),密钥一律从环境变量读:

```python
import os
api_key = os.environ["ZHIPU_API_KEY"]   # 绝不写死在代码里
```

本地放进 `.env`(已 ignore),并在 `.env.example` 里留一份不含真实值的字段说明。

> ⚠️ 密钥一旦推上公开仓库,**删掉 commit 也没用**——历史仍可查,必须立刻去服务商后台吊销重发。

---

## 常见问题

**推 `main` 被拒,报 `GH013: Repository rule violations found`**

这是保护规则在正常工作。把改动挪到分支上:

```bash
git branch feat/my-work      # 把当前提交存到新分支
git reset --hard origin/main # main 退回远端状态
git checkout feat/my-work
git push -u origin feat/my-work
```

**PR 有冲突怎么办**

```bash
git checkout feat/my-work
git fetch origin
git merge origin/main        # 解决冲突后
git add .
git commit
git push
```

**改错分支了(该在 feat 上改,结果改在了 main)**

改动还没 commit 时,直接 `git stash` → 切分支 → `git stash pop` 即可。

---

## 素材贡献

往 `sounds/` 加素材时:

- 只从 **CC0 / 免版税**来源取(Freesound 筛 CC0、Pixabay、BBC Sound Effects 等)
- 每类物体准备 **3~5 个变体**,提升真实感
- **必须**在 [`sounds/metadata.csv`](../sounds/metadata.csv) 登记:标签、时长、是否可循环、默认音量、许可协议、来源 URL
- 新增标签要同步更新 [`sounds/trigger_map.json`](../sounds/trigger_map.json)

音频本体不进 Git,但**元数据和映射表必须进**——报告里的「素材来源与版权说明」直接由 `metadata.csv` 生成。

详见 [`sounds/README.md`](../sounds/README.md)。
