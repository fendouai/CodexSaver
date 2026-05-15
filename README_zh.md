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
- 可选 worker 输出压缩，让委派结果更短、更容易审查
- 已通过测试、真实 DeepSeek 调用和全局 MCP launcher 检查

---

## 一眼看懂

CodexSaver 不是想替代 Codex，而是想把**真正需要昂贵判断的部分**留给 Codex，
把可以标准化、可验证、可并行的部分交给更便宜的 worker。

当前仓库里已经证明的事情：

| 维度 | 当前已经证明的结果 |
|---|---|
| 成本 | v2 的 5 任务 benchmark 达到了 `45%` 到 `100%` 的预计节省 |
| 速度 | v2 成功任务耗时在 `0.03s` 到 `14.95s`；v3 只读 swarm 成功耗时 `6.45s` |
| 质量 | v2 bounded work packet 能稳定过 verifier；v3 只读 swarm 产出了 `10` 条 findings，质量分 `0.75` |
| 安全 | 受保护路径、allowlisted commands、沙箱 patch apply、Codex fallback 都是内建能力 |

最重要的一点是：

- v2 是当前成熟的单任务执行通道
- v3 是正在成型的 specialist 编排通道
- v3 目前最先站住脚的胜利点是 **只读 specialist 编排**

---

## CodexSaver 最擅长什么

CodexSaver 最强的领域，不是“替代 Codex 做所有代码修改”，而是那些同时满足下面几个条件的任务：

- 低风险
- 重复性高
- 容易验证
- 适合并行
- 用 Codex 做太贵，但用便宜 worker 做很划算

落到实际场景，CodexSaver 目前最擅长：

- 代码解释
- 仓库扫描
- 性能提示
- docstring / README 维护
- 有边界的测试生成
- 文件范围明确的小型重构

CodexSaver 目前不擅长：

- 认证、安全、支付、权限
- 破坏性迁移
- 模糊的架构设计
- 验证链条不清晰的多文件行为修改
- 任何每一步都必须依赖 Codex 级判断的任务

当前产品判断可以压缩成一句话：

```text
CodexSaver 先赢在只读 specialist 编排。
再赢在有边界、可验证的 patch 任务。
高风险和高歧义任务仍然交给 Codex。
```

这个顺序很重要，因为它和当前代码能力、当前 benchmark 结论是一致的。

---

## 为什么它真的有效

CodexSaver 在降低成本、提高效率、提升质量上，并不是靠一句“便宜模型替代昂贵模型”。
它依赖的是一个很明确的技术拆分：

### 1. 为什么更省钱

Codex 只做高价值判断，不再为大量重复劳动买单。
便宜 worker 负责：

- 解释代码
- 写文档
- 生成测试
- 做小范围、有边界的实现任务

这样昂贵模型不会再为每一个机械步骤付费。

### 2. 为什么更快

当任务可拆解时，CodexSaver 可以把 specialist 并行拉起来：

- 一个 specialist 解释代码
- 一个 specialist 看性能
- 一个 specialist 写 docs 或 tests

此时总耗时更接近：

```text
最长那个 specialist 的耗时 + 编排开销
```

而不是：

```text
所有子任务串行耗时相加
```

### 3. 为什么质量不会掉

CodexSaver 并不会无脑相信 worker 输出。
它的质量提升来自一套硬约束：

- router 判断任务是否适合下放
- work packet 限制可写范围
- sandbox 在隔离环境 apply patch
- verifier 检查 changed files、diff 大小、命令、失败情况
- Codex 保留最终审核权

所以它不是“廉价模型乱改代码”，而是“廉价模型在受控边界里工作，昂贵模型保留判断”。

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

如果启用了 worker 输出压缩，`interaction` 里也会显示当前压缩级别，
这样 Codex 能知道为什么委派结果会更短。

---

## V2：有边界的 Work Packet

CodexSaver v2 新增了一条更严格的委派路径：bounded work packet。它不再只是把任务
丢给 worker，而是把任务压成一个可验证的小工作包：

- 明确目标
- 允许修改的文件或 glob
- 禁止路径
- 验收标准
- 允许执行的检查命令
- 最大迭代次数和 diff 行数

