# 交接单：工单 06（串口复测命令台接入自建件）——**代码已完成，收尾未做完**

> 2026-09-23 深夜，会话中途交接（用户换 agent）。**新会话请先读 CLAUDE.md / CONTEXT.md /
> `docs/agents/local-environment.md`，再读 `.scratch/hwcheck-unknown-device/spec.md` 与本单
> `issues/06-console-retest.md`，然后照本文件「还差什么」一节收尾。**
>
> ⚠ 工作区**尚未提交**（HEAD = `f750d08b`，分支 main）。工单 06 的状态是 `claimed`。

## 一句话现状

工单 06 的**实现、测试、两轴评审、评审整改全部做完**（域层 / 端点 / 前端 / 浏览器用例 /
反证探针都在），**只差**：在冻结版上复跑三门禁与真编译矩阵、把读数写进工单结论、
更新 `local-environment.md`、标记 `resolved`、中文提交。

## 已经做完的（别重做）

### 交付物（代码）

| 落点 | 是什么 |
|---|---|
| `src/contest_generator/hwcheck_console.py` | **命令空间新增自建件那一半**：`build_console_table(sections, custom=())`、`_custom_candidates`（先试 id 去掉 `mine_` 后的字母数字，再兜底池 `a`–`z`/`0`–`9`）、`_assign_custom_command`（跳过保留字 `r/y/g/o/b/?` 与已占用的；**分不出 = 构建期 `HwCheckError`**，报错句含"可用一共 31 个 / 已经占了 N 个"）；`ConsoleEntry` 新增 `func_name` / `custom` / `name` 三个字段与 `call_target` / `label` 两个属性（**判别式只有 `custom` 一个**）；`console_payload` 只给自建件那几行加 `tag` / `name` 两个键（库内件载荷逐字不变） |
| `src/contest_generator/hwcheck.py` | `render_main_c` 里 `build_console_table(sections, custom)`；文件头命令表用 `entry.label` |
| `src/contest_generator/hwcheck_board.py` | `hwcheck_view` 里 `build_console_table(sections, custom_sections)`——**页面与产物同一次装配、同一个字符** |
| `src/contest_generator/static/js/fx/hwcheck.js` | `hwcheckConsoleHTML` 的「哪一件」那一格：有 `tag` 就画 slug + 名称 + 自建件徽章，没有就还是 slug（缺字段 = 库内件） |
| `src/contest_generator/static/js/ui/hwcheck.js` | 命令台占位文案改说清"库内器件按配方、自建件按它自己的探测小节" |
| `CONTEXT.md` | 「我的器件」词条补了**串口复测（工单 06）**那段 + 实现列加 `hwcheck_console.py`（**已做，别重做**） |
| `tests/test_hwcheck_console.py` | 44 → **56** 条：字符取自 id / 保留字与配方优先 / 复测调**上电那遍同一个函数** / 帮助与文件头带标注词 / 行缓冲 / 载荷形状 / 确定性 / **用尽即红** / **票面第 5 条的逐字锁**（用改动前的字面量，不是"新代码等于新代码"）/ 真库 + 自建件同表 |
| `tests/test_my_devices_endpoint.py` | +1 条端到端：预览载荷给的字符 = 生成产物里那条 `case`，且那个 case 调的与上电那遍同一个函数（`hwcheck_custom_mine_gyro();` 出现 2 次、定义 1 次） |
| `tests/js/hwcheck.test.mjs` | +4 条 fx 判据（自建件那行的标注词/名称、无自建件时逐字不变、名称转义、ui 占位文案） |
| `tests/browser/hwcheck.spec.mjs` | +1 条真浏览器用例（**排在文件最后**，它会生成新工程）：页面读到的字符 → 产物里那条 case → 同一个函数 → 不勾串口时明说不能复测 |

### 两轴评审（已做完，findings 已逐条处置）

**Standards 轴**（1 硬违规 + 4 判断题）：

1. 「这一趟一条命令都没有」那三句（板上帮助 / 检测页 hint / 产物文件头）措辞不一 → **判为不改**：
   自建件从不声明字符，所以那三句在新世界里**仍然为真**；统一措辞要动它们的字节，而工单第 5 条
   要求"一件自建件都没有时命令台产物**逐字**与改动前一致"——两条要求冲突时以票面为准。
   代码里两处注释写明了这个取舍，工单结论也要记一笔。
