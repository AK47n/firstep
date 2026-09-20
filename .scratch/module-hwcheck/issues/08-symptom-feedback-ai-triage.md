# 08 — 现象回填 + AI 排障

**要做什么：** 用户上板跑完，把「我实际看到的现象」填回检测页，AI 给出排查方向（先判断是接线问题、器件问题还是代码问题，再说下一步查什么），并把这次检测的现象与清单勾选一起留档。

**被谁阻塞：** 04（要有专精检测结果可供讨论）。

**状态：** resolved

- [x] 检测页有现象输入区；提交后返回中文排查建议（结构化：可能原因 + 下一步查什么）
- [x] 送进模型的上下文含：接触线表与引脚绑定、检测项清单、勾选状态、用户填写现象；**不编造库内没有的接口或引脚**
- [x] LLM 失败**不阻断**（中文兜底文案 + 可重试），检测记录照常保留
- [x] telemetry 与"最近工作流"接入既有机制（事件常量登记在事件词表单源）
- [x] 协议方法列入既有协议清单用例（假 LLM 桩同步），保证漏实现即红
- [x] 事实约束：建议里出现的引脚名与模块名必须来自本次检测上下文（假 LLM 桩注入非法值 → 拒收或降级，有单测）
- [x] 检测记录（现象 + 勾选 + 建议）随该次检测落盘，刷新可回显

## 边界与决策引用

- 这是本功能里 **LLM 的唯一入口**（其余全程确定性渲染）；失败降级照既有"步骤报告"先例。
- 检测没过 = 正常结果：建议里要给"必要时把问题反馈成一张修复单"的出口，不含糊其辞。

## 落地形态（做完的记录）

| 面 | 落点 |
|---|---|
| 域层（纯逻辑 + 记录） | `src/contest_generator/hwcheck_triage.py`（`TriageContext` / `TriageAdvice` / `TriageFacts` / `TriageFactError` / `HwCheckRecord`） |
| LLM 协议方法 | `llm.py::triage_hwcheck_symptom`（协议 / DeepSeek 实现 / RoutingLLM 委托三处齐；`PROTOCOL_METHOD_NAMES` + `_call_all_protocol_methods` 同步，漏实现即红） |
| 端点 | `POST /api/hwcheck/triage`（同步；模型失败 = 200 + 兜底 + `degraded`）、`POST /api/hwcheck/checklist`（零 LLM，勾选落盘）、`GET /api/hwcheck/project` 多返回 `record` |
| 事件 | `events.EVENT_HWCHECK_TRIAGE = "hwcheck_triage"`（与 `buy_discuss` / `idea_chat` 同款：同步端点只登记常量，观察面板走 `recent_llm_workflows`） |
| 上下文与白名单 | 同一处装配（`build_triage_context`）：材料 = `triage_context_text`，白名单 = 接线行脚 ∪ 板上共享脚 ∪ **材料里出现过的脚** ∪ 本次工程模块集（对整库 slug 词表判"编造了本次没有的件"） |
| 拒绝分道 | 形状错 → `HwCheckError` → `LLMError(parse)` 快重试；事实错 → `TriageFactError` → `LLMError(kind=domain)` + `domain_retry=True`（带被拒理由重出一次，先例 `real-acceptance/03`） |
| 记录文件 | 工程根 `.contest_hwcheck_record.json`（现象 + 勾选 + 建议；原子写；坏 JSON 大声失败点名文件） |
| 前端 | `fx/hwcheck.js` 8 个新纯函数（请求体 / 建议渲染 / 记录归一 / 勾选响应）+ `ui/hwcheck.js` 三处接线 + `index.html` 一张新卡片 + CSS |

## 评审处置（code-review 两轴，工作区 diff）

**Standards 轴**——5 条硬性 + 5 条判断题，逐条处置：

