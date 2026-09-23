# 06 — 串口复测命令台接入自建件

> ⚠ **接手提示（2026-09-23 会话中途交接）**：本单的**代码 / 测试 / 两轴评审 / 评审整改都已完成**，
> **收尾没做完**（复跑三门禁与真编译矩阵 → 把读数写进本单结论 → 标 resolved → 中文提交）。
> **动手前先读 `.scratch/hwcheck-unknown-device/handoff-06.md`**：那里有已完成清单、还差哪几步、
> 所有读数命令、以及本轮踩到的坑。

**要做什么：** 自建件也能**不重烧复测** —— 它分到一个串口命令字符，页面上显示该敲哪个键，敲下去就重跑这一件的探测（学生边动线边看现象）。

**被谁阻塞：** 05（页面计划投影）

**状态：** resolved

- [x] 自建件参与**既有命令字符分配**（保留字 / 重复 / 形状的判据沿用既有单源；冲突仍在**构建期**大声失败，不静默少一条）
- [x] 板上敲该字符重跑这一件探测，输出与上电那一遍**同一措辞**
- [x] 页面命令区显示自建件的字符与说明；没有串口的形态照既有口径明说"不能交互式复测"
- [x] 既有的 `r/y/g/o/b` 四条命令语义一个字节不动
- [x] 一件自建件都没有时，命令台产物逐字与改动前一致（既有命令台用例全绿）
- [x] 真编译 0 error / 0 warning（命令台排在逐件小节之后的既有顺序判据不破）

---

## 结论（2026-09-23，工单 06 已 resolved）

> 本单经历一次会话中途交接：实现 / 测试 / 两轴评审 / 评审整改由上一会话完成，收尾
> （冻结版上复跑三门禁 + 两探针 + 编译矩阵 → 写结论 → resolved → 提交）由本会话完成。
> **下面记的读数全部是整改后的冻结版上重跑的**（交接单里的旧读数作废）。

### 一句话

库内器件的串口复测命令台只认配方件；这一单把自建件接进**同一张命令表**——字符从 id 里
取（`mine_hall` → `h`），取不出就在兜底池里分，分不出在**构建期**大声失败；板上敲该字符
重跑它自己的探测小节（与上电那一遍同一个函数），页面命令区照载荷画出"这是自建件"。

### 交付物

| 落点 | 是什么 |
|---|---|
| `src/contest_generator/hwcheck_console.py` | **命令空间新增自建件那一半**：`build_console_table(sections, custom=())`、`_custom_candidates`（先试 id 去掉 `mine_` 后的字母数字，再兜底池 `a`–`z`/`0`–`9`）、`_assign_custom_command`（跳过保留字 `r/y/g/o/b/?` 与已占用的；**分不出 = 构建期 `HwCheckError`**，报错句含"可用一共 31 个 / 已经占了 N 个"）；`ConsoleEntry` 新增 `func_name` / `custom` / `name` 三个字段与 `call_target` / `label` 两个属性（**判别式只有 `custom` 一个**）；`console_payload` 只给自建件那几行加 `tag` / `name` 两个键（库内件载荷逐字不变） |
| `src/contest_generator/hwcheck.py` | `render_main_c` 里 `build_console_table(sections, custom)`；文件头命令表用 `entry.label` |
| `src/contest_generator/hwcheck_board.py` | `hwcheck_view` 里 `build_console_table(sections, custom_sections)`——**页面与产物同一次装配、同一个字符** |
| `src/contest_generator/static/js/fx/hwcheck.js` | `hwcheckConsoleHTML` 的「哪一件」那一格：有 `tag` 就画 slug + 名称 + 自建件徽章，没有就还是 slug（缺字段 = 库内件） |
| `src/contest_generator/static/js/ui/hwcheck.js` | 命令台占位文案改说清"库内器件按配方、自建件按它自己的探测小节" |
| `CONTEXT.md` | 「我的器件」词条补**串口复测（工单 06）**那段 + 实现列加 `hwcheck_console.py` |
| `tests/test_hwcheck_console.py` | 44 → **56** 条：字符取自 id / 保留字与配方优先 / 复测调**上电那遍同一个函数** / 帮助与文件头带标注词 / 行缓冲 / 载荷形状 / 确定性 / **用尽即红** / **票面第 5 条的逐字锁**（断言改动前的字面量，不是"新代码等于新代码"）/ 真库 + 自建件同表 |
| `tests/test_my_devices_endpoint.py` | +1 条端到端：预览载荷给的字符 = 生成产物里那条 `case`，且那个 case 调的与上电那遍同一个函数（`hwcheck_custom_mine_gyro();` 出现 2 次、定义 1 次） |
| `tests/js/hwcheck.test.mjs` | +4 条 fx 判据（自建件那行的标注词/名称、无自建件时逐字不变、名称转义、ui 占位文案） |
| `tests/browser/hwcheck.spec.mjs` | +1 条真浏览器用例（**排在文件最后**，它会生成新工程）：页面读到的字符 → 产物里那条 case → 同一个函数 → 不勾串口时明说不能复测 |
| `.scratch/hwcheck-unknown-device/probe-06-guard-strength.py` / `.mjs` | 反证探针（6 条后端注入 + 2 条前端注入，逐字节复原 + sha256 复核） |

### 验收读数（2026-09-23 冻结版复跑）

**三门禁**：

```
python -m pytest -n auto -q                   5272 passed + 1 skipped / 131.5s
node --test "tests/js/*.test.mjs"             1752 passed / 0 fail / 5.3s
node --test --test-concurrency=1 "tests/browser/*.spec.mjs"
                                              37 passed / 0 fail / 102.8s（05 轮 36 + 本单 1）
```

