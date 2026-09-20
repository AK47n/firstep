# 01 — 检测页装配回域（约 483 行从 webapp 搬进 hwcheck_board / hwcheck_recipe）

**要做什么：** 硬件检测页的装配（一次投影 / 配方装载 / 母版 syscfg 读取 / 小节载荷投影）整体
搬回它的域模块，接口从 `AppContext` 收成**显式路径 + 配置对象**；webapp 侧只剩「取配置 →
调域函数 → 组响应」。页面与端点行为零变化，但检测页装配从此可以不经 HTTP 直测，改检测页
也不再需要动 webapp.py。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

## 判据（搬运零变化的验收尺）

- **载荷逐字不变**：`board` 的**五个**顶层键（`wiring` / `sections` / `console` /
  `unspecialized` / `exclusive_groups`）与各端点响应形状不变（前端零改动是它的机器判据）。
  **更正（实施时核出）**：本单原先按 webapp 旧 docstring 写成"六个键（… / `pin_fixes`）"——
  那是**过期口径**，代码从来只有五个顶层键，「动了哪几根线」住在 `wiring.pin_fixes` 里
  （前端读的也是 `static/js/ui/hwcheck.js` 的 `wiring.pin_fixes`）。搬运逐字照抄了代码，
  没有照抄那句错的 docstring（新 `HwCheckView` docstring 已按五键写）。
- **错误时机不变**：`_hwcheck_library_config` 的 400（「还没配置模块库 / 母版库目录…」）在
  各端点里的触发位置与从前一致（含**同一请求里两个 400 的先后**——回读端点按从前的求值顺序
  拼载荷：`main.c` / 清单先读 → 取配置 + 装配 → 检测记录最后）；坏配方 / 库外 slug / 装不下
  （`require_pins=True`）三处大声失败照旧，且回读端点照旧只投影不判装不装得下。
- **判据零改动**：`tests/test_hwcheck*.py` 既有用例全绿，且**不需要改任何断言**——需要改就
  说明搬错了语义，回头改实现。

## 计划

1. `hwcheck_board.py` 收下检测页一次投影与它的输入：
   - `HwCheckView`（frozen dataclass）：`board`（**五键**载荷）/ `sections`（`tuple[RecipeSection,
     ...]`）/ `generic`（`tuple[GenericSection, ...]`）/ `pin_bindings`（`dict[str, str]`）/
     `known_slugs`（`tuple[str, ...]`）。
   - `hwcheck_view(config, *, module_library_dir, masters_dir, recipe_path=None,
     require_pins=True) -> HwCheckView`：读库一次 → 展开依赖 → 配方装载 → 引脚消解
     （`hwcheck_pin_plan`）→ 板侧投影 → 小节解析 → 通用降级 → 命令台 → 互斥组。
   - 母版 `mspm0.syscfg` 全文读取（原 `_hwcheck_master_syscfg`）：读不到 / 平台不对 = `None`
     （「判不了就不判」语义不变）。
2. `hwcheck_recipe.py` 收下配方装载与小节载荷：
   - `load_library_recipes(module_library_dir, masters_dir, manifests, *, recipe_path=None)`：
     按平台装配接口清单（母版工程树不在的平台跳过校验的既有判据逐字保留）+ `platform_header_
     names` → `load_recipes`。
   - 小节载荷投影（原 `_hwcheck_sections_payload`）：字段与 `SECTION_TAG` 逐字不变。
3. `webapp.py`：
   - 删四个私有 helper 与它们专用的 import（`SECTION_TAG` / `interface_names` / `load_recipes`
     / `platform_header_names` / `resolve_sections` / `build_console_table` / `console_payload`
     / `generic_message` / `resolve_generic_sections` / `hwcheck_board_view` / `hwcheck_pin_plan`
     / `iter_project_files` / `MSPM0_SYSCFG_FILENAME`——以实际用尽为准，逐个核对）。
   - 四个端点（preview / generate / project / triage）改为：自己调 `_hwcheck_library_config
     (context)` 拿 AppConfig → 直调 `hwcheck_view(...)` → 用属性访问取 `view.board` /
     `view.sections` / `view.generic` / `view.pin_bindings` / `view.known_slugs`。
   - `_hwcheck_library_config` / `_hwcheck_devices` / `_hwcheck_record_dir` **留在 webapp**
     （它们分别是「AppContext → 配置」的翻译、payload 取参、记录落点判据）。
