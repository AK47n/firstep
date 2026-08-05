# 05 — 报告形态收口：整合产物全文 + 残留清单 + 骨架预览 + 一次确认

**What to build:** 报告完整形态：判定清单（每项带原因）+ 整合产物（全文 + 整合说明）+ 残留清单（规则化原因）+ 模板 main.c 全文预览；用户一次审查确认；动作被改 → 按最终集合重新校验并落盘。

**Blocked by:** 02 — 判定模型（整合产物数据）；03 — 残留清单；04 — 模板 main.c 预览

**Status:** resolved

## Answer

- [x] DistillationReport 扩展字段全打通：整合产物（content + 说明）、残留条目、模板 main.c 预览
- [x] 确认流程：一次确认 → 落盘（复制 / 整合产物写入 / 剔除 + 模板 main.c 落位）
- [x] 用户改动作（如改回选某份 / 改剔除）→ 校验拦截非法组合，按最终集合落盘
- [x] 全量测试绿（含既有 test_master.py 回归）

实施要点：02（整合产物 content + explanation 进报告）与 03/04（残留条目、旧 main.c 条目带规则化原因进 exclude）的字段已在各自工单打通；本工单补齐最后一块——`DistillationReport` 新增必填 `main_c_preview`（模板 main.c 全文预览，ADR 0002：落盘永远写 `main_c_template(platform)`）。`assemble_report` 用 `main_c_template(platform)` 填充；`to_dict` 输出（确认请求回传同形）；`from_dict` 不信客户端回传值、按平台重推导（保证报告里预览 = 实际落盘内容；平台非法在重建时就大声失败）。落盘仍写模板本体，预览只参与审查。必填字段使"预览 = 落盘内容"不变量结构化（代码评审两轴同点：`= ""` 默认值会让漏填的报告静默带空预览）。一次确认与用户改动作后的重新校验（`_validate_report` / `_validate_forced_exclusions`）由 02/03/04 已有实现覆盖，本工单回归全量测试（347 通过）与 webapp 端到端（distill 响应带预览、确认回传含预览仍 200）。
