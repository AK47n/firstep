# 发版 v1.4.4 —— 把 `pin-type-contrast` 送到用户手上

> **上游**：`main` 上已完成的 `pin-type-contrast`（五张单全 resolved；12 个提交在 `origin/main` 之前）
> ＋ `backlog.md` §35 末「本轮不发版」＋ `local-environment.md` §0 交接区（两份账同源）。
>
> **拍板（2026-10-02，用户）**：
> ① 版本号 = **v1.4.4**——照 `docs/agents/releasing.md` 的 SemVer 表「小修小补（bug 修复）→ 修订号 +1」；
> 先例 v1.4.1 / v1.4.2 / v1.4.3 同属对比度修复批，都是修订号 +1；
> ② 发布说明**点名浅色主题下引脚卡片的配色变了**（三条要点：可见变化 + 暗色只动 enc / uart + 内部加固）；
> ③ **不跑沙箱真机验收**——链条 = 三处版本号同步 → 版本相关单测 → 三套门禁 → 打包 → 上传 → 账本收口；
> 证据由本批的真像素读数（变好 77 / 没变 43 / 变差 0）＋ 三套门禁承担；
> ④ 范围外照 `backlog.md` §35 的四条账，且**本轮只发不修**（发版路上撞到真缺陷先报，不擅自改产品面）。

## 问题陈述

用户手上最新是 **v1.4.3**（2026-10-01 发布）。`main` 上有一批做完的引脚配色修复没发出去 ⇒
**修好的东西用户拿不到**：**浅色主题**下引脚配置卡片的角色类型标、（`已绑 / 现绑`）状态文字、
板图上已绑引脚的名字、图例与菜单色点，仍然几乎读不出来（`spi` / `exti` 1.45、`i2c` 1.40，
八族**全低**）。这一批的价值全卡在「没发版」这一步。

## 方案

按 `docs/agents/releasing.md` 走完整条路，账本形状照 `.scratch/release-v1.4.3/`：

1. **版本同步与自检**：三处版本号 → v1.4.4；`VERSIONS.md` 顶部写用户视角条目；`README.md` 当前/上一版两行；
   `tools/preflight.ps1` 四项全绿 ＋ 版本相关单测。
2. **三套门禁**：前端 / 浏览器（**单独跑**）/ 全量 pytest 现跑并落盘。
3. **打包**：更新包（基线 = v1.4.3 的 `files.txt`）＋ 完整包（基线 = v1.4.3 的 `manifest.json`）
   ——注意本机事实①：**打包脚本拒脏工作树，而落盘读数本身会弄脏**，顺序摆成
   「先提交手上的改动 → 打更新包 → 提交读数 → 打完整包 → 再提交读数」。
4. **发布**：annotated tag `v1.4.4` → 推送 `main` ＋ tag（会跑 pre-push 闸门，十几分钟）→
   Release 八件套 → 服务端逐件对账 → 联网自检 `tools\check-download-docs.py`。
5. **账本收口**：`local-environment.md` §0（落差归零 ＋ 发布块）/ §3（版本表补 v1.4.4 行 ＋
   基线换成 v1.4.4 两份）/ §1（沙箱状态：本轮**没动**沙箱）/ §2（端口实况）；
   `backlog.md` §35 的「发版」一条划掉；`.scratch/pin-type-contrast/README.md` 的「本轮不发版」回改。

## 用户故事

1. 作为用户（浅色主题），我想要引脚卡片上的类型标、「已绑 / 现绑」状态文字、板图上已绑引脚的名字
   与色点**读得清**，以便不用凑近屏幕猜这根脚是什么角色。
2. 作为用户（暗色主题），我想要这一版**别把我已经看惯的地方改乱**，以便升级后观感照旧
   （暗色只动 enc / uart 两处文字档）。
3. 作为已装用户，我想要在工具里点「检查更新」就能拿到 v1.4.4，以便不用重下完整包。
4. 作为新用户，我想要 Release 说明第一行就告诉我该下哪个包，以便不在八个资产之间犹豫。
5. 作为维护者，我想要三套门禁在**要发的那棵树**上现跑并落盘，以便"绿"有据可查而不是靠记忆。
6. 作为维护者，我想要发版全程**产品面零改动**（除版本号三处），以便这次发布的每个字节都能追溯到
   已评审过的批次。
7. 作为下一轮接手的人，我想要 §0 落差归零、§3 的版本表与基线跟着走，以便下次发版不必重新考古。

