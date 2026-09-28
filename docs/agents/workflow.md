# Workflow: clarify → spec → tickets → implement

Default engineering workflow for this repo, distilled from Matt Pocock's `mattpocock-skills` v1.2.2 (MIT License): the `to-spec`, `to-tickets`, and `implement` skills. The local issue tracker conventions this workflow publishes to live in `docs/agents/issue-tracker.md`.

## When to use

Any non-trivial feature, change, or bug-fix request. Skip only for trivial single-step tasks — and say so explicitly when skipping.

## Step 1 — Clarify first

Before writing a spec:

- Ask the user targeted questions until the requirement is unambiguous.
- When the plan or decision is consequential, stress-test it with the `grilling` skill. When domain terms get resolved, update `CONTEXT.md` / `docs/adr/` (see the `domain-modeling` skill).
- Do not proceed until the user confirms the shape of the work.

## 语言规范（硬性约定）

仓库面向用户与代理的文档一律用**中文**书写（技术术语 / 标识符 / 状态标签可保留英文）：

- spec 与工单正文（`.scratch/**/spec.md`、`issues/*.md`）必须中文；工单模板字段用中文（见下文模板），`Status:` / `Blocked by:` 等标签值保持英文规范值（`ready-for-agent` / `claimed` / `resolved` 等）。
- git 提交信息必须中文（可中英混合）：`.githooks/commit-msg` 钩子强制（安装：`git config core.hooksPath .githooks`，新 clone 后需重配）；`--no-verify` 可绕过但不鼓励。
- CHANGELOG 条目由提交信息自动补录（post-commit → changelog.py），提交信息中文即保证中文；`tests/test_repo_language.py` 对工单 / spec / CHANGELOG 做第二道兜底。
- 反例（发生过，勿重演）：llm-observability-dashboard 的工单与 08-18 的 CHANGELOG 记录整段英文。
- **PowerShell 脚本编码（硬性约定）**：所有 .ps1（含检查 / 探针脚本）必须存成 **UTF-8 with BOM**。Windows PowerShell 5.1 对无 BOM 的 .ps1 按系统 ANSI 代码页（中文系统 GBK/CP936）解码：UTF-8 中文注释的字节流经 GBK 双字节硬配对后，行尾剩余字节与换行符 0x0A 构成无效配对被双双丢弃 → 换行符消失 → 注释行吞掉下一行代码（"行解析错位"，变量/语句静默丢失）。是否吞行取决于逐字节配对路径，无法按字符数奇偶推断，故一律带 BOM 杜绝。`tests/test_ps1_encoding.py` 兜底。

## Step 2 — To spec

Synthesize the clarified conversation into a spec and publish it to the issue tracker at `.scratch/<feature-slug>/spec.md`. Do NOT re-interview the user — synthesize what was already agreed.

Before finalizing the spec, check the test seams with the user: where will this feature be tested? Prefer the highest existing seam; if a new seam is needed, propose it at the highest point possible. The fewer seams across the codebase, the better — the ideal number is one.

Use the spec template below. Do NOT include specific file paths or code snippets — they go stale fast. Exception: if a prototype produced a snippet that encodes a decision more precisely than prose (state machine, reducer, schema, type shape), inline the decision-rich part and note that it came from a prototype.

```markdown
## 问题陈述

用户面临的问题，从用户视角描述。

## 方案

问题的解决方案，从用户视角描述。

## 用户故事

一个长编号列表，每条形如：

1. 作为<角色>，我想要<能力>，以便<收益>

列表应详尽，覆盖特性的所有方面。

## 实现决策

- 将构建/修改的模块
- 这些模块将被修改的接口
- 技术澄清
- 架构决策
- 模式变更
- API 契约
- 具体交互

## 测试决策

- 什么构成好测试（只测外部行为，不测实现细节）
- 将测试哪些模块
- 测试的既有先例（代码库中已有的类似测试）

## 范围外

明确不在本 spec 范围内的事项。

## 补充说明

关于该特性的任何进一步说明。
```

