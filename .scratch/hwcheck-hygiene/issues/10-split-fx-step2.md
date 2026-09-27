# 10 — 拆 fx 第二步：迁移消费者、删掉旧文件与再导出

**要做什么：** 把纯函数层的全部消费者改指到新的六个模块，然后**删掉旧文件与那段过渡性的再导出**
——`static/js/fx/hwcheck.js` 这个路径从此不存在。

**被谁阻塞：** **09**（六件新模块 + 搬迁完整性自检先绿）。

**状态：** resolved

## 现状（实测：旧文件的 fan-in 很小）

| 消费者 | 引用数 | 引的是什么 |
|---|---|---|
| `static/js/ui/hwcheck.js` | 1 条大 import 块（约 90 个名字） | 大部分导出 |
| `tests/js/hwcheck.test.mjs` | 13 处 | 纯函数与渲染产物断言 |
| `static/js/ui/generate-recommend.js` | 2 处 | 衔接相关的名字 |
| `tests/browser/hwcheck.spec.mjs` | 1 处 | 直接引用（若为字符串/注释也要一并改） |

## 验收标准

- [x] 四个消费者全部改指新模块（`ui/hwcheck.js` 那条大 import 块按新模块拆成若干条，
      并保留既有的行尾注释体裁）。
- [x] 旧文件与其再导出**删除**；`grep -r "fx/hwcheck.js" static tests` **零命中**
      （`boot.js` 的模块清单若列了它也要一并改）。
- [x] `window` 桥名字并集在删除前后**完全相等**（每件新模块各自发布自己那一段）——
      页面内联脚本与浏览器探针仍能取到同样的全局名。
- [x] 搬迁完整性自检切到"搬前快照"那一侧（见 09），仍然绿；**自检不许随旧文件一起删掉**。
- [x] **反证**：故意漏迁一个消费者的一个名字 → `static-import-guard` 判据④或 `import-usage-guard`
      必须红；复原后逐字节相同（`.scratch/hwcheck-hygiene/probe-10-red.py` / `probe-10-red.txt`）。
- [x] 读数：全套 pytest + 前端门禁 + 浏览器门禁，三个读数落盘。
- [x] 本单收口后本文件**没有留下任何过渡态**（barrel、临时快照脚本的去留：快照留档在本目录，
      脚本若只服务 09/10 则移进本目录而不是留在 `tests/js/`）。

## 结论（读数与账）

**这笔做了什么。** 09 留的过渡态 barrel（`fx/hwcheck.js`，六条 `export { … } from`）的消费者全部
改指六件，然后**把 barrel 删掉**：

| 消费者 | 改法 |
|---|---|
| `ui/hwcheck.js` | 那条 90 来名的大 import 按**名字的归属**劈成六条（state / project / wiring / plan / triage / handoff），块首一句说明；既有注释体裁照旧 |
| `tests/js/hwcheck.test.mjs` | 同样劈成六条；「ui 应从 fx/hwcheck.js 导入纯件」改成**六条边逐条**断言（少一条就点名缺哪一件） |
| `ui/generate-recommend.js` | `hwcheckHandoffMerge` → `/js/fx/hwcheck-handoff.js` |
| `tests/browser/hwcheck.spec.mjs` | 注释里的路径（那条用例的前提说明） |

**票面「现状」表只列了这四个消费者，实测还有 5 处指着旧路径**（`index.html` 三处注释 /
`webapp.py` / `hwcheck.py` / 两个 pytest 文件的说明文字 / `tests/test_js_gate.py` 的**路径字面量**）
——本单一并改指新家（`apply-10-migrate.py` 的 `RENAMES` 表，20 处、每条要求命中指定次数）。
**不是范围蔓延**：`test_js_gate.py` 那条是真读的路径（不改就红），其余 5 条是文档漂移（留着就是
下一个"哪句是过期的"）。`boot.js` 的装载清单只列 `ui/hwcheck.js`（实测），无需改。

**⚠ 口径收窄一处（票面说 grep 零命中，实现判的是"没有 import 边"）**：六件的文件头与
`tests/js/export-surface-guard.test.mjs` 里还留着 14 处**文本**命中，全是"由 `fx/hwcheck.js`
按职责整段搬来"这类**墓碑注释**——那是本仓既有体裁（`boot.js` 里满是这样的话，
`boot-contract.mjs` 也明确按「注释不是消费者」处理）。真会炸的是 **import 边**：
请求一个不存在的模块 = SyntaxError + 整页不亮。所以判据 `过渡态不留痕` 判的是
① barrel 必须不存在、② `from "…/fx/hwcheck.js"` / 裸装载 / `src="…"` 三类边零命中
（覆盖面还扩到了 `.py` / `.html`），**注释留着解释来历**。判据文件里本文件自豁免
（它的正则必须字面写着那个路径），自指风险由 5 条正向对照兜住。

