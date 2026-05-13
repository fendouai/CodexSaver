# CodexSaver

> 在不让 Codex 变笨的前提下，让它更便宜。

![CodexSaver](./CodexSaver.png)

CodexSaver 是一个 MCP 工具，它把 Codex 变成一个有成本意识的路由器。
低风险开发工作下放给更便宜的 worker LLM，高风险判断留给 Codex，并且返回足够清晰的交互信息，
让你明显感知到这个工具正在工作。

- 用更低成本处理测试、文档、搜索、解释类任务
- Codex 继续负责架构、安全、受保护域和最终审核
- 默认全局安装，一次配置后每个 Codex 工作区都能使用
- 默认 DeepSeek，同时支持 OpenAI、Anthropic、Gemini、Qwen、Ollama、LM Studio 等 provider
- provider 配置持久化到 `~/.codexsaver/config.json`
- 可选 worker 输出压缩，受统一配置和 CLI 控制
- 已通过测试、真实 DeepSeek 调用和全局 MCP launcher 检查

---

## 这个项目解决什么问题

大多数编码会话其实混着两类完全不同的工作：

- 昂贵的判断
- 廉价的执行

Codex 很擅长第一类，但用它去做大量第二类工作，往往太贵了。

CodexSaver 故意把这两件事拆开：

- `Codex` 负责推理、模糊需求、受保护域和审批
- 已配置的 worker provider 负责低风险、高吞吐的执行工作

它想建立的是这样一个模式：

```text
把昂贵模型用在判断上。
把便宜模型用在体力活上。
不要混用这两种价值。
```

---

## 用起来是什么感觉

CodexSaver 返回的不是一段静默 JSON。
它会附带一个 `interaction` 区块，让你一眼看出这次调用发生了什么：

```json
{
  "interaction": {
    "tool": "codexsaver.delegate_task",
    "mode": "delegated_execution",
    "headline": "CodexSaver delegated this task to the configured worker provider.",
    "route_label": "[CodexSaver] route=deepseek task_type=write_tests risk=low",
    "next_step": "Review the worker result and apply it only if the patch looks safe."
  }
}
```

你只需要理解三种状态：

- `preview`：只是预览路由，没有外部模型调用
- `delegated_execution`：委派执行已经完成
- `codex_takeover`：风险太高或任务太模糊，交回 Codex 处理

当压缩启用时，`interaction` 里还会带上压缩状态和级别。

---

## 快速开始

### 推荐：全局安装

```bash
git clone https://github.com/fendouai/CodexSaver
cd CodexSaver

python cli.py auth set --provider deepseek --api-key YOUR_API_KEY
python cli.py install
python cli.py doctor
```

这就够了。`python cli.py install` 会把 CodexSaver 写入全局 Codex MCP 配置
`~/.codex/config.toml`，并指向一个稳定启动入口：
`~/.codexsaver/codexsaver_mcp.py`。

之后任意 Codex 工作区都可以调用：

```text
codexsaver.delegate_task
```

只有当你想写入当前仓库自己的 `.codex/config.toml` 时，才需要使用：

```bash
python cli.py install --project
```

### Provider 配置

DeepSeek 是默认 provider，因为价格低，并且提供 OpenAI-compatible API。
切换 provider 只需要改一个参数：

```bash
python cli.py auth set --provider openai --api-key YOUR_API_KEY --model gpt-4o-mini
python cli.py auth set --provider anthropic --api-key YOUR_API_KEY --model claude-3-5-haiku-latest
python cli.py auth set --provider gemini --api-key YOUR_API_KEY --model gemini-2.0-flash
python cli.py auth set --provider qwen --api-key YOUR_API_KEY --model qwen-plus
```

本地模型：

```bash
python cli.py auth set --provider ollama --model llama3.1
python cli.py auth set --provider lmstudio --model local-model
```

任意自定义 OpenAI-compatible endpoint：

```bash
python cli.py auth set \
  --provider custom \
  --api-key YOUR_API_KEY \
  --base-url https://example.com/v1/chat/completions \
  --model your-model
```

查看内置 provider：

