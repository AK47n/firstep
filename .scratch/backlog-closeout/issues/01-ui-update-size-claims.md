# 01 — 更新面板的体量声明说实话，并让守卫扫到产品界面

**要做什么：** 学生在更新面板上读到的完整包体量是**真的数字**（几百 MB 级），不是已下线
7z 渠道那个 6.2 GB；而且这条判据**测试期就有机器盯**（不必等到发版前跑联网自检）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-09-27；读数、双轴评审处置、偶发红与账见文末）

## 现状（实测，带 file:line）

- `src/contest_generator/static/index.html:4785`：「…一键更新（轻量更新包，几百 MB），
  **不用重下 6.2 GB 完整包**…」——6.2 GB 是 **v1.0.0 那个 7z 分卷形态**的体量。
- 同文件 `:4803`：「一键下载整份 firstep（…，约 **1 GB**，…）」——同一面板里的另一处体量。
- **实测真值**（本机发布产物 + 线上资产，见 `docs/agents/local-environment.md` §0）：
  完整包 `791,672,980 B` = **792 MB**（755 MiB）；轻量更新包 `301,813,614 B` = **302 MB**。
- 同文件 `:4794`：「电赛资料库（`sources\materials`，**5 GB+**）随大发版更新；…**几 GB 级更新**
  也能选批次下载…」——**这处也是错的**（工单初稿以为它是真的，实测推翻了）：
  - 装完的资料库实测 **≈0.67 GiB**（沙箱 `firstep-sim\sources\materials` = 5088 文件 / 0.67 GiB；
    发布包里的 `sources/materials` = 0.65 GiB / 5066 文件）；
  - 「5 GB 以上」那句在 `README.md:24`——它说的是**故意不进包的第三方安装件**
    （CCS 安装包 / K230 资料 / VSCode），**不是资料库**：本机 `sources/materials` 之所以 5.94 GiB，
    是因为摊着 `.zip` 1993 MiB + `.exe` 1054 MiB + `.z01`/`.xz`/`.gz` 那批网盘原件（都不进包）。
  - 所以「5 GB+」把两件事混成了一件；「几 GB 级更新」也随之不成立（整库才 0.7 GB）。
- 守卫现状：`tools/check-download-docs.py`（发版前、联网）与 `tests/test_onboarding_docs.py`
  （测试期）**都只扫 README 与 Release 说明**，`static/index.html` 不在扫描面里 → 所以它一直没报。

## 验收标准

- [ ] 界面三处体量按实测改写：`:4785`「6.2 GB 完整包」→ 完整包真值口径（约 800 MB）；
      `:4794`「5 GB+ / 几 GB 级更新」→ 资料库真值口径（约 0.7 GB / 5000+ 个文件）；
      `:4803`「约 1 GB」→ 与上面同口径（实测 792 MB）。
      **工单原文说 `:4794` 是真的、不改——那句判断本身错了，就地更正（依据见上「现状」）。**
- [ ] 守卫扩面（`tests/test_onboarding_docs.py`）：把既有的 `dead_channel_hits` **同一份判据**
      用到产品界面文本（`static/index.html`）上；并新增一条体量判据——界面里出现「完整包」
      的那一行若带 `N GB` 且 `N >= 2` → 红（真值 < 1 GB，十倍级错法一次抓住）。
- [ ] 正向对照：把「6.2 GB」那句话塞回一份**合成文本** → 新判据必须红（不靠真改文件）。
- [ ] 前端门禁 `node --test "tests/js/*.test.mjs"` 与**浏览器门禁**
      `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` 各一份读数（`index.html` 是浏览器门禁落点）。
- [ ] 全量 `python -m pytest -n auto -q` 一份读数。
- [x] 反证探针：撤掉界面那句修（改回 6.2 GB）→ 新判据红；逐条声明 + 与实得对账 + 复原 sha256 逐字节。
      **三段**：A 撤「6.2 GB」/ B 撤「5 GB+」/ C 撤「不用装 7-Zip」的否定式。
