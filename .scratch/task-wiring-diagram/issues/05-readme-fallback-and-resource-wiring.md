# 05 旧工程读取兜底 + 退化路径按资源标定接线图

Status: resolved

已提交：0392ac0（实现）+ e348669（CHANGELOG）；ff4c135（评审整改：taskWiringRefs 单点收口 / _split_role 归一化 / board 守卫）+ ead2b91（CHANGELOG）。
双轴评审通过：标准轴无硬违规（Duplicated Code 已整改）；规格轴无实质缺失（三点打磨：归一化 ✓ / 守卫 ✓ / 组合边缘记录为可接受）。

## 要做什么

用户实测反馈（工单 01-04 交付后）：旧工程（无 `.contest_wiring.json` 快照、任务迭代无 wiring 字段）走退化路径只显示「资源高亮板图」——只标出本步引脚，**不知道每根引脚接哪个模块哪个端子，仍要读文字**。要求退化图也表达「引脚 → 模块端子」接线关系。

本次修改两部分：

1. **读取侧兜底（后端）**：`/api/wiring` 快照缺失时，从 README「引脚接线表」（与快照**同源**——README 表由 `_pin_row_items` 同一推导渲染，解析即恢复 rows）+ `.contest_context.json` 的 platform + 静态板定义（board_for_platform）→ 返回与快照同形的非空载荷 `{platform, board, rows}`。任意环节缺失/坏 → None → 维持空载荷（前端退化），绝不 500。
2. **前端退化增强**：wiring 空时，用本任务 `resources`（AI 拆解标定的真实引脚名/模块 slug）∩ 接线行（快照或 README 兜底）反推「本步涉及的线」→ 渲染接线图（本步高亮 + 显示全部接线可用），caption 注明「按引脚资源标定」；无行可命中 → 既有资源高亮板图（保持现状）；再无 → 纯文字。
   - 引脚名命中：row.pin == resource → 该行端子（role_id）即接线目标；
   - 模块 slug 命中：row.slug == resource → 该模块全部行；
   - 无匹配项（供电/板载资源名/外设名等无接线行）→ 跳过，不出现幻觉线。

数据纪律不变：图仍由确定性数据渲染（接线行 + 引脚/端子名引用），resources 只是「选哪些行」的名字；接线行与 README 同源。

## 被谁阻塞

无（04 已提交；本工单在其之上增量）。

## 变更面

- `src/contest_generator/readme.py`：`parse_pin_table(text) -> list[dict] | None`（README 表解析：定位 `## 引脚接线表` 段、表头 `| 模块 | 角色 | 引脚 | 说明 |`、跳过 `|---|` 分隔行、角色列拆 `id（label）`、行 → {slug, role, role_id, role_label, pin, remark}；无表/无数据行 → None）。
- `src/contest_generator/wiring.py`：`read_wiring_snapshot_legacy(output_dir) -> dict | None`（context platform + README 表 + 静态板 → 快照同形 dict；容错全 None 化）。
- `src/contest_generator/webapp.py`：`/api/wiring` 快照 None → legacy 兜底（docstring 同步）。
- `src/contest_generator/static/js/fx/wiring.js`：`wiringFromResources(resources, rows)`（反推 wiring 引用，去重保序）；`wiringDiagramHTML` opts 增 `inferred`（caption「按引脚资源标定的接线」）。
- `src/contest_generator/static/js/fx/task.js`：`wiringSectionHTML` 增 ①b 分支（wiring 空 + rows 非空 + resources 反推非空 → inferred 接线图）。
- `src/contest_generator/static/js/ui/wiring.js`：`attachWiringInputs` wiring 空时用反推结果挂句柄（toggle 可用）。
- 测试：`tests/test_readme.py`（round-trip 同源）、`tests/test_wiring.py`（legacy 兜底 + 容错）、`tests/test_webapp.py`（兜底 payload）、`tests/js/wiring.test.mjs`（反推 + inferred caption）、`tests/js/task.test.mjs`（①b 三输入域）。

## 验收标准

- round-trip：`render_readme(...)` 输出 → `parse_pin_table` → 与 `wiring_rows(...)` 结构化逐行相等（同源一致，图上不出现在表格之外的线）。
- 旧工程目录（无快照、有 README + context）`/api/wiring` → 200 + 非空 {platform, board, rows}；无 README / 无 context platform / 未知平台 → 200 空载荷。
- resources 引脚/模块 slug 反推出正确接线引用（含去重、多行同 pin、无匹配跳过）。
- 前端：无 wiring 但有反推行 → 接线图（inferred caption、wiring-line 存在、toggle 可用）；反推空 → 资源高亮板图；再无 → 纯文字。
- 全量 pytest + tests/js 绿；评审两轴通过后提交（中文提交信息）+ CHANGELOG + 本工单 resolved。