## 实现决策

- **改的**：`src/contest_generator/__init__.py`、`pyproject.toml`、`VERSIONS.md`、`README.md`、
  `tests/test_changelog.py` 的版本清单断言（**追加而非替换**）、`docs/agents/local-environment.md`、
  `.scratch/backlog.md`、`.scratch/pin-type-contrast/README.md`、本目录账本。
- **不改的**：`src/contest_generator/static/**` 与一切业务逻辑——**本轮只发不修**。
- **打包**：`tools/pack-update.ps1 -Tag v1.4.4 -Baseline firstep-update-v1.4.3.files.txt`、
  `tools/pack-full.ps1 -Tag v1.4.4 -Baseline firstep-full-v1.4.3.manifest.json`（基线在
  `%USERPROFILE%\Desktop\firstep-pack`，开工前已核实两份都在）。
- **tag 与推送**：annotated tag `v1.4.4`；推送用
  `git -c http.curloptResolve=github.com:443:<当场验过的 IP> -c http.postBuffer=524288000 push origin main v1.4.4`。
  ⚠ **推 tag 会触发 pre-push 整套复跑**（pytest ＋ 前端 ＋ 浏览器），预留时间、别当卡死。
- **上传**：`gh release create` ＋ 两发 `gh release upload`（八件、ASCII 名）；
  ⚠ 本机事实②：**这段上行极慢**（实测 ≈ 0.22 MB/s，1.08 GB 传了一个多小时）——**用后台任务跑**。
- **发布说明**：照 `releasing.md` 模板，前两行固定（新用户 / 已装用户），正文按**用户视角**写，
  点名一处可见变化（浅色引脚配色）。
- **联网自检**：`python tools\check-download-docs.py`（打包上传之后那一发才算数）。
- **沙箱验收**：本轮**不做**（用户拍板③）；`local-environment.md` §1 照实写「沙箱仍是 v1.4.3、
  本轮没动」。

## 测试决策

- **版本相关单测**：`pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q`
  → 全绿（读数 `pytest-version-01.txt`）。
- **三套门禁**（顺序照纪律，浏览器门禁**不与任何 pytest 并行**）：
  前端 `node --test "tests/js/*.test.mjs"`；浏览器 `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`；
  全量 `python -m pytest -n auto -q`。读数用
  `python .scratch/hwcheck-hygiene/readings.py <名> --out-dir .scratch/release-v1.4.4 -- <命令>` 落盘
  （PowerShell 的 `>` 写 UTF-16LE，不能用）。
- **包内抽检**：照 `.scratch/release-v1.4.3/check-packs.py` 的口径复制一支到本目录
  （版本块 / `__version__` / 禁止面 0 / `00-START-HERE.txt` / 两个 zip 实算 sha256）。
- **判定纪律**：读数落盘时间戳必须**晚于**最后一次改产品面；红了先单跑那条 spec 再查产品；
  浏览器门禁不与任何 pytest 并行。

## 范围外

- **`spi` / `exti` 两族库内零实例**（造不出角色 ⇒ 渲染面没有读数；令牌成套由腿⑪ 看着）——不是缺陷。
- **SVG 属性写法**（`font-size="11"`）不进判据——留白，别当新发现。
- **叠加态定价**（浅 3.42 / 暗 3.11）与 **`--accent` 非文字 3:1**（2.70）——明账，**不收**。
- 等人的四单不变：`hwcheck-acceptance/05` / `hwcheck-hardening/08` / `identity-fields/06` /
  `real-acceptance/01`。
- **产品面改动**：本轮只发不修。
- `.scratch/**` 里历史批次的探针脚本本身（只复跑，不改口径）。
- **沙箱真机验收**：本轮不做（拍板③；v1.4.3 那轮做过 50/50，v1.4.2 那轮也没做）。

## 补充说明

- **基线**：`firstep-pack\firstep-update-v1.4.3.files.txt`（168,621 B）与
  `firstep-pack\firstep-full-v1.4.3.manifest.json`（3,722,132 B），10-01 22:25 / 22:26 打的。
- **上一版实测体积**（写进 README/说明作参照）：更新包 **301,994,538** B、完整包 **791,853,978** B。
- **本机实况（开工前核过）**：工作树干净；`origin/main...main` = **`0 12`**（12 个提交待推）；
  Node v24.15.0 / Python 3.14.6 / gh 2.97.0（已认证 `AK47n`）。
