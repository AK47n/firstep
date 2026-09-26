# 04 — 两处"失败"不许伪装成"没问题"：母版配置读不出来 / 检测记录读不出来

**要做什么：** 两类**读失败**当场说中文真话——① 母版配置**存在但读不出来**时，不许静默跳过
容量判定（预览放行、生成才 400），要当场给理由；② 检测记录**读不出来**（被占用 / 权限 / IO）时，
不许说成"记录坏了、删掉重填"——照那句提示做就是**删掉自己的检测记录**。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**来源**：评审 P2-11 的 Y7 + Y8。**实测更正**：评审说 Y7"与自述的『这种情况不可能出现』直接矛盾"
**不成立**——该文件 docstring 本来就写"判不了就不判"，全包 grep「不可能出现」零命中。
真问题是**把"判不了"伪装成"判过了"**。

## 现状（实测）

- `src/contest_generator/hwcheck_board.py:148-156`：`path.is_file()` 为假 → `None`；
  `except OSError` → **也** `None`（两种语义完全不同的情况在这里被抹平）。
- 同文件 `:216-217`：`if not master_syscfg:` → 直接返回 `HwCheckPinPlan(...)`，
  **容量判定整段跳过**；`:204` 的注释自述"母版没导入 / 假母版 = 判不了就不判，只做第 1 步"。
- `src/contest_generator/hwcheck_triage.py:764-770`：`except (OSError, json.JSONDecodeError)` 共用
  一句话术——「检测记录 hwcheck_record.json **损坏（不是合法 JSON）**：{exc} —— 可以把它**删掉重填**，
  或修好 JSON 再看」。OSError（占用 / 权限 / IO）被冠以"损坏"。

## 验收标准

- [x] **区分两种"没有配置"**：母版**没导入**（平台本来就不可用，页面有状态可依）与母版
      **存在但读不出来**（失败）。后者给**中文 400**（或等价的页面明确提示），文案说清"读不出来"
      与下一步（检查文件是否被占用 / 权限），**不许**再走静默降级分支。
- [x] 容量判定的跳过**不再无声**：凡"因为读不到母版配置而没判容量"，响应里/页面上要能看出来
      （口径自定，但必须存在且用户可见）。
- [x] 记录读失败与坏 JSON **分开两支话术**：
      · 坏 JSON（`json.JSONDecodeError` / 非对象 / version 非法）→ 保留既有"可删可修"的引导；
      · 读不出来（`OSError`，含占用 / 权限 / IO）→ 说明"读不出来"，并**明确不许**出现"删掉重填"
        这类引导（照做会毁掉学生的记录）。
- [x] pytest 用例：注入 `OSError`（monkeypatch 读写函数）→ 断言状态码与文案（含"读不出来/被占用"，
      **不含**"删掉重填"）；坏 JSON 仍走原话术（**不许放松**既有断言）；母版配置存在但读不出来 →
      断言 400 与中文理由（不是"预览通过"）。
- [x] **反证**：把两支话术合回一处（或把静默降级分支放回去）→ 相应用例红；复原后逐字节相同
      （`.scratch/hwcheck-hygiene/probe-04-red.py` / `probe-04-red.txt`）。
- [x] 读数：`python -m pytest -n auto -q` 全套 + `-k "hwcheck or triage or board or pin"` 落盘。

## 结论（读数与账）

**改了什么。**

| 那一处 | 旧形态 | 新形态 |
|---|---|---|
| `hwcheck_board.read_master_syscfg` | `except OSError: return None`——与"母版没导入"挤成同一档 | **读不出来 → `HwCheckError` 中文 400**（说清"读不出来" + 谁占着 / 权限 + 下一步） |
| 容量判定的跳过 | 静默（预览照常放行） | `HwCheckPinPlan.capacity_note` → `wiring.capacity_note` 载荷 → 页面接线区那句警告（**两句话分开**：母版没导入 / 母版在但读不出来） |
| `hwcheck_triage.read_hwcheck_record` | `except (OSError, json.JSONDecodeError)` 共用"损坏…删掉重填" | **两支**：读不出来（说"读不出来"，**不提删**）；内容坏了（保留"可删可修") |