## Step 3 — To tickets

Break the spec into **tracer-bullet tickets** — vertical slices, each declaring the tickets that block it.

### Vertical slice rules

- Each slice cuts a narrow but COMPLETE path through every layer (schema, API, UI, tests) — vertical, NOT a horizontal slice of one layer.
- A completed slice is demoable or verifiable on its own.
- Each slice is sized to fit in a single fresh context window.
- Any prefactoring goes first. "Make the change easy, then make the easy change."

**Wide refactors are the exception.** One mechanical change whose blast radius fans across the whole codebase should be sequenced as expand–contract: first add the new form beside the old (one ticket), then migrate call sites in batches sized by blast radius (each batch its own ticket, blocked by the expand), finally delete the old form (a ticket blocked by every migrate batch). Keep green batch to batch; if even batches can't stay green alone, let them share an integration branch and a final integrate-and-verify ticket.

### Quiz the user

Present the proposed breakdown as a numbered list. For each ticket show: **Title**, **Blocked by**, **What it delivers** (the end-to-end behaviour). Then ask:

- Does the granularity feel right? (too coarse / too fine)
- Are the blocking edges correct — does each ticket only depend on tickets that genuinely gate it?
- Should any tickets be merged or split further?

Iterate until the user approves the breakdown.

### Publish

Write one file per ticket under `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01` in dependency order (blockers first). Never a single combined file. Use the template below.

```markdown
# <NN> — <工单标题>

**要做什么：** 本工单让什么端到端行为可用（从用户视角），不是分层实现清单。

**被谁阻塞：** 前置工单的编号/标题，或「无——可立即开始」。

**状态：** ready-for-agent

- [ ] 验收标准 1
- [ ] 验收标准 2
```

## 闸门：推之前与合并之前（工单 commit-gate/01-04）

三道自动闸门，判据都是**既有测试**（不另造一套）：

| 时机 | 谁 | 跑什么 |
|---|---|---|
| **push 之前**（本地） | `.githooks/pre-push` → `tools/prepush.py` | 按本次要推的改动选**关联子集**（改公共面模块 / 认不出的落点 / 推 tag → 整套）；**改动落在前端（`static/` 或 `tests/js/`）时另跑前端门禁** `node --test "tests/js/*.test.mjs"`（工单 module-hwcheck/01——pytest 面看不见那 1500+ 条前端用例）；**改动落在浏览器门禁的落点（`tests/browser/`、`static/js/ui/`、`static/index.html`、`static/js/app.js`）时再跑浏览器门禁** `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`（工单 ui-dom-contract-gate/03——26 条真浏览器 + 真后端用例，本机约 35–80 秒）。测试红 → 拒推并点名失败用例 |
| **push / PR 之后**（远端） | `.github/workflows/ci.yml` | windows-latest 跑全套 `pytest -n auto` + 同一条前端门禁 + **独立 job `browser-suite`** 跑同一条浏览器门禁（要 `npm install` + `npx playwright install chromium`）；ubuntu-latest 跑发版自检（`tools/preflight.py`）+ 语言 / 编码 / 闸门自身用例。**测试不打网络、不吃 secret**（CI 装依赖当然要联网——两件事别混着读） |
| **打 tag 之前**（发版） | `tools/preflight.ps1` | 三处版本号一致 / 母版 `.settings` 编码钉在库 / 下载文档一致性 / README 版本行 |

用法与绕过：

