# 01 深化效果报告（deepen-report）

Status: resolved (commit 62fd8a6)

## 目标

深化完成后，界面展示「深化了什么」：main.c 前后确定性 diff 的统计 + 逐处改动点（可展开），不依赖 LLM 自述。

## 验收

1. `run_deepen` 返回载荷含 `main_diff`：无差异 = `null`；有差异 = `{"text", "stats": {"additions", "deletions", "hunks"}, "hunks": [{"header", "line", "title", "lines": [{"kind": "add|del|ctx", "text"}]}]}`（done 载荷形状稳定，新增字段不破坏既有字段）。
2. hunk 标题提取规则：删除行 TODO 注释 → 「填充 TODO「…」」；删除行注释 → 注释文本；上下文行注释 → 注释文本；无 → 空（前端 fallback 行号）。
3. 前端 `reviseRenderVerify` 在验证卡下渲染「深化效果」：统计行（新增 +N / 删除 −M / K 处改动）+ 每个 hunk 一个 `<details>`（标题 = title 或「第 N 行附近」，展开 = 逐行着色 diff）；`main_diff` 为 null → 「深化未改动 main.c（无差异）」；无字段（旧后端）→ 不渲染。
4. 测试：`_main_diff` 纯函数（无差异 null / 单 hunk / 多 hunk 统计）；既有 run_deepen 用例补 main_diff 断言；webapp 端点 done 载荷含 main_diff。

## 实现文件

- `src/contest_generator/deepen.py`：新增 `_main_diff` / `_hunk_title` / `_comment_text`；`run_deepen` 三个返回分支加 `main_diff`。
- `src/contest_generator/static/index.html`：`reviseRenderVerify` 追加 `reviseRenderDeepenDiff` + 行渲染函数。
- `tests/test_deepen.py`：纯函数 + 行为断言。
- `.scratch/deepen-report/spec.md` 已建。
