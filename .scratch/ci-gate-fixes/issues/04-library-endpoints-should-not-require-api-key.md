# 04 — 库相关的只读端点不该被「先配 API」那道闸挡住

**要做什么：** 没配 API key 的时候，**库本身**（模块库 / 母版库 / 赛题库 / 参考文件库的浏览与读取）
仍应可用——用户拿到工具第一件想做的事是"看看里面有什么模块"，而不是先被要求填 key。
AI 相关的端点照旧中文拒绝。

**被谁阻塞：** 无（`ci-gate-fixes/01` 已把"库在哪"这件事修好，本单只动那道闸的射程）。

**状态：** resolved

- [x] 盘清 `_require_config` 的 46 处调用点，**逐个分成两类**：真的需要 AI（推荐 / 生成 / 蒸馏 /
      修订 / 参数 / 排障……）与其实只需要"库在哪"（模块库读写列表、母版库、赛题库、参考库、
      PDF / Markdown 资料库、代码查看器……）。分类要写进工单 Comments 当判据，不能只改代码
      ——**实测是 49 处调用**（不是 46，量具与两张表见下）
- [x] 只把后一类改成用"库目录解析"（`_library_dir(ctx)` / 新抽一个 `_require_library_dir(ctx)`），
      **不动前一类**——AI 端点仍是"没 key 就 400 中文"
- [x] 引导态（`install.bat` 写的那份：库路径齐全 + key 空串）与"随包库回退"两种来源走**同一条路**
- [x] `tests/test_config.py::test_app_context_resolves_default_path_at_construction` 里那条
      **钉住现状**的断言（`/api/modules` == 400）必须跟着改——它红了就是本单落地的信号
- [x] 逐端点补一条"未配 key 也能读"的用例（至少：`/api/modules` 列表 + 单文件、`/api/masters`、
      `/api/topics`、`/api/references`），并保留一条"AI 端点未配 key 仍 400"的用例防反向
- [x] 前端确认：设置页/首页在"未配置"态下不再因为库端点 400 而空窗（必要时只需文案，不必改结构）
- [x] 中文提交

## Comments

### 立项事实（2026-09-25，量自 `ci-gate-fixes/01` 的现场）

空 key（无配置文件、随包库在场）时四个库端点的实测读数：

| 端点 | 现在 |
|---|---|
| `/api/modules` | **400** 未配置 AI API |
| `/api/masters` | **400** 未配置 AI API |
| `/api/topics` | **400** 未配置 AI API |
| `/api/references` | **400** 未配置 AI API |
| `/api/settings` | 200（报的是随包库路径） |
| `/api/env/status` | 200（`api_configured=False`） |

即：**库的位置已经知道，但浏览不了**。这是既有行为（不是 `ci-gate-fixes/01` 引入的），
射程 = `webapp.py` 里 46 处 `_require_config(context)`。本单价值在于让"从干净检出起服务"
这件事真的**有得看**，而不只是"位置对了"。

### 盘点（量具 `.scratch/ci-gate-fixes/survey-04-require-config.py`，只读、可复跑）

**计数更正：立项时写 46 处，实测 `_require_config` 一共 49 处调用**（另有 1 处定义），
落在 48 个函数里（`skeleton` 一处函数两处调用）。量具输出三张表：调用点归属表、
端点闸门来源矩阵、**调用图传递闭包**（谁经由辅助函数也能走到 LLM）。

**分类就是代码里那把尺子**：`_require_config` = AI 闸（看 `api_key`）；
`_library_config` / `_library_dir` / `_masters_dir` = 库闸（只看"库在哪"）。

**A. 真需要 AI —— 22 处调用，一个字没动**