| 意见 | 处置 |
|---|---|
| 事实错与形状错共用 `parse` kind，与 CONTEXT.md「错误映射」的 domain 分道相悖 | **已修**：新增 `TriageFactError` 类型 → `LLMError(kind=ERROR_KIND_DOMAIN)` + `domain_retry=True`（两处单测：域拒绝带理由重问一次、形状错仍走 parse 快重试） |
| `check_advice_facts` docstring 说"形如 xxx_yyy"，与实现/用例矛盾 | **已修**（判据是按整库 slug 词表命中，不要求下划线） |
| `webapp.py` 函数内重复 import `LLMError` | **已修**（删掉，用顶部那份） |
| `__all__` 漏 `check_advice_facts` | **已修**（并补 `TriageFactError` / `DEFAULT_ISSUE_HINT`） |
| `_hwcheck_view` / `GET /project` docstring 未随新键更新 | **已修**（补 `known_slugs`、`record`） |
| 三处重抄时间戳逻辑 | **已修**：抽 `_stamped(record)` 单源 |
| `TriageContext` 持 `Mapping`（Data Clumps / Primitive Obsession） | **保留**：这些 Mapping 就是 `hwcheck_board` 的投影形状（页面与模型吃同一份），另造一套 dataclass = 同一份数据两种表示 |
| `_dedup_str(values: Sequence[str] \| Any)` 注解形同虚设 | **已修**：改 `Iterable[object]` 并说明两个调用方 |
| `extract_module_selection_data` 名字与语义不符（存量问题，新调用点加剧） | **不改**（存量命名；改名要动 10+ 调用点，另开单） |
| ui 用"勾选为空"判"没有记录"→ 本地旧勾选可能复活 | **已修**：判据改成"这次回读带没带 `record` 键" + 守卫用例 |

**Spec 轴**——2 条实现问题 + 3 条缺失 + 3 条范围蔓延：

| 意见 | 处置 |
|---|---|
| ① 事实判据与材料两张皮：清单「不对先查」里写着 `PC13/PC14/PC15`，模型复述却被判非法 → 重问 → 降级 | **已修（本单最重的一处）**：白名单补上**材料里出现过的脚**（`_material_texts`，只收会印进 prompt 的字段 + 现象本身），并加两条守卫（材料里的脚放行、材料外的脚照旧拒收） |
| ② checklist 端点只判 `is_dir()`，能把记录写进赛题工程 | **已修**：`_hwcheck_record_dir` 走 `read_hwcheck_project` 的 kind 判据；端点用例补"指到赛题工程 → 400 且不落文件" |
| ③「不编造库内没有的**接口**」只查了引脚与模块 | **部分达成并如实记录**：prompt 材料里**不出现函数名**（小节只印 `plan`），所以模型没有"引用接口"的入口；判据覆盖"可查表的两类话题词"（引脚 / 库内模块）。函数级白名单不在本单（检测页不改代码，建议是给人看的排查方向）——要收紧得先让材料带上接口清单，另开单 |
| ④ 反馈出口可空 = 不含糊其辞没兜住 | **已修**：`DEFAULT_ISSUE_HINT` 兜底（模型不给就用产品那句） |
| ⑤ `EVENT_HWCHECK_TRIAGE` 无发射点 | **保留**（与 `buy_discuss` / `task_discuss` / `idea_chat` 同款：同步端点无 SSE 发射器，票面只要求"事件常量登记在事件词表单源"；观测走 `recent_llm_workflows`） |
| ⑥ 范围蔓延：新端点 `checklist` / `known_slugs` / 本机笔记 | `checklist` 与 `known_slugs` **是本条验收标准的实现手段**（"勾选随该次检测落盘"要一个零 LLM 的写入口；事实约束要整库 slug 词表），本机笔记是 `CLAUDE.md` 的更新纪律 |

## 判据强度（反证实测）

`.scratch/module-hwcheck/probe-08-guard-strength.py` 对 **9 处判据**逐个做最小停用，
要求点名用例变红并**逐字节复原**——9/9 PASS（原始输出 `verify-08-guard-strength.txt`）：
事实约束查表 / 降级不阻断 / triage 落盘 / 勾选落盘 / 勾选响应只认勾选 /
材料脚入白名单 / 勾选端点 kind 判据 / 域拒绝分道 / 反馈出口缺省。

## 测试读数（本机，2026-09-20）

| 跑法 | 读数 |
|---|---|
| `tests/test_hwcheck*.py` + `test_llm.py` + `test_webapp.py` + `test_errors.py` + `test_context_manifest.py` | **1057 passed**（新增：`tests/test_hwcheck_triage.py` 34 条域层用例 + `test_hwcheck.py` 6 条端点用例 + `test_llm.py` 2 条分道用例） |
| 前端门禁 `node --test "tests/js/*.test.mjs"` | **1679 passed / 0 failed**（新增 14 条：请求体 / 建议渲染 / 记录归一 / 逃逸 / 控件与阅读顺序 / ui 单源与并发纪律） |

**未上板**：本单只到"工程能编译 + 页面能提交"这一层；真机现象回填的一轮在上板证据
（工单 09 收尾）里记，没跑就写"未上板"，不假装。