Worker 可以产出 patch，但 CodexSaver 只会在临时沙箱中 apply。只有 patch 没越界、
检查命令通过，结果才会被接受。如果任务本身已经满足，v2 会返回
`preflight_satisfied=true`，不再浪费一次 worker 模型调用。

CLI 示例：

```bash
codexsaver work-packet \
  "Create docs/v2-smoke.md with one sentence." \
  --files README.md \
  --allowed-file docs/v2-smoke.md \
  --acceptance "docs/v2-smoke.md exists in sandbox" \
  --allowed-command "python -c \"from pathlib import Path; assert Path('docs/v2-smoke.md').exists()\"" \
  --workspace .
```

MCP 工具：

```text
codexsaver.delegate_work_packet
```

---

## V3：编排式 Specialist

CodexSaver v3 把 v2 的单 worker 扩展成了一个小型 specialist 编排系统。核心变化不是
“再加几个 prompt”，而是架构升级：

- Codex 继续负责判断和最终审核
- CodexSaver 先规划 work graph
- 只读 specialist 可以并行执行
- patch specialist 复用 v2 的 sandbox + verifier
- patch 聚合保持保守，一旦同批次输出重叠就回退给 Codex

当前仓库里的 v3 状态：

- `explainer` 和 `perf_reviewer` 已能作为真实 `readonly_swarm` 执行
- mixed graph 已能通过 v2 work-packet runtime 执行 bounded patch 节点
- 同一批 patch 节点若 `changed_files` 重叠，会直接返回 `needs_codex`
- v3 是 CodexSaver 自己的 orchestration 层，不依赖脆弱的 Codex 原生 subagent 私有配置

主要参考：

- [v3 规格](./docs/SPEC_v3.md)
- [v3 开发任务清单](./docs/V3_TASKS.md)
- [v3 基准测试，2026-05-14](./docs/benchmarks/v3-benchmark-2026-05-14.md)
- [v3 项目基准测试，2026-05-15](./docs/benchmarks/v3-project-benchmark-2026-05-15.md)

当前 benchmark 状态：

- `readonly_swarm`：已经真实跑通执行链，但在 2026-05-14 的 fixture 运行里仍出现 provider 回退
- `impl + tests`：已经真实跑通执行链，但当前仍然偏保守，可能返回 `needs_codex`
- `impl + docs + explain`：在 2026-05-14 的 fixture 运行里完整成功

这意味着 v3 已经是真实可测的系统，但它目前仍处在“早期可用”阶段，还不是对所有 v2 场景的完整替代。

### 核心卖点：只读 Specialist 编排已经成立

v3 现在最重要的卖点，不再只是概念，而是已经在当前项目的 benchmark 里得到验证。
在 2026-05-15 的项目级测试中，下面这个只读任务已经完整成功：

- 任务：`Explain installer flow and review performance`
- 路由：`deepseek`
- 状态：`success`
- 预计节省：`52%`
- 延迟：`6.45s`
- 质量分：`0.75`
- 只读 findings：`10`

这就是当前 v3 最清晰的价值点：

- Codex 把解释和性能分析下放给便宜 specialist
- specialist 可以并行工作
- 不需要生成 patch
- 验证逻辑仍然严格
- 最终判断依然保留给 Codex

这也是目前最适合对外强调的卖点，因为它已经在真实项目测试里站住了。

### 五个项目级任务测试说明了什么

项目级 benchmark 在当前仓库的临时拷贝上跑了 5 个典型任务，结论很明确：

- 5 个任务里，v3 成功了 2 个
- 2 个成功任务都落在 CodexSaver 当前最强的能力带
- 其中 1 个是纯只读编排
- 其中 1 个是 docs + explain 的混合流程
- 另外 3 个更偏 patch / test 的任务都保守回退成了 `needs_codex`

这说明：

- 只读 specialist 编排已经是一个真实优势
- bounded patch 编排有潜力，但成熟度还不如只读链路
- `test_writer` 聚合回放和 patch verification 仍然是当前 v3 的主瓶颈

如果要用一句最诚实的话描述当前 v3：

```text
只读编排已经成立。
单个有边界 patch 已经可用。
复杂 patch 编排仍在成熟中。
```

CLI 示例：

```bash
codexsaver orchestrate "Explain config loader logic and review performance" --files codexsaver/config.py
codexsaver orchestrate "Implement login and add tests" --files src/user_auth.py --dry-run
codexsaver specialist explainer "Explain this module" --files codexsaver/config.py
```

