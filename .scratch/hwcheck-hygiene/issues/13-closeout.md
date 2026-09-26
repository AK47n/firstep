# 13 — 收尾：全套闸门读数落盘 + 账本与评审处置状态

**要做什么：** 把本批（`01`–`12`）的最终状态钉死：**最后一次实跑**的三道闸门读数落盘、
评审文档每一项标出处置、账本按事实更新、本目录的 spec 收口。做完这张单，本批就可以进 v1.3.1 发版。

**被谁阻塞：** **01–12**（全部）。这是本 spec 的最后一张单，不许提前开工。

**状态：** ready-for-agent

## 验收标准

- [ ] **三道闸门各跑一次全套，读数落盘**（写进本目录，文件名带日期）：
      · 全套 `python -m pytest -n auto -q`（含 skipped 数）；
      · 前端门禁 `node --test "tests/js/*.test.mjs"`；
      · 浏览器门禁 `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`。
      **读数按实跑结果写**，不许抄上一批的数字（`hwcheck-hardening` 的读数是它那一刻的）。
- [ ] 若本批动过生成链 / 配方数据（05、07），**两平台真编译矩阵**复跑并落盘
      （`probe-13-compile-matrix.txt`，按 `hwcheck-hardening/04` 的格数与口径）。
- [ ] `docs/improvement-review-hwcheck.md`：P2 七项 + R1/R2/R3/R4 的**处置状态**逐项更新
      （已修 / 如实降级 / 已记账未修），**并写明本轮对评审自身的三处更正**（Y7 注释引语、
      Y9 板库路径、Y6 行号与漏记的两处）——评审文档不许留着已被证伪的描述。
- [ ] `.scratch/backlog.md`：补一节记本批结论（含"另三处同构固定 tmp 名未修"这条账）。
- [ ] `docs/agents/local-environment.md` §0 更新：本批（P2 + 前端守卫 + 拆分）**未发布**、
      下一步进 v1.3.1、以及"`tests/js` 不许从导出面消费者集合里排除"这条实测事实。
- [ ] `CONTEXT.md`：若本批引入了新术语（"全局桥 / 桥依赖"），补进领域词表。
- [ ] **没有任何工单留在 frontier**：`01`–`13` 全 `Status: resolved`，每张单的读数/反证都在票里或本目录。
- [ ] spec 里「范围外」那几条**逐条确认仍在本批之外**（多实例展开 / 删除 window 桥 /
      排除 `tests/js` / 上板验证 / OLED 分页 / Y10 数据面 / 另三处记录写）。
- [ ] 明确交接一句：本批之后**下一步是发版 v1.3.1**（版本号已拍板；三处同步、`tools/preflight.ps1`、
      两个包、tag、Release 见 `docs/agents/releasing.md`；本机推送要按 `local-environment.md` 的
      `git -c http.https://github.com/.resolve=…` 钉 IP）。
