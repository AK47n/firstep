# 新手指引（beginner-guide）规格说明

## 问题陈述

完全新手（第一次参加电赛、第一次接触单片机）打开 firstep 后：虽然散点提示已经铺开（首次欢迎卡、生成页底部新手词表、12 张步骤卡人话副标题、导航分组与 tab 悬停说明、任务卡「下一步」引导），但**没有一处「从零到交付」的聚合教程可随时回看**。新手不知道：要先准备什么（Python/key/板子/IDE）、8 个导航 tab 里哪几个是做题用的、12 步向导怎么走、哪些步骤需要 AI key、生成后去哪写代码、第一次怎么编译/接线/烧录、做完怎么交付与收尾。顶部导航没有「帮助/指南」类入口。

## 方案

新增「新手指引」教程页（纯前端、纯静态内容，无后端改动）：

- **双入口**：①顶部导航新增第三组「指南」，内含「新手指引」一个按钮；②首次欢迎卡（full 态）增加「先看新手指引」按钮，点击切到教程页。
- **教程页四子页签**：准备 / 做题主线 / 编译与上板 / 交付与收尾，面向**完全新手**从零讲起（解释什么是 IDE、Keil 与 CCS 怎么选、什么是烧录器/ST-Link、怎么接线），文字 + 表格排版，不依赖图片素材。
- **教程内「跳到功能」按钮**：如「去设置配 key」「去生成」「看词表」——点击直接切到对应页签/锚点。
- **内容与界面事实一致**：导航 tab 名、12 步步骤号、AI 边界（哪些步骤要 DeepSeek key）、平台接线事实，实现时逐点核对代码/资料，不凭记忆写；并由内容守护测试钉住关键句。

## 用户故事

1. 作为完全新手，我第一次打开 firstep，想要一眼看到「新手指引」入口（欢迎卡按钮 + 导航按钮），以便知道从哪里开始学。
2. 作为新手，我想要「准备」章，以便知道要准备的四样东西（Windows 电脑 / Python 3.13+ / DeepSeek API key / 板子 + IDE）、怎么装、怎么配 key、平台怎么选（STM32 还是 MSPM0）。
3. 作为新手，我想要「做题主线」章，以便知道导航哪些 tab 是做题用的、12 步向导每步干什么、哪些步骤需要 key（AI 边界）、生成后去哪写代码（第 11 步「任务推进」是主路径）。
4. 作为新手，我想要「编译与上板」章，以便知道怎么编译（自动 / 手动开 IDE）、第一次怎么接线与烧录（STM32 的 ST-Link SWD 四线、MSPM0 的下载方式）、上板自检先做什么。
5. 作为新手，我想要「交付与收尾」章，以便知道报告草稿 / 演示脚本 / 交接提示词怎么用、工程在哪、怎么停服务、怎么再做下一题。
6. 作为新手，我希望教程里的按钮能直接把我带到对应功能页，以便不用自己找。
7. 作为老用户，我希望教程不强制弹出（不做首次浮层），以便只在需要时点开。
8. 作为维护者，我希望教程内容有测试守护，以便内容不随界面改动漂移（导航结构 / 词表 / AI 边界）。

## 实现决策

- **数据与 HTML 单源**：新增 `static/js/fx/guide.js`（参照 fx/glossary.js 先例）——四章教程数据（章节标题、小节、正文段落、跳转按钮）与 HTML 渲染纯函数同源导出；`window` 桥登记（沿用 fx 惯例）。
- **UI 胶水**：新增 `static/js/ui/guide.js`——渲染教程页（注入 `#tab-guide`）、四子页签切换（简化版 revise-tabs 模式：按钮 `data-guide-tab` + 面板显隐）、「跳到功能」按钮接线（点击顶部导航按钮切换页签 + 可选聚焦，参照 ui/welcome.js `gotoSettings` 模式；若走共享化，把该跳转泛化为 `gotoNavTab(tab, focusId)` 并让 welcome/guide 共用，避免两处各写一遍）。
- **index.html**：
  - 顶部导航新增第三组 `<div class="tab-group" role="group" aria-label="指南">`（组标签「指南」，位置在「资料管理」组之后），内含 `<button data-tab="guide" title="…中文 ≥8 字…">新手指引</button>`；
  - 新增 `<section id="tab-guide" class="page">`（页内四子页签按钮条 + 四个面板容器）；
  - 模块脚本区新增 import + `initGuide()` 调用（页签切换是通用 `nav button[data-tab]` 逻辑，guide 无异步加载、无需新分发分支）。
