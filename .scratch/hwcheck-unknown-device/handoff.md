# 总交接单：hwcheck-unknown-device 剩余**全部**工单（一口气做完的那一份）

> 2026-09-23 深夜交接（用户换 agent）。**新会话第一件事**：读 `CLAUDE.md`、`CONTEXT.md`、
> `docs/agents/local-environment.md`、`docs/agents/workflow.md`，再读本文件 +
> `.scratch/hwcheck-unknown-device/spec.md`。工单 06 的细节另有 `.scratch/hwcheck-unknown-device/handoff-06.md`。
>
> 工作区**未提交**（HEAD `f750d08b`，分支 `main`）；工单 01–05、11 已 resolved；**06 = claimed（代码已完成，只差收尾）**；
> **07 / 08 / 09 / 10 / 12 = ready-for-agent**。

## 进度表（随工单推进更新；接手的人从这里看现状）

| 工单 | 状态 | 提交 | 关键读数（2026-09-23 收尾实测） |
|---|---|---|---|
| 06 串口复测命令台 | **resolved** | `946e9cc4` | 三门禁 5272+1skipped / 1752 / 37 全绿；反证 6+2 条注入全红逐字节复原；编译矩阵 11 格 × 2 平台 0e/0w |
| 12 id 连字符编不过 | **resolved** | 见 `git log` | 三门禁 5285+1 / 1755 / 37（首跑 2 红=launcher-reload 已知偶发，单跑复证）；量具改判 1（三端点全 400）；反证 3+1 条注入全红；矩阵 12 格 × 2 平台全 PASS（含 hyphen-id-refused 边界格） |
| 07 资料→草稿 | ready-for-agent | — | — |
| 08 快照+回读 | ready-for-agent | — | — |
| 09 排障带事实 | ready-for-agent | — | — |
| 10 收口 | ready-for-agent | — | 必须最后做；验收线"含连字符 id 那一格"按 12 的边界格口径读 |

## 剩余队列与建议顺序

| 序 | 工单 | 阻塞 | 一句话 |
|---|---|---|---|
| 1 | **06 收尾**（claimed） | 05 ✓ | 复跑读数 → 写结论 → 标 resolved → 提交（详见 `handoff-06.md`） |
| 2 | **12** 自建件 id 带连字符产物编不过 | 无 | 02 的 id 文法允许 `-`，03 把 id 直接拼进 C 函数名 —— 现场/量具/读数都已就绪 |
| 3 | **07** 资料 → 事实草稿 | 02 ✓ | 贴文字 / 传 PDF / 传照片 → 一次 LLM 抽成**草稿 JSON**（带出处片段），用户逐字段确认后才落盘；AI 不写代码 |
| 4 | **08** 工程内快照 + 回读 | 02 ✓ 03 ✓ | 生成时把定义/资料/草稿写进工程 `custom_device/<id>/`，回读**以快照为准** |
| 5 | **09** AI 排障带自建件事实 | 05 ✓ | 排障上下文加「自建器件事实」段 + 事实白名单扩容（顺带把 05 删掉的那句清真话加回来） |
| 6 | **10** 闸门与真机验收收口 | 04 ✓ 06 07 08 09 | 读数汇总 + CONTEXT/ADR/CHANGELOG/local-environment 收口 + 未上板如实 |

07/08/09 互相没有硬依赖，谁先都行；**10 必须最后**（它要引用 06–09 的读数）。

## 每一单的固定循环（仓库纪律，别省）

1. **claim**：把该单 `**状态：**` 改成 `claimed` 并落盘，再动手。
2. **tdd**：先写红用例（缝在 spec「测试决策」里已定：域层纯函数 + TestClient 假 LLM 桩 + fx 纯件 + 浏览器门禁），再实现；垂直切片，别批量写测试。
3. **code-review**：两轴（Standards / Spec）并行子代理评审，**findings 逐条处置**（改掉或写明为什么不改）。
4. **resolved**：把实测读数（用例条数 / 探针读数 / 编译矩阵 / 三闸门）写进工单结论，勾上 checkbox，状态改 `resolved`。
5. **提交**：一个工单一次提交，**提交信息中文**（`.githooks/commit-msg` 拒英文；CHANGELOG 由 post-commit 钩子自动补，会额外产生 `chore: 自动更新 CHANGELOG` 提交，正常）。

## 通用命令（本机实测口径）