| 处（函数） | 为什么真需要 AI |
|---|---|
| `_llm` | LLM 工厂本身：所有 AI 端点的必经口，闸门就在这 |
| `_assemble_topic_context` | 题面装配（粘贴题面要 LLM 识别编号） |
| `extract`、`topics_split` | 上传件的视觉图注 / 拆条（视觉与拆条主路径要模型） |
| `recommend`、`skeleton`(×2)、`generate` | 推荐 / 骨架 / 生成 |
| `revise_analyze`、`revise_apply`、`revise_deepen` | 修订影响分析 / 套用 / 深化 |
| `tasks_plan`、`tasks_execute`、`tasks_params_scan`、`tasks_params_apply`、`params_chat_send`、`tasks_discuss`、`tasks_idea_chat_send`、`tasks_idea_analyze`、`tasks_idea_fix` | 任务推进 / 参数 / 想法对话（全部派发模型） |
| `fix_errors` | 编译错误修复 |
| `masters_confirm` | 蒸馏确认（归档动作要 LLM 判定；判断见下） |

**B. 只需要「库在哪」—— 27 处调用，本单改成库闸**

| 处（函数） | 它真正要的 |
|---|---|
| `_library_dir`、`_masters_dir` | 两个访问器本身（改成库闸后，下面 C 那 32 个端点一起放行） |
| `_desktop_topic_title` | 读赛题库拿目录标题（调用方 `generate_preview_dir` 是"纯静态计算、不调用 LLM"的预览端点） |
| `revise_context` | 加载生成上下文：读盘 + 库内 slug 校验 |
| `revise_rollback`、`fix_errors_rollback`、`tasks_rollback_iteration` | 回滚 = 从备份目录恢复文件 + 改清单状态 |
| `references`、`reference_add`、`reference_delete`、`reference_update`、`reference_files`、`reference_file` | 参考文件库读写 |
| `pdfs`、`pdf_pages_count`、`pdf_trash`、`pdf_refs`、`pdf_file` | PDF 资料库 |
| `materials_md`、`materials_md_file`、`materials_md_asset` | Markdown 资料库 |
| `topics`、`topics_confirm`、`topic_update`、`topic_get`、`topic_pages_get`、`topic_delete` | 赛题库浏览 / 入库 / 编辑 / 取题面 / 页图 / 删除 |

22 + 27 = 49 ✓。改完复跑量具：**只剩 22 处调用，全在 A 表里**（判据：数出来的行数 = 表 A 行数）。

**C. 两张表之外的 32 个端点**：它们本来就走 `_library_dir` / `_masters_dir` 取库路径
（`/api/bindings/validate|matrix|auto`、`/api/selection/expand`、模块库 CRUD 八件、
母版库六件、`/api/update/materials/*`……）。改的是那两个访问器，所以它们**一起**从
"没 key 就 400"变成"库在哪就能读"。**其中 `/api/bindings/matrix` 正是 CI 夹具当初撞见
400 的那个端点哨兵**（spec「实测读数」表里的后端日志）。

### 安全边界：为什么改访问器不会给 AI 端点开口子

- **求值顺序**：既碰库又派发模型的端点，都在碰库**之前**先取 LLM——`module_add` 的
  `_llm(context)` 是 `add_module(...)` 的第一个实参、`module_description` 同理（`_llm` 是
  `update_module_description` 的第一个实参），所以缺 key 时仍然先 400，不会"先写库再报错"。
- **传递闭包查过**：有 9 个端点派发 LLM 却没有直接 `_require_config`
  （`topic_preread` / `my_devices_draft` / `hwcheck_triage` / `buy_discuss` / `module_add` /
  `module_description` / `masters_distill` / `reference_draft` / `topics_extract_number`）——
  它们的闸门在 `_llm` / `LLMRun().llm()` 上，**本单没动那条路**。
- **反向用例兜住**：`tests/test_library_gate.py::test_bootstrap_state_still_rejects_ai_endpoints`
  在同一个引导态客户端上打四发 AI 端点，四发都必须 400 且带「未配置 AI API」。

### 几处判断（写下来便于复核）

| 处 | 归类 | 理由 |
|---|---|---|
| `masters_confirm` | **留 AI** | 它的 docstring 自己写着「无归档动作的确认不要求 AI 配置（与现状一致）」，而代码是无条件 `_require_config`——**两者本就不一致**。放行会把 400 从"动手前"挪到"归档那一步"（事务语义要重新论证），不属于"库闸门射程"。**已另立单 `issues/06`**（评审提醒本单 Comments 承诺过"另立单"，这句现在是兑现的） |
| `extract`、`topics_split` | **留 AI** | 视觉图注 / 拆条都能降级，但主路径确实要模型；不属于"只需要库在哪" |
| `topic_get` | 改库 | 视觉补图注本来就是"失败降级返回原题面"的增强；放行后它拿到的是 key 空串的配置 ⇒ `vision_configured("") == False` ⇒ 不补注、返回原题面（与它 docstring 的「未配置 = 与现状逐字节一致」一致） |
| `revise_context` + 三个回滚端点 | 改库 | 只读盘 / 只恢复备份，一个模型都不派发 |