2. CONTEXT.md 未登记 → **已补**（见上表）。
3. `ConsoleEntry` 用"布尔 + 两个空串哨兵"编码两种来源 → **已收**：`call_target` 改成只看 `custom`。
4. JS 变量 `who` 与后端 `label` 不同名 → **已改名** `label`（含浏览器用例里的局部变量）。
5. 两个调用点各建一次命令表（Shotgun Surgery）→ **判为保留**：纯函数 + 确定性，两个调用点
   各有一条用例钉着（探针注入 E 打 `hwcheck_board` 那条、本单用途例打 `render_main_c` 那条）。
6. 前端用例用 `ui.slice(at, at+200)` 魔数窗口 → **已改成整段字面量断言**。
7. 端点用例函数体内 import → **已移到模块顶**。

**Spec 轴**（1 处破票面 + 2 处口径）：

1. 🔴 **票面第 5 条被破**（最重的一条）：我把文件头 else 分支改成了"这一趟没有复测命令…"，
   零自建件时产物**不再逐字一致** → **已改回原字面量**（帮助行与文件头两处），并补了一条
   **真守卫**（`test_a_run_without_custom_devices_keeps_the_old_console_text`：断言改动前那两句
   中文原文还在产物里 + 两条调用形状逐字相同）。
2. 该验收项原先没有守卫（新代码比新代码 = 恒真）→ **已补**（同上；探针也加了注入 F 打它）。
3. 报错句「可用的字符（31 个…）」只扣保留字、不扣已占用 → **已改**为"可用一共 31 个 / 已经占了 N 个"，用例断言两个数。
4. 两处文档漂移（`ConsoleTable` docstring、`_header_brief` docstring）→ **已改**。
5. matrix-logs 里那条"工单 11"措辞变化不是本单改的，是**探针重跑**时按当前代码重新生成的 notes（重跑会整份重写日志）。

### 已取到的读数（**注意：都是在评审整改之前那一版上取的**，收尾要重跑）

- 反证探针（后端，6 条注入全红 + 逐字节复原）：`probe-06-guard-strength.txt`、`probe-06-guard-strength.py`
- 反证探针（前端，2 条注入）：`probe-06-guard-strength-front.txt`、`probe-06-guard-strength.mjs`
- 浏览器：`browser-06-hwcheck-spec.txt`（那一版 18 passed / 0 fail）
- 真编译矩阵：`probe-06-compile-matrix.txt`（**11 格 × 2 平台全部 0 error / 0 warning**）
- 整套 pytest：**上一版**是 `5271 passed + 1 skipped + 1 failed`，那 1 failed 是**已知并行争用偶发**
  （`tests/test_js_gate.py::test_full_mode_runs_gates…`，单跑该文件 29 passed）；整改后的整套读数
  被掐断没留下（`probe-06-suite.txt` 已删，等重跑）
- 前端门禁：上一版 **1752 passed / 0 fail**（整改后又单跑了 `tests/js/hwcheck.test.mjs` **135 passed**，
  **整支未重跑**）
- 浏览器门禁：整改后**未重跑**（上一版 hwcheck 单支 18 passed / 0 fail；整支预计 37 条，05 那轮是 36）

## 还差什么（照顺序做，别跳）

```powershell
# 0) 先看现场是否干净（无进程、无注入态残留、无临时探针）
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like '*contest_generator.webapp*' -or $_.CommandLine -like '*pytest*' }
git status --short

# 1) 三门禁（顺序无所谓，别并发；探针会真改文件，**跑探针时别跑套件**）
python -m pytest -n auto -q                                        # 期望 5271+ 全绿；若又撞 js_gate 那条偶发，单跑该文件复证
node --test "tests/js/*.test.mjs"                                  # 期望 1752 passed / 0 fail
node --test --test-concurrency=1 "tests/browser/*.spec.mjs"        # 5 个 spec / 约 37 条，串行约 2 分钟

# 2) 两个反证探针（会真改源文件、跑完逐字节复原；**跑之前别让套件在跑**）
python .scratch\hwcheck-unknown-device\probe-06-guard-strength.py
node .scratch\hwcheck-unknown-device\probe-06-guard-strength.mjs

# 3) 两平台真编译矩阵（约 4–6 分钟；会重写 matrix-logs/ 里的 tracked 日志，属正常）
python .scratch\hwcheck-unknown-device\probe-03-compile-matrix.py --out .scratch\hwcheck-unknown-device\probe-06-compile-matrix.txt
```

