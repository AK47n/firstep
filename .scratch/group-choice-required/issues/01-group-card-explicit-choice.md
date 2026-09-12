# 01 — 功能组卡不预选 + 未选卡住生成（前后端同源）

**要做什么：** 功能组卡一开始**不替用户勾选**（标题挂「请选择」），需求句灰注写「（请选择）」；
用户点一下成员即完成选择（自动顶替同组的另一个件）；**没选就点生成 → 就地拦住**（前端提示 +
服务端 400 同一条规矩）。

**被谁阻塞：** 无——可立即开始（spec：`.scratch/group-choice-required/spec.md`）。

**状态：** resolved

- [x] 载荷契约：`exclusive_groups[]` 新增 `choice_required`（命中卡 true / hint 卡 false；旧载荷无键 = false）。
- [x] 域层判据单源 `missing_group_choices(group_defs, platform, group_choices, selected_slugs)`：
      待选组 = `choice_required` 且平台投影后 ≥2 成员；已选 = `group_choices[id]` 在该组成员内。
- [x] 端点门禁：`/api/generate` 与 `/api/skeleton` 缺选 → 400 中文（含组名），且**不产生输出目录**。
- [x] 前端纯件：`renderGroupCards` 未选不画 selected + 「请选择」；`applyGroupChoices`（幂等/换选/非组模块不动）；
      `pendingGroupChoices` / `pruneGroupChoices` / `groupChoiceGapText`（hint 卡与旧载荷不算）。
- [x] 前端状态：`groupChoices` 随草稿持久化（`draftState`/`draftRestoreMeta` 加字段）；点 radio 即写入并重算集合；
      需求句灰注未选时写「（请选择）」。
- [x] 两个生成入口就地拦下：主生成走就绪检查单新增的那条硬判据（step 5「功能组选择」），
      骨架/自检走 `groupChoiceGapText()` 前置。
- [x] 测试：`tests/js/group-choice-required.test.mjs`（9 例）+ `group-cards`/`readiness-checks`/`draft-memory`
      口径同步、`tests/test_selection.py`（判据正反例 + `choice_required` 契约）、
      `tests/test_webapp.py`（两端点 400/200 共 5 例）。
- [ ] 真机：一次真实推荐 → 组卡不预选、点一下即选定、未选点生成被拦。**待用户点一次**（见「验收记录」）。
- [x] 回归：全量 `pytest` **4022 passed**、`node --test tests/js/*.test.mjs` **1467 passed**；mypy 两个改动文件干净。

## 双轴评审整改（2026-09-12）

两轴各报一批真问题，**全部整改**（每条都带回归测试）：

| # | 评审发现 | 性质 | 整改 |
|---|---|---|---|
| 1 | `ui/generate-recommend.js` 点 radio 时裸调 `scheduleDraftSave()`——本模块没有这个符号（旧代码走 `clusterDeps.scheduleDraftSave`）→ 点选抛 `ReferenceError`，选中态不刷新、草稿不落盘 | **真 bug（硬）** | 改回 `clusterDeps.scheduleDraftSave()` |
| 2 | `applyGroupChoices` 只算 `choice_required` 组 → **hint 卡点了不进集合**（radio 已勾、工程里没有它） | **真 bug** | 统一重算规则：点组内**快照里已有**的成员 = 换选顶替；点**快照里没有**的 = 只新增（不带走用户手动加的同组件）。hint 卡因此也生效（取代了旧 `applyGroupRadio`，后者已删） |
| 3 | 用户把模块从已选清单移除后，`groupChoices` 仍记着它 → 界面显示「已选」而工程里没有（静默漏件） | **真 bug** | 新增 `clearGroupChoiceForSlug`，两条移除路径（推荐区 chip / 已选清单）都清；移除后组内没人进选中集 → 前后端判据条件② 都放行（不再永久卡住） |
| 4 | 前后端判据漂移：前端缺后端条件②「该组确实进了选中集」→ 用户删掉组内模块后前端永久红、后端却放行 | **真 bug（漂移）** | `pendingGroupChoices(groups, choices, selectedSlugs)` 补上条件②；并加**跨语言镜像守卫**（场景表单源 → fixture → JS 逐场景比对，见下） |
| 5 | 拦截文案两份（后端 Python 一份、前端 `fx/module.js` 与 `ui/generate-core.js` 各一份，措辞还不一样） | 规范违规（仓库「文案单源」先例） | 前端只留 `fx/module.js::groupChoiceGapText` 一份，`ui/generate-core.js` 与就绪检查单经 `groupChoiceGapMessage()` 读它；后端 400 文案保留（跨语言不能共享字符串，但**语义**由镜像守卫的场景表约束） |
| 6 | 旧载荷兼容的书面口径与实现不符（工单写「旧载荷不该被拦」，而服务端按库内组定义判 → 会 400） | 文档不实 | spec 与工单都改成实况，并把「怎么让用户走出来」写进 400 文案（后注：重跑一次「让 AI 推荐」），端点测试新增该断言 |
| 7 | 判据重复实现无镜像守卫、`applyGroupRadio` 被取代后仍留着 | 规范违规 + 死代码 | 新增 `tests/test_group_choice_mirror.py`（场景表单源）+ `tests/js/group-choice-mirror.test.mjs`（13 场景逐条比对）+ `tools/gen_group_choice_mirror.py`（fixture 生成器，**不自动重写**）；`applyGroupRadio` 删除、旧用例改写为 `recordGroupChoice` + `applyGroupChoices`、`fx-guard` 导出面同步 |
| 8 | 合法选择判据散在三处（`slug && members.some(...)`） | Duplicated Code | 提 `groupMemberPick(group, choices)` 单源，`pendingGroupChoices` / `applyGroupChoices` / `pruneGroupChoices` / `groupRequirementNote` 共用 |
| 9 | 新载荷字段缺「逐字段钉」的契约断言 | 测试缺口 | `tests/test_selection.py` 的字段级断言保留 `choice_required`，另加镜像 fixture 覆盖前端侧读法 |