（`tests/test_js_gate.py` 那条并行争用偶发本轮未出现。）

**判据强度（反证）**——后端 6 条注入（读数 `probe-06-guard-strength.txt`）：

```
注入 A: 命令分配不再跳过保留字/配方占用           → RED ｜ 复原 sha256 相等 ✓
注入 B: 复测命令改调别的函数（不再与上电同一遍）   → RED ｜ 复原 sha256 相等 ✓
注入 C: 分不出字符时静默少一条（不再构建期报错）   → RED ｜ 复原 sha256 相等 ✓
注入 D: 载荷不再带 tag/name（页面画不出自建件行）  → RED ｜ 复原 sha256 相等 ✓
注入 E: 板侧视图不再把自建件喂给命令表             → RED ｜ 复原 sha256 相等 ✓
注入 F: 顺手改掉「这一趟没有配方命令」那两句       → RED ｜ 复原 sha256 相等 ✓
复原后复跑：六条全 PASS（回绿）；收尾指纹 3 个文件逐字节未变 ✓
```

前端 2 条注入（读数 `probe-06-guard-strength-front.txt`）：

```
PASS  命令表忽略 tag：自建件当库内件画 → 门禁退出码 1，红 5 条
PASS  名称不转义：用户填的名字直接进 HTML → 门禁退出码 1，红 3 条
复原复核：被注入文件与注入前逐字节相同
```

**两平台真编译矩阵**（`probe-03-compile-matrix.py --out probe-06-compile-matrix.txt`，
矩阵原始日志 `matrix-logs/custom-*.log`）：**11 格 × 2 平台全部 PASS，0 error / 0 warning**。
（mspm0 带 `ml_mpu6050` 的格另计**已知工具链告警** `#10210-D .sysmem` 一条——与本仓库代码
无关，单列不混入；`all-recipes` 的 mspm0 格按预期在**生成前**被"装不下"拦下，属边界读数、
不计入验收线。）

### code-review 两轴结论与整改

**Standards 轴**（1 硬违规 + 4 判断题 → 硬违规已修、判断题收掉 3 条）：

1. 「这一趟一条命令都没有」那三句（板上帮助 / 检测页 hint / 产物文件头）措辞不一
   → **判为不改**：自建件从不声明字符，那三句在新世界里仍然为真；统一措辞要动它们的
   字节，而票面第 5 条要求"一件自建件都没有时命令台产物**逐字**与改动前一致"——
   两条要求冲突时以票面为准。代码里两处注释写明了这个取舍。
2. CONTEXT.md 未登记 → **已补**（见交付物表）。
3. `ConsoleEntry` 用"布尔 + 两个空串哨兵"编码两种来源 → **已收**：`call_target` 改成只看 `custom`。
4. JS 变量 `who` 与后端 `label` 不同名 → **已改名** `label`（含浏览器用例里的局部变量）。
5. 两个调用点各建一次命令表（Shotgun Surgery）→ **判为保留**：纯函数 + 确定性，两个调用点
   各有一条用例钉着。
6. 前端用例 `ui.slice(at, at+200)` 魔数窗口 → **已改成整段字面量断言**。
7. 端点用例函数体内 import → **已移到模块顶**。

**Spec 轴**（1 处破票面 + 2 处口径 → 1 条真缺陷已修）：

1. 🔴 **票面第 5 条曾被破**：文件头 else 分支一度改成"这一趟没有复测命令…"，零自建件时
   产物不再逐字一致 → **已改回原字面量**（帮助行与文件头两处），并补了**真守卫**
   （`test_a_run_without_custom_devices_keeps_the_old_console_text`：断言改动前那两句
   中文原文还在产物里 + 两条调用形状逐字相同）——验收项原先没有守卫（新代码比新代码
   = 恒真），探针注入 F 打的就是它。
2. 报错句「可用的字符（31 个…）」只扣保留字、不扣已占用 → **已改**为"可用一共 31 个 /
   已经占了 N 个"，用例断言两个数。
3. 两处文档漂移（`ConsoleTable` / `_header_brief` docstring）→ **已改**。

### 实施时定的口径

1. **字符分配的优先级**：先取 id 里 `mine_` 之后的字母数字，取不出（全被占用或不剩）
   走兜底池 `a`–`z` / `0`–`9`；保留字 `r/y/g/o/b/?` 与库内配方已占用的字符跳过；
   **兜底池也分不出 = 构建期 `HwCheckError`**（400 报给页面），绝不静默少一条。
2. **页面与产物同一次装配**：`hwcheck_view` 与 `render_main_c` 各调一次
   `build_console_table`（同参同序 → 同一个字符），前端只照 `console_payload` 画，
   不另算字符。
3. **库内件载荷零变化**：`console_payload` 只给自建件行加 `tag` / `name`；缺字段 =
   库内件（前端判据）。

### 范围外 / 留给后面的工单

- **自建件 id 带连字符时产物编不过** = 工单 12（本单会话发现：02 的 id 文法允许 `-`、
  03 把 id 直接拼进 C 函数名；与 06 的字符分配无关——`isalnum()` 会把连字符挡掉，
  实测 `mine_gyro-2` 分到字符 `2`）。现场、量具（`probe-12-hyphen-id.py`）与读数已随本单提交。
- **资料 → 事实草稿** = 07；**工程内快照与回读** = 08；**AI 排障带自建件事实** = 09。
- **未上板**：本单是命令台与页面，没有真机动作；照 spec 口径写"未上板"，不假装。
