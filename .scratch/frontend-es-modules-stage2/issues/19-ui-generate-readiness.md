# 19 — 生成页 · 就绪检查：static/js/ui/generate-readiness.js

**要做什么：** generate tab 的「就绪检查面板」簇迁入 `static/js/ui/generate-readiness.js`（readinessState / renderReadinessPanel / refreshReadinessPanel / initReadinessCheck）。**被谁阻塞：** 02 + 18（stepDoneSet import 读）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数（8739-8797）：readinessState 8739（`stepDoneSet.has(5)` @8746 —— import 自 ui/generate-steps.js）/ renderReadinessPanel 8750 / refreshReadinessPanel 8760 / initReadinessCheck 8763。
- 依赖：`$`（app.js）；fx/readiness.js（generateReadinessChecks / readinessSoftChecks / readinessRowHTML / readinessRowsHTML）+ fx/draft.js?（stepProgress——grep 复核）；stepDoneSet（ui/generate-steps.js）。
- markup：#readiness-* 容器 id 不动；host init* 清单含 initReadinessCheck。

## 检查表

- [ ] 新建 `static/js/ui/generate-readiness.js`：4 函数逐字搬移 + import（app.js / fx/readiness.js / ui/generate-steps.js）+ export（readinessState / renderReadinessPanel / refreshReadinessPanel / initReadinessCheck）+ 头部注释
- [ ] index.html：CRLF 感知行区间删除（8739-8797；**物理升序**）+ 顶部 import 行追加
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 就绪面板实况（initReadinessCheck 后行数 > 0）
- [ ] grep 零残留：index.html 无 `function readinessState(` 等 4 名定义
- [ ] 中文提交

## 风险点

- 本簇是 generate 八簇最后一票——收尾前用 `node --test` 全量确认 stepDoneSet 读方（host 分发器 @2321）import 链完整。
