# 06 — 环境体检：CCS 三件套跨安装目录混搭（探到 ccs2051 的 SDK/SysConfig + ccs2050 的编译器）未说明

**要做什么：** 把「三件套各取目录名排序最大、可能来自不同 ccs 安装目录」这一事实
写进环境体检文案（并可考虑在体检结果里显示三件各自的来源根），避免用户按
「一个 CCS 版本 = 一套工具链」的直觉排查问题。

**被谁阻塞：** 无。

**状态：** ready-for-agent

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

- [ ] 体检文案含「三件套独立探测 / 可能跨目录」说明（`tests/test_env*.py` 或
      `tests/js` 文案守卫按现有先例补）
- [ ] 本机实测三件的来源根在体检结果里可见（若采纳增强 2）
- [ ] 全量 pytest + node 绿；不改探测行为（除非用户拍了同根优先）

## 实施提示词（新会话粘贴）

> 工单：`.scratch/real-acceptance/issues/06-ccs-toolchain-mix-and-match.md`（先读全文）。
> 背景：`.scratch/tracker-audit/2026-09-09-在途盘点.md`「第十六轮」④ O-4；
> 实测证据 `.scratch/real-run/verify-16-A8-mspm0-min-servo.txt`（makefile 引用三件路径）+ `verify-16-A6-desktop-gmake.txt`。
> 任务：环境体检补「CCS 三件套独立探测、可能跨安装目录」文案（可选：带出各件安装根）；探测行为默认不动。
> 文件边界：`src/contest_generator/static/js/fx/env.js`（文案）+ `compile_runner.py`（若加来源根）+ 相应测试。
> 验收：体检页文案可见 + 全量绿；本机三件来源与本工单表格一致。