**保留（有意，不整改）**：`renderableGroupCards` / `pruneGroupChoices` / CSS `.needs-choice` /
就绪检查单新行 step 5 / 灰注「已由『组』的 X 替代」——都是让「不预选 + 请选择 + 未选拦住」这条
口径在界面上真站得住的最小配套（spec「方案」第 1~4 条要求的可见面；工具函数各有测试）。
`choice_required` 字段保留：前端靠它区分「硬选择卡 / hint 卡」，而服务端坚持只信库内组定义
（两端判据由镜像守卫对齐，字段本身不参与后端判决）。

## 验收记录（2026-09-12）

**机器可判的部分（已验）**

| 层面 | 判据 | 结果 |
|---|---|---|
| 载荷契约 | `build_exclusive_groups` 命中卡带 `choice_required: True`、hint 卡 `False` | `tests/test_selection.py` 逐字段断言 |
| 判据 | `missing_group_choices` 七组正反例（未选 / 合法成员 / 越界 / 非字符串 / 未进选中集 / stm32 单成员投影 / 无组定义） | 全过 |
| 端点 | `/api/generate` 缺选 400 带组名 + **输出目录未产生**；越界值 400；非对象 400；带齐 200 且目录产生 | `tests/test_webapp.py` 5 例 |
| 端点 | `/api/skeleton` 缺选 400（在调用 LLM **之前**拦下，假 LLM 用 `RaisingLLM` 证明没被碰到） | 同上 |
| 前端纯件 | 未选不画 selected + 「请选择」；点选记账幂等；换选顶替；hint 卡点选也生效；灰注写「请选择」/「已由…替代」；移除模块清记账 | `tests/js/group-choice-required.test.mjs` 12 例 |
| 就绪检查单 | 新增硬判据（step 5「功能组选择」），顺序 3/6/5/1/9 | `tests/js/readiness-checks.test.mjs` |
| 跨语言镜像 | 13 个场景：前端 `pendingGroupChoices` 与后端 `missing_group_choices` 逐条同结论（fixture 由 Python 现算） | `tests/test_group_choice_mirror.py` + `tests/js/group-choice-mirror.test.mjs` |
| 服务在位 | `/js/fx/module.js`、`/js/ui/generate-recommend.js`、`index.html` 新 CSS 均已由运行中的服务提供（重启后 `resolve_port` 与新代码生效） | 实拉端点核对 |

**需要人眼一次的部分（未验，如实留口）**：真实推荐出来的那张组卡在浏览器里的观感（未选态 + 「请选择」徽标 +
点一下即选中、标题徽标消失、需求句灰注从「请选择」变回理由）。这条只能用户在页面里点一次才算验过——
**注意**：页面上现成的那份推荐是**改之前**生成的载荷（没有 `choice_required`）：前端不会本地拦它，
但**服务端会 400**（判据只信库内组定义，不信可能过期的载荷字段）——那条 400 文案会直接告诉用户
「重新跑一次『让 AI 推荐』拿到新版结果」。所以这一步的正确验法是：**重跑一次推荐**再点卡。

## 实施记录：改了什么、为什么这么改

- **状态单源**：前端只用一个 `groupChoices = {组 id: 用户点过的成员}` 决定「选中态」与「能否生成」，
  不再从 `selectedSlugs` 反推「默认选中」——旧口径下「AI 推荐件」自动就是选中态，正是用户说的
  「明明是 AI 替我选的」。
- **集合推导**：`applyGroupChoices(selectedSlugs, groups, choices)` 先移除出卡组的全部成员、再按
  `choices` 加回，幂等可复算；hint 卡与旧载荷不参与（不做硬拦，避免历史缓存把用户卡死）。
- **拦两层**：前端（就绪检查单硬判据 + 骨架前置）与服务端（两端点 400）**同一条判据**的两处实现，
  域层 `missing_group_choices` 是后端那份，前端纯件 `pendingGroupChoices` 与它逐条对齐（含
  「单成员组不算」「组没进选中集不算」「值必须是组内成员」）。
- **代价如实记**：`selectedSlugs` 在用户点选前**仍带着** AI 推荐的那一件（服务端生成集合不因
  「还没点」而缺件），但界面不显示为已选、且不许生成——用户点一下即把它顶替成自己的选择。

## Comments

- 2026-09-12：立单。用户拍板口径：**必须先选才能生成（卡住 + 提示）**、**加「请选择」提示**。
  前半句的另一种自然语言理解是「允许直接生成、未点时用 AI 推荐的那件」，用户明确选了前者。
- 2026-09-12：落地。机器可判部分全绿；浏览器目视那一条留给用户点一次（单内已写清怎么验）。