**一处按评审改的口径（比工单字面更细）**：母版读不出来时的 400 **只在需要判容量的那条路上**大声
（`require_pins=True`：预览 / 生成）；**回读与排障**（`require_pins=False`：回放的是已经生成成功的
那一次，容量早判过）不让母版文件被占用就打不开自己的检测工程——那两条路按"判不了就不判"走，
但**照样把原因带在载荷里**（`PIN_CAPACITY_UNREADABLE_NOTE`）。两条合起来才是工单要的
"失败不许静默降级" + "跳过不许无声"：**没有一条路是无声的**，而"打不开工程"这个更坏的后果被避开了。

**页面可见的证据链**（工单要的是"响应里 / 页面上要能看出来"，两半都验了）：
载荷（pytest：`test_view_payload_discloses_the_skipped_capacity_check`）→ 纯函数渲染
（前端门禁：`hwcheckPinCapacityNoteHTML`）→ **真浏览器**（新 spec
`tests/browser/hwcheck-capacity-note.spec.mjs`：造"母版在、但没有 mspm0.syscfg"的库根，
点开检测页真渲染出那句，并顺带钉住页面上无字面星号）。
为什么造这一档而不是"母版整个没导入"：**后者在页面上走不到**——平台卡在母版没导入时是置灰不可点的
（母版没导入 = 平台不可用），可到达的那一档正是"平台可用、这份配置不在"。

**读数（本机实跑，落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 全套 pytest | `python -m pytest -n auto -q` | **5596 passed + 11 skipped**（≈209s；上一单 5587 + 11，+9 = 本单新用例） | `probe-04-pytest-full.txt` |
| 定向 pytest | `python -m pytest -n auto -q -k "hwcheck or triage or board or pin"` | **1020 passed + 10 skipped** | `probe-04-pytest-hwcheck.txt` |
| 前端门禁 | `node --test "tests/js/*.test.mjs"` | **1818 passed / 0 fail** | `probe-04-js.txt` |
| 浏览器门禁 | `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` | **45 passed / 0 fail**（≈208s；含本单新增的那条 spec） | `probe-04-browser.txt` |
| 反证 | `python .scratch/hwcheck-hygiene/probe-04-red.py` | 三处注入各自点名变红（A 1 条 / B 3 条 / C 2 条），三次复原 sha256 逐字节相同、回绿 | `probe-04-red.txt` |

**双轴评审（Standards / Spec，2026-09-26）与处置。**

| 评审发现 | 处置 |
|---|---|
| 硬：`PIN_CAPACITY_SKIPPED_NOTE` 里写了字面 `**没判**` —— 正是工单 02 刚消灭的形态，而判据 ⑨ 的面只切 `static/js/**`、**管不到 Python 文案** | 去掉星号；并补一条真的守卫 `test_page_facing_copy_carries_no_markdown_markers`（把本单四处页面文案一起钉住，含两条错误消息） |
| 硬：回读 / 排障被新 400 打穿（母版文件被占着就打不开自己的检测工程） | 见上「一处按评审改的口径」：`loud=require_pins`，回读路径降级但**说出来**；补 `test_readback_still_opens_when_the_master_syscfg_is_locked` 同时钉两侧 |
| 硬：`HwCheckView.pin_capacity_note` 是零消费者的镜像字段 | 删掉（页面读的是载荷那一份；域层字段没有第二个用途就不留） |
| 硬：反证探针 / 全套读数当时还缺 | 都已补（本单收尾时齐） |
| 判：`_raise_when_reading` 与 `boom` 两处同款注入各写一遍 | 保留（分属两个测试文件；各三行，抽共享件要另开 conftest，本单不值得）——记在这里 |
| 判：注入缝按文件名打 `Path.read_text`，实现改用 `open()` 就会静默失效 | 属实（已知边界）。它是"让某个文件读失败"的最小可移植缝；探针的**前置检查**会在锚点失配时当场红，不会静默放行 |
| 判：其余装配入口（生成 / checklist / 排障）是否同样 400 未验 | 预览（`require_pins=True`）已验 400；生成的容量判据走**同一条** `hwcheck_view` 且同为 `require_pins=True`，所以同一条路径；checklist 不装配板侧视图（不读母版） |
