# Spec：立创 wiki 手册素材来源标注（lckfb-attribution）

## 问题陈述

本项目大量使用立创开发板技术文档中心（wiki.lckfb.com）「地猛星 MSPM0G3507 模块移植手册」的素材：
70 篇手册（`sources/materials/lckfb-地猛星移植手册/`）+ 56 个由手册代码改写入库的模块
（`library/modules/`，manifest 的 `source_url` 指向 wiki 原页）。

立创官网版权声明第三条要求：**任何使用该文件的个人或组织，如需使用或者参考手册中的模块资料，
将其复制、传播、修改、公开展示或在其他网站上使用，都需要在使用时清楚的标明文件的来源以及链接。**

现状盘点：
- 70 篇 wiki 手册 .md：抓取时已在元数据头写入 `来源：<原页 URL>` ✓
- manifest：`source_url` 已存 wiki 原页 ✓
- **模块源码 .c/.h：全库 0 处含原页 URL**（.h 仅引仓库内 md 相对路径，拿到生成工程的同学无法访问；.c 完全无来源声明）✗
- **生成工程 README「模块清单与依赖」：无来源行**（生成工程是传播面）✗
- **UI 模块详情弹窗：`source_url` 一律显示「购买链接」**——wiki 来源模块标签错位 ✗
- **仓库 README：无第三方素材知识产权说明** ✗
- **无结构测试兜底**：今后补录 wiki 派生模块可能漏标 ✗

## 方案

在全部「复制 / 传播 / 修改 / 公开展示」面补上来源 + 链接，口径 = **仅 wiki 派生模块**
（`source_url` 匹配 `wiki.lckfb.com` 的 56 个模块），其余模块（自研 / 逐飞库 / 淘宝套件）不硬标来源，
避免错标。具体：

1. 模块源码 .c/.h 顶部统一注入标准来源注释块（原页 URL + 页面标题 + 改写说明）；
2. 生成工程 README「模块清单与依赖」每模块行附来源链接（仅 wiki 模块）+ 新增固定
   「第三方素材来源」声明段（立创版权要求第三条原文 + wiki 首页链接）；
3. UI 模块详情弹窗：source_url 为 wiki 页面 → 标签显示「来源（立创 wiki）」，其余维持「购买链接」；
4. 仓库 README 增「第三方素材来源与知识产权说明」章节；
5. 新增结构测试兜底：wiki 派生模块的 .c/.h 必须含原页 URL（防回潮/防漏标）。

不做独立 NOTICE.md：来源行随模块清单逐条渲染，声明随 README 常驻——不新增生成树产物，
对 Keil/CCS 工程文件零影响。

## 用户故事

1. 作为拿到生成工程的参赛学生，我想要在工程 README 里看到每个模块驱动的来源与链接，
   以便在使用/分享时按要求标注，避免侵权。
2. 作为拿到模块源码（modules/<slug>/code/）的人，我想要文件头直接写明来源页面与链接，
   以便复制、修改、传播时不丢来源。
3. 作为浏览模块库 UI 的人，我想要 wiki 来源模块的链接显示为「来源（立创 wiki）」而不是
   「购买链接」，以便知道这是什么链接。
4. 作为维护者，我想要结构测试自动拦截「wiki 派生模块源码缺原页 URL」，以便后续补录不破坏合规。
5. 作为项目发布者，我想要 firstep 仓库 README 说明第三方素材来源与遵循的版权要求，
   以便公开分发（GitHub / 完整包）时尽到告知义务。

## 实现决策

- **来源 URL 判据单源**：`url.startswith("https://wiki.lckfb.com/")`（大小写敏感，全库实测 56 个命中）；
  判据函数放 `manifest.py`（`is_wiki_source_url`），UI/README/测试共用，不三处各写一遍。