- [x] 顺手修掉判据自身一个**假阴性**（评审实测、本单 C 段钉住）：否定式回看跨了分句——
      `…不用手动下分卷、需要装 7-Zip` 里的「不用」正好落在窗口上限，把真推荐放行了；
      改成**只在同一分句里回看**（`_CLAUSE_BREAKS` 含冒号与换行）。
- [x] `tools/check-download-docs.py` 同步同一份判据（它自己的注释要求两处一致）+ 显式钉 UTF-8 stdout
      （旧读数整份乱码，143 个 U+FFFD —— 本机 `python` stdout 默认 GBK）。

## 结论（读数、评审处置、账）

**形状。** 界面三处体量按实测改写 + 确认弹窗那处同型数字去掉；守卫从"只扫 README/Release 说明"
扩到**产品界面文本面**（`static/index.html` + `static/js/**/*.js`），并顺手修掉它自己的一个假阴性；
`tools/check-download-docs.py`（发版前孪生自检）同步同一份判据与 UTF-8 stdout。

**实测真值（本单的立论依据，都是本机量的）**

| 项 | 实测 | 界面原来写的 | 现在写 |
|---|---|---|---|
| 完整包 | `firstep-full-v1.3.1.zip` = 791,672,980 B = **792 MB** | 6.2 GB（已下线的 7z 分卷形态） | 约 800 MB |
| 轻量更新包 | `firstep-update-v1.3.1.zip` = 301,813,614 B = **302 MB** | 几百 MB ✅ | 几百 MB（不动） |
| 资料库（装完） | 沙箱 `firstep-sim\sources\materials` = 5088 文件 / **0.67 GiB**；发布包里 = 5066 文件 / 0.65 GiB | 5 GB+ / 几 GB 级更新 | 约 0.7 GB / 5000+ 个文件 |
| 装机件（故意不进包） | `README.md:24` 的「5 GB 以上」说的是它们 | 被混成了资料库体量 | 界面不再混为一谈 |

**读数（本机实跑，全部 UTF-8 落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 定向 pytest | `python -m pytest tests/test_onboarding_docs.py tests/test_repo_language.py -q` | **18 passed** | `probe-01-tests.txt` |
| 反证（三段） | `python .scratch/backlog-closeout/probe-01-red.py` | **PASS**：A/B/C 三段各让界面判据点名红、复原 sha256 逐字节、复原后 13 passed | `probe-01-red.txt` |
| 前端门禁 | `node --test "tests/js/*.test.mjs"` | **1830 passed / 0 fail** | `probe-01-js.txt` |
| 浏览器门禁 | `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` | **60 passed / 0 fail**（先红过一次，见下"偶发"） | `probe-01-browser.txt` |
| 发版前自检（离线） | `python tools/check-download-docs.py --offline` | **PASS**（README 与包内文件一致） | `probe-01-offline-docs.txt` |
| 全量 pytest | `python -m pytest -n auto -q` | **5641 passed + 11 skipped**（基线 5639 + 2 条新守卫） | `probe-01-pytest.txt` |

**双轴评审（2026-09-27，跑在工作树 vs `4b6e24c0`）与处置。**

