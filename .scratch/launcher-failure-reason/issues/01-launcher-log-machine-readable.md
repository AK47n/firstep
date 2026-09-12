# 01 — 启动器失败原因可机读（launcher.log 留痕）

**要做什么：** 用户双击 `start-app.vbs` 之后，无论成功还是失败，`%USERPROFILE%\.contest_generator\launcher.log`
里都会多出一行机器可读的启动记录（`[ISO8601] reason=<分支码> key=value…`）——做真机验收的 agent 与用户
自己都能凭这一行判定「这次走的是哪条分支」，不用再靠退出码 + 计时猜。附带把「本应用已在跑」与
「端口被别的程序占」分开记，各分支退出码钉成固定 0/1。

**被谁阻塞：** 无——可立即开始（spec 已拍板：`.scratch/launcher-failure-reason/spec.md`）。

**状态：** resolved

- [x] `tools/launcher-log.ps1` 落地（UTF-8 with BOM）：参数 `-Reason` + 可选 `key=value`，追加一行到
      `%USERPROFILE%\.contest_generator\launcher.log`，UTF-8 **无 BOM**、目录不存在则自动创建、
      时间戳 = `yyyy-MM-ddTHH:mm:sszzz`（`datetime.fromisoformat` 可解析）。
- [x] `start-app.bat` 的**每一条退出路径**都留痕（成功也算）：`updating` / `update_left` /
      `no_python` / `old_python` / `no_deps` / `port_busy` / `timeout` / `already_running` / `started`。
- [x] 端口身份三态分流：`/api/health` 返回 JSON 且 `app == "contest-generator"` → `already_running`（exit 0）；
      返回了但身份不符 → `port_busy`（exit 1）；请求失败/非 JSON → 维持今天的行为（起服务）。
- [x] 退出码固定：成功分支 `exit /b 0`，全部失败分支 `exit /b 1`（不引入新码值，理由见 spec）。
- [x] 弹窗正文补「详情见 …launcher.log」（`no_deps` / `port_busy` / `timeout` 三条）。
- [x] `.bat` 保持 GBK 无 BOM + CRLF（`.gitattributes` 的 `eol=crlf` 不得回退）；新增 `rem` 注释纯 ASCII。
- [x] 测试 `tests/test_launcher_log.py`：① helper 形态（真跑 + 解析 + 无 BOM + 追加语义 + 自建目录）；
      ② 静态守卫「每条 `exit /b` 前必有一次 launcher-log 调用」+「码表被穷举引用」；
      ③ 端口覆盖单源；④ 真机探针与落盘的在位性/全 PASS 判读。
- [x] **不**改控制流本身：本次只加「判读 + 留痕」，失败分支的触发条件与今天逐条一致。
- [x] 回归：全量 `pytest` 与 `node --test tests/js/*.test.mjs` 绿（本单不动前端）。

## 验收记录（2026-09-12）

**真机分支矩阵**：`.scratch/launcher-failure-reason/probe-01-branch-matrix.py` 实跑 → 落盘
`verify-01-branch-matrix.txt`，**7/7 PASS**（真跑 `start-app.bat`，非推断）：

| 形态 | 退出码 | launcher.log | 备注 |
|---|---|---|---|
| `updating` | 1 | `reason=updating` | 更新锁在场 |
| `no_python` | 1 | `reason=no_python` | PATH 与沙箱里都没有 python |
| `started` | 0 | `reason=started tries=1 port=8899` | 真起服务、`/api/health` 就绪 |
| `already_running` | 0 | `reason=already_running port=8899` | 重复双击 = 正常路径，不是失败 |
| `port_busy` | 1 | `reason=port_busy port=8899` | 占位服务身份不符（`app=someone-else`） |
| `timeout` | 1 | `reason=timeout port=8899` | 服务启动被挂住 → 20 次轮询走完 |
| `already_running@8000` | 0 | `reason=already_running port=8000` | 默认端口与用户真实会话共存（只读） |

**单元/静态层**：`tests/test_launcher_log.py` **12 passed**（helper 3 + 静态守卫 5 + 端口覆盖 2 +
探针验收件 1 + …）。

## 实施记录：三条踩过的坑（都会让「看起来在跑」变成假绿/扰民）

1. **模态弹窗不能进测试套**：失败分支的 `WScript.Shell.Popup` 没人点就不返回。第一版把它们直接
   放进 pytest → ① 用户桌面被弹了一排框（两次截图报障）；② 测试挂死 9 分钟。拦框的替代方案逐条
   证伪（PATH/PATHEXT 垫片对绝对路径无效；假 SystemRoot + `.exe` 桩报「不是有效的 Win32
   应用程序」；`.cmd` 桩因命令行带 `.exe` 不被查询）。最终分工：**测试套只跑不弹框的路径**
   （并用「没有 powershell 的假 SystemRoot」兜底），会弹框的四态交给探针（自带弹窗清扫线程 +
   `taskkill /T`）。