- **模块源码注入**：一次性脚本 `.scratch/lckfb-attribution/inject_source_notes.py`——
  遍历 `library/modules/*/manifest.json`，对 source_url 为 wiki 的模块，在其 code/*.c/*.h
  顶部（.h 在 `#ifndef` 前、.c 在首个 `#include` 前）注入标准注释块；幂等（文件已含该 URL 跳过）；
  页面标题 = 对应 wiki md 首行（`sources/materials/lckfb-地猛星移植手册/<cat>--<slug>.md`，
  cat/slug 由 URL 推导）；md 缺失（轻量 clone 无资料库）→ 标题降级为「地猛星 MSPM0G3507 模块移植手册」
  （FALLBACK_TITLE——与抓取批次目录名同义）。
  注入不改动任何代码行，仅插入注释（注释不影响编译，编译器矩阵既有结论）。
- **README 渲染**：`readme.py` 模块清单行对 wiki 模块追加 `（来源：<url>）`；
  「第三方素材来源」声明段 = 固定文本（含第三条原文 + wiki 首页链接），渲染在模块清单章之后；
  段位常量单一出处。`render_readme` 签名不变（ManifestSummary / ModuleManifest 自带 platforms，
  无需新增参数）。**声明段首行按模块集是否含 wiki 派生模块分两版措辞**（code-review 整改：
  空模块集 / 仅母版工程不得谎称「部分模块改写自 wiki」——source_notice_lines 纯函数，
  有则 HAS_WIKI、无则 NO_WIKI，正文与原文引用两版共用）。
- **UI**：`fx/module.js` 来源链接渲染处按 `is_wiki_source_url` 分支标签文案；
  JS 侧标签判定与后端判据同构（库内先例：pinShareClass 镜像）。
- **仓库 README**：新增章节，含 70 篇手册 + 56 模块来源、第三条原文、wiki 链接、本工具已采取的标注措施。
- **不改**：70 篇 md 的抓取器与元数据头（已合规）、manifest 结构（source_url 语义=来源链接，
  不新增字段）、推荐/生成链路的 LLM prompt（内部消费非公开展示面）、生成树文件清单。

## 测试决策

- **结构测试（新文件 `tests/test_lckfb_attribution.py`）**：遍历真实库，凡 source_url 命中
  wiki → 该模块 code/ 每 .c/.h 顶部 600 字符内必须含该 source_url（逐条目独立断言、
  不做跨条目互证——多 wiki 平台条目场景下互证会让漏标蒙混）；幂等断言（跑两遍注入函数
  结果一致）。wiki md 资料存在时断言其头部含 `来源：` + 原页（资料库可能缺失 → 跳过，
  不硬遍历 sources/）。
- **README 渲染测试（扩充 `tests/test_readme.py`）**：wiki 模块 → 行含来源 URL；非 wiki 模块 →
  行无来源；声明段标题与第三条原文存在；空模块集也有声明段（措辞 = NO_WIKI，不谎称）。
- **UI 测试（扩充 `tests/js/module-info-dialog.test.mjs` 或 fx 纯函数测试）**：
  wiki URL → 「来源（立创 wiki）」标签；淘宝 URL → 「购买链接」。
- **跨语言常量同步（code-review 整改）**：fx/module.js 的 wiki 前缀字面量必须与后端
  `WIKI_SOURCE_URL_PREFIX` 逐字一致（test_js_wiki_prefix_mirrors_python 守护——JS/Python
  不能共享常量，改任一侧即红，防 UI 标签与后端判据静默漂移）。
- **回归**：既有 test_module_* 读源码断言关键词，注入均以注释形式置于头部，不删不改原注释，
  应零影响（跑全量确认）；test_repo_language.py 检查新增文件中文规范。

## 范围外

- 非 wiki 模块（逐飞库、自研模块、淘宝套件资料）的来源标注；
- wiki 站内其他栏目（原理图 / 数据手册 PDF 等）改标；
- 生成工程增加独立 NOTICE.md 文件；
- 修改立创抓取器 / 重新抓取 70 篇 md。

## 补充说明

- 立创版权要求原文（第三条）已随 70 篇手册抓取时保留在网页；本 spec 引用的原文来自
  用户提供的官网表述：「请大家务必尊重贡献者的智力劳动成果：任何使用该文件的个人或组织，
  如需使用或者参考手册中的模块资料，将其复制、传播、修改、公开展示或在其他网站上使用，
  都需要在使用时清楚的标明文件的来源以及链接。」
- wiki 首页 = https://wiki.lckfb.com/zh-hans/dmx/（地猛星栏目）。
