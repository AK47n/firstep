# 03 — 真器件身份字段回填（只填能核实到出处的）

**要做什么：** 真器件条目里**出处能核实到**的，把 kit 与 source_url 填进 manifest，
模块详情弹窗从此显示套件型号与购买链接；核不出的留在工单 04 的待补清单，**不落库**。
审计 `[身份]` 行随之只报「真器件待补」。

**被谁阻塞：** 02（豁免落地后缺口才只剩真器件）

**状态：** resolved

- [x] 按 spec 取源优先级回填（每条都能指到出处，逐条记 Comments）：
      ① 库内同硬件已有条目（motor/mspm0 ← TB6612 条目；xunji/mspm0、pid 双平台 ←
      灰度传感器条目）；② 立创 wiki 模块手册原页（oled 双平台、servo/mspm0、
      motor/mspm0、xunji/mspm0、pid 双平台、k230 双平台）
- [x] **零编造**：每条 source_url 都在本次抓取的 wiki 模块索引（dmx 70 页 /
      dkx-stm32f103c8t6 77 页）里，或来自库内既有条目 / 本地手册原文；填完跑一次
      全库 URL 存在性探针（HEAD 200）记证据
- [x] 复跑 `tests/test_library_invariants.py` 身份守卫绿 + 全量 pytest 绿
- [x] 复跑 audit `[身份]`：缺 kit / 缺 source_url 数 = 剩余真器件待补数（13 条 /
      7 slug），并把清单写进工单 04
- [x] 复跑预算回归（`tests/test_manifest.py::test_lean_summary_lines_fit_preselect_budget_for_real_library`
      + 词表预算），确认 kit 只进完整行、瘦身行不含套件段、余量未被吃穿
- [x] 不碰 5.5 四条遗留

## Comments

- 取源核实手法：在线抓取 lckfb wiki 模块手册索引页（`wiki_index_links.py`，dmx + dkx
  共 201 条站内链接）全量核对 + 候选页 HEAD 200 实测；本地
  `sources/materials/lckfb-地猛星移植手册/` 的模块手册 md 提供套件名与采购链接原文。
  探针：`.scratch/library-audit/wiki_index_links.py` / `probe_identity_guard_red.py` /
  `apply_identity_backfill.py`（回填脚本，可复跑幂等）/ `probe_backfill_urls.py`（URL 实测）。
- kit 文本形态沿用库内既有惯例（`型号 + 简述`，必要时带 `页面采购链接：…`），
  source_url 一律用可核实的公开页面。
- **回填实录（9 条 / 6 slug）**：
  | 条目 | kit | source_url | 出处 |
  |---|---|---|---|
  | motor/mspm0 | TB6612FNG 电机驱动模块（双 H 桥，淘宝 id=616285586821） | dmx tb6612 页 | ① 库内 motor/stm32 同硬件条目 |
  | xunji/mspm0 | 电子积木模拟灰度传感器（天猫 id=676917570259） | dmx grayscale 页 | ① 库内灰度传感器条目 + 本地手册原文 |
  | pid/mspm0、pid/stm32 | 同上 | dmx / dkx grayscale 页 | ① 同上 |
  | oled/mspm0、oled/stm32 | 0.96 寸 OLED 12864（SSD1306，淘宝 id=40809409804） | dmx / dkx `screen/0-96-iic-single-screen.html` | ② 本地手册原文 + 索引页 |
  | servo/mspm0 | SG90/MG90S 9g 舵机（天猫 id=615779197448） | dmx sg90 页 | ① 库内 servo/stm32 同硬件条目 |
  | k230/mspm0、k230/stm32 | 立创·庐山派 K230-CanMV 开发板 | `wiki.lckfb.com/zh-hans/lushan-pi-k230/` | ② 官方板页（本地手册 `k230资料/立创·庐山派K230-CanMV开发板原理图.pdf` 佐证型号） |
- URL 实测（`probe_backfill_urls.py`）：9 条全部 HEAD 200（非 200 = 0）。
- audit 复跑：`[身份] 平台条目共 170（内部件/协议切片豁免 24）：真器件缺 kit 13、
  缺 source_url 13`——缺的 13 条全在工单 04 待补清单（7 slug）。
- **本轮暴露并修正的判据缺陷（记一笔）**：`tests/test_lckfb_attribution.py` 原先按
  `is_wiki_source_url(source_url)` 反推「wiki 派生模块」，于是把硬件出处补成 wiki 页的
  原生移植驱动（motor/oled/xunji/pid/servo/k230）误判成「源码缺来源标注」。判据改取
  **代码事实**（头部来源标注块）后，两向都守且不误伤；细节见该测试 docstring 与本工单
  提交信息。附带新增两条断言：条目 source_url 是 wiki 页且源码头部引用了该页 → 头部
  必须有来源块；单 URL 来源块必须与条目 source_url 指同一页（跨平台同页版本算命中）。
- 预算：kit 只进 `ManifestSummary.to_line()` 完整行，瘦身行 `lean_copy` 不含套件段——
  `test_lean_summary_lines_fit_preselect_budget_for_real_library` 与词表预算回归全绿。