```powershell
# python：用系统 python（3.14，装了 pytest）；.venv 里没有 pytest，别用
python -m pytest -n auto -q                                        # 整套（约 3.5 分钟）
python -m pytest tests/test_hwcheck_custom.py -q                   # 单文件
node --test "tests/js/*.test.mjs"                                  # 前端门禁（约 8 秒）
node --test --test-concurrency=1 "tests/browser/*.spec.mjs"        # 浏览器门禁（5 spec，串行约 2 分钟）
python tools/prepush.py --full                                     # 推之前可先自查（含三闸门）
```

真编译在本机是**可用**的：Keil `C:\Keil5\Core\UV4\UV4.exe`（`compile_runner.find_uv4()`）、
CCS gmake `C:/ti/ccs2050/ccs/utils/bin/gmake.exe`（`find_make()`）。
两平台矩阵一条命令：`python .scratch\hwcheck-unknown-device\probe-03-compile-matrix.py --out <证据.txt>`。

**上板（真机插线跑一轮）本轮做不到**：照 spec 口径写「**未上板**」，不假装（工单 10 有这一条）。

## 钉住的坑（每一单都适用）

- **探针会真改源文件**（反证/强度探针注入后逐字节复原）：**跑探针时别让测试套件在跑**（先例：`module-hwcheck/09`、`webapp-state-into-ctx`）。
- **`pytest -n auto` 有一条已知偶发**：`tests/test_js_gate.py::test_full_mode_runs_gates…` 并行争用下会崩 xdist worker（不是产品问题）——单跑该文件复证（29 passed）即可。
- **行尾两种形态并存**：git 检出的文件是 CRLF，工具新写的是 LF。写探针锚点要**先试 LF 再试 CRLF**（`probe-06-guard-strength.py` 的 `match_anchor` 是现成写法）。
- **PowerShell 控制台是 GBK**：读证据/工单用 `read` 工具（或探针 `--out` 先落盘再打印），别信 `Get-Content` 的回显。
- **别用 `| Select-Object -First N` 掐管道跑浏览器门禁**：SIGPIPE 会把 node 带走、`test.after` 的停服跑不到 → 残留后端进程（要截取就 `Tee-Object` 落文件再读）。
- 动 `.ps1` 必须 **UTF-8 with BOM**（`tests/test_ps1_encoding.py` 兜底）。
- 新域词 / 新判据落地时**顺手更新 `CONTEXT.md`**（03/05/11 三单都做了，评审会抓）。
- 收尾清一遍残留：`Get-CimInstance Win32_Process -Filter "Name = 'python.exe'"`（看 `contest_generator.webapp` / `pytest`）。

## 各单要点（读工单全文为准，这里是地图）

### 06 收尾 → 见 `handoff-06.md`（已完成清单 / 还差哪几步 / 读数命令 / 两轴评审整改）

### 12 —— 自建件 id 带连字符时产物编不过

- **根因两处**：`entry_store.SLUG_PATTERN` 允许 `-`（`my_devices._require_device_id` 复用它），
  而 `hwcheck_custom.CustomSection.func_name = f"hwcheck_custom_{id}"` 把 id 原样拼进 C 标识符。
- **两条出路（取其一并在结论里说清取舍）**：① id 文法收紧到 `[A-Za-z0-9_]`（已在盘上的坏 id
  会读不回来 → `_load_entry` 必须如实点名 + 说清怎么改）；② 渲染层消毒（注意两个 id 消毒后撞名
  = 两个同名 C 函数，必须大声失败）。
- **判据面三条**：建件端点 / 预览载荷 `console.commands`（06 的字符分配对连字符是安全的，别弄坏）/ 产物 `main.c`。
- 现成量具：`python .scratch\hwcheck-unknown-device\probe-12-hyphen-id.py`（现在返回 0 = 缺陷复现；
  修好后它应当返回 1，读数文件同步更新）。
- 真编译矩阵补一格带连字符 id 的形态（两平台），并做一次「停用守卫 → 用例变红」反证。

### 07 —— 资料 → 事实草稿（本队列里最大的一单）

- **域层**：草稿形状 + 校验（字段白名单 / 地址与寄存器是合法数 / 每条事实带**原文出处片段** /
  抽不到留空并说明"手册里没找到"，绝不编）。拒收后重问，仍不行 → **降级为纯手填**，流程不阻断。