```bash
python cli.py auth providers
```

### Worker 输出压缩

压缩只影响委托给 worker 的调用，不影响 Codex 自己的输出。

查看当前配置：

```bash
python cli.py compression show
```

启用压缩：

```bash
python cli.py compression set --enabled true --level full
```

关闭压缩：

```bash
python cli.py compression set --enabled false
```

级别说明：

- `lite`：简洁回答，保留技术术语
- `full`：穴居人风格，去招呼、去填充词、短片段输出，保留代码和错误
- `ultra`：电报风格，只留关键词
- `wenyan`：文言极简，保留实义与技术细节

默认关闭。

如果你不想保存 key，而是只在当前 shell 会话里临时使用：

```bash
export CODEXSAVER_PROVIDER=deepseek
export CODEXSAVER_API_KEY=YOUR_API_KEY
python cli.py install
python cli.py doctor
```

### 一句话让 Codex 安装

如果 Codex 已经打开了这个仓库，你可以直接发：

```text
帮我为 CodexSaver 保存 worker provider API key，运行 `python cli.py auth set --provider deepseek --api-key ...`，然后运行 `python cli.py install` 和 `python cli.py doctor`，告诉我是否已经就绪。
```

如果你只想做项目级安装：

```text
帮我为 CodexSaver 保存 worker provider API key，并只把 CodexSaver 安装到当前仓库，运行 `python cli.py auth set --provider deepseek --api-key ...`、`python cli.py install --project`，然后运行 `python cli.py doctor` 并总结结果。
```

这里的“就绪”指的是：

- `~/.codex/config.toml` 包含全局 `codexsaver` MCP server，或仓库里存在 `.codex/config.toml`
- 全局安装时存在 `~/.codexsaver/codexsaver_mcp.py`
- provider 配置来自环境变量或 `~/.codexsaver/config.json`
- compression 配置来自 `~/.codexsaver/config.json`
- `python cli.py doctor` 报告 `CodexSaver is ready`

---

## 60 秒体验

`python cli.py install` 生成的全局 MCP 配置大致是：

```toml
[mcp_servers.codexsaver]
command = "python"
args = ["/Users/you/.codexsaver/codexsaver_mcp.py"]
startup_timeout_sec = 10
tool_timeout_sec = 120
```

然后直接告诉 Codex：

```text
对低风险任务使用 CodexSaver。
给 user service 添加单元测试。
```

也可以直接走 CLI：

```bash
python cli.py delegate "Explain the routing logic briefly" --files codexsaver/router.py --workspace .
```

试运行：

```bash
python cli.py "添加单元测试" --files src/user/service.ts --workspace . --dry-run
```

真实运行：

```bash
python cli.py "添加单元测试" --files src/user/service.ts --workspace .
```

---

## 已验证的安装流程

基于 2026 年 5 月 8 日、全局安装和本地 key 流程的实测结果：

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全量测试 | `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider` | `86 passed in 0.23s` |
| 全局安装 | `python cli.py install --workspace .` | `status=ok`，全局配置指向 `~/.codexsaver/codexsaver_mcp.py` |
| 本地 provider 保存 | `python cli.py auth set --provider deepseek --api-key ...` | 已保存到 `~/.codexsaver/config.json` |
| 压缩配置 | `python cli.py compression set --enabled true --level full` | 已保存到 `~/.codexsaver/config.json` |
| 工作区诊断 | `python cli.py doctor --workspace .` | `provider_api_key_source=local_config:deepseek`，工作区已就绪 |
| 全局 launcher 检查 | 用 MCP `initialize` 调用 `~/.codexsaver/codexsaver_mcp.py` | 返回 `serverInfo.name=codexsaver` |
| 真实 DeepSeek 调用 | `python cli.py delegate "Explain the CodexSaver router..." --files codexsaver/router.py --workspace .` | `route=deepseek`、`status=success`、验证通过 |

推荐流程就是：

1. 保存一次 key
2. 全局安装 CodexSaver
3. 用 `doctor` 确认就绪
4. 之后直接发起真实委派调用，不再重复导出 API key

---

