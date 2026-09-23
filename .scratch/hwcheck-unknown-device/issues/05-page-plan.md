# 05 — 检测页计划投影：接线说明 / 清单 / 顺序 / 标注

**要做什么：** 自建件出现在检测页的**器件计划**里 —— 接线说明（「你的器件 <名称>（地址 0xNN）接到上面那对脚」）、上板清单、建议顺序、以及它自己的标记；**非 I2C 的库外件**只给清单 + AI 排障，并说明为什么不生成探测程序。

**被谁阻塞：** 02（定义）、03（渲染产物）

**状态：** resolved

- [x] 器件计划 / 接线区出现自建件一行（名称 + 地址 + 接到 `i2c_probe` 声明的那对脚）；文案**单源在域层**，前端一个字不另写
- [x] 上板清单有自建件条目（应看到什么 / 不对先查哪里），三类各一条：**有应答**、**期望值不符**、**无应答**
- [x] 顺序：库内 bring-up 件在前，**自建件排最后**（判据复用既有排序，不另立一套）
- [x] 标注词是「**自建件：按你确认的事实探测**」，产物里**不出现 `[专精]`**（结构守卫钉住两个词不互串）
- [x] 非 I2C 自建件：页面明说这一版不生成探测程序、只给清单与 AI 排障；且**不出现在 C 产物里**（不假装测过）
- [x] 一件自建件都没有时，检测页逐字与改动前一致（既有前端用例全绿）
- [x] 前端 fx 纯件单测进前端门禁；真实浏览器验收覆盖这块面板

---

## 结论（2026-09-23，工单 05 已 resolved）

### 一句话

03/04 已经把「这一趟对自建件做什么」算好了（三档文案、探测小节、平台代价），**但页面上一个字都没显示**；这一单把它显示出来，并补上 03 没管的那一半：**不出小节的件也要在计划里**（非 I2C、没勾输出通道——它们不是模块、没有 C 产物，但这一趟确实选了它们，页面上必须如实说"为什么没有它的探测程序"，否则就是一次悄无声息的少测）。

### 交付物

