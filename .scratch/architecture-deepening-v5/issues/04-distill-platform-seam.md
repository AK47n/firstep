# 04 — 架构深化 v5：蒸馏侧平台适配接缝——平台分派双机制合一（候选 4）

**What to build:** 第五轮架构深化（2026-08-09 grilling 共识，候选 4，源自 architecture-review-20260809-102431）。生成侧有 patchers registry 接缝，蒸馏侧没有：master.py 内联 stm32 if/else（`_config_preview` :492 / `apply_distillation` :573 / `_config_summary` :812 / `_detect_platform` :800 四处分派）+ 直连 keil（4 名：KeilProjectError / build_master_uvprojx / extract_config_summary / render_master_uvprojx）与 ccs（2 名）；mspm0 = "keil 减一切"（无渲染 / 无结构校验 / 无密度守卫 / 预览恒空串）；密度守卫从蒸馏缝逃逸成 KeilProjectError（distill_master docstring 承诺 MasterError，test_startup_dedup_without_md_guard_fires_at_distill 坐实）；工程配置文件识别知识五处拷贝；启动去重规则通用声明、实现只认 stm32 文件名（keil.is_startup_candidate 的 stm32 正则）。本轮收口：**蒸馏侧平台行为全过一条适配器接缝（distill_adapters.py，摘要读 / 渲染 / 启动候选谓词 per platform），守卫错误翻译在缝内归 MasterError，识别知识单源 = platforms.py**。行为零变化（报告形状 / 预览空串 / 去重语义逐字节不变）。

1. **新建 `src/contest_generator/distill_adapters.py`**（蒸馏侧平台适配器，薄壳——格式知识仍归 keil.py / ccs.py）：
   - `DistillAdapter` Protocol：`renders_config: bool` + `config_summary(project_dir) -> tuple[str, ...]` + `render_config(kept_paths, startup_path, include_dirs) -> str` + `write_config(output_dir, kept_paths, startup_path, include_dirs) -> Path | None` + `is_startup_candidate(rel_path) -> bool` + `is_md_startup(rel_path) -> bool`；
   - `KeilDistillAdapter`（stm32）：config_summary = 委托 `extract_config_summary` 并 catch KeilProjectError → 返回软失败行（`(f"{PLATFORM_STM32} 工程配置读取失败：{exc}",)`，现 master.py:812-824 的 catch 逻辑逐字下移）；render_config = 委托 `build_master_uvprojx`，**try/except KeilProjectError → raise MasterError(str(exc)) from exc**（密度守卫翻译：message 原样，HTTP 层 MasterError 同映射 400）；write_config = 委托 `render_master_uvprojx` 同款包装；is_startup_candidate / is_md_startup = 委托 keil；renders_config = True；
   - `CcsDistillAdapter`（mspm0，显式无操作）：config_summary = 委托 `extract_ccs_config_summary` + catch CcsProjectError 同款软失败行；render_config = 恒 `""`（无现写，判例 09 保留首份）；write_config = 显式无操作（返回 None，docstring 写明"renders_config=False，apply 永不调用"）；is_startup_candidate / is_md_startup = 恒 False（docstring：mspm0 母版无 .s 启动文件，TI/CCS 启动为 .c，不在基础设施词表）；renders_config = False；
   - `get_distill_adapter(platform) -> DistillAdapter`：模块级 dict 分派（{PLATFORM_STM32: KeilDistillAdapter(), PLATFORM_MSPM0: CcsDistillAdapter()}），未知平台抛 MasterError（文案照 master_store._validate_known_platform）；
   - import：keil / ccs / platforms / master_store（MasterError）。**不 import patchers**（生成侧 registry 零改动）。
