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

## Step 4 — Implement ticket by ticket

Work the **frontier**: any ticket whose blockers are all resolved. For a purely linear chain, that means top to bottom.

For each ticket:

1. **Claim** it: set `Status: claimed` and save before doing any work.
2. **Build** the end-to-end behaviour the ticket describes. Use the `tdd` skill where possible, at the seams pre-agreed in the spec. Run typechecking regularly, single test files regularly, and the full test suite once at the end.
3. **Review**: once done, use the `code-review` skill to review the work against the ticket/spec.
4. **Resolve** the ticket: append any answer/notes, set `Status: resolved`, then commit your work to the current branch.
5. Move to the next unblocked ticket. Do not batch tickets.

## Relationship to the original skills

This document bakes the essential instructions of Matt Pocock's user-invoked skills into the repo so they are followed even when the runtime does not expose those skills to the model. The full skill set is installed on this machine at both:

- `~/.dsh/skills/` — deepseek harness skills (`to-spec`, `to-tickets`, `implement`, `triage`, `wayfinder`, `grill-with-docs`, etc.)
- `~/.claude/plugins/cache/claude-plugins-official/mattpocock-skills/1.2.2/skills/` — Claude Code plugin copy of the same skills

The set also includes `triage` (state machine for triage roles) and `wayfinder` (planning huge multi-session efforts as decision tickets); their file formats are already covered by `docs/agents/issue-tracker.md`.
