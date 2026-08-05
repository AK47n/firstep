# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

电赛工程生成器 — 一个本地运行的网页工具：输入电赛赛题原文，输出一个"打开就能编译、直接开写"的完整工程（MSPM0G3507 / CCS 与 STM32F103C8T6 / Keil5 两条线）。

## Agent skills

### Issue tracker

Issues and specs live as markdown files under `.scratch/<feature-slug>/` (local tracker, one file per ticket). See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