**⚠ 票面点名的两条守卫为什么不红（这一条要记账）**：票面写「漏迁一个消费者的**一个名字** →
`static-import-guard` 判据④ 或 `import-usage-guard` 必须红」。**照字面做，两条都不会红**——
`graphBreaks`（全图对账）只判"被 import 的名字在目标模块有没有出处"（少一个 import 名不影响），
`import-usage` 只判"导了却没用"。会红的是另外三条：判据 ⑧（靠桥解析）、`ReferenceError`
（用例侧）、以及**判据③ 的"文件不存在"**（消费者还指着已删的 barrel）。所以反证按**等价形态**
（"这条边没迁"）做，三段：

| 段 | 注入 | 红在哪 |
|---|---|---|
| ① | ui 里指向 `hwcheck-plan.js` 的 import 整条删掉 | `window-bridge-guard` 判据 ⑧ 点名 `hwcheckSectionsState`（**桥兜住了运行态**，只有这条判据看得出来） |
| ② | 用例里指向 `hwcheck-handoff.js` 的 import 整条删掉 | 前端门禁红，点名 `ReferenceError: hwcheckHandoffPlan is not defined` |
| ③ | 把 ui 的 state import 改回**已删除的 barrel** | `static-import-guard` 判据③ 报「`ui/hwcheck.js → /js/fx/hwcheck.js`：**文件不存在**」——票面点名的那条守卫 |

三段各自「注入即红、复原 sha256 逐字节相同」（`probe-10-red.txt`）。

**读数（本机实跑，落盘在本目录）。**

| 闸门 | 读数 | 文件 |
|---|---|---|
| 全套 pytest | **5604 passed + 11 skipped** | `10-pytest-full.txt` |
| 前端门禁 | **1827 / 0**（基线 1819 → 09 的 1826 → 本单 +1「过渡态不留痕」） | `10-js-gate.txt` |
| 浏览器门禁 | **48 / 0** | `10-browser-gate.txt` |
| 反证 | **3/3 段**（见上表） | `probe-10-red.txt` |
| 独立复核 | 零掉队模块；桥搬前 77 = 六件并集 77（逐名）；**barrel 已不在**；导出并集 78 = 搬前 | `10-reachability.txt` |
| 迁移脚本 | 归属表现算（78 名 → 六件）＋ 每个消费者迁移前后具名集合逐名相同 ＋ 按原换行逐字节写回 | `10-migrate-write.txt` |

**双轴评审（Standards / Spec，2026-09-27）与整改。**

| 轴 | 发现 | 处置 |
|---|---|---|
| Spec 硬 | 票面 7 条仍全 `-[]`、无「结论（读数与账）」，而自检里写着"理由在票尾"——**票没改、账没记** | 就是本节（含上面两处 ⚠ 记账）＋ 验收标准逐条勾 |
| Spec 硬 | 票面点名的两条守卫没有落盘读数（当时 `probe-10-red.txt` 只有 2/2） | 补第 ③ 段（回指已删 barrel → `static-import-guard` 判据③「文件不存在」）并重跑落盘 **3/3**；同时把"照字面做两条都不会红"写进票尾 |
| Standards 判 | `apply-10-migrate.py` 用文本模式 I/O：读数报的是**剥掉 CRLF 后的字符数**（盘上 68129 B 报 50857），复现不出来 | 改成**逐字节读、按原换行写回**（`load()` / `save()` / `EOLS`），报告改报**字节数**（`68129 → 68469 B（换行 CRLF）`） |
| Spec / Standards 判 | `ui/hwcheck.js` 新增的块首注释截断（「…计划 /」后断，六类只列四类） | 补成两行完整句（并同步到脚本的 `CONSUMERS`，保证重跑同形） |
| Standards 判 | 口径收窄是否算偷放宽 | 判为合理（票面 `grep` 口径会把墓碑注释一起判死，而注释不是消费者）；本条与理由写进票尾 |
| Spec 判 | 12 号单的基线被本单改了，两票都没记 | 记在此：`hwcheck.test.mjs` 里旧路径引用 **55+1 → 43**；「纯件留在 fx」那 1 条源码串断言扩成 **6 条**（结构守卫，非行为断言）；「单平台件不误导」由"读单件"改成"读整层"（判据面放宽一处，12 号单重算时按新口径算） |
| Standards 判 | `apply-10-migrate.py` 里"两遍写覆盖"与"Windows 键分隔符"两个坑 | 都留在脚本注释里（键统一 `as_posix()`、两变换合成一次写；重跑会因锚点已迁而 assert 失败，不会二次破坏） |

**未上板**：本单是纯搬迁收口，**没有任何板上行为被验证**（本机没有板子）。