2. **识别知识单源 = platforms.py**（词表层，谁都能 import 无循环）：新增 `PLATFORM_CONFIG_FILE_SUFFIXES = {PLATFORM_STM32: (".uvprojx",), PLATFORM_MSPM0: (".cproject", ".project")}`（逐字迁移 master_store.py:43 的表 + docstring）；master_store 删 `PLATFORM_CONFIG_FILES`（:43-46）与 docstring :14 的提及，analyze_structure :116 改消费 platforms 表（master_store 已 import platforms，无新 import）；**categories.py:167 的死常量 `CONFIG_FILE_SUFFIXES` 删除**（全库无消费方，grep 坐实；config_file_reason 的 endswith 判定是分类知识——后缀 → 规则原因映射，保留）。keil._find_uvprojx / ccs._find_cproject 的 glob 是各自格式知识（非平台识别表拷贝，文档边界）。
3. **master.py 收口**（蒸馏侧不再直连 keil/ccs）：
   - import：删 keil 四名 + ccs 两名 + platforms 两常量（PLATFORM_MSPM0/PLATFORM_STM32）；加 `from .distill_adapters import get_distill_adapter`、platforms 改 import `KNOWN_PLATFORMS, PLATFORM_CONFIG_FILE_SUFFIXES`；
   - `_detect_platform`（:800）：硬编码 glob 改遍历 `KNOWN_PLATFORMS × PLATFORM_CONFIG_FILE_SUFFIXES`（`_find_config_files` 用法不变，两种错误文案逐字不变）；
   - `_config_summary`（:812）：函数体 = `return get_distill_adapter(platform).config_summary(project_dir)`，软失败语义在适配器内（catch 逻辑下移，行为零变化）；
   - `_config_preview`（:492）：`if platform != PLATFORM_STM32: return ""` 分支删除 → `return get_distill_adapter(platform).render_config(*_render_inputs(platform, decisions, comparison))`（mspm0 恒空串来自适配器显式无操作）；`_render_inputs`（:469）增 platform 参数（透传给 _pick_startup），三个调用点（:500 / :576 / :766）同步；
   - `apply_distillation`（:573）：`if report.platform == PLATFORM_STM32: render_master_uvprojx(...)` 改 `adapter = get_distill_adapter(report.platform); if adapter.renders_config: adapter.write_config(output_dir, *_render_inputs(report.platform, ...))`；else 分支（保留首份复制循环）原样 + docstring 注明"非渲染平台保留首份原样（判例 09）——复制是编排层通用操作，非平台能力"；
   - `classify(rel, path, platform)`（:188 调用点，platform 局部量已有 :179）；
   - `_pick_startup(comparison.startup_files, platform)`（:442 / :489 两处）。
4. **categories.py 启动谓词平台化**：删 keil import（:18）；加 `from .distill_adapters import get_distill_adapter`；`classify(rel, path, platform)`（签名增参，docstring 注明谓词按平台取）:278 改 `get_distill_adapter(platform).is_startup_candidate(rel)`；`_pick_startup(startup_files, platform)` :293 改 `get_distill_adapter(platform).is_md_startup(c)`；`_validate_startup_disposition(report, startup_files)` 签名不变（内部 :308 经 `report.platform` 取适配器）。依赖图：categories → distill_adapters → {keil, ccs, master_store, platforms}，无环。
5. **master_store 边界（诚实的缝外）**：analyze_structure 的 `validate_project_structure` 直连 keil 保留一行（master_store.py:38，加注释："入库结构校验是母版库域操作（存储域），不走蒸馏编排接缝"——其唯一生产消费方就是入库；适配器不设 validate 能力，避免死方法）。errors.py 零改动（MasterError 仍在 master_store，KeilProjectError 表项保留——生成侧 KeilPatcher 仍抛）。
6. **测试**：test_categories.py:495-507 断言 `KeilProjectError` 翻成 `MasterError`（match="STM32F103C8T6" 不变，文案逐字保留）；新增结构测试（防回退，先例 errors.py）：master 模块无 `KeilProjectError / CcsProjectError / build_master_uvprojx / render_master_uvprojx / extract_config_summary / PLATFORM_STM32 / PLATFORM_MSPM0` 属性；categories 无 `is_startup_candidate / is_md_startup / CONFIG_FILE_SUFFIXES` 属性；master_store 无 `PLATFORM_CONFIG_FILES` 属性；distill_adapters 无 `PatcherRegistry` 属性（不碰生成侧）；行为测试：mspm0 适配器 `renders_config is False`、`render_config(...) == ""`、`is_startup_candidate("startup_mspm0g3507.s") is False`（显式无操作 pin）；守卫翻译单测：KeilDistillAdapter.render_config 非 md 启动 → MasterError（非 KeilProjectError）。
7. **CONTEXT.md 词表更新**（同批提交）：「平台」主要实现列补"识别知识（工程配置文件后缀表）= platforms.PLATFORM_CONFIG_FILE_SUFFIXES 单源；蒸馏侧平台行为经 distill_adapters 适配器（master 只消费）"；「启动文件」主要实现列补"谓词（is_startup_candidate / is_md_startup）经蒸馏适配器按平台取，mspm0 显式 False"；「工程配置文件」主要实现列补"渲染与预览经蒸馏适配器（守卫翻译归 MasterError）"；「架构要点」新增 bullet：蒸馏侧平台适配接缝 = distill_adapters（摘要读 / 渲染（含密度守卫翻译）/ 启动候选谓词 per platform；mspm0 显式无操作；母版库入库结构校验留在 master_store，存储域边界）。