4. 结构钉：webapp 的 hwcheck 族 import 面收敛（上面那批域原语不再被 webapp 直接 import）。
5. `CONTEXT.md`「硬件检测」行的「主要实现」列对齐（检测页一次投影归 `hwcheck_board`）。

## 验收标准

- [x] `hwcheck_view` / `HwCheckView` / 母版 syscfg 读取（`read_master_syscfg`）落
      `hwcheck_board.py`；配方装载（`load_library_recipes`）与小节载荷（`sections_payload`）
      落 `hwcheck_recipe.py`；**`hwcheck.py` 零改动**（纯函数、不碰盘的边界不动）
- [x] 域层签名不吃 `AppContext`（显式 `module_library_dir` / `masters_dir` / `recipe_path` /
      `require_pins`）；`AppContext.hwcheck_recipe_path` 的测试注入面经 `recipe_path` 保留
- [x] 四个端点自己取 AppConfig 后直调域函数（webapp 里**不留** ctx 版适配层）；
      `_hwcheck_library_config` 的 400 文案与触发位置不变；`board` **五键**与响应形状逐字不变
      （六键是工单原来的过期口径，见判据一节「更正」）
- [x] 新直测缝（不经 HTTP，真库 + 真母版）：`HwCheckView` 五字段 / `board` 五键齐全 /
      `require_pins=False` 不因装不下 400 / 坏配方仍 400 / **库外 slug 仍 400**
- [x] 结构钉：webapp 的 hwcheck 族 import 面收敛（11 条装配原语退场，见 Comments）
- [x] `tests/test_hwcheck*.py` 全绿（363 = 基线 354 + 新增 9）且**既有判据零改动**
      （`git diff HEAD -- tests/` 的删除行只有 4 行注释里的旧符号名）；全量
      `python -m pytest -n auto` 全绿
- [x] 前端产品代码零改动（`node --test "tests/js/*.test.mjs"` 全绿 1686）；`tests/js` 只改了一处
      注释里的旧符号名（记在 Comments）
- [x] `CONTEXT.md` 对齐（检测页一次投影归 `hwcheck_board`）；`docs/agents/local-environment.md`
      无需补记（本单**一次服务器都没起**：验证全走进程内 TestClient + pytest + node）

## Comments

### 2026-09-20 实施记录（Status: resolved）

**文件边界**

- `src/contest_generator/hwcheck_board.py`：新增 `HwCheckView`（frozen dataclass：
  `board` / `sections` / `generic` / `pin_bindings` / `known_slugs`）、`hwcheck_view`（路径 +
  配置进、一次投影出）、`read_master_syscfg`（原 `_hwcheck_master_syscfg`，**不进 `__all__`**：
  只有本模块用，评审判为投机面）。模块 docstring 补一节说明装配归位。
- `src/contest_generator/hwcheck_recipe.py`：新增 `load_library_recipes`（按平台装配接口清单
  → `load_recipes`）与 `sections_payload`（小节载荷投影）。两者都进 `__all__`——
  `sections_payload` 是跨模块缝（`hwcheck_board` 导入它），不是投机面。
- `src/contest_generator/webapp.py`：删 4 个私有 helper（`_hwcheck_recipes` /
  `_hwcheck_master_syscfg` / `_hwcheck_view` / `_hwcheck_sections_payload`，约 483 行）与它们
  专用的 11 条 import；四端点改为「取参 → `_hwcheck_library_config(context)` → 直调
  `hwcheck_view(...)` → 属性访问」。`_hwcheck_library_config` / `_hwcheck_devices` /
  `_hwcheck_record_dir` 留在 webapp（翻译 / 取参 / 落点判据）。
