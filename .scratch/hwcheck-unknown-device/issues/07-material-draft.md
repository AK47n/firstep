# 07 — 资料 → 事实草稿

**要做什么：** 学生贴一段文字 / 传 PDF 手册 / 传模块照片或手册截图，AI 把里面的关键事实抽成**草稿**填进「我的器件」表单（名称、总线、地址、身份寄存器、期望值、备注），每条带**原文出处片段**；抽不到的字段留空并说明。**草稿一律由用户逐字段确认后才保存。**

**被谁阻塞：** 02（定义与表单）

**状态：** resolved

- [x] 复用既有抽取通道（PDF 文本 + 示意图描述 / 图片视觉描述）拿到文本，再走**一次** LLM 调用抽成严格形状的草稿 JSON
- [x] 草稿形状校验在**域层**：字段白名单、每条事实带出处片段、地址 / 寄存器 / 期望值必须是合法数值；不合法 = 拒收重问，仍不行 = **降级为纯手填**（流程不阻断）
- [x] 抽不到的字段留空 + 一句"手册里没找到"，**绝不编造**（用例：喂一段无关文本，草稿必须为空字段 + 说明）
- [x] AI 不可用 / 未配置 key：页面直接走纯手填，不报错
- [x] 页面**明说资料会被送到 AI 通道**抽取；草稿填入后用户可逐字段改，**未确认前不落盘**
- [x] AI **不写代码、不生成判据、不决定探测动作**（结构守卫：本链路不产出任何 C）
- [x] 提示词与页面文案中文（仓库语言规范）；前端 fx 纯件单测进前端门禁

---

## 结论（2026-09-23，工单 07 已 resolved）

### 一句话

学生手上的资料（卖家页 / 手册 / 照片）第一次有了入口：贴文字或传文件（**既有抽取通道**
`/api/extract` 拿文本）→ **一次** LLM 调用抽成严格形状的草稿 → 页面带出处片段地展示
（"AI 没编"的可见证据）→ 填进表单 → 用户逐字段确认后走**既有的保存路径**。草稿
永远只是表单预填，**一个字节都不落盘**；AI 不可用就降级纯手填，流程不阻断。

### 交付物

