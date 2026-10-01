# 发版 v1.4.3 —— 把 `contrast-residue` 送到用户手上

> **上游**：`main` 上已完成的 `contrast-residue`（六张单全 resolved；7 个实质提交 + 7 个
> `chore: 自动更新 CHANGELOG`，`origin/main` 之后 **14 个提交**）＋ `backlog.md` §34 末
> 「发版：本批未发版」＋ `local-environment.md` §0 交接区（两份账同源）。
>
> **拍板（2026-10-01，用户）**：
> ① 版本号 = **v1.4.3**——照 `docs/agents/releasing.md` 的 SemVer 表「小修小补（bug 修复）→ 修订号 +1」；
> 先例 v1.4.2（对比度禁用态）与 v1.4.1（全站颜色三批）同为对比度修复批，都是修订号 +1；
> ② 范围外照 `backlog.md` §34 四条账，且**本轮只发不修**（发版路上撞到真缺陷先报，不擅自改产品面）；
> ③ 沙箱验收取「从**要发的那棵树**重造干净沙箱 + 真浏览器验收」这一档，**不跑**「真包装进沙箱」那一档。

## 问题陈述

用户手上最新是 **v1.4.2**（2026-10-01 发布）。`main` 上有一批做完的对比度修复没发出去 ⇒
**修好的东西用户拿不到**：三条被 `opacity` 压到 WCAG AA 以下的说明文字（资源总览的「非硬件资源」行、
库外建议 chip 的「⤵ N 方案」计数、被点掉的推荐 chip 上的理由）在浅色下仍然几乎读不出来；
浅色主题板图里「固定/电源」焊盘仍然是浅灰一片里的近黑块。这一批的价值全卡在「没发版」这一步。

## 方案

按 `docs/agents/releasing.md` 走完整条路，账本形状照 `.scratch/release-v1.4.2/`：

1. **版本同步与自检**：三处版本号 → v1.4.3；`VERSIONS.md` 顶部写用户视角条目；`README.md` 当前/上一版两行；
   `tools/preflight.ps1` 四项全绿 ＋ 版本相关单测。
2. **门禁与读数**：前端 / 浏览器（**单独跑**）/ 全量 pytest 三套现跑并落盘；对比度三条冻结读数复跑；
   全站两支老探针不退化。
3. **沙箱「模拟用户机」验收**：从要发的那棵树重造干净沙箱（工具根 / 数据目录 / 端口 8020 / `sim-run.py`），
   真进程 ＋ 真 Chromium，看"用户打开工具会看到什么"。
4. **打包与发布**：更新包 ＋ 完整包（基线 = v1.4.2 两份清单）→ annotated tag → 推送 `main` ＋ tag →
   Release 八件套 → 服务端逐件对账 → 联网自检。
5. **发布后对账与账本**：`local-environment.md` §0（落差归零 ＋ 发布块）/ §3（版本表补 v1.4.3，并**顺带
   补上 v1.4.1 / v1.4.2 两行**——§3 停在 v1.4.0 没跟上）/ §1（沙箱当前状态）/ §2（端口实况）；
   `backlog.md` §34 的「发版」一条划掉；本目录 README 的读数指针。

## 用户故事

1. 作为用户（浅色主题），我想要资源总览的「非硬件资源」行、库外建议 chip 的计数、被点掉的推荐 chip
   上的理由**读得清**，以便不用凑近屏幕猜那句话是什么。
2. 作为用户（浅色主题），我想要板图里「固定/电源」焊盘与「空闲 IO」焊盘**是同一套颜色**，
   以便一眼分得清哪根脚能点。
3. 作为已装用户，我想要在工具里点「检查更新」就能拿到 v1.4.3，以便不用重下完整包。
4. 作为新用户，我想要 Release 说明第一行就告诉我该下哪个包，以便不在八个资产之间犹豫。
5. 作为维护者，我想要三套门禁在**要发的那棵树**上现跑并落盘，以便"绿"有据可查而不是靠记忆。
6. 作为维护者，我想要沙箱上是**真进程 ＋ 真浏览器**看到的观感，以便发现"夹具里看不出来"的问题。
7. 作为维护者，我想要发版全程**产品面零改动**（除版本号三处），以便这次发布的每个字节都能追溯到
   已评审过的批次。
8. 作为下一轮接手的人，我想要 §0 落差归零、§3 的版本表与基线跟着走，以便下次发版不必重新考古。

## 实现决策

- **改的**：`src/contest_generator/__init__.py`、`pyproject.toml`、`VERSIONS.md`、`README.md`、
  `tests/test_changelog.py` 的版本清单断言（**追加而非替换**）、`docs/agents/local-environment.md`、
  `.scratch/backlog.md`、本目录账本。