2. **验收不许反复开浏览器**：成功分支末了 `start "" "http://…"` 是产品行为，但探针每跑一轮就真开一个
   标签（用户当场叫停）。`start` 是 cmd **内建命令**，PATH 垫片与「替换内建分派」两种做法都无效；
   最终用**临时改写当前用户默认浏览器的 URL 关联**（`HKCU\…\Classes\<ProgId>\shell\open\command`
   → `cmd.exe /c exit`），跑完（含异常）立刻复原，并在探针里**先自证再开跑**（自证不过立即停手）。
   证据：落盘里三次「新增浏览器进程=0 已复原=True」+ `browser-suppressed.json` 记账。
3. **端口覆盖必须两头同源**：`FIRSTEP_LAUNCHER_PORT` 只覆盖 launcher 侧时会出现「launcher 轮询
   8899、服务绑 8000」的**假超时**（探针第一版就这么误判过 `started`）。因此 `webapp.resolve_port()`
   读同一个环境变量（默认仍是 8000），并由 `tests/test_launcher_log.py` 的两条用例钉住同源。

## 双轴评审整改（2026-09-12）

**Standards 轴**：无成文规范违规（BOM / GBK / CRLF / 中文文档 / 工单格式逐条核对）。评审提出的
四类判断题已整改：① `launch-wrapper.bat` 与 `launch-wrapper.marker` **已删**（包装件的角色被
「Python 侧到点 `taskkill /T`」取代，跑完即删以免留无 caller 的死件；码表单源搬进
`tests/test_launcher_log.py::REASON_CODES`）；② 探针里已废弃的 `SHIM` 常量与两处重复的「ping 说明」
已删/收敛；③ spec 里「测试用假 SystemRoot」与测试模块实际结论（假 SystemRoot 写不出日志）的矛盾
已在测试模块头注释里逐条写清（假 SystemRoot 只当兜底）；④ `launcher-log.ps1` 头注释里从未使用的
`http_status=` 例子已删，改为实际字段（`port=` / `tries=`）。

**Spec 轴**：三处实质整改——① **端口身份判据的口径矛盾**（spec 初稿写「请求失败/非 JSON → 起服务」，
实现与既有行为都是 `:port_busy`）已在 spec 里澄清并声明「以行为为准，本单没改走向」；
② **端口旋钮两侧口径不一**（`.bat` 无校验、Python 有）→ `.bat` 补 `findstr` 数字形态 + `gtr 65535`
回落 8000，并加测试钉住同源（原先只数变量出现次数，挡不住漂移）；③ **静态守卫挡不住「留错痕」**
（码表来自手工文件、新分支复制一个已有码就能过）→ 码表改成测试内的单源常量 + 新增
`test_reason_code_table_matches_spec_table`（与 spec 表格对齐）与
`test_guard_catches_regressions_on_synthetic_bat`（合成文本上必须抓住漏留痕/表外新码/重复用码）。
另两条如实记账（见下「已知局限」）。

## 已知局限（评审提出、本轮有意不做的）

- **`test_probe_artifact_and_wiring` 是静态闸**：它只查「落盘在、7 态判读、全 PASS、30 天内」，
  不重跑探针——手写一份「看起来很对」的落盘能骗过它。真正的证据是落盘本身（逐态 `reason` 行 +
  退出码 + 耗时）。要做到强绑定需把探针跑进 CI（一条要 2 分钟、且需要真浏览器/端口），
  那超出本单范围，已在测试 docstring 里写明。
- **`port_busy` 的真机证据只覆盖「JSON 但 `app` 不符」一种形态**；「请求失败 / 返回非 JSON」那一支
  是既有行为（本单没改走向），未单独取证。
- **用户故事 5 只落了 `port=`**（每个分支都带端口）——`ok` 字段与更细的身份读数没有额外记，
  因为 `app` 一个键就是身份判据本身。

## Comments

- 2026-09-12：立单并认领。口径来自 2026-09-18「待拍板六项」第 ⑤ 条（放行、另立单）与
  `newcomer-onboarding/verify-16-E2-timeout-state.txt` 的「下一步建议」。用户本轮同时选了
  「顺带把 E2 超时态真机复现收口」，那部分记在本 feature 的工单 02。
- 2026-09-12：落地 + 双轴评审整改完毕（见上两节）。**偏离工单原句「不改控制流」一处**已记明：
  轮询的 `timeout /t 1` 改 `ping`（stdin 被重定向时 `timeout` 立刻失败、会把「服务没起来」
  误判成超时），spec/工单/测试三处都写清了理由与影响。
- 2026-09-12：落地并真机验收（7/7 PASS）。用户两次就「验收弹出模态框 / 反复打开浏览器」叫停，
  两条纪律已写进 spec 与测试模块头注释。