| 落点 | 是什么 |
|---|---|
| `src/contest_generator/my_device_draft.py`（新） | **草稿的形状与校验单源**：`DRAFT_FIELDS` 六字段白名单（多一个 / 少一个都拒）、`parse_device_draft`（形状 / 数值区间 / 词表全按定义层同一套常量）、**反编造判据**（每条有值的事实必须带原文出处片段，归一化后子串比对**真的在原文里**——不在 = `DeviceDraftFactError` 域拒绝）、`MISSING_TEXT`（"手册里没找到"文案单源）、`draft_payload` / `empty_draft`；**零写盘函数**、import 面不含任何渲染 / 生成侧模块（结构守卫钉住） |
| `src/contest_generator/llm.py` | `DEVICE_DRAFT_SYSTEM_PROMPT`（"硬件资料抄写员"立场：只逐字抄、没写就是 null、不写代码不生成判据）+ `_device_draft_user_prompt`（资料原文整段进，出处比对查的就是同一份）+ `draft_device_facts`（LLM 协议 / DeepSeekLLM / RoutingLLM 三处——两类拒绝分道照 triage 先例：`DeviceDraftFactError` → `ERROR_KIND_DOMAIN` 带理由重出一次，形状错 → 解析类快重试） |
| `src/contest_generator/webapp.py` | `POST /api/my-devices/draft`：text 必填 → 一次抽取 → `{draft, degraded, message}`；`LLMError` → **200 + draft:null + degraded:true**（照 triage 降级口径）；`LLMRun.settle()` 在 finally |
| `tests/fakes.py` | FakeLLM 加 `device_draft` / `device_draft_error` 参数与 `draft_calls` 记录（缺省 = `empty_draft()`，诚实形态）；RecordingLLM 补齐协议方法 |
| `static/index.html` | `#my-devices-material` / `#my-devices-draft` 容器 + 资料入口 / 草稿面板样式 |
| `static/js/fx/my-devices.js` | `MY_DEVICE_MATERIAL_NOTICE`（知情文案单源：明说送 AI 通道 + AI 不写代码）、`myDeviceMaterialHTML`（文本框 + 文件入口 + 忙态）、`myDeviceDraftPanelHTML`（字段值 + **出处片段** + 没找到的实话 + 填表 / 不用按钮）、`myDeviceDraftToForm`（只覆盖**找到了的**字段，用户已填的 id 不覆盖）——全部纯件 |
| `static/js/ui/hwcheck.js` | 状态五键 + renderMyDevices 扩展 + `draftMyDevice` / `draftFromMyDeviceFile`（FormData → `/api/extract` 既有通道，抽出的文字回填文本框——用户看得到送出去的是什么）/ `applyDraftResponse`（降级 → "直接手填，一样能测"）/ `applyMyDraft`（**编辑已有器件时拒绝覆盖**——编辑态保存按 id 幂等，草稿冲掉原事实是数据损失）；文本框打字只同步 state 不重绘（表单同款纪律） |
| `tests/test_my_device_draft.py`（新） | **30 条**：好草稿解析归一（整数 / 十进制 → 0xNN）、载荷精确形状、白名单、有值没出处、**编造出处**、跨空白大小写的出处比对、超长出处、区间与写法、未知总线、无关文本全空、部分抽取只列缺的、空草稿、形状健壮、import 面结构守卫、提示词契约对账 |
| `tests/test_my_devices_endpoint.py` | +5 条：成功路（载荷 + `draft_calls` + **数据目录零触碰**）、降级路（200 + degraded）、text 必填、**无关文本全空**（票面点名用例）、完全未配置（400 中文指路） |
| `tests/test_llm.py` | +2 条 LLM 层：编造出处 → domain kind + 带理由重问（两次调用 + 理由进 user 消息）；形状错 → parse kind；`draft_device_facts` 进 `PROTOCOL_METHOD_NAMES` 覆盖清单与派发扫描（remote 集） |
| `tests/js/my-devices.test.mjs` | +9 条：知情文案、忙态 / 消息 / 回填、面板字段与出处、esc、已填态、草稿→表单（值形态 / id 派生 / 不覆盖用户输入 / 空草稿）、**DRAFT_FIELDS 跨语言逐字对账** |
| `tests/browser/hwcheck.spec.mjs` | +1 条（文件最后）：资料入口渲染 + 知情文案可见 + 空文本本地提示——**零 LLM 请求**（浏览器夹具继承真机配置，真点一次就是真额度） |
| `.scratch/hwcheck-unknown-device/probe-07-guard-strength.py` / `.mjs` | 反证探针（4 条后端注入 + 1 条前端注入，逐字节复原 + sha256 复核） |

### 验收读数（2026-09-23 冻结版）

**三门禁**：

```
python -m pytest -n auto -q                   5322 passed + 1 skipped / 139.5s（12 轮 5285 + 本单 37）
node --test "tests/js/*.test.mjs"             1764 passed / 0 fail（12 轮 1755 + 本单 9）
node --test --test-concurrency=1 "tests/browser/*.spec.mjs"
                                              38 passed / 0 fail（12 轮 37 + 本单 1；
                                              首跑 2 红为 launcher-reload 已知并行偶发，复跑全绿）
```

**判据强度（反证）**——后端 4 条注入（读数 `probe-07-guard-strength.txt`）：

```
注入 A: 出处比对绕过（编造放行）            → RED ｜ 复原 sha256 相等 ✓
注入 B: 字段白名单放宽                      → RED ｜ 复原 sha256 相等 ✓
注入 C: 数值区间放开（7 位地址守卫短路）    → RED ｜ 复原 sha256 相等 ✓
注入 D: import 面破戒（生成侧模块混进草稿） → RED ｜ 复原 sha256 相等 ✓
复原后复跑：四条全 PASS（回绿）；收尾指纹逐字节未变 ✓
```