- `CONTEXT.md`：硬件检测行的「主要实现」列对齐。
- 新测试：`tests/test_hwcheck_board.py`（直测缝 4 条）、`tests/test_hwcheck_assembly_home.py`
  （**新文件**：import 面结构钉 + 合成片段红证，一条不变量一个文件，照
  `test_download_sequence_home.py` 先例）、`tests/test_hwcheck.py`（端点载荷 = 域投影 1 条、
  四端点共用缺库 400 1 条、回读求值顺序 1 条）。

**逐字保留的判据**（搬运没动语义）：配方校验「母版工程树不在的平台跳过」/「按平台分开装配
接口清单」、`require_pins` 三态、装不下时的 `HWCHECK_PIN_EXIT_MARKER` 出路文案、
`board` 五键与 `wiring.pin_fixes` 的嵌套位置、库外 slug 的 `UnknownModuleError`。

**双轴评审（固定点 HEAD 6fc01208）与处置**

- Standards 轴（`.scratch/webapp-consolidation/standards-review-01.md`）：**无硬违规**。两条
  判断题当场修——① 结构钉错位（webapp import 白名单长在板侧用例文件里）→ 拆出
  `test_hwcheck_assembly_home.py`；② 新用例手抄库根路径绕过刚收出的缝 → 改用
  `ctx.config.module_library_dir` / `masters_dir`。另修：`read_master_syscfg` 退出 `__all__`；
  判据函数改名并去掉「限定串反解两次」（`_hwcheck_imports` 返回 `(模块, 名字)` 对）。
  未修（记录理由）：`hwcheck_view` 的 Feature Envy 是工单指定的落点；`read_master_syscfg`
  吞 `OSError` 与母版头读取上抛的两种失败策略是**搬运前就有的**（各有注释：引脚判据
  「判不了就不判」，配方校验不该降级）。
- Spec 轴（`.scratch/webapp-consolidation/spec-review-01.md`）：搬运主体忠实（无 ctx 适配层、
  `hwcheck.py` 零改动、既有判据零改动）。三条处置：
  ① 缺「库外 slug 仍 400」的新缝直测 → 补 `test_hwcheck_view_rejects_a_slug_outside_the_library`；
  ② 工单/读数「board 六键」口径过期 → 已按实现更正为五键（并在本单判据一节写明更正）；
  ③ 回读端点求值顺序 → 实测核对：`hwcheck_view` 一度被提到 `read_project_main_c` **之前**，
  已改回**从前的顺序**（main.c / 清单 → 取配置 + 装配 → 记录），并加一条能分辨的用例
  `test_project_endpoint_reads_main_c_before_taking_the_library_config`（桩让 main.c 先抛：
  顺序错则报「还没配置模块库」→ 实测**变红**，改回即绿）。评审推断的「坏记录 + 未配库时报
  记录那句」经核对**不成立**：取配置在两种顺序里都早于读记录（已在用例 docstring 里写明）。
  另一条「`test_preview_payload_equals_the_domain_projection` 子集断言弱于判据」→ 已收紧为
  键集合全等。

**范围蔓延（如实记账）**：`tests/js/hwcheck.test.mjs` 改了一处注释里的旧符号名
（`_hwcheck_view` → `hwcheck_board.hwcheck_view`）——注释不是产品代码，但确实动了
`tests/js` 文件；不视为「前端零改动」的违反（产品 `static/` 零改动，前端门禁 1686 全绿）。

**验证读数**：`.scratch/webapp-consolidation/verify-01-homing.txt`（含红证原始输出
`verify-01-pin-red-proof.txt`：HEAD 版源码喂同一判据 → 11 条泄漏，工作树 → 0 条）。