| 落点 | 是什么 |
|---|---|
| `src/contest_generator/hwcheck_custom.py` | **检测页计划**这一半：`CustomPlanEntry`（`device` / `plan` / `probes` / `pins` / `wiring_text`）+ `resolve_custom_plan` + `plan_payload` + `plan_order_rows` + `custom_checklist`。**判据单源 `_probes`**（C 侧 `resolve_custom_sections` 与页面计划共用）；**文案单源**：`NOT_PROBED_NOT_I2C` / `NOT_PROBED_NO_CHANNEL` 与三档 `PLAN_*` 并列，接线那一行 `_wiring_text` 由支点接线行拼出；清单那三条应看到的文本与产物**同一份字面量**（`_ANSWER_LABEL` / `_ANSWER_YES` / `_ANSWER_NO` / `_MATCH_YES` / `_ping_trouble`），"不对先查"复用 `_TROUBLE_PING` / `_TROUBLE_JUDGE` |
| `src/contest_generator/hwcheck_board.py` | `HwCheckView` 新增 `custom_plan`；`board["custom"]` 从"只出小节的件"改成**计划载荷**（选中的每一件都在）；`board["wiring"]["order"]` 把 `plan_order_rows` **接在既有排序之后** |
| `src/contest_generator/hwcheck.py` | `render_checklist(config, custom=())`：自建件那几条接在**通道形态之后、`reset` 之前**（文案全部来自 `hwcheck_custom`，这里只装成 `ChecklistItem`） |
| `src/contest_generator/webapp.py` | 新增 `_hwcheck_checklist_payload(config, view)`——三个端点（生成 / 回读 / 排障）共用**一处**清单投影；回读端点的清单改到视图之后拼（`read_project_main_c` 仍在取库配置之前，既有求值顺序判据不破） |
| `src/contest_generator/static/js/fx/hwcheck.js` | `hwcheckCustomState` / `hwcheckCustomPlanHTML`（计划面板）/ `hwcheckCustomWiringHTML`（接线区那一行）；`hwcheckOrderHTML` 给自建件那几行加标注词徽章与名称（**空集 = 空串**，既有渲染零变化） |
| `src/contest_generator/static/js/ui/hwcheck.js` | 计划随载荷落地（`refreshHwcheckView` / `hwcheckProjectState`）、`renderHwcheckCustom()`、接线区多画那一行、失败时一并清空 |
| `src/contest_generator/static/index.html` | `#hwcheck-custom` 容器（「这一趟真测哪几件」卡里，专精小节之后）+ 四个类名的样式（`.hwcheck-custom-plan` / `.hwcheck-section-tag.custom` / `.hwcheck-custom-wiring` / `.badge.custom` / `.hwcheck-order-name`） |
| `tests/test_hwcheck_custom.py` | 判据 **47 → 63**：计划覆盖面 / 单源（`_probes` 两条路对账）/ 接线那一行与生效脚逐字对账 / 编不出脚就留空 / 顺序接在库内之后 / 不出小节的件不进顺序表 / 清单三类与"不编它产生不了的类" / 载荷 `custom` / 产物里 `[专精]` 不互串 / 非 I2C 不进产物 / **清单投影单源**（源码判据） |
| `tests/test_my_devices_endpoint.py` | 端点面：`custom` 计划载荷、接线行与接线表同源、顺序最后、生成后的清单三类、回读给同一份清单 |
| `tests/js/hwcheck.test.mjs` | +9 条 fx/接线判据（含"空集 = 空串"与"标注词来自载荷、不许出现 `[专精]`"） |
| `tests/browser/hwcheck.spec.mjs` | +1 条真浏览器用例（接线那一行在表之后 / 计划面板 / 顺序最后 / 生成后的清单三类 / 非 I2C 不进产物）——**刻意排在文件最后**：它会生成一个新工程，而这一支后面的用例靠"上次生成的目录"回读 |
| `.scratch/hwcheck-unknown-device/probe-05-guard-strength.py` / `.mjs` | 反证探针（5 条后端注入 + 2 条前端注入，逐字节复原 + sha256 复核） |

### 验收读数

**判据强度（反证）**——`python .scratch/hwcheck-unknown-device/probe-05-guard-strength.py`
（读数 `probe-05-guard-strength.txt`；4 个源文件 sha256 前置 + 收尾各一次）：

```
[1] 前置检查：hwcheck_custom.py fbb2f7df…／hwcheck_board.py 00ae1579…／hwcheck.py af3994ee…／webapp.py ea406dc2…（锚点各一处 ✓）
[2] 注入前（守卫在）：PASS（五条全绿）
[3] A 顺序不再把自建件排在最后                   → RED ｜ [4] 复原 sha256 相等 ✓
[3] B 计划只列出了小节的那几件                   → RED ｜ [4] 复原 sha256 相等 ✓
[3] C 上板清单不再接自建件那几条                 → RED ｜ [4] 复原 sha256 相等 ✓
[3] D 出不出探测小节不再看总线                   → RED ｜ [4] 复原 sha256 相等 ✓
[3] E 回读端点自己拼一份清单（漏喂自建件计划）   → RED ｜ [4] 复原 sha256 相等 ✓
[5] 复原后复跑：五条全 PASS（回绿）
[6] 收尾指纹：4 个文件逐字节未变 ✓
结论：反证成立
```

前端那两条（读数 `probe-05-guard-strength-front.txt`，`node .scratch/hwcheck-unknown-device/probe-05-guard-strength.mjs`）：

```
PASS  标注词互串：计划面板写死 [专精]            → 门禁退出码 1，红 5 条
PASS  接线区不过滤：没有线可接的件也画一行        → 门禁退出码 1，红 3 条
复原复核：被注入文件与注入前逐字节相同
```