## Provider 一览

内置预设覆盖常见云端和本地模型：

| Provider | 接口风格 | 默认模型 | API key |
|---|---|---|---|
| `deepseek` | OpenAI-compatible | `deepseek-chat` | 需要 |
| `openai` | OpenAI | `gpt-4o-mini` | 需要 |
| `anthropic` | native Messages API | `claude-3-5-haiku-latest` | 需要 |
| `gemini` | OpenAI-compatible endpoint | `gemini-2.0-flash` | 需要 |
| `qwen` | OpenAI-compatible endpoint | `qwen-plus` | 需要 |
| `ollama` | 本地 OpenAI-compatible endpoint | `llama3.1` | 不需要 |
| `lmstudio` | 本地 OpenAI-compatible endpoint | `local-model` | 不需要 |

完整列表可以运行 `python cli.py auth providers` 查看。

---

## 配置完成后的使用占比

在配置完成之后，我统计了这轮工作会话里真正进入“模型路由决策”的任务。
像 `pytest`、`git`、`install`、`doctor`、README 编辑这类纯本地步骤都不计入比例。

结果是：

- `DeepSeek`：`7 / 8 = 87.5%`
- `Codex`：`1 / 8 = 12.5%`

为什么不是 100%？

有一个测试任务最初包含了 `production logic` 这类措辞。
这会触发路由器有意设计的高风险关键词保护，从而把任务交回 Codex。
这不是失败，而是保护逻辑按预期生效。

如果只看后面那组经过标准化措辞处理的“五任务基准”，则结果是：

- `DeepSeek`：`5 / 5 = 100%`
- `Codex`：`0 / 5 = 0%`

结论很直接：

- 在真实使用里，CodexSaver 默认会把大多数低风险小任务交给 DeepSeek
- 但它仍然保留了严格的回退路径，用来处理高风险表述和受保护域

---

## 五个小任务的 A/B 对比

方法说明：

- **A** = 反事实的 `Codex-only` 基线，归一化成本指数固定为 `1.00`
- **B** = `CodexSaver` 模式，真实经过当前路由器和 DeepSeek worker 执行
- 延迟统计的是 CodexSaver 实时调用的墙钟时间
- 节省比例来自当前 `CostEstimator` 的估算，所以这是一个可复现的路由基准，不是账单级财务数据

文字总结：

- 这 5 个任务都属于典型的低风险开发小任务：解释代码、补文档、补测试、维护 README
- 在使用更自然的低风险表述后，5 个任务全部成功委派
- 实测平均延迟是 `6.18s`
- 平均预计节省是 `48.4%`
- 从归一化成本看，平均成本指数从 `1.00` 降到 `0.52`
- 预计相对下降 `48.0%`

| 任务 | 类型 | 路由 | 延迟 | A: Codex-only 成本指数 | B: CodexSaver 成本指数 | 预计节省 | 输出形态 |
|---|---|---|---:|---:|---:|---:|---|
| Explain router logic | `explain` | `deepseek` | `2.13s` | `1.00` | `0.55` | `45%` | 只读总结 |
| Document router module | `docs` | `deepseek` | `3.13s` | `1.00` | `0.55` | `45%` | 单文件 patch |
| Add cost tests | `write_tests` | `deepseek` | `9.29s` | `1.00` | `0.55` | `45%` | 测试 patch |
| Explain verifier flow | `explain` | `deepseek` | `2.30s` | `1.00` | `0.55` | `45%` | 只读总结 |
| Update install docs | `docs` | `deepseek` | `14.06s` | `1.00` | `0.38` | `62%` | README patch |

![五任务基准图](./assets/ab-test-benchmark.svg)

图示说明：
灰色柱子是固定为 `100` 的 `Codex-only` 基线，绿色柱子表示同一任务在
`CodexSaver` 模式下的归一化成本指数。柱子越低，预计节省越大。

结果解读：

- 只读解释型任务是最快、最稳定的收益来源
- 小型文档修改也很适合下放，而且会返回紧凑、易审查的 patch
- 测试生成的延迟高于 explain，但仍然保持在低风险节省区间
- 上下文更大的文档任务节省更高，因为 `Codex-only` 模式下的上下文成本更高