4) 把上面读数写进 `.scratch/hwcheck-unknown-device/issues/06-console-retest.md` 末尾的
   「结论」段（照 05 那单的格式：交付物表 / 验收读数 / 两轴评审与整改 / 实施时定的口径 /
   范围外），6 个 checkbox 打勾，**`**状态：**` 改成 `resolved`**。
5) 更新 `docs/agents/local-environment.md`：本单读数 + **第 0 节 main-only 落差表**再加一批
   （工单 06），并按该文件纪律顺手记本轮踩到的坑（见下面「坑」一节）。
6) 中文提交（见下）。提交前确认工作树里没有临时文件、没有注入态。

## 提交信息模板（中文；`.githooks/commit-msg` 会拒英文）

```
工单 hwcheck-unknown-device/06：自建件接入串口复测命令台（字符由命令空间分配）

- 自建件进既有命令表：字符先取自 id（mine_hall → h），保留字与配方已占用的跳过，
  分不出 = 构建期 400 不静默少一条（复用 RESERVED_COMMANDS / 形状 / 判重判据）
- 复测调它自己的探测小节函数（与上电那一遍同一措辞），页面命令区照载荷渲染
- 件都没有时命令台产物逐字不变（那三句旧文案一个字节没动）
- 另开工单 12：自建件 id 带连字符时产物编不过（现场 + 量具 + 读数已落）
```

要提交的清单（`git status --short` 全量）：源码 5 个 + 测试 4 个 + `CONTEXT.md` +
`.scratch/hwcheck-unknown-device/` 下的工单/探针/读数 + `matrix-logs/*.log`（重跑产物）。
**别把 `.scratch/hwcheck-unknown-device/matrix/`（生成+编译产物）加进来**——按惯例 gitignore。

## 钉住的坑（本轮踩过，别再踩）

- **行尾**：本仓库两种形态并存（git 检出的文件是 CRLF，工具新写的是 LF）。反证探针的多行锚点
  必须**先试 LF 再试 CRLF**（`probe-06-guard-strength.py` 的 `match_anchor` 就是为此写的；
  第一版只按 `\n` 匹配，三个锚点全部命中 0 次被前置检查拦下）。
- **探针别与套件并发**：探针会真改源文件（`module-hwcheck/09`、`probe-03/04/05` 同一条纪律）。
- **`-n auto` 的已知偶发**：`tests/test_js_gate.py::test_full_mode_runs_gates…` 会在并行争用下崩
  worker（不是产品问题，单跑 29 passed）。
- **读证据文件用 `read` 工具**：PowerShell 控制台是 GBK，`Get-Content`/`Select-String` 会把中文
  显示成乱码（文件本身没问题）。
- **别用 `| Select-Object -First N` 掐管道跑浏览器门禁**：SIGPIPE 会把 node 带走，
  `test.after` 的 `server.stop()` 跑不到 → 残留后端进程（用 `Tee-Object` 落文件再读）。
- 收尾前清一遍残留：`Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like '*contest_generator.webapp*' }`。

## 范围外（本单不做，已另有归属）

- **工单 12（已开，未开工）**：`.scratch/hwcheck-unknown-device/issues/12-custom-id-c-identifier.md`
  ——自建件 id 带连字符（`mine_gyro-2`）时产物里出现 `static void hwcheck_custom_mine_gyro-2(void)`
  （**不是合法 C 标识符**），而建件 / 预览 / 生成**三个端点都 200**，坏工程照落盘。现场、量具
  （`probe-12-hyphen-id.py`）与读数（`.txt`）都已就绪，**根因是 02 的 id 文法与 03 的 func_name
  拼法对不上**，与 06 的字符分配无关（连字符会被 `isalnum()` 挡掉，实测分到字符 `2`）。
- 工单 **07**（资料 → 事实草稿）、**08**（工程内快照与回读）、**09**（AI 排障带自建件事实）、
  **10**（闸门与真机验收收口）都还没开工——07/08 的阻塞项 02/03 已 resolved，09 的 05 也已 resolved，
  所以 07/08/09 都在 frontier 上；10 要等 04/06/07/08/09 全 resolved。
- **未上板**：本单是命令台与页面，没有真机动作；照 spec 口径写"未上板"，不假装。
