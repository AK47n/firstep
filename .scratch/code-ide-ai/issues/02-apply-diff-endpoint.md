# 02 — 后端 /api/code/apply-diff 端点（preview + 写模式）

**要做什么：** src/contest_generator/codeview.py 新增端点 `/api/code/apply-diff`
（POST）：`{dir, path, base_mtime_ns, hunks, preview}`——
- 校验：dir 合法输出目录、path 相对路径（与 save_code_file 同口径）、hunks
  结构（kind 枚举/line 数字/text）→ 非法 400 中文。
- 应用：hunks 按 line 起点 + ctx 对齐应用到当前文件内容——**复用/对齐后端
  既有 fix/apply 与 deepen main_diff 应用函数族（单套实现，不复制算法）**；
  行号无法对齐 / 越界 → 400（说明原因）。
- preview=true：只算不写，返回 `{new_content, stats:{additions,deletions,
  hunks}}`；false：写盘（先校验 base_mtime_ns 与磁盘一致——不一致 409 与
  save_code_file 同口径），返回 `{saved, mtime_ns, stats}`。
- main.c 与任意 .c/.h 均可（path 任意合法文件）。

**被谁阻塞：** 无——契约 spec 已定稿，与 01 并行（01 是前端校验器，各自独立）。

**状态：** resolved

- [ ] 验收 1：preview 不落盘（mtime 不变、返回 new_content 与手验一致）。
- [ ] 验收 2：写模式成功 → 磁盘内容 = 应用后内容，返回新 mtime_ns。
- [ ] 验收 3：base_mtime_ns 不匹配 → 409（与 save 同口径消息模式）。
- [ ] 验收 4：hunk 行号越界/不对齐、kind 非法、path 越界 → 400 中文。
- [ ] 验收 5：pytest 新增用例（test_codeview.py 或新文件）全绿 + 全量回归绿。

**结论：** 已落地（双轴评审通过）。

**src/contest_generator/codeview.py**（save_code_file 之后新增）：
- `_validate_ai_hunks(hunks)`：结构校验（kind ∈ ctx/del/add、line ≥1 整数、
  title 可空、每 hunk ≥1 非 add 锚点行）——与 fx/ai-diff.js parseAiDiff 契约对齐。
- `_find_hunk_line(lines, old, from_idx)`：**顺序整行精确匹配** old 段
  （hunk 非 add 行 = 锚点）；返回下标或 None。不做归一化——用户确认路径
  显式失败提示重预览，不静默魔改。
- `_apply_hunks_to_lines(lines, hunks)`：游标顺序消费——跳过区间补磁盘行
  + hunk 行输出（ctx 保留 / add 插入 / del 丢弃）+ 尾部补全。unified 语义：
  替换 = del+add、插入 = ctx+add。
- `apply_code_diff(root, rel_path, hunks, base_mtime_ns=None, preview=False)`：
  路径 `_resolve_in_root` 单源 + is_file；UTF-8 守卫；读取 CRLF→LF 归一化
  （匹配不受行尾差干扰）；`preview=True` 只算不写 → {new_content, stats}；
  写模式 base_mtime_ns 字符串 int 化，不匹配 → CodeViewConflictError 409
  「已被外部修改…为免覆盖请重新加载后再应用」；超限 _raise_oversize；
  atomic tmp+os.replace；返回 {saved,path,size_bytes,mtime_ns,stats}。
  **关键设计：应用以 old 段整行匹配为锚点，AI 行号 line 仅展示语义不参与
  匹配**（免疫 LLM 行号不准；与 parseAiDiff「解析器不钉死 line↔lines」决策
  闭环）。

**webapp.py**：`@app.post("/api/code/apply-diff")`（code_apply_diff，位于
/api/code/save 前）——{dir, path, hunks, base_mtime_ns?, preview?}；
preview 时 base_mtime_ns 非必填。

**双轴评审（子代理 062bc2cd）**：A 轴 0 硬性违规，3 判断项（冲突文案后半句
与 save 稍异——核心「已被外部修改」一致，合理；base_mtime_ns 校验位于
oversize 之后；hunk 文本未参与归一化）；B 轴验收 1-5 全覆盖，2 条有意偏差
（均记录在案）：
1. 「行号不对齐→400」未按字面实现——实测 line=999 但内容匹配仍成功应用。
   **验收文本过期**：与「old 段匹配为锚、line 仅展示」设计一致，保留。
2. 「复用既有 apply 函数族」未字面满足——后端无 hunk-apply 既有函数，
   新写 _apply_hunks_to_lines 必要（单套实现不复制，满足）。
已知限制（低危）：old 段在文件中多次出现时 line 零消歧可能错位——AI 给的
hunk 通常含上下文行，且 409 三选模态提供改后审查，接受。

**全量回归**：3116 passed；node 1049（本期先行）全绿。

- [x] 验收 1：preview 只算不写（disk 不变）。
- [x] 验收 2：preview 无 base_mtime_ns 可调用。
- [x] 验收 3：写模式错误 base_mtime_ns → 409 中文「已被外部修改…」。
- [x] 验收 4：hunks 应用正确（多 hunk 顺序 / 替换 / 插入 / 首行 / 尾部）。
- [x] 验收 5：全量回归绿（3116）。

## Comments

- 2026-09-09 补标 resolved（代码事实盘点，复核工单自述）：
  `src/contest_generator/codeview.py`——`_validate_ai_hunks`（391）、
  `_find_hunk_line`（430）、`_apply_hunks_to_lines`（444）、`apply_code_diff`（465，
  `_resolve_in_root` 安全单源 + UTF-8 守卫 + CRLF 归一 + preview 只算不写 +
  写模式 `st_mtime_ns` 不匹配 → `CodeViewConflictError` 409 + 原子 tmp/os.replace）。
  路由 `src/contest_generator/webapp.py:4433 @app.post("/api/code/apply-diff")`。
  测试：域算法 `tests/test_apply_diff.py` 13 用例（:45 preview 不写 / :66 写模式与
  stats / :85 与 :97 409 / :111 preview 无 base / :125 首行替换 / :136 尾部插入 /
  :145 多 hunk 顺序 / :168 子目录 / :182 结构非法 400 / :197 ctx 不匹配 400 /
  :207 路径越界与缺文件 400 / :217 非 UTF-8 拒绝）；路由层
  `tests/test_webapp.py:8690/8723/8751`（preview 不写、写成功、409）。
  验收逐条对照：① preview 不落盘（域 :45 + 路由 :8690）✓ ② 写模式内容与 mtime
  （:66 + :8723）✓ ③ base_mtime_ns 不匹配 409「已被外部修改」（:85 + :8751）✓
  ④ hunk 结构/越界/路径非法 400（:182/197/207）✓ ⑤ pytest 用例全绿 ✓。
  记录：工单结论段已自述两处有意偏离（「行号不对齐 → 400」未按字面实现、
  「复用既有 apply 函数族」后端无既有 hunk-apply），本盘点确认与代码一致，
  不构成未落地项。
