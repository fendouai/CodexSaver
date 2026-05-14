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
codexsaver install
codexsaver install --project
codexsaver doctor --workspace .
codexsaver delegate "Explain the routing logic briefly" --files codexsaver/router.py --workspace .
codexsaver work-packet "Create docs/example.md with one sentence." --files README.md --allowed-file docs/example.md --workspace .
```

---

## Roadmap

- [x] MCP server
- [x] 规则路由
- [x] 上下文裁剪
- [x] DeepSeek 默认 worker 集成
- [x] 多 provider OpenAI-compatible worker 支持
- [x] 本地 API key 持久化
- [x] 可感知的交互返回
- [x] 端到端验证流程
- [x] v2 bounded work packet 和沙箱 patch 验证
- [x] v2 已满足任务的 preflight
- [ ] 成本感知动态路由
- [ ] 成本感知 provider 选择

---

## 如果它真的帮你省钱了

点个 Star。