可选的项目增强安装：

```bash
# 低侵入：只往 AGENTS.md 里加一个 CodexSaver 托管块
codexsaver superpower install --profile basic --workspace .

# 更激进：额外写入 .codex/hooks.json、prompt hook 脚本，以及本地 codex_hooks 开关
codexsaver superpower install --profile full --workspace .
```

配置建议：

- `basic`：最稳妥，只做项目级 AGENTS 引导
- `full`：AGENTS 引导 + 可选 hook scaffolding + 本地 `.codex/config.toml` feature flag

目标是尽量不去悄悄修改用户的全局配置，只在项目范围内把 Codex 更稳定地引导到 CodexSaver。

---

## 测试报告

CodexSaver 现在有两条 benchmark 叙事，而且两条都很重要：

### v2：成熟的单任务执行通道

参考：

- [v2 基准测试，2026-05-12](./docs/benchmarks/v2-benchmark-2026-05-12.md)

结论：

- `5 / 5` bounded task 成功
- 成功任务稳定落在 `45%` 预计节省
- 有一个“任务已满足”案例走了 `preflight`，达到 `100%` 节省，耗时 `0.03s`

这是当前最成熟、最适合直接推广的能力带：

- bounded docs
- bounded tests
- 小范围单目标实现

### v3：真实项目上的 specialist 编排

参考：

- [v3 项目基准测试，2026-05-15](./docs/benchmarks/v3-project-benchmark-2026-05-15.md)

结论：

- `5` 个项目级典型任务里，`2 / 5` 成功
- 成功的两个任务都落在 CodexSaver 当前最强的能力带
- 最有代表性的成功是 `readonly_swarm`
- 更偏 patch 的编排路径还在保守回退

总结表：

| 通道 | 当前最强场景 | 成熟度 |
|---|---|---|
| v2 | 单个 bounded patch 任务 | 成熟 |
| v3 只读通道 | explain + scan + perf hint specialist | 已成立 |
| v3 patch 编排 | docs/tests/impl 混合图 | 有潜力但仍在成熟 |

如果今天要判断该怎么用 CodexSaver，最准确的心智模型是：

- 需要稳定 bounded implementation，就优先用 v2
- 需要让 Codex 低成本编排只读 specialist，就优先用 v3
- 多 patch 的 v3 graph 还应该被视作前沿能力，而不是已经完全解决的问题

---

## 快速开始

### 推荐：全局安装

```bash
git clone https://github.com/fendouai/CodexSaver
cd CodexSaver

python -m pip install -e .
codexsaver auth set --provider deepseek --api-key YOUR_API_KEY
codexsaver install
codexsaver doctor --workspace .
```

这就够了。`codexsaver install` 会把 CodexSaver 写入全局 Codex MCP 配置
`~/.codex/config.toml`，并指向一个稳定启动入口：
`~/.codexsaver/codexsaver_mcp.py`。

之后任意 Codex 工作区都可以调用：

```text
codexsaver.delegate_task
```

只有当你想写入当前仓库自己的 `.codex/config.toml` 时，才需要使用：

```bash
codexsaver install --project
```

### Provider 配置

DeepSeek 是默认 provider，因为价格低，并且提供 OpenAI-compatible API。
切换 provider 只需要改一个参数：

```bash
codexsaver auth set --provider openai --api-key YOUR_API_KEY --model gpt-4o-mini
codexsaver auth set --provider anthropic --api-key YOUR_API_KEY --model claude-3-5-haiku-latest
codexsaver auth set --provider gemini --api-key YOUR_API_KEY --model gemini-2.0-flash
codexsaver auth set --provider qwen --api-key YOUR_API_KEY --model qwen-plus
```

本地模型：

```bash
codexsaver auth set --provider ollama --model llama3.1
codexsaver auth set --provider lmstudio --model local-model
```

任意自定义 OpenAI-compatible endpoint：

```bash
codexsaver auth set \
  --provider custom \
  --api-key YOUR_API_KEY \
  --base-url https://example.com/v1/chat/completions \
  --model your-model
```

查看内置 provider：

```bash
codexsaver auth providers
```

### Worker 输出压缩