**明确不动的（边界，勿越）**：行为零变化（报告形状 / 预览空串 / 去重语义 / 错误文案逐字不变，既有断言原样过）；keil.py / ccs.py 格式知识零改动（密度守卫仍住 build_master_uvprojx，只在外层翻译）；errors.py 映射表零改动（MasterError 不动窝，KeilProjectError 表项保留）；patchers.py registry 零改动；generator.py:19 的 include 读缝（registry 不是读侧接缝、mspm0 门禁空基座）**留待下轮候选**——本工单不碰生成侧；master_store 的结构校验直连保留（见 5 节）；不引入新配置项；webapp 路由零改动；CONFIG_FILE_SUFFIXES 删除前先 grep 坐实无消费方（已坐实：仅定义处）。

**Status:** resolved（2026-08-09 同批 PR 勾选，815 绿 + mypy 干净）

## 验收

- [x] 全量 pytest 绿（基线 804 → 815，+11：适配器行为 / 结构测试 / 守卫断言）+ mypy 干净；蒸馏 / 去重 / 预览既有断言原样过（行为零变化）
- [x] `grep -rn "KeilProjectError\|CcsProjectError\|build_master_uvprojx\|render_master_uvprojx\|extract_config_summary\|PLATFORM_STM32\|PLATFORM_MSPM0" src/contest_generator/master.py src/contest_generator/categories.py` 无结果（master/categories 不再直连 keil/ccs，也不再用平台常量分派）
- [x] `grep -rn "PLATFORM_CONFIG_FILES\|CONFIG_FILE_SUFFIXES" src`：PLATFORM_CONFIG_FILES 与裸 CONFIG_FILE_SUFFIXES 零命中；仅剩 PLATFORM_CONFIG_FILE_SUFFIXES 单源表（platforms.py 定义 + master/master_store 消费）
- [x] categories.py 谓词 grep 仅命中两处适配器方法调用（`get_distill_adapter(platform).is_startup_candidate/md`，工单 4 节逐字实现——谓词确实经适配器）+ docstring；模块级无谓词属性（结构测试 `not hasattr` 兜底）；`def classify(rel, path, platform)` 签名带 platform；test_categories.py 无 KeilProjectError 引用（守卫翻 MasterError，match="STM32F103C8T6" 文案逐字保留）
- [x] 结构测试过（工单 6 节清单全绿：master/categories/master_store/distill_adapters 四模块）；mspm0 显式无操作行为测试过（renders_config is False / render_config 恒 "" / 谓词恒 False）
- [x] CONTEXT.md 四处更新到位（平台 / 启动文件 / 工程配置文件实现列 + 架构要点新 bullet）