**测试面**（同一份冻结 revision）：

```
python -m pytest -n auto -q                     5253 passed + 1 skipped / 159.4s
node --test "tests/js/*.test.mjs"               1748 passed / 0 fail        （改动前 1739）
node --test --test-concurrency=1 "tests/browser/*.spec.mjs"
                                                36 passed / 0 fail / 105.0s（改动前 35）
```

### 验收第 6 条（一件自建件都没有时逐字一致）怎么钉的

三条腿，缺一条都不算：
① 渲染层：`hwcheckCustomPlanHTML([])` / `hwcheckCustomWiringHTML([])` 都返回**空串**，
`#hwcheck-custom` 容器里一个字都不写；`hwcheckOrderHTML` 对没有 `custom` 的行走的
是原来的分支（用例「计划面板：**一件自建件都没有 = 空串**」+ 既有 131 条一条没改）；
② 服务端：`render_checklist(config) == render_checklist(config, ())`（用例
「上板清单…在正确的位置」最后一行）；
③ 门禁：**既有前端用例全绿**（1748 passed，一条没删没改）。

浏览器门禁那 36 条里本单新增的是「自建件的检测计划：接线那一行 / 计划面板 / 顺序 /
上板清单三类」——**刻意排在那支 spec 的最后**（它会生成一个新工程，而该 spec 后面的
用例靠"上次生成的目录"回读，插在中间会让它们读到这一条生成的工程）。

容器本身落在「这一趟真测哪几件」卡**里**（专精小节之后），不是新开一张卡——空集时
页面上没有多出任何可见的东西（`.hwcheck-custom-plan` 只有有件时才渲染）。

### code-review 两轴结论与整改

**Standards 轴**（1 硬违规 / 8 判断项）——**硬违规已修、判断项收掉 7 条**：

1. **硬违规：`docs/agents/local-environment.md` 已过期**（§0 还写着「05–10 未开工」）。
   → 收尾时按该文件的更新纪律改写（含本单读数与 main-only 落差的记账）。
2. **同一句话两处字面量**：清单那三条"应看到"与产物里那几句判定是两份字面量
   （`hwcheck_custom.py` 里 `ping_trouble` / `"（与期望值一致）"` / `"应答：有"`）。
   → 收成 `_ping_trouble(device)` 与 `_ANSWER_LABEL` / `_ANSWER_YES` / `_ANSWER_NO` /
   `_MATCH_YES` / `_MATCH_NO`，渲染与清单读同一份。
3. **同一个 `CustomSection` 建两遍**（`resolve_custom_sections` 与 `resolve_custom_plan`
   各建一次，`_plan_for` 在一个循环里算两遍）。→ `CustomPlanEntry` 不再持 `section`
   （改成 `probes: bool` 字段），`_plan_for` 一圈只算一次。
4. **载荷里两个前端零消费的键**（`not_probed` 恒等于不出小节时的 `plan`；`pins` 只有
   `wiring_text` 用到）。→ 两个都撤出载荷（`pins` 留在 dataclass 里拼那句话）。
5. **`not_probed`（str）与 `probes`（bool）并排的命名**、`custom_payload` 与
   `custom_sections` 两个"custom"含义相反。→ 前者随第 4 条消失，后者改成在唯一使用点
   内联调用。
6. **`.badge.custom` 没有 CSS 规则**（顺序表那枚徽章只有形状没有色）。→ 补规则。
7. **三处端点各写一遍清单列表推导**。→ 收成 `_hwcheck_checklist_payload(config, view)`
   + 源码判据（`test_the_checklist_projection_has_a_single_home`）钉住"路由层不许
   出现第二处投影"——这一条同时消掉下一个判断项（**漏喂计划不会报错、只会静默少几条**，
   正是本功能一路在防的那类坏法）。