```powershell
python tools/prepush.py --changed <文件>        # 手动看会跑什么（--dry-run 只打印）
python tools/prepush.py --full                  # 强制整套（pytest + 前端门禁 + 浏览器门禁）
python tools/prepush.py --no-js                 # 明写跳过两支前端门禁（确知不需要时）
node --test "tests/js/*.test.mjs"               # 只跑前端用例（glob 由 node 展开；
                                                # 目录形式 `node --test tests/js` 在
                                                # Node 24 上会把目录当模块解析而失败）
node --test --test-concurrency=1 "tests/browser/*.spec.mjs"   # 只跑浏览器门禁（要
                                                # npm install + npx playwright install chromium；
                                                # 串行是刻意的：每个 spec 各起真后端 + 真 Chromium）
FIRSTEP_PREPUSH=full git push                   # 临时整套；=off 跳过（不鼓励）；=select-only 只选择
powershell -File tools\preflight.ps1            # 发版前一条命令
```

改了 `.githooks/` 下的钩子请注意：**LF + 无 BOM**。钩子带 UTF-8 BOM 时 git 会
`cannot spawn ...: No such file or directory`，而且**成功 push 时 stderr 是静默的**——
表现为「钩子存在但从不生效」（2026-09-16 实测，排查花掉半小时）。别用 PowerShell 5.1 的
`-Encoding utf8` 生成钩子文件。

## Step 4 — Implement ticket by ticket

Work the **frontier**: any ticket whose blockers are all resolved. For a purely linear chain, that means top to bottom.

For each ticket:

1. **Claim** it: set `Status: claimed` and save before doing any work.
2. **Build** the end-to-end behaviour the ticket describes. Use the `tdd` skill where possible, at the seams pre-agreed in the spec. Run typechecking regularly, single test files regularly, and the full test suite once at the end.
3. **Review**: once done, use the `code-review` skill to review the work against the ticket/spec.
4. **Resolve** the ticket: append any answer/notes, set `Status: resolved`, then commit your work to the current branch.
5. Move to the next unblocked ticket. Do not batch tickets.

### 三条纪律（`ui-density-sitewide` 轮用血换的，2026-09-28 固化）

这三条来自**一页一单、连做十四页**的那一轮（`.scratch/ui-density-sitewide/`）；它们通用，
凡"读数/门禁/注释里的数"参与判断的工单都适用：

1. **读数每轮重跑，整改过一轮还要再跑一遍。** 读数（探针输出、截图、门禁结果）是**照片**，
   不是"结论"——盘上改一个字节，它就可能过期。**整改之后忘了重跑**是那一轮最常见的一种
   "绿得可疑"（07 单评审 Standards 抓到：`apply-07d` 改完，三份读数还是旧树的）。
   → 判据：**提交前，每份落盘读数的时间戳必须晚于最后一次改产品面的时间**。
2. **浏览器门禁单独跑，不与全量 `pytest` 并行。** 两套都要抢 CPU + 端口，
   并行时浏览器用例会随机超时（那一轮实测过一次假红）。顺序：先浏览器门禁（~190s），
   再全量 `pytest`（~120s）。
3. **注释里的数按脚本复算，不按记忆写。** 票面、守卫注释、README 索引里的每个数字都要能
   用一条命令复现（`probe-00` / `probe-01` / `probe-04`）；**票面最初那次 recon 的数常常是错的**
   （07 单三个口径全对不上）。写进口径时连"这个数是哪个口径"一起写——两个口径混着读
   （"border 声明" vs "整圈完整框"）是那一轮第二常见的误判。

## Relationship to the original skills

This document bakes the essential instructions of Matt Pocock's user-invoked skills into the repo so they are followed even when the runtime does not expose those skills to the model. The full skill set is installed on this machine at both:

- `~/.dsh/skills/` — deepseek harness skills (`to-spec`, `to-tickets`, `implement`, `triage`, `wayfinder`, `grill-with-docs`, etc.)
- `~/.claude/plugins/cache/claude-plugins-official/mattpocock-skills/1.2.2/skills/` — Claude Code plugin copy of the same skills

The set also includes `triage` (state machine for triage roles) and `wayfinder` (planning huge multi-session efforts as decision tickets); their file formats are already covered by `docs/agents/issue-tracker.md`.