---

## 输出 Token 压缩检查

我还用一个更长、更开放的任务，分别跑了三种模式来对比 `total_tokens`：

- `original`：普通 prompt，不带 CodexSaver system prompt
- `CodexSaver`：只加 worker prompt
- `CodexSaver + Caveman`：worker prompt 再加 `full` 压缩指令

这是一次真实 API 测量，不是估算。这个更长的任务里，caveman 风格带来的短输出
抵消了额外的 prompt 开销，所以 `total_tokens` 明显下降了。

| 模式 | total tokens | 输出形态 |
|---|---:|---|
| Original | 912 | 详细解释 |
| CodexSaver | 760 | 简洁技术总结 |
| CodexSaver + Caveman | 598 | 电报式摘要 |

结论：

- 这个更长的任务里，CodexSaver 相比普通 prompt 的总 token 更低
- 加上 caveman 压缩指令后，回复进一步变短，而且总 token 也优于普通 CodexSaver prompt
- 如果想更清楚看到压缩收益，最好选更长、更开放的任务，让输出长度有足够空间体现差异

---

## 路由规则

### 适合委派给 DeepSeek 的任务

- 仓库扫描和代码搜索
- 代码解释与总结
- 编写单元测试
- 修复 lint / type error
- 文档更新
- 样板代码生成
- 小范围局部重构

### 应该保留给 Codex 的任务

- 架构决策
- 认证、安全、支付、账单、权限逻辑
- 数据库迁移
- 部署和生产操作
- 模糊需求
- 最终审核

### 为什么有些中风险任务仍然会委派

CodexSaver 问的不是：

```text
这是不是编码任务？
```

它问的是：

```text
这是不是一个足够便宜、又不会损失判断质量的编码任务？
```

所以它会形成一个刻意的不对称：

- 只读理解型工作可以尽量便宜
- 敏感域里的写操作，哪怕改动很小，风险也会迅速升高
- 一旦任务模糊，默认交回 Codex，而不是默认下放

这也是为什么 `Explain auth code` 还有机会走 DeepSeek，而 `Refactor auth service`
必须留给 Codex。

---

## 工作原理

```text
User
  ↓
Codex
  ↓ MCP tool call
CodexSaver
  ├─ Router
  ├─ Context Packer
  ├─ Worker LLM Provider
  ├─ Verifier
  └─ Cost Estimator
  ↓
Codex review / apply / finalize
```

核心模块：

- `Router`：任务分类和风险判断
- `ContextPacker`：在委派前裁剪文件上下文
- `ProviderClient`：调用已配置的 worker 模型
- `Verifier`：检查返回结构、受保护路径和建议命令
- `CostEstimator`：估算相对节省区间

---

## 安全与持久化

- `python cli.py auth set --provider ... --api-key ...` 会把 provider 配置保存到 `~/.codexsaver/config.json`
- 配置文件会使用仅本地用户可读写的权限
- `doctor` 会告诉你 key 是来自环境变量还是本地配置，并且只显示脱敏预览
- 如果没有导出环境变量，真实调用会自动使用本地配置
- 只要验证失败，CodexSaver 就会回退为 `needs_codex`

---

## 常用命令

```bash
python cli.py auth providers
python cli.py auth set --provider deepseek --api-key YOUR_API_KEY
python cli.py install
python cli.py install --project
python cli.py doctor
python cli.py delegate "Explain the routing logic briefly" --files codexsaver/router.py --workspace .
```

---

## Roadmap

- [x] MCP server
- [x] 规则路由
- [x] 上下文裁剪
- [x] DeepSeek 默认 worker 集成
- [x] 多 provider OpenAI-compatible worker 支持
- [x] 本地 API key 持久化
- [x] worker 输出压缩开关与 prompt 注入
- [x] 可感知的交互返回
- [x] 端到端验证流程
- [ ] 成本感知动态路由
- [ ] 成本感知 provider 选择

---

## 如果它真的帮你省钱了

点个 Star。
