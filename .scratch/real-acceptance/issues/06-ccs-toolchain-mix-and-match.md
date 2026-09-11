# 06 — 环境体检：CCS 三件套跨安装目录混搭（探到 ccs2051 的 SDK/SysConfig + ccs2050 的编译器）未说明

**要做什么：** 把「三件套各取目录名排序最大、可能来自不同 ccs 安装目录」这一事实
写进环境体检文案（并可考虑在体检结果里显示三件各自的来源根），避免用户按
「一个 CCS 版本 = 一套工具链」的直觉排查问题。

**被谁阻塞：** 无。

**状态：** resolved（2026-09-11 落地：体检补「三件逐件独立探测 / 可能跨目录」说明行 +
逐件安装根；**探测行为未改**——「同根优先」是行为变更，见文末「未采纳的方案」）

## 真机现场（2026-09-10 第十六轮 A8/C-A6 实跑）

本机盘上实况：

| 件 | 探测结果 | 来源 |
|---|---|---|
| 编译器 | `C:\ti\ccs2050\ccs\tools\compiler\ti-cgt-armllvm_4.0.4.LTS` | **ccs2050** |
| MSPM0 SDK | `C:\ti\ccs2051\mspm0_sdk_2_10_00_04` | **ccs2051** |
| SysConfig CLI | `C:\ti\ccs2051\sysconfig_1.26.2\sysconfig_cli.bat` | **ccs2051** |

生成工程 `Debug/makefile` 里逐字引用的就是上面三条（见
`.scratch/real-run/verify-16-A8-mspm0-min-servo.txt` 的编译输出头两行），
而**编译实测通过**（servo 最小工程 `exit=0` / 0 错 0 警；2024H 工程 `gmake exit=0` + `.out` 11936B）。

即：**混搭可用**，但探测规则（`compile_runner._newest` 各件独立取目录名最大）意味着
「装了新版 CCS 但只带一半组件」时会出现跨目录组合——环境体检目前只报 `found / path`，
不说明这一点。

## 修复方向（实施会话定）

1. 文案：`fx/env.js` 的 CCS 三件行 / `ccs_tools_status` 提示里补一句「三件套独立探测，
   可能来自不同 CCS 安装目录（本机实测：编译器 ccs2050 + SDK/SysConfig ccs2051）」。
2. 可选增强：体检结果里把每件的**安装根**一并带出（现在 path 有，根要自己看），
   并在 `ccs_sdk_dir` / `ccs_compiler_dir` / `ccs_sysconfig_cli` 三个覆盖项下各写一行
   「留空 = 自动探测（各取最新）」。
3. 若判定「跨目录混搭不安全」，则把探测改成**同根优先**（先找三件齐全的 ccs 目录，
   全缺才回退逐件最大）——这条要用户拍板（会改变本机当前可用组合）。

## 验收标准

- [x] 体检文案含「三件套独立探测 / 可能跨目录」说明（`tests/test_env*.py` 或
      `tests/js` 文案守卫按现有先例补）
      —— `fx/env.js` 新常量 `CCS_PROBE_NOTE` + `envCheckStatusHTML` 说明行
      `data-env-row="ccs-note"`；守卫
      `tests/js/env-check-center.test.mjs::CCS 探测说明行：独立探测 / 可能跨安装目录文案 + 三件来源一句话（工单 06）`
- [x] 本机实测三件的来源根在体检结果里可见（若采纳增强 2）——**采纳**：载荷逐件带
      `root`（`compile_runner.ccs_tools_status` 反推，推不出为 `null` 不猜），
      `ccs-*` 三行各带「（安装根 …）」+ 说明行给「三件来源：…（跨安装目录）」
- [x] 全量 pytest + node 绿；不改探测行为（除非用户拍了同根优先）——探测规则与
      `find_ccs_tools` 的取件结果逐字节未变（新增字段是只读投影），「同根优先」未做

## 实施记录（2026-09-11）