前端 1 条注入（读数 `probe-07-guard-strength-front.txt`）：知情文案改含糊 →
门禁红 3 条，首条红即「资料入口明说…」；逐字节复原 ✓。

### 实施时定的口径

1. **反编造 = 出处片段的机械比对**："绝不编造"不能靠提示词自觉——域层把每条
   出处归一（去空白 + 小写）后比对资料原文，不在原文 = 编造（域拒绝，带理由重问
   一次）。改写 / 概括 / 从别处补充都会被拒，宁可重问也不采信。
2. **两类拒绝分道照 triage 先例**：形状 / 区间 / 词表问题 = 解析类快重试；出处
   编造 = 本地域判决（`ERROR_KIND_DOMAIN`，重问消息带上被拒字段与理由）。两条
   LLM 层用例把分道钉住。
3. **草稿只覆盖找到了的字段**：用户先填了半截再抽草稿，没找到的字段**不清掉**
   他已填的；id 是用户的决定（已填不覆盖），没填才从名称派生建议。编辑已有
   器件时草稿**拒绝填入**（编辑态保存按 id 幂等覆盖——冲掉原事实是数据损失）。
4. **浏览器用例刻意零 LLM**：浏览器夹具继承真机配置，真点"抽取"就是真调 LLM——
   所以浏览器只验入口渲染 + 知情文案 + 本地提示，抽取 / 填表 / 降级三路由端点
   与 fx 用例钉住（本支 spec「检测生成零 LLM，不花额度」的既有纪律延续）。

### code-review 两轴结论与整改

**Standards 轴**（0 红 2 黄 → 全修）：

1. `PROTOCOL_METHOD_NAMES` / `_call_all_protocol_methods` 漏新方法，且
   `draft_device_facts` 在 LLM 层零测试 → **已修**：方法名进覆盖清单与派发扫描
   （remote 集），补 2 条同款用例（域拒绝 kind + 带理由重问 / 形状错 parse kind）。
2. 前端 `DRAFT_FIELD_LABELS` 与服务端 `DRAFT_FIELDS` 无跨语言对账 → **已修**：
   读两份真源码逐字对账（失配 = 静默渲染成"没找到"的那类坏法，必须有守卫）。
   判断题：missing_text 前端兜底句改读载荷（文案单源回服务端）+ 照纪律过 esc
   （已改）；编辑态下面板"已填进表单"提示过期（cosmetic，`openMyDeviceForm`
   已清 `myDraftApplied`）；提示词内联词表 / 区间（漂移后果响亮 + 字段契约已有
   对账守卫，判为保留）。

**Spec 轴**（无破票面 / 无蔓延；1 缺失 + 1 轻缺失 → 全补）：

1. 票面点名的"无关文本"用例缺失 → **已补**（端点层：无关文本 + 缺省空草稿 →
   全字段 missing + "手册里没找到"）。
2. **反证读数缺失（spec「测试决策」硬要求）** → **本单补齐**（判断：不推给
   工单 10——10 的角色是汇总各单读数，07 拿不出自己的读数等于把欠账挪个地方；
   `probe-07-guard-strength.py` 4 条 + `.mjs` 1 条，见上）。
3. （轻）完全未配置路径无测试 → **已补**（400 中文指路；前端通用 catch 送进
   消息区，与降级路同一 UX）。

### 范围外 / 留给后面的工单

- **草稿归档进工程**（`custom_device/<id>/` 里的"抽取草稿"一份）= 工单 08。
- **AI 排障带自建件事实** = 工单 09。
- **未上板**：本单是抽取与表单预填，没有真机动作；照 spec 口径写"未上板"，不假装。