- **欢迎卡**：`fx/welcome.js` 的 `welcomeCardHTML('full')` 增加「先看新手指引」按钮（id=btn-welcome-guide）；`ui/welcome.js` 接线（切 guide 页签）。compact/hidden 态不含该按钮。
- **样式**：复用现有 `.card` / `.card-details` / `.tab` / `.btn` 令牌，新增少量 `guide-*` CSS；亮暗主题均用现有 `var(--*)`，不破版。
- **AI 边界表述**：教程「哪些步骤需要 API key」必须与实际调用点一致——已知事实锚点：`llm.py` `LOCAL_LLM_METHODS`（preread_topic / summarize_module / reference_summarize / clarify / validate_module_description / reference_judge_archivable 六个方法可走本地 Ollama，离线可用）；其余 AI 动作（AI 推荐、骨架 main.c、编译修复、修订/深化、任务推进执行、参数速调咨询、报告草稿等）走 DeepSeek（remote）。实现时逐步骤核对调用点后成文，表述口径与 README「只有生成/修改工程这一步需要调用 DeepSeek API」兼容（README 是简化口径，教程给出细化版：哪些步骤点按钮就会调 DeepSeek）。
- **接线/烧录事实**：STM32 用 ST-Link SWD（3V3/GND/SWDIO/SWCLK 四线，接口名以套件文档为准）；MSPM0G3507 地猛星板以 `boards/mspm0-dimx.json` 与参考库套件文档为准（烧录方式、下载器型号），实现时核实后成文，不确定处不写具体型号。
- **范围外事项**（明确不做）：首次打开分步引导浮层/spotlight；教程图片素材（纯文字/表格）；12 步向导流程改动；赛题库补年份、离线兜底（C1/B2/G1 遗留）；导航 tab 平铺改折叠。

## 测试决策

- **测试 seam 沿用 tests/js（node:test，.mjs）**：
  - 新增 `fx/guide.test.mjs`：数据结构完整（4 章、每章标题/小节/正文非空）、HTML 渲染含关键锚点（章节 id、子页签按钮与面板映射、跳转按钮 count/目的）、转义正确；
  - 更新 `nav-tabs-guard.test.mjs`：GROUPS 增第三组 `{ label: "指南", keys: ["guide"] }`，总数 9、组序断言（做题 → 资料管理 → 指南）、title 中文 ≥8 字；
  - 更新 `welcome.test.mjs`：full 态 HTML 含 `btn-welcome-guide` 且文案「先看新手指引」；compact/hidden 不含；
  - 新增内容守护测试（参照 `glossary-refs.test.mjs` 先例，如 `guide-refs.test.mjs`）：教程正文钉住「12 步」「任务推进」「新手词表」等与界面事实一致的词；AI 边界关键句钉住（如「AI 推荐」步骤需要 key 与 README/代码一致）；
  - `fx-guard.test.mjs` 登记新 fx 模块名（防双源回退）。
- **浏览器验收**：探针脚本（参照 .scratch 内 `probe-*.mjs` 惯例）：导航三组渲染、「新手指引」可点入、四子页签切换、欢迎卡按钮跳转、亮暗主题渲染截图检查；不引入新端到端框架。

## 补充说明

- 本 spec 承接 `docs/improvement-review-newcomer-onboarding.md` 评审（其 R3/Y2/Y3 及部分 Y4 已落地，本特性覆盖其「聚合教程入口」遗留）与用户确认（双入口、四子页签、完全新手向、欢迎卡按钮触达）。
- 教程正文语言规范同仓库：全中文，技术术语可保留并在首次出现处给一句人话。
- 内容体量提示：四章正文均为长文本，实现时分两个工单（前两章 / 后两章）以保持单工单上下文可控。