- **LLM 一次调用**：照 `selection.build_module_selection` 的先例（模型输出 → 域层解释链，模型只做机械提取）。
  资料文本走**既有抽取通道**（`extraction.py` 的 PDF 文本 + 视觉描述；`/api/extract` 同款）——别新开第二条抽取路。
- **端点**：`POST /api/my-devices/draft`（TestClient + `tests/fakes.py` 的 FakeLLM 桩）。
- **前端**：`static/index.html` 的「我的器件」卡加资料入口；`fx/my-devices.js`（纯件、可单测，进前端门禁）+ `ui/my-devices.js`；
  页面上要**明说资料会被送到 AI 通道**；草稿填入后用户可逐字段改，**未确认前不落盘**。
- **结构守卫**：本链路**不产出任何 C**（AI 不写代码、不生成判据）。

### 08 —— 定义 / 资料 / 草稿归档 + 回读以快照为准

- 生成时把**本次用到的自建件定义快照 + 资料副本 + 抽取草稿**写进检测工程 `custom_device/<id>/`；
  上下文清单（`context_manifest`）记下本次用到的 id（`devices` 字段已经在写了，看 `read_context_fields`）。
- 回读（`/api/hwcheck/project`）：**以工程内快照为准**——用户之后改了或删了「我的器件」，已生成工程的回读**不变**；
  页面标出「来自我的器件 &lt;id&gt;」，该条目已不存在时如实说明（不静默、不报错）。
- 向后兼容：没有自建件的旧工程回读结果**逐字与改动前一致**；归档文件**不进最近工程记录**那条赛题链路。

### 09 —— AI 排障带自建件事实

- `hwcheck_triage.build_triage_context` 新增「自建器件事实」段：id / 名称 / 地址（7 位+8 位两种写法）/
  寄存器 / 期望值 / 备注 / 本次探测形态（判定·只回显·只 ping）/ 是否与库内件共总线。
- **事实白名单扩容**（自建件 id / 名称 / 地址），否则模型一提它们就被当"上下文里没有的东西"拒收；
  **反向判据仍要成立**：提一个不在本次的自建件仍被拒。
- ⚠ **05 留下的欠账**：`hwcheck_custom._CHECK_NOT_PROBED` 第③条现在写的是"你填的地址这一版还进不了它的
  上下文"——09 落地后**要把那句清真话改回来**（05 结论文末明写）。
- 提示词写明 `[自建件]` 的结论来自**用户确认的事实**，不许说成"库内模块有问题"；
  AI 不可用 → 兜底建议照旧、记录照常落盘；**无自建件时上下文逐字与改动前一致**（既有用例全绿）。

### 10 —— 闸门与真机验收收口（最后做）

- 每条新守卫各一次「停用后用例必须变红」的实测读数（06/07/08/09/12 的探针读数汇总）；
- 三闸门本机读数（pytest / 前端 / 浏览器串行）+ 两平台真编译矩阵（含"只有自建件""自建件+库内器件"
  "全选装不下如实拦下"三类形态）——**06 的矩阵读数可直接引用，别重复跑**；
- `CONTEXT.md` 的「硬件检测」词条扩写（我的器件 / `i2c_probe` 支点 / 自建件标注 / 探测只读边界）；
- **ADR 0016 补一笔**：检测程序 = 确定性渲染 +（库内配方数据 **或** 用户确认的事实），AI 不产出检测程序的一个字节；
- CHANGELOG 与提交信息中文；**未上板就写未上板**；本机环境事实有变化就同步
  `docs/agents/local-environment.md`（含**第 0 节 main-only 发布落差表**：本特性整批还没进任何发布包）。

## 全做完的验收线（自查清单）

- [ ] 06–10、12 全部 `resolved`，每单结论里有实测读数
- [ ] `git log` 里每单一次中文提交（+ 自动 CHANGELOG 提交）
- [ ] `python -m pytest -n auto -q` 与两支前端门禁全绿（偶发那条除外，且能单跑复证）
- [ ] 两平台真编译矩阵 0 error / 0 warning（含连字符 id 那一格）
- [ ] `CONTEXT.md` / `docs/adr/` / `CHANGELOG.md` / `docs/agents/local-environment.md` 四份文档与新行为一致
- [ ] 工作树干净（`.scratch/hwcheck-unknown-device/matrix/`、`probe-*-data/` 这类产物按惯例 gitignore）
