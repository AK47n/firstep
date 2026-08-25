# Spec：评分点覆盖清单（score-checklist / B3）

## 问题陈述

生成结果的「评分点」目前是一段只读文本（`res-score-points`，`评分点：\n- id｜分区｜分值｜句子引用｜描述`）。写电赛报告时要逐条核对「这条评分点做到了没有」，纯文本只能人肉数，错了也不知道；核对进度也不跨会话保留。

## 方案

把生成结果面板里的评分点区块从只读文本升级为**可勾选核对清单**：

- 每条评分点 = 一行：checkbox + `id｜区（基础/发挥）｜分值｜句子引用｜描述`（转义渲染）。
- 区块头部：小标题「评分点核对」+ 进度「已核对 X/M」+「复制核对表」按钮。
- 勾选状态按 **生成工程目录** 持久化到 localStorage（key = `score-checklist:<output_dir>`，
  存已勾选 id 数组）；换工程互不干扰，同一工程重开进度还在。
- 「复制核对表」= 复制纯文本到剪贴板（clipboard → execCommand 兜底，btn-copy-dir 同款）：
  每行 `☑/□ id｜区｜分值｜句子引用｜描述`，勾上的在前面标 ☑，未勾 □。贴进报告/任务清单直接用。
- 进度与勾选实时联动（勾/取消即更新进度与存储，不点保存）。

## 用户故事

- 作为参赛学生，生成工程后我能逐条勾掉已经实现的评分点，一眼看到还剩几条没做。
- 作为参赛学生，我第二天打开同一工程目录，核对进度还在（按目录记住）。
- 作为参赛学生，我能把核对表一键复制成文本贴进实验报告，勾上的自动带 ☑。

## 实现决策

- 纯函数（tests/js 抽取范式，自包含内联 esc）：
  - `scoreChecklistKey(outputDir)` → `score-checklist:<dir>`（dir 空 → 空串不存）。
  - `scoreChecklistItemsHTML(points, checkedSet)` → 每行 HTML（checkbox `data-idx`，
    id 用 `p.id || "score-"+(i+1)`，与 formatScorePoints 同规则；checked 由 checkedSet.has 决定）。
  - `scoreChecklistProgressHTML(checkedCount, total)` → `已核对 X/M`（total 0 → `已核对 0/0` 不炸）。
  - `scoreChecklistExportText(points, checkedSet)` → 多行 `☑/□ ...`（用与列表一致的
    `id｜partLabel｜scoreText｜refsText｜description` 行内格式；part/score/refs 标注规则
    复用 formatScorePoints 的字典：basic→基础、development→发挥，分数字符串、refs 取
    sentence_refs join"、"）。
  - `scoreChecklistParse(storageValue)` → Set（null/坏 JSON/非数组 → 空 Set）。
  - `scoreChecklistSave(key, ids, storage)` / `scoreChecklistLoad(key, storage)` 薄壳；
    storage 抛错（隐私模式）→ 静默返回空/不写，不干扰主流程。
- 交互接线（DOM 部分，不测）：
  - 生成成功回调里 `renderScoreChecklist(data.score_points, data.output_dir)` 替代现在
    的 `textContent` 赋值；`res-score-points` 显隐逻辑保留。
  - `initScoreChecklist()`：`#res-score-points` 上事件委托 change → 重算进度 + 存储；
    `#btn-score-export` 点击 → 复制导出文本 + toast「核对表已复制」（空表时 toast info
    「还没有评分点可复制」）。
  - res-block 静态 HTML 加 `.res-label`「评分点核对」+ 操作行
    （`#sp-progress` + `#btn-score-export`）+ `#sp-list`；移除 `white-space:pre-line`。
- 不与推荐面板的 `renderScorePointPanel`（只读展示）合并——推荐面板保持现状，
  核对清单只在**生成结果**面板（历史目录入口的评分点展示也仍走现有路径，范围外）。

## 测试决策

- `tests/js/score-checklist.test.mjs`：itemsHTML（勾选态/转义/缺 id 兜底）、
  progressHTML（0 分/空、正常）、exportText（☑/□、勾选混合、坏输入不炸）、
  parse（null/坏 JSON/非数组/数组）、save/load 往返 + storage 抛错容错。
- 既有 `formatScorePoints` 及其测试不动（推荐面板/handoff 仍用）。
- 手工 headless：生成后出现清单，勾选→进度+存储，刷新找回，复制按钮出 toast。

## 范围外

- 评分点数据来源/结构不动（后端 `score_points` 载荷不变）。
- 不做导出 .md 文件下载（用户选「复制文本」；下载留给以后要时再说）。
- 不做「一键全勾/清空」按钮（当前条目数少，勾选成本低；需要时再扩）。