压缩只影响委派给 worker 的调用，不影响 Codex 自己的最终回答。它适合用在
解释、扫描、发现问题、patch notes 这类场景，让便宜 worker 的结果更短、更易审查。

```bash
codexsaver compression show
codexsaver compression set --enabled true --level full
codexsaver compression set --enabled false
```

压缩级别：

- `lite`：简洁回答，保留技术术语和精确信息
- `full`：压缩片段，去寒暄和填充词，保留代码和错误
- `ultra`：电报式，只留关键事实和标识符
- `wenyan`：文言极简，适合中文工作流

默认关闭，配置持久化在 `~/.codexsaver/config.json`。

如果你不想保存 key，而是只在当前 shell 会话里临时使用：

```bash
export CODEXSAVER_PROVIDER=deepseek
export CODEXSAVER_API_KEY=YOUR_API_KEY
codexsaver install
codexsaver doctor --workspace .
```

### 一句话让 Codex 安装

如果 Codex 已经打开了这个仓库，你可以直接发：

```text
帮我为 CodexSaver 保存 worker provider API key，运行 `codexsaver auth set --provider deepseek --api-key ...`，然后运行 `codexsaver install` 和 `codexsaver doctor --workspace .`，告诉我是否已经就绪。
```

如果你只想做项目级安装：

```text
帮我为 CodexSaver 保存 worker provider API key，并只把 CodexSaver 安装到当前仓库，运行 `codexsaver auth set --provider deepseek --api-key ...`、`codexsaver install --project`，然后运行 `codexsaver doctor --workspace .` 并总结结果。
```

这里的“就绪”指的是：

- `~/.codex/config.toml` 包含全局 `codexsaver` MCP server，或仓库里存在 `.codex/config.toml`
- 全局安装时存在 `~/.codexsaver/codexsaver_mcp.py`
- provider 配置来自环境变量或 `~/.codexsaver/config.json`
- compression 配置来自 `~/.codexsaver/config.json`
- `codexsaver doctor --workspace .` 报告 `CodexSaver is ready`

---

## 60 秒体验