## 实施提示词（新会话用）

```
工单：.scratch/architecture-deepening-v5/issues/04-distill-platform-seam.md（架构深化 v5：蒸馏侧平台适配接缝，候选 4）

先读工单全文，按 1-7 节执行。独立 worktree（勿在主检出改，必须 -b 形式）：
git worktree add -b v5-04-distill-seam ../firstep-v5-04 main

1. 新建 distill_adapters.py（工单 1 节）：Protocol + Keil/Ccs 两个适配器 + get_distill_adapter；守卫翻译 try/except → MasterError（message 原样）；mspm0 显式无操作（renders_config=False / render_config 恒 "" / 谓词恒 False）
2. platforms.py 加 PLATFORM_CONFIG_FILE_SUFFIXES；master_store 删 PLATFORM_CONFIG_FILES 改消费 platforms（docstring 同步）；categories 删死常量 CONFIG_FILE_SUFFIXES（先 grep 坐实无消费方）
3. master.py 收口（工单 3 节）：删 keil/ccs import 与平台常量；_detect_platform 遍历词表；_config_summary/_config_preview 过适配器；_render_inputs 增 platform 参数（三调用点同步）；apply_distillation 改 renders_config 分派；classify/_pick_startup 调用传 platform
4. categories.py 平台化（工单 4 节）：谓词经适配器；classify/_pick_startup 增 platform 参数；_validate_startup_disposition 经 report.platform 不改签名
5. master_store 直连 keil 保留一行 + 边界注释（工单 5 节）
6. 测试（工单 6 节）：test_categories 守卫断言 KeilProjectError → MasterError；新增结构测试清单；mspm0 显式无操作行为测试
7. CONTEXT.md 按工单 7 节更新
8. 全量 pytest 绿 + mypy 干净 + 验收全勾后提交（refactor 一条 + docs 一条，风格照仓库）→ PR base 指 main

注意：编辑前先确认 cwd 在 worktree；勿串行做别的工单。
```

## Comments

（2026-08-09 立项，grilling 共识：候选 4 蒸馏侧平台适配接缝。用户看不懂技术树、委托按"最需要"选型，逐项复核后定稿。D1 接缝形态：新模块 distill_adapters.py 薄壳 + 简单 dict 分派，格式知识仍归 keil/ccs——否决"MasterError 移籍 errors.py 全闭环"（破坏仓库"错误随域模块住"先例：KeilProjectError 住 keil.py / TopicError 住赛题库；结构校验的唯一生产消费方是母版库入库，那是存储域操作不是蒸馏编排，过缝只剩延迟导入补丁）与"适配器抛平台错误"（就是今日摩擦的换址重演）；循环约束事实：master → master_store → keil，适配器抛 MasterError 则 master_store 不能模块级 import 适配器。D2 错误契约：翻译在适配器方法内，message 原样；_config_summary 软失败语义下移保留。D3 mspm0 显式无操作：摘要真实现、渲染恒空串、谓词恒 False；"补齐启动候选正则"否决（仓库无 .s 启动样本，TI/CCS 启动是 .c，编正则 = 猜测死代码）。D4 识别知识单源 = platforms.py（词表层谁都能 import 无循环）；五拷贝收敛为：表单址 + keil/ccs finder glob 是格式知识 + categories 分类器是分类知识（死常量 CONFIG_FILE_SUFFIXES 顺手删除，grep 坐实无消费方）。D5 启动去重平台化：谓词经适配器，classify/_pick_startup 增 platform 参数，_validate_startup_disposition 不改签名（经 report.platform）。D6 边界：generator.py:19 include 读缝（registry 不是读侧接缝、mspm0 门禁空基座）留待下轮候选，工单明示不动。报告：architecture-review-20260809-102431.html。）