- **不改的**：`src/contest_generator/static/**` 与一切业务逻辑——**本轮只发不修**。
- **打包**：`tools/pack-update.ps1 -Tag v1.4.3 -Baseline firstep-update-v1.4.2.files.txt`、
  `tools/pack-full.ps1 -Tag v1.4.3 -Baseline firstep-full-v1.4.2.manifest.json`（基线在
  `%USERPROFILE%\Desktop\firstep-pack`，开工前已核实两份都在）。
- **tag 与推送**：annotated tag `v1.4.3`；推送用
  `git -c http.curloptResolve=github.com:443:<当场验过的 IP> -c http.postBuffer=524288000 push origin main v1.4.3`。
  ⚠ **推 tag 会触发 pre-push 整套复跑**（pytest ＋ 前端 ＋ 浏览器，十几分钟），预留时间、别当卡死。
- **发布说明**：照 `releasing.md` 模板，前两行固定（新用户 / 已装用户），正文按**用户视角**写，
  点名两条可见变化（三条文字变清楚 / 浅色焊盘换色）。
- **联网自检**：`python tools\check-download-docs.py`（打包上传之后那一发才算数）。

## 测试决策

- **三套门禁**（顺序照纪律，浏览器门禁**不与任何 pytest 并行**）：
  前端 `node --test "tests/js/*.test.mjs"`；浏览器 `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`；
  全量 `python -m pytest -n auto -q`。读数用
  `python .scratch/hwcheck-hygiene/readings.py <名> --out-dir .scratch/release-v1.4.3 -- <命令>` 落盘
  （PowerShell 的 `>` 写 UTF-16LE，不能用）。
- **对比度冻结读数复跑**：`.scratch/contrast-residue/probe-06-register-readings.py`（渲染方登记 19 条）、
  `.scratch/disabled-forms/probe-00-inventory.py`（`opacity` 活规则 15 / 未在册 0）、
  `.scratch/contrast-residue/probe-09-cant-readings.py`（`li.cant` 真像素）。
- **全站不退化**：`.scratch/ui-density-sitewide/probe-00-survey.py`（裸 px 字号 0 / `--fs-*` 引用 428 处）、
  `.scratch/ui-density-sitewide/probe-04-scope-calibers.py`（十四个作用域 0/0、页面尺 0 条、整圈完整框 115）。
- **沙箱验收**：照 `.scratch/release-v1.4.0/probe-sandbox-accept.mjs` 的口径（计算样式、折叠区全展开、
  "有文字的元素"），本目录复制一支并**加本轮的检查**（三条文字的计算色与其对比度、浅色固定焊盘取值、
  版本读数）。
- **判定纪律**：读数落盘时间戳必须**晚于**最后一次改产品面；红了先单跑那条 spec 再查产品；
  浏览器门禁不与任何 pytest 并行。

## 范围外

- ⚠ **`.role-type` 角色类型标的浅色 3.54**（暗 4.94）——要收先定"模板变量内联取色怎么入判据"，**另立**。
- **叠加态定价**（浅 3.42 / 暗 3.11）与 **`--accent` 非文字 3:1**（2.70）——明账，**不收**。
- **亮色覆盖完整性**要不要立腿（本轮只补了一个值）——不收。
- 等人的四单不变：`hwcheck-acceptance/05` / `hwcheck-hardening/08` / `identity-fields/06` / `real-acceptance/01`。
- **产品面改动**：本轮只发不修。
- `.scratch/**` 里历史批次的探针脚本本身（只复跑，不改口径）。

## 补充说明

- **基线**：`firstep-pack\firstep-update-v1.4.2.files.txt`（168,621 B）与
  `firstep-pack\firstep-full-v1.4.2.manifest.json`（3,722,132 B），10-01 10:34 打的。
- **本机实况（开工前核过）**：工作树干净；`origin/main` = `01beebce`、本地 `HEAD` = `e4cc6612`
  （**14 个提交待推**）；8020 / 8021 空着；8000 上真身**现在没在跑**（§2 记的"2026-09-29 13:07 起在跑"
  是那一刻的事实）；真身数据目录 `~\.contest_generator\config.json` mtime = **2026-09-10 23:28:07**
  （这是本次验收的"零触碰"基线）。工具链：`node v24.15.0` / `Python 3.14.6` / `pytest 9.1.1`。
- **`.res-soft` 的真像素账没抹平**：它只在"带 AI 洞察的任务计划"里渲染得出来，本轮不改产品面、
  也不重造那份数据；发布说明照样点名它（用户视角它确实变清楚了），依据是"只删了 `opacity` 一句
  ＋ 同一对色在别处量过（浅 5.25 / 暗 5.67）"。