`codexsaver install` 生成的全局 MCP 配置大致是：

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
codexsaver delegate "Explain the routing logic briefly" --files codexsaver/router.py --workspace .
```

试运行：

```bash
codexsaver delegate "添加单元测试" --files src/user/service.ts --workspace . --dry-run
```

真实运行：

```bash
codexsaver delegate "添加单元测试" --files src/user/service.ts --workspace .
```

---

## 已验证的 v2 安装流程

基于 2026 年 5 月 12 日、editable 安装、全局 launcher 和本地 key 流程的实测结果：

| 检查项 | 命令 | 结果 |
|---|---|---|
| Editable 安装 | `python -m pip install -e .` | 安装 `codexsaver-0.2.0` |
| 全量测试 | `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider` | `97 passed in 0.41s` |
| 全局安装 | `codexsaver install --workspace .` | 全局配置指向 `~/.codexsaver/codexsaver_mcp.py` |
| 本地 provider 保存 | `codexsaver auth set --provider deepseek --api-key ...` | 已保存到 `~/.codexsaver/config.json` |
| 压缩配置 | `codexsaver compression set --enabled true --level full` | 已保存到 `~/.codexsaver/config.json` |
| 工作区诊断 | `codexsaver doctor --workspace .` | `provider_api_key_source=local_config:deepseek`，工作区已就绪 |
| 全局 launcher 检查 | 用 MCP `initialize` 调用 `~/.codexsaver/codexsaver_mcp.py` | 返回 `serverInfo.version=0.2.0` |
| v2 MCP 工具检查 | MCP `tools/list` | 包含 `delegate_work_packet` |
| v2 preflight 检查 | MCP `tools/call delegate_work_packet` | 返回 `preflight_satisfied=true` |

推荐流程就是：

1. 保存一次 key
2. 安装 editable 包和全局 launcher
3. 用 `doctor` 确认就绪
4. 如果 Codex 窗口在安装前已经打开，需要停止或重载旧 MCP 进程
5. 之后直接发起真实委派调用，不再重复导出 API key

如果已经打开的 Codex 窗口仍在使用旧 MCP 进程，请停止或重载那个 MCP server。
全局 launcher 是 v2 的事实来源，会返回 `serverInfo.version=0.2.0`。

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

完整列表可以运行 `codexsaver auth providers` 查看。

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

最新 v2 报告：

- [v2 重启确认，2026-05-12](./docs/benchmarks/v2-restart-confirmation-2026-05-12.md)
- [v2 基准测试，2026-05-12](./docs/benchmarks/v2-benchmark-2026-05-12.md)

5 月 12 日这轮测试是在停止旧的内存 MCP 进程之后执行的，并且已经确认全局
launcher 返回 `serverInfo.version=0.2.0`。

方法说明：

- **A** = 反事实的 `Codex-only` 基线，归一化成本指数固定为 `1.00`
- **B** = `CodexSaver` 模式，真实经过当前路由器和 DeepSeek worker 执行
- 延迟统计的是 CodexSaver 实时调用的墙钟时间
- 节省比例来自当前 `CostEstimator` 的估算，所以这是一个可复现的路由基准，不是账单级财务数据

v2 bounded work-packet 总结：

- `5 / 5` 任务成功
- `4 / 5` 走 DeepSeek worker 路径
- `1 / 5` 走 v2 preflight，因为任务已经满足
- 平均归一化成本指数是 `0.44`
- 平均预计节省是 `56%`

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
- `WorkPacketRuntime`：在沙箱中 apply worker patch，并运行 allowlisted checks

---

## 安全与持久化

- `codexsaver auth set --provider ... --api-key ...` 会把 provider 配置保存到 `~/.codexsaver/config.json`
- `codexsaver compression set ...` 会把可选 worker 输出压缩配置保存到同一个本地配置
- 配置文件会使用仅本地用户可读写的权限
- `doctor` 会告诉你 key 是来自环境变量还是本地配置，并且只显示脱敏预览
- 如果没有导出环境变量，真实调用会自动使用本地配置
- 只要验证失败，CodexSaver 就会回退为 `needs_codex`

---

## 常见问题

### Windows TOML Unicode Escape 报错

如果安装后 Codex 启动时报：

```text
failed to read configuration layers ...\.codex\config.toml:21:14:
too few unicode value digits, expected unicode hexadecimal value
```

说明 Codex 配置里有未转义的 Windows 路径，例如：

```toml
args = ["C:\Users\admin\.codexsaver\codexsaver_mcp.py"]
```

TOML 会把 `\U` 当成 unicode escape 的开头。升级到最新版 CodexSaver 后重新安装即可：

```bash
python -m pip install -e .
codexsaver install
codexsaver doctor --workspace .
```

也可以手动修复为双反斜杠：

```toml
args = ["C:\\Users\\admin\\.codexsaver\\codexsaver_mcp.py"]
```

Windows 也支持正斜杠写法：

```toml
args = ["C:/Users/admin/.codexsaver/codexsaver_mcp.py"]
```

---

## 常用命令

```bash
codexsaver auth providers
codexsaver auth set --provider deepseek --api-key YOUR_API_KEY
codexsaver compression show
codexsaver compression set --enabled true --level full
codexsaver install
codexsaver install --project
codexsaver doctor --workspace .
codexsaver delegate "Explain the routing logic briefly" --files codexsaver/router.py --workspace .
codexsaver work-packet "Create docs/example.md with one sentence." --files README.md --allowed-file docs/example.md --workspace .
codexsaver orchestrate "Explain config loader logic and review performance" --files codexsaver/config.py
codexsaver specialist explainer "Explain this module" --files codexsaver/config.py
```

---

## Roadmap

- [x] MCP server
- [x] 规则路由
- [x] 上下文裁剪
- [x] DeepSeek 默认 worker 集成
- [x] 多 provider OpenAI-compatible worker 支持
- [x] 本地 API key 持久化
- [x] worker 输出压缩开关与 provider prompt 注入
- [x] 可感知的交互返回
- [x] 端到端验证流程
- [x] v2 bounded work packet 和沙箱 patch 验证
- [x] v2 已满足任务的 preflight
- [x] v3 只读 specialist 编排
- [x] v3 通过 v2 sandbox runtime 执行 bounded patch 节点
- [x] v3 对重叠 patch 输出回退 Codex
- [ ] v3 节点级文件所有权约束
- [ ] v3 持久 ledger 与自适应路由

---

## 如果它真的帮你省钱了

点个 Star。