### 设计：判据单源（命名与工单建议略有出入，理由在此）

工单建议"`_library_dir(ctx)` / 新抽一个 `_require_library_dir(ctx)`"。实际落成三个函数，
因为**闸门的判据是"整份配置里库在哪"，而不只是模块库目录那一个字段**：

- `_resolve_library_config(ctx) -> AppConfig | None`：**「库在哪」的唯一解析处**，
  两级——① `_current_config`（含 `load_config` 的"配置文件不在 + 随包库在场"回退）；
  ② `_bootstrap_library_config`（引导态：配置在、key 空串 → 现造一份只有库路径的
  `AppConfig`，与 `load_config` 回退造的是同一种东西）。定不出来 = `None`。
- `_library_config(ctx)` = 上面那个 + "定不出来就 400 中文"（文案单源
  `_LIBRARY_UNCONFIGURED`：**不再借 AI 那句**，否则用户被指去填一个与"看不见库"
  无关的 key）。`_library_dir(ctx)` / `_masters_dir(ctx)` 是它的两个薄访问器
  （`topic_get` 要的是整份 `AppConfig`——`vision_base_url` / `vision_detail_qa` 也在里面）。
- **三个调用方共用同一处解析、只在最后一步分道**：库端点与检测页定不出来 → 400 指路
  （各说各那句文案）；设置页 GET 不能 400（表单总得渲染出两栏）→ 兜底缺省位置显示。
  「引导态与随包库回退走同一条路」（验收标准③）由此成立。

> **评审整改（两轴评审，2026-09-25）**：
> ① **第三道库闸补口**——`_hwcheck_library_config`（检测页）原先只走 `_current_config`，
> 于是引导态下**同一台机器两套说法**：库端点 200、检测页 400，而它自己 docstring
> 就写着「硬件检测不需要 AI」。现已改走 `_resolve_library_config`（文案仍按检测页那处），
> 并补用例 `test_bootstrap_state_serves_the_hardware_check_page`（真库 + 引导态打
> `/api/hwcheck/preview`）。
> ② **`_library_config` 与设置页 GET 原先各写一遍两级控制流**（注释却自称"同一处"）
> → 抽出 `_resolve_library_config`，两份内联消失。
> ③ B 表漏列 `pdf_refs`（已补）；`tests/test_config.py` 那条"非空"护栏原先另打一发 GET、
> 400 时 `.json()` 的 `{"detail": …}` 长度为 1 也能过 → 改成同一份响应读状态与非空。
> ④ 同类陈旧注释一并更正：`tests/test_module_intro.py`、`tests/test_module_i2c_probe.py`
> 里"裸 `create_app()` → `/api/modules` 400「未配置 AI API」"（保留历史，注明 04 起不再成立）。

### 射程澄清：库的**写侧**也在这道闸里（评审提问，答在此）

B 表含 `POST /api/references`、`DELETE /api/references/{id}`、`PUT /api/topics/{key}`、
`DELETE /api/topics/{key}`、`POST /api/pdfs/{p}/trash` 这些**破坏性**端点，比"看看里面
有什么模块"那句话宽。归它们进 B 类的依据有两条：

1. 工单 B 类的原话是「模块库**读写**列表、母版库、赛题库、参考库、PDF / Markdown 资料库」
   ——写侧本来就在射程内；
2. **`api_key` 从来不是这个工具的权限边界**：它是本机单人工具，key 只用于"能不能调模型"，
   没有任何鉴权语义。管理库（补录 / 编辑 / 删除 / 回收）要先把 AI key 填上，纯属两道
   判据共用一道闸的副作用——正是本单要拆掉的东西。

### 读数

