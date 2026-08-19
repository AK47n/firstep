# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

电赛工程生成器 — 一个本地运行的网页工具：输入电赛赛题原文，输出一个"打开就能编译、直接开写"的完整工程（MSPM0G3507 / CCS 与 STM32F103C8T6 / Keil5 两条线）。

## Agent skills

### Default workflow

For any non-trivial feature or change request, read `docs/agents/workflow.md` in full first, then follow it — don't jump straight to implementation:

1. **Clarify first** — ask the user targeted questions (use `grilling` to stress-test consequential plans) before writing anything down.
2. **Record the spec** — write the agreed outcome to `.scratch/<feature-slug>/spec.md` using the template in `docs/agents/workflow.md`.
3. **Cut tickets** — break the spec into vertical-slice tickets, one per file at `.scratch/<feature-slug>/issues/NN-<slug>.md`, numbered from `01` in dependency order.
4. **Implement ticket by ticket** — claim the next unblocked ticket (`Status: claimed`), build it with `tdd`, review it with `code-review`, then mark it resolved. Work the frontier; don't batch tickets.

Skip this only for trivial single-step tasks — and say so explicitly when skipping.

**语言规范（硬性约定）**：spec / 工单 / git 提交信息 / CHANGELOG 一律用中文书写（技术术语、标识符、`Status:` 等标签值可保留英文）。英文提交信息会被 `.githooks/commit-msg` 拒绝（`tests/test_repo_language.py` 兜底工单与 CHANGELOG）。详见 `docs/agents/workflow.md`「语言规范」。

### Issue tracker

Issues and specs live as markdown files under `.scratch/<feature-slug>/` (local tracker, one file per ticket). See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical triage roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Session handoff preference

当会话已经很长、继续重活容易丢细节时，主动告诉用户：建议开新会话；新会话用 `max` 还是 `high`；并直接给出新会话的第一段提示词（让它读 CLAUDE.md / CONTEXT.md / 相关 spec，然后继续哪个工单）。用户原话："你觉得该开新会话时直接告诉我新会话该用max还是high然后给我新会话的提示词，这样能省很多力"。
