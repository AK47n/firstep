# 02 — 三套门禁（浏览器门禁单独跑）+ 对比度冻结读数 + 全站不退化

**要做什么：** 在**冻结的 revision**（01 之后的树，产品面零改动）上把三套门禁与读数各跑一遍、落盘成证据：
确认"要发的那棵树"没有退化，且本批的冻结数还是原值。

**被谁阻塞：** 01（版本号就位后跑的读数才对应要发的那棵树）。

**状态：** resolved（2026-10-01）

- [ ] 前端门禁 `node --test "tests/js/*.test.mjs"` → `js-gate.txt`
- [ ] **浏览器门禁单独跑**（不与**任何** pytest 并行）`node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`
      → `browser-gate.txt`（≈3 分钟）
- [ ] 全量 `python -m pytest -n auto -q` → `pytest.txt`
- [ ] 对比度冻结读数复跑：`contrast-residue/probe-06-register-readings.py`（渲染方登记 **19** 条）、
      `disabled-forms/probe-00-inventory.py`（`opacity` 活规则 **15** / 未在册 **0**）、
      `contrast-residue/probe-09-cant-readings.py`（`li.cant` 整行 浅 5.25 / 暗 5.67）
- [ ] 全站两支老探针不退化：`ui-density-sitewide/probe-00-survey.py`（裸 px 字号 **0**、`--fs-*` **428** 处）、
      `probe-04-scope-calibers.py`（十四个作用域 0/0、页面尺 **0** 条、整圈完整框 **115**）
- [ ] 读数落盘时间戳**晚于**最后一次改产品面（三条纪律第 1 条）
- [ ] 摘要写进票尾；提交信息中文

## 读数落盘怎么跑

```powershell
python .scratch\hwcheck-hygiene\readings.py js-gate --out-dir .scratch\release-v1.4.3 -- node --test "tests/js/*.test.mjs"
```

（别用 PowerShell 的 `>` / `Tee-Object`：写出来是 UTF-16LE，`read` 工具拒读。）

## Comments

### 落地事实（2026-10-01，冻结 revision = `897aba45` + 它的 CHANGELOG 提交 `734deaab`）

| 门禁 / 读数 | 结果 | 文件 |
|---|---|---|
| 前端门禁 | **1847 passed / 0 fail**（15.5 s） | `js-gate.txt` |
| 浏览器门禁（**单独跑**） | **61 passed / 0 fail**（228.9 s） | `browser-gate.txt` |
| 全量 pytest | **5694 passed + 11 skipped / 0 failed**（201.3 s） | `pytest.txt` |
| `probe-06` 渲染方登记表 | 登记 **19** 条（`text` 16 / `surface-bordered` 3）、`skip` **0**；机械面 **394**（冻结 394）、族面 **172**（冻结 172）、`:root` **2** 块 | `probe-06-register.txt` |
| `probe-00-inventory`（opacity 全量） | 总 20 = 动画帧 5 + **活规则 15**，**未在册 0 条** | `probe-08-opacity-inventory.txt` |
| 真像素新拍 + `probe-09` | `.pin-menu-list li.cant` 整行 **浅 5.25 / 暗 5.67**，与静态族面（`--muted` × `--panel-2`）**逐位一致**；每主题命中 20 格 | `probe-09-cant.txt`（新拍 JSON `probe-08-shots-cant.json` + **72** 张 PNG） |
| `probe-00` 家底 | 裸 px 字号 **取值 0 种**、`--fs-*` 引用 **428** 处 | `probe-00-sitewide.txt` |
| `probe-04` 逐作用域 | 十四个作用域 **bareFont 0 / bareSpace 0**；页面尺 **0 条**（完工 14/14）；整圈完整框 **115** | `probe-04-sitewide.txt` |

- **顺序照纪律走**：前端门禁 → 浏览器门禁（**单独跑**）→ 全量 pytest，三段互不重叠；
  真像素那支探针（自己起服务器 + 真 Chromium）也在 pytest 之后单独跑（它文件头明写"不要与全量 pytest 同时跑"）。
- **冻结数一个没动**：394 / 172 / 19 / 0 / 15 / 0 / 428 / 115 —— 与 `contrast-residue` 收尾那一轮逐项相同。
  本批产品面零改动，这正是预期的读数（对不上才要查）。
- **真像素那一发用了新目录 + 一层薄包装**（`run-probe-09.py`）：`probe-08-disabled-state.mjs`
  拍到**本目录**（`--out .scratch/release-v1.4.3`），`probe-09` 的输入路径是写死的常量，
  故包装只把那个常量换成本目录的新 JSON 再调它的 `main()`——**判据与算法仍是同一份代码**，
  上一轮的 PNG/JSON 原地零覆盖。
- ⚠ **读数里那一格 3.54 是已知的账、不是本轮的**：新拍的像素表里 `li.cant` 内的
  `.role-type` 浅色 **3.54**——那正是 `backlog.md` §34「仍开着的①」那条（模板变量拼出来的内联取色，
  腿⑨ 认不到），**本轮范围外**，如实留在读数里。
- 读数落盘时间戳（22:07–22:2x）**晚于**最后一次改产品面的提交（`897aba45`）；此后只改 `.scratch` 证据与单子。