**真机探针 `.scratch/ci-gate-fixes/probe-04-unconfigured-page.mjs`**（真后端 + 真 Chromium +
真静态资源；配置 = 引导态，库 = 检出内真库），同一支探针跑**改前 / 改后**两次
（改前那次把 HEAD 的 `webapp.py` 放进一份 `src` 副本里用 `PROBE_SRC` 指过去）：

| 判据 | 改前（`probe-04-before.txt`） | 改后（`probe-04-after.txt`） |
|---|---|---|
| `env/status` 报未配置 AI | ok（`api_configured=false`） | ok |
| `/api/recommend` 仍 400「未配置 AI API」 | ok | ok |
| `/api/modules` / `masters` / `topics` / `references` | **400 / 400 / 400 / 400** | **200 / 200 / 200 / 200** |
| `/api/modules` 条数 | 0 | **96** |
| 生成页模块池 | `共 0 个可用模块`（cells=1 = 空占位） | **cells=96 /「共 96 个可用模块」** |
| 模块库 tab 真数据格 | **0** | **480**（96 行 × 5 格） |
| 页面 JS 报错 | 0 | 0 |

**套件读数（本机 LF 检出，最终态）**：`python -m pytest -n auto -q` **5545 passed + 11 skipped**；
前端门禁 `node --test "tests/js/*.test.mjs"` **1796 passed / 0 fail**；
浏览器门禁 `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` **42 passed / 0 fail**
（读数留 `.scratch/ci-gate-fixes/browser-gate-04.txt`）。

**判据强度反证（`.scratch/ci-gate-fixes/probe-04-guard-strength.py`，读数同名 `.txt`）**：
三格注入都让对应用例变红、跑完 `webapp.py` **逐字节复原**（sha256 前后相同，`f8ccc3c8…`）——
① 库端点又挂回 `_require_config` → 分类注册表红；② `_library_dir` 又看 `api_key` →
访问器不变量红；③ 检测页那道闸退回只看"有没有配置" → 检测页引导态用例红。

**新增/改动的判据**：`tests/test_library_gate.py`（13 条：引导态放行四库 + 单文件 + 素材正文 +
板图/展开 + 检测页；AI 面反向 4 发；**库定不出来时 400 且文案不含「未配置 AI API」**；
key 空但没写库路径 = 不算来源；有配置的正方向；**两条结构判据**——`_require_config` 调用点
=frozen AI 表（两向都判）、库访问器不看 `api_key`）；
`tests/test_config.py::test_app_context_resolves_default_path_at_construction` 那条钉现状的断言
按工单要求翻面（`/api/modules` 400 → **200 + 非空**，四库各打一发）——它原来那段注释就写着
"它红了 = 那条产品决策落地了"。

### 前端：结构未动，改了三条**已经不成立**的注释

前端本来就把库端点 400 降级成空列表（`boot.js` 的 `catch { state.modules = [] }`），
所以没有"要不要改结构"的问题；放行后它拿到的是真清单，模块池/模块库 tab 自然不再空窗
（上表 96 / 480 就是它的读数）。三处注释按事实更正：
`static/js/boot.js`、`static/js/ui/settings.js`（都写着"未配置 AI API 时模块库读不到"），
以及夹具 `tests/browser/server.mjs` 里"假 key 是因为库端点也要它"那段理由
——现在那个假 key 保的是 **AI 面与前端"已配置"态**（`state.api_configured` 为真时页面
不显示未配置横幅、AI 按钮不置灰），不是库端点。

### 本轮发现的既有问题（不在本单射程，未开单）

1. **「尚未配置 AI API」横幅首屏不出现**：`#gen-banner` 只在 `ui/settings.js:534`
   （保存设置之后）被 toggle，首屏没人开它。探针两次读数都是 `isVisible=false`
   ——**改前改后一样**，与库闸门无关。用户在没配 key 的机器上冷启动，生成页不会主动
   提示这件事（设置页的环境体检与欢迎卡另有提示）。要不要治由维护者裁。
2. `masters_confirm` 的 docstring「无归档动作的确认不要求 AI 配置」与代码（无条件
   `_require_config`）不一致——**已开单 `issues/06`**（见上表「几处判断」）。
