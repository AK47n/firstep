# 01 — 平台事实归平台缝（外部头豁免三层拆分 + 配置后缀消费 + 语义正名）

**What to build:** 平台知识只在名义上单源——`PLATFORM_CONFIG_FILE_SUFFIXES` 只被 2 处消费（master._detect_platform / master_store.analyze_structure），`.uvprojx`/`.cproject`/`.project` 又硬编码在 categories 规则、master 报错文案、llm 提示词五处；工具链外部头豁免（stm32f10x_conf.h = DFP、ti_msp_dl_config.h = SysConfig）混在生成核心 `_EXTERNAL_HEADERS`（与 C 标准库头一锅），且门禁对跨平台头静默放行。本工单把工具链事实收进平台模块（keil/ccs 声明 + patchers 分派），确定性消费点改吃单源表；AI 提示词投影留候选 8。

**Blocked by:** 无

**Status:** resolved

## 需求

1. **外部头豁免分三层**：
   - `generator.py`：`_EXTERNAL_HEADERS` 拆为 `_LIBC_HEADERS`（28 个 C 标准库头，平台无关——两平台同名同集，注释说明）+ 门禁内 `_LIBC_HEADERS | patchers.external_headers(corpus.platform)`（并集在循环前算一次；语料已有 platform 字段（build_module_corpus 早已传入），**门禁签名零变化**）
   - `keil.py`：`EXTERNAL_HEADERS = frozenset({"stm32f10x_conf.h"})`（STM32F1xx DFP 提供，docstring 说明）
   - `ccs.py`：`EXTERNAL_HEADERS = frozenset({"ti_msp_dl_config.h"})`（SysConfig 构建时生成，docstring 说明）
   - `patchers.py`：`external_headers(platform)` 读侧分派（与 include_search_dirs 同文件先例；未知平台 UnknownPlatformError 文案同 registry.get——已登记 400）
2. **行为变化（刻意，修门禁洞）**：跨平台工具链头从静默放行变 `UnresolvedIncludeError`——stm32 工程 include `ti_msp_dl_config.h` / mspm0 工程 include `stm32f10x_conf.h` 现在落盘前拒绝（今天它们过门禁、编译必失败——门禁存在的意义就是抓这个；各平台豁免集合不再互相泄漏）
3. **categories.config_file_reason 消费单源**：`PLATFORM_CONFIG_FILE_SUFFIXES` → 后缀→原因映射（stm32 后缀 → `UVPROJX_CONFIG_REASON`，mspm0 → `CCS_CONFIG_REASON`），大小写不敏感保持，**行为逐字**
4. **master._detect_platform 报错文案从表推导**：两条文案（"工程同时含…无法判定平台" / "工程里没有…无法判定平台"）改由后缀表生成（"、"与"与"连接 helper，当前文本 = 全后缀列出，语义更准）；pinned 测试同步更新
5. **"Keil 语义"注释正名**：generator.py:518/562/594 三处注释描述的是 C 预处理器语义（两平台共用，ccs 读侧已对偶实现），改平台中性措辞，**零行为**
6. **边界不碰**：`keil._find_uvprojx` / `ccs._find_cproject` glob（platforms.py:15-16 已文档化 = 各自格式知识非识别表拷贝，不重开）；`llm.py:147` 提示词后缀（判定边界投影 = 候选 8）
7. **CONTEXT.md**：平台词条实现列补"外部头豁免经 patchers 分派、C 标准库头归门禁"；架构要点补一句

## 文件边界

- `src/contest_generator/generator.py`（_LIBC_HEADERS 拆分 + 门禁并集 + 注释正名）
- `src/contest_generator/keil.py` / `ccs.py`（各加 EXTERNAL_HEADERS 常量 + docstring）
- `src/contest_generator/patchers.py`（external_headers 分派）
- `src/contest_generator/categories.py`（config_file_reason 吃表）
- `src/contest_generator/master.py`（_detect_platform 文案推导）
- `tests/test_generator.py`（豁免并集断言 + 跨平台泄漏两态 + 结构测试：generator 源码无工具链头字面量（grep 式先例）、keil/ccs 有 EXTERNAL_HEADERS、patchers 有 external_headers）
- `tests/test_master.py`（两条报错文案 pinned 同步）
- `tests/test_categories.py`（config_file_reason 行为逐字 + 表消费结构）
- `CONTEXT.md`

## 验收

- [x] 全量测试绿 + mypy 干净
- [x] 结构自证：grep generator 无 `stm32f10x_conf` / `ti_msp_dl_config` 字面量；keil/ccs 各含 EXTERNAL_HEADERS；patchers 含 external_headers
- [x] 跨平台泄漏两态新测试（stm32 + ti_msp_dl_config.h → 拒；mspm0 + stm32f10x_conf.h → 拒）
- [x] 既有豁免用例零改动通过（stm32 + conf.h 过、mspm0 + SysConfig 头过）
- [x] config_file_reason 行为逐字（现有用例零改动通过）
- [x] 报错文案派生后 pinned 测试同步更新
- [x] CONTEXT.md 平台词条更新
- [x] 独立 worktree + 独立 commit，工作区其他未提交修改不混入

## Comments

- 2026-08-09 立项（架构评审 2026-08-09 候选 3，用户授权代决）：① 豁免三层拆分——C 标准库头 = C 语言事实留门禁（平台无关，两平台同名同集）；工具链头 = 平台事实入 keil/ccs（DFP / SysConfig 各自 docstring）；分派入 patchers 读侧（include_search_dirs 同文件先例）；门禁吃 corpus.platform 签名零变化；② 跨平台泄漏改拒绝 = 刻意行为变化（门禁洞修复：今天 stm32 工程 include SysConfig 头静默过门禁、Keil 编译必失败）；③ categories 吃表（表 → 后缀→原因映射，行为逐字）；④ 报错文案派生 + pinned 同步（全后缀列出，语义更准）；⑤ 注释正名零行为；⑥ 边界不碰 glob（platforms.py docstring 已文档化"格式知识非识别表拷贝"）与 llm 提示词（候选 8 投影）；⑦ 第三平台 = 平台模块加声明 + 表加行，核心与规则零改动
- 2026-08-09 实施完成（worktree-platform-facts，commit ce114c0，902 绿 + mypy 干净）：跨平台泄漏两态新测试红→绿已实证（旧行为模拟下两态均静默过、新测试红）；一处小偏差——_LIBC_HEADERS 实为 27 个 C 标准库头（工单文案写 28，现有集合本数即 27，行为逐字不凑数）。generator.py:336 的 ModuleCorpus docstring "keil 语义" 按工单三处边界（518/562/594）未动