| 轴 | 发现 | 处置 |
|---|---|---|
| Standards 硬① | 工单写「**不改** `:4794`（实测为真）」而 spec 写"改"——两边打架，实施取了 spec 一方 | **属实**：工单那句判断本身错了（把"装机件的 5 GB"当成了资料库），**工单与 spec 都已就地更正**并写明依据（沙箱 0.67 GiB / 发布包 0.65 GiB / `README.md:25` 自己就写「约 688 MB」） |
| Standards 硬② | 判据自述"产品界面"实为单文件：`static/js/ui/update.js:47` 还写着「**6 GB 资料库**」——同型十倍数 | **属实，已修**：扫描面扩到 `static/index.html` + `static/js/**/*.js`（新判据当场把它抓红），那句去掉数字（"与电赛资料库都不受影响"） |
| Standards 硬③ | `probe-01-offline-docs.txt` 整份乱码（143 个 U+FFFD：子进程 GBK、readings.py 按 UTF-8 收） | **属实，已修**：`tools/check-download-docs.py` 显式 `sys.stdout.reconfigure(encoding="utf-8")`（照 `tools/preflight.py` 口径），重录读数 **0 个 U+FFFD** |
| Standards 硬④ | 缺全量读数 | **已补**（上表最后一行） |
| Standards 判断 | `_DEAD_TOOL_PATTERNS` 文案写死「README 仍在提…」——扫界面时红了会指错地方 | **属实，已修**：`why` 文案去掉文件名，由调用方带文件路径 |
| Standards 判断 | `_CLAUSE_BREAKS` 漏 `：` 与换行 | **属实，已修**（补上并加断言） |
| Standards/Spec 判断 | 按行 + 关键词配对会误伤合法句（"装机件占 5 GB 以上、故意不进包"） | **属实，已修**：带「装机件 / 第三方安装包 / 不进包」的行**豁免**，并写进判据 docstring |
| Spec (b) | 判据面从"完整包"扩到"含资料库"**是承重改动**（不扩面 `:4794` 本不红），理由只写在注释里 | **已记账**：spec 与工单都写清"口径由**本机目录**换成**分发包基线**"，并给出两侧实测数 |
| Spec (b) | 删掉界面「几 GB 级更新也能选批次下载」是未要求的可见信息删减 | **记账保留**：整库才 0.7 GB，那句随之不成立（不是删信息，是删错话） |
| Spec (c) | 判据对 **MB 级偏差零覆盖**（「约 1 GB」不改也不红） | **记账**：写进判据 docstring——本地没有发布产物的真值可比，机器判据只钉 ≥2 GB 那一档；"约 800 MB"是精度修正 |
| Spec (c) | 探针直接改受测源文件（非原子、无并发保护） | **不改**：与本仓既有探针同一做法（`record-write-hardening` 那一批同款），已在用法段写明"跑它时别同时跑别的读数" |
| Standards 事实核对 | README 三处仍写「约 770 MB」，与界面新写的 800 MB 两渠道不一 | **属实，已修**：README 三处 → 「约 800 MB」（实测 792 MB） |

**账（留给后面的人）：**

1. **浏览器门禁在本机负载下会偶发红（本单实测到一次）**：`launcher-reload.spec.mjs` 的 A 用例
   `page.reload` 30.8 s 超时，随后 B/B2/C/D/E 秒级连红（共享夹具被带塌）——**全量读数 54/6**。
   机器空闲后**同一份代码**：该 spec 单跑 **6/6 绿**、全量重跑 **60/60 绿** ⇒ **不是本单引入的**，
   与 `docs/agents/local-environment.md` 记的那条本机偶发同宗（那节写"已修、连跑 12 轮全绿"，
   本单的观测说明**负载下仍会出现**，该节已补一句）。
   教训（已记）：**遇到偶发红先把那份红读数另存一份**——本轮 `readings.py` 按同名覆写，
   红读数只剩控制台输出（本票记的就是它）。
2. 判据面只到"产品界面文本 + 2 GB 粗线"：MB 级精度、README 那侧的真值对账仍归
   `tools/check-download-docs.py`（联网才比得了线上资产）。

## 备注

- `tools/check-download-docs.py` 的判据与 `tests/test_onboarding_docs.py` 是**刻意分开的两份**
  （它自己的注释写了理由：测试不联网）。本单只动测试期那份的**扫描面**，联网那份保持同口径
  （它扫 README，不看界面——界面的守卫归测试期，这样每次 CI 都跑）。
- 发布说明要带上这条（用户可见：面板上的体积数字变了）。