| 改动 | 位置 |
|---|---|
| 逐件安装根反推：`<ccs>/mspm0_sdk_*` 上一级 / `<ccs>/ccs/tools/compiler/ti-cgt-armllvm_*` 上四级 / `<ccs>/sysconfig_*/sysconfig_cli.bat` 上两级；根名不以 `ccs` 开头（自定义布局）= `None` 不猜。**布局知识的单源就是本模块既有的 `_sdk_candidates` / `_compiler_candidates` / `_sysconfig_candidates`**，故反推归这里，前端不重写一份目录布局 | `compile_runner.py`（`_piece_install_root` / `CCS_ROOT_PREFIX` / `ccs_tools_status`） |
| `ccs_tools_status` 每件从 `{found, path}` → `{found, path, root}`（只读投影，`find_ccs_tools` 取件结果不变） | `compile_runner.py` |
| 体检说明行 `ccs-note`（env-warn「注意」、无跳转按钮）：`CCS_PROBE_NOTE` 全文 + `ccsSourceText` 一句话；三件行补「（安装根 …）」 | `static/js/fx/env.js` |
| `ccsSourceText(ccs)` 纯函数：逐件来源根 → 「编译器 ccs2050；SDK ccs2051；SysConfig ccs2051」+ 判语（≥2 个不同根 = 跨安装目录 / 三件都探测到且同根 = 三件同源 / 全无根 = 空串不猜） | `static/js/fx/env.js` |
| 设置页三行覆盖项提示点明「留空 = 自动探测：三件各取目录名最新」（判据 = 载荷带 `root` 的即 CCS 件；uv4/gmake 无此字段，不说「各取最新」——它们按候选顺序 / PATH 探测） | `static/js/fx/env.js`（`toolchainProbeText`；settings.js 零改动） |
| 文案守卫：说明行 + 跨目录判定 + `ccsSourceText` 三态 + CCS 探测提示 | `tests/js/env-check-center.test.mjs`（+4 条：逐行安装根 / 说明行 / `ccsSourceText` / CCS 提示） |
| `fx` 导出登记（防双源回退） | `tests/js/fx-guard.test.mjs` |
| 安装根反推三条用例（真机跨目录形态 / 自定义布局推不出 / 缺件态） | `tests/test_compile_runner.py` |
| `ccs_tools` 载荷形状断言补 `root` | `tests/test_webapp.py`（两处） |

**真机证据**（本机 `C:\ti` 下 `ccs2050` / `ccs2051` 两套安装）：

- `.scratch/real-acceptance/probe-06-ccs-roots.py` → `probe-06-ccs-roots.txt`：
  `ccs_tools_status()` 逐件与本工单表格**逐字一致**（编译器 `C:\ti\ccs2050\…\ti-cgt-armllvm_4.0.4.LTS`
  root `C:\ti\ccs2050`；SDK `C:\ti\ccs2051\mspm0_sdk_2_10_00_04` root `C:\ti\ccs2051`；
  SysConfig CLI `C:\ti\ccs2051\sysconfig_1.26.2\sysconfig_cli.bat` root `C:\ti\ccs2051`）
  → 来源根集合 `{ccs2050, ccs2051}` = 跨安装目录；ALL PASS
- `.scratch/real-acceptance/probe-06-env-render.mjs` → `.txt`：**线上端点载荷**
  （`GET 127.0.0.1:8000/api/env/status`，重启后的服务）+ **真渲染函数**
  `envCheckStatusHTML` → 体检页四行原文（三件行带安装根 + 说明行「…可能来自不同 CCS
  安装目录——排查时别按「一个 CCS 版本 = 一套工具链」…三件来源：编译器 ccs2050；
  SDK ccs2051；SysConfig ccs2051（跨安装目录）」）→ ALL PASS