8. `CUSTOM_CHECK_IDS` 导出但无人用、四条里三条是恒等映射。→ 撤掉那张表（id 只在本模块拼，
   前端照渲染不认名字）；`.py` 探针的 `--out` 改成缺省即落盘（与 `.mjs` 那支一致）。

**Spec 轴**（缺失 1 / 蔓延 2 / 实现不对 1）——**1 条真缺陷已修**：

1. **🔴 清单里那句承诺了不存在的能力**（最重的一条）：`_CHECK_NOT_PROBED` 第③条原文
   写「AI 会带上你填的总线 / 地址 / 寄存器给排查方向」，而**自建件的事实进排障上下文
   是工单 09**（03 的「留给后面的工单」明写），`hwcheck_triage.build_triage_context`
   的入参里根本没有自建件事实——这一版写这句话就是让学生去等一个不存在的能力。
   → 改成「它按平台与检测计划给「下一步查什么」的方向（你填的地址 / 寄存器这一版还
   进不了它的上下文）」。
2. **验收第 2 条的字面（"三类各一条"）在形态①/② 上是两条**：只有地址（①）与有寄存器
   无期望值（②）都产生不了"期望值不符"那一档。**判为刻意的偏离并保留**（不为一件器件
   编它产生不了的类——编一条学生照着比、板上永远不会发生的事比少一条更坏），
   三个字段齐备（形态③）才是票面那句话的基准形态，用例钉的就是它。
3. **两处轻量蔓延**（判为可辩护、保留）：计划面板多印「你填的备注：」与「板上判定」
   徽章（票面只要求名称 + 地址 + 接线 + 这一趟做什么）——备注是用户自己填的事实
   （02 的字段说明写明它"进清单与 AI 排障"），徽章与库内小节用同一套视觉语言；
   顺序表那枚徽章的 `.badge.custom` 缺规则已按上面第 6 条补齐。

评审同时提了一条**过程事实**（照做）：评审期间工作区被并发改写（Standards 整改），
所以 `probe-05-*.txt` 里记的 sha256 会过期——**收尾在同一份 revision 上重跑了两个
探针与三门禁**，本工单记的读数是重跑后的。

### 两处实施时定的口径

1. **`board["custom"]` 的语义从"出了小节的件"扩成"选中的每一件"**（计划载荷）。
   它是 03 落的键、当时只装得出小节的件；05 起页面要显示"为什么没有它的探测程序"，
   所以覆盖面必须与"选中集"对齐。判据仍是 `probes` 一栏（前端按它画徽章），
   **产物那一半一个字没动**（`view.custom` 仍是 `CustomSection` 元组，
   `generation_slugs` 的判据不变）。既有用例
   `test_a_non_i2c_custom_device_still_does_not_render_a_probe` 由"载荷里空数组"
   改成"这一件在、但 `probes=False`"（**产物侧断言一条没松**）。
2. **顺序表里 `i2c_probe` 照旧在**：它是这一趟真进工程的模块（04 起页面接线表里就有它
   的行），顺序表与进工程集合同源；**悬空的是那个不存在的"用户选了它"**——页面从来
   只按 `devices` 画 chip，支点模块不进 chip、也不进 `missing`。本单没有为它开特例
   （开特例 = 在顺序投影里再加一处"谁算用户选的"判据）。
3. **接线区那一行接在表下面**，措辞说「接到**上面**接线表里 `i2c_probe` 的那对脚」
   ——那句话指的就是刚读完的那张表。

### 范围外 / 留给后面的工单

- **串口复测命令**（自建件分字符、页面上显示敲什么）= 06；**资料上传与草稿** = 07；
  **工程内快照与回读** = 08；**AI 排障带自建件事实** = 09（本单已把清单里那句
  "AI 会带上你填的地址"的清真话**删掉**，等 09 落地再加回来）。
- **母版引脚符号重名** = 工单 11（本轮新开的母版级缺陷，与 05 无交集）。
- **未上板**：本单是页面与投影，没有上板动作；器件真能应答仍属 03/04 留下的真机口径。