- `.scratch/real-acceptance/probe-06-env-page.mjs` → `probe-06-env-page.txt` +
  `shot-06-env-ccs-note.png`：**真浏览器**打开设置页 → 展开 `[data-collapse-id="env-check"]`
  → 点「一键体检」→ 读页面里 `#env-check-results` 的渲染文本 → 四行原文同上、页面零 JS 异常
  → ALL PASS（这条才是「体检页能看到说明」的页面级证据；消耗 = 体检自带的文本/视觉各一次最小调用）

**回归**：全量 `pytest` **3971 passed, 1 warning**；`node --test tests/js/*.test.mjs`
**1444 pass / 0 fail**（本单新增 js 2 条：说明行 / `ccsSourceText`，另扩写 2 条既有断言；
新增 python 2 条：安装根反推 / 自定义布局不猜）。

## 未采纳的方案：同根优先探测（需用户拍板，属行为变更）

工单修复方向第 3 条（「先找三件齐全的 ccs 目录，全缺才回退逐件最大」）**本轮明确不做**，
理由三条：

1. **混搭实测可用**：本机这套跨目录组合（编译器 ccs2050 + SDK/SysConfig ccs2051）
   编译实测通过（servo 最小工程 `exit=0` 0 错 0 警；2024H 工程 `gmake exit=0` + `.out` 11936B），
   没有「不安全」的现场证据；
2. **它是行为变更**：同根优先会**改变本机当前的可用组合**。本机盘上实况（`Get-ChildItem C:\ti\*`
   逐目录核过）：`ccs2050` 只有 `ccs`（无 SDK / SysConfig）；`ccs2051` 没有
   `ccs/tools/compiler/ti-cgt-armllvm_*`（顶层另有 `ti_cgt_arm_llvm_4.0.2.LTS` 独立安装）
   —— 即**本机一个「三件齐全的 ccs 目录」都没有**，同根优先在本机会直接退回逐件最大（等于没变）；
   但在「新装 CCS 只带一半组件」的机器上，它会把用户从一个**能编译**的组合挪到另一个，得用户拍板。
   探测规则本身有测试钉住：`tests/test_compile_runner.py::test_find_ccs_tools_pieces_span_ccs_versions`
   （「逐件独立」是既定行为，不是疏漏）；
3. 本单是文案/体检单：先把事实说清，让用户能自查来源。

**顺带记下两条「探测面」事实**（都不是本单范围，都是探测策略问题，改则同样需拍板）：

- 本机顶层另有**独立安装**：`C:\ti\mspm0_sdk_2_11_00_07`（比被选中的 `mspm0_sdk_2_10_00_04` 新）、
  `C:\ti\sysconfig_1.20.0`、`C:\ti\ti_cgt_arm_llvm_4.0.2.LTS`——当前 `_*_candidates` 只扫
  `<ccs>/` 内部，**不认这些独立安装**（所以 SDK 取的是 2.10 而不是 2.11）。这是既有探测面口径，
  不是「取最新」的完整实现。
- 因此体检给出的「来源根」是**探测结果**的来源根，不是「盘上所有 CCS 相关安装」的清单
  ——说明行只声称「三件逐件独立探测、可能跨目录」，不声称「已选到最新」。

## 实施提示词（新会话粘贴）

> 工单：`.scratch/real-acceptance/issues/06-ccs-toolchain-mix-and-match.md`（先读全文）。
> 背景：`.scratch/tracker-audit/2026-09-09-在途盘点.md`「第十六轮」④ O-4；
> 实测证据 `.scratch/real-run/verify-16-A8-mspm0-min-servo.txt`（makefile 引用三件路径）+ `verify-16-A6-desktop-gmake.txt`。
> 任务：环境体检补「CCS 三件套独立探测、可能跨安装目录」文案（可选：带出各件安装根）；探测行为默认不动。
> 文件边界：`src/contest_generator/static/js/fx/env.js`（文案）+ `compile_runner.py`（若加来源根）+ 相应测试。
> 验收：体检页文案可见 + 全量绿；本机三件来源与本工单表格一致。
