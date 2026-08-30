// fx/guide.js — 「新手指引」教程页纯函数（工单 beginner-guide/01 骨架 +
// 02 内容：两章「准备 / 做题主线」数据与 HTML 渲染单源；03 扩展后两章）。
// 无 DOM / fetch——node:test 直测。模块约定见 fx/core.js 头部。

import { esc } from "./core.js";

// 子页签定义（key = data-guide-tab / 面板 id 后缀；label = 子页签文案）。
// index.html #guide-tabs 静态按钮标记与 GUIDE_TABS 的契约由 tests/js/guide.test.mjs
// 守卫钉住（键 / 顺序 / 面板 id 一一对应，防四处漂移）。
export const GUIDE_TABS = [
  { key: "prepare", label: "准备" },
  { key: "build", label: "做题主线" },
  { key: "compile", label: "编译与上板" },
  { key: "deliver", label: "交付与收尾" },
];

/** tab key → 面板 id（index.html #guide-panel-<key> 面板容器契约）。 */
export function guidePanelFor(tab) {
  return "guide-panel-" + tab;
}

/** 方向键循环：index 移动 dir 步（±1，Home/End 由 ui 层直给 0/count-1），
 * 在 [0, count) 内回绕；count=0 返回 -1。 */
export function guideTabNext(index, dir, count) {
  const n = Math.max(0, Math.floor(Number(count) || 0));
  if (n === 0) return -1;
  const i = Number.isFinite(Number(index)) ? Math.floor(Number(index)) : 0;
  return ((i + dir) % n + n) % n;
}

// ---------------------------------------------------------------------------
// 教程正文（面向完全新手，2026-08-30 事实核对：install.bat / start-app.vbs /
// 端口 8000 / config.json 路径 / 12 步卡 h2 与 index.html 一致；AI 边界按
// llm.py LOCAL_LLM_METHODS 与 webapp.py 路由核对，见 guide-refs.test.mjs 守护）。
// 块类型：p / note（label+text 提醒框）/ ul / ol / table（head+rows）/
// jump（label + tab + 可选 focus——跳转按钮，data-jump-tab / data-jump-focus）。
// ---------------------------------------------------------------------------
export const GUIDE_CHAPTERS = {
  prepare: {
    title: "准备：装好工具、配好 key、挑块板子",
    intro: "先了解一下你手里是什么：firstep 是一个本地网页工具——双击启动，浏览器里操作，数据全部留在本机。用之前，把下面四样东西备齐（一般半小时内搞定）。",
    sections: [
      {
        title: "开始前，四样东西",
        blocks: [
          {
            type: "ul",
            items: [
              "Windows 10 / 11 电脑（本工具只支持 Windows）。",
              "Python 3.13 或更新版本——到 python.org 下载安装，安装时务必勾选 Add python.exe to PATH。",
              "DeepSeek API key——到 platform.deepseek.com 注册 / 登录，左侧「API keys」创建一个；生成一次消耗几分钱，先充少量即可。key 只保存在本机。",
              "至少一套板子 + 对应的 IDE（下面两张表）。",
            ],
          },
          {
            type: "p",
            text: "浏览器：任意现代浏览器即可（Windows 自带 Edge 就行，用 Chrome 也可以）——本工具是本地网页，不需要任何插件或特殊设置。",
          },
          {
            type: "table",
            head: ["平台", "板子", "IDE", "怎么选"],
            rows: [
              ["stm32", "STM32F103C8T6 最小系统板", "Keil5（MDK-ARM）", "入门资料最多、社区最大，多数人的第一块板"],
              ["mspm0", "地猛星 MSPM0G3507 开发板", "TI CCS（Code Composer Studio）", "TI 官方工具链，SysConfig 可视化配置外设"],
            ],
          },
          {
            type: "note",
            label: "选板建议",
            text: "学校已发板 / 学长推荐哪块就用哪块，跟着大部队最省事；两款同时备也不冲突（生成时按题选平台）。",
          },
        ],
      },
      {
        title: "三步装好，然后配 key",
        blocks: [
          {
            type: "ol",
            items: [
              "双击 install.bat：自动创建虚拟环境并安装依赖（需要联网，约几分钟；脚本可重复运行，重复安装不会出错）。",
              "双击 start-app.vbs：后台启动服务，浏览器自动打开 http://127.0.0.1:8000 。",
              "网页右上角「设置」→ 粘贴 DeepSeek API key → 点「一键体检」：体检卡会逐个检查 Python、API key、IDE 工具链、母版与模块库是否就绪。",
            ],
          },
          {
            type: "note",
            label: "就绪总览与一键补齐",
            text: "进生成页后顶部有「就绪总览」卡，列出各项是否就绪；里面的「一键补齐」会按顺序把你带到还没完成的步骤（题面 / 平台 / 模块清单 / 输出目录），只带路、不下载任何文件。库目录的事不用操心——见下面「库目录自动指向」。",
          },
          {
            type: "ul",
            items: [
              "库目录自动指向：首次运行 install.bat 时，模块库 / 母版库已经自动指向工具包里的 library 文件夹（library\\modules、library\\masters）——正常情况不用手动设置。",
              "体检仍提示「模块库 / 母版未就绪」？到「设置 → 库目录」核对两项：模块库目录 = 工具包根目录（含 install.bat 的那个文件夹）\\library\\modules；母版库目录 = 工具包根目录\\library\\masters。赛题库与参考文件库也随包在 library 里（与模块库目录同级）。",
            ],
          },
          {
            type: "jump",
            label: "去设置配 API key",
            tab: "settings",
            focus: "set-api-key",
          },
          {
            type: "jump",
            label: "去设置做环境体检",
            tab: "settings",
            focus: "btn-env-check",
          },
          {
            type: "note",
            label: "双击没反应",
            text: "先运行一次 install.bat 装依赖；再不行看日志 %USERPROFILE%\\.contest_generator\\webapp.log；提示端口 8000 被占用时，关掉占用该端口的程序后重新双击 start-app.vbs（本工具不会自动换端口）。",
          },
        ],
      },
      {
        title: "什么是 IDE / Keil5 / CCS（人话版）",
        blocks: [
          {
            type: "p",
            text: "IDE = 集成开发环境：写代码、把代码编译成单片机认识的程序文件（.hex / .out）、下载到板子，都靠它。本工具生成的是完整工程——用对应 IDE 打开就能编译，你通常不需要手写任何工程配置，所以也不用先学 IDE。",
          },
          {
            type: "ul",
            items: [
              "Keil5（MDK-ARM）：STM32 的 IDE，Windows 上装好即可；编译出 .hex 后配合烧录器进板子（具体步骤见「编译与上板」）。",
              "CCS（Code Composer Studio）：TI 官方 IDE，用于 MSPM0；配套 MSPM0 SDK 与 SysConfig（外设可视化配置）。",
              "工具链自动集成：在「设置」页填 IDE / 工具链路径后，「生成」第 10 步可一键自动编译；「一键体检」会提示当前缺哪一项。",
            ],
          },
          {
            type: "table",
            head: ["工具", "官方下载入口", "备注"],
            rows: [
              ["Keil5（MDK-ARM）", "https://www.keil.com/download/product/（下载中心选 MDK-ARM）", "评估版限 32KB 代码（限制明细见 https://www2.keil.com/limits）；学校 / 老师处通常有正版授权，先用评估版也行"],
              ["CCS（Code Composer Studio）", "https://www.ti.com/tool/CCSTUDIO", "免费；装好后可继续装 MSPM0 SDK"],
              ["MSPM0 SDK", "https://www.ti.com/tool/MSPM0-SDK", "免费；编译 MSPM0 工程需要（GitHub 镜像：TexasInstruments/mspm0-sdk）"],
              ["ST-Link 驱动", "https://www.st.com/en/development-tools/stsw-link009.html", "免费；STM32 烧录用（OpenOCD / st-flash 共用此驱动）"],
            ],
          },
          {
            type: "note",
            label: "下载以官网为准",
            text: "以上都是官方产品页入口，页面若有调整按官网指引来；安装顺序建议：先装 IDE 与驱动，再打开工具做体检。",
          },
        ],
      },
    ],
  },
  build: {
    title: "做题主线：从粘贴赛题到生成工程",
    intro: "这一章回答两个问题：页面上哪些东西是你要用的、12 步向导怎么走。看完就能自己跑通第一道题。",
    sections: [
      {
        title: "顶部导航：三组，分清主次",
        blocks: [
          {
            type: "ul",
            items: [
              "「做题」组（生成 / 赛题库 / 设置）：你日常用的——生成页是主流程，赛题库存历年真题（点「取题面」一键填入），设置里配 key 与体检。",
              "「资料管理」组（模块库 / 参考文件库 / PDF 资料库 / 母版 / 更新记录）：内容管理页，做题用不到——除非要补录资料，先别动，尤其别删除。",
              "「指南」组（新手指引）：就是你现在看的这个页面。",
            ],
          },
          {
            type: "note",
            label: "一句话",
            text: "做题只碰「做题」组；想深入了解工具怎么改，再去看更新记录。",
          },
        ],
      },
      {
        title: "12 步向导速览（每一步做什么、要不要 AI）",
        blocks: [
          {
            type: "table",
            head: ["步骤", "做什么", "要不要 AI（DeepSeek key）"],
            rows: [
              ["1 赛题原文", "粘贴赛题文字，或上传 PDF / Word / 图片自动抽字", "粘贴 / 文字抽取不用；图片与 PDF 示意图识别要 AI"],
              ["2 赛题预读", "AI 先读题面，整理关键信息与提醒", "要 AI（配置了本地 Ollama 时可离线）"],
              ["3 目标平台", "选 STM32 还是 MSPM0，决定工程与工具链", "不用"],
              ["4 参考资料", "选套件例程 / 说明书作学习素材（可选）", "勾选不用；AI 摘要可走本地模型"],
              ["5 AI 推荐模块", "AI 对照题面推荐可复用驱动模块，可勾选 / 调整", "要 AI"],
              ["6 模块清单", "确认进工程的模块，看清平台警告（哪些没在你这块板子上验证过）", "不用"],
              ["7 引脚配置", "板图上点选把引脚绑定到具体脚（不配用默认也能编译）", "不用"],
              ["8 main.c 骨架", "AI 初始化好所有模块的 main.c 草稿", "要 AI"],
              ["9 输出目录并生成", "生成完整可编译工程到指定目录", "不用（本地模板组装）"],
              ["10 修复中心", "编译报错时看错误、让 AI 自动修", "看错误 / 重新编译不用；AI 自动修复要 AI"],
              ["11 修订与深化", "生成后继续打磨：任务推进 / 修订 / 参数速调 / 交付", "各 AI 动作要 AI（应用与编译本地）"],
              ["12 交接提示词", "把这次上下文打包成一段话，复制给另一个 AI（可选）", "不用（本地打包）"],
            ],
          },
          {
            type: "note",
            label: "key 的边界",
            text: "粗略说：只有「生成 / 修改工程」这类 AI 动作需要调 DeepSeek。没有 key 时 AI 推荐、骨架、自动修复等会提示先配置——所以第一步永远是去设置里配 key。个别小操作（比如模块简介校验、推荐澄清）在你配了本地 Ollama 时也能离线——主流程按上表为准。",
          },
          {
            type: "jump",
            label: "去设置配 API key",
            tab: "settings",
            focus: "set-api-key",
          },
        ],
      },
      {
        title: "生成完去哪写代码：第 11 步「任务推进」",
        blocks: [
          {
            type: "p",
            text: "工程生成后，你写逻辑的主路径不是打开 IDE 手抄代码，而是回到生成页第 11 步——里面有几个页签：任务推进（主路径）、修订（补赛题答疑）、参数速调（改参数）、交付（打包）。",
          },
          {
            type: "ul",
            items: [
              "「任务推进」把功能拆成一张张任务卡，按顺序实现 main.c 里的逻辑；每张卡有「有不懂的？问这里」入口（也就是和 AI 商量），做完可即时编译验证。",
              "卡片之间有前置依赖：前置没做完，做下一步时会有温和提醒（可跳过，但建议按顺序）。",
              "完成一张卡后，卡上会出现「下一步 →」提示并高亮下一张，照着走即可。",
              "生成成功后结果区有「去任务推进」按钮——点击直达第 11 步「任务推进」；结果区同时展示编译横幅 / 烧录按钮 / 评分点核对清单。",
            ],
          },
          {
            type: "ul",
            items: [
              "「任务推进」区顶部有「评分点覆盖总览」：每个评分点对应哪些任务一目了然——某个评分点没有任何任务覆盖会标红，这就是丢分风险，点进去补任务。",
              "「参数速调」页签：AI 扫描 main.c 里可调的数值（阈值 / 速度 / 频率…），每项给当前值、单位与建议范围；改完点「应用」即自动编译验证，想反悔可「恢复旧值」。页签内还有「问 AI：我该调哪个参数？」——拿不准先问它。",
            ],
          },
          {
            type: "note",
            label: "评分点核对清单",
            text: "生成成功后，结果区还有一张「评分点核对」清单（按赛题评分点逐条可勾选）——相当于按评分标准自查一遍，交稿前记得过一遍。",
          },
          {
            type: "note",
            label: "还要外部 AI 吗",
            text: "工具内已有任务卡的「有不懂的？问这里」（和 AI 商量）与「参数速调」的「问 AI：我该调哪个参数？」，一般不需要第二个 AI。第 12 步「交接提示词」只在你确实想把上下文复制给外部 AI（比如网页版 DeepSeek）时用。",
          },
        ],
      },
      {
        title: "遇到不懂的词：新手词表",
        blocks: [
          {
            type: "p",
            text: "母版、模块、多实例、平台警告……这些术语在生成页底部有一个「新手词表」折叠卡，每个词一句人话。看到不认识的词，点开看一眼。",
          },
          {
            type: "jump",
            label: "打开新手词表",
            tab: "generate",
            focus: "glossary-card",
          },
        ],
      },
    ],
  },
  compile: {
    title: "编译与上板：把代码烧进板子",
    intro: "生成工程后，把固件烧进板子通上电——本工具的编译与烧录都是点按钮完成的。这一章讲第一次全流程怎么走、四根线怎么接、常见报错怎么解。",
    sections: [
      {
        title: "第一次编译（三种方式）",
        blocks: [
          {
            type: "p",
            text: "编译 = 把 C 代码变成单片机认识的固件文件（STM32 出 .hex / MSPM0 出 .out）。生成工程时工具已经自动编译过一次（报错会走 AI 自动修复）；之后随时可以再编译。",
          },
          {
            type: "ul",
            items: [
              "自动编译：第 9 步生成后自动进行；未检测到工具链会跳过并提示（结果区注明），此时去设置点「一键体检」看缺什么。",
              "一键编译修复（第 10 步修复中心）：编译报错后点它，AI 读错误自动修、重编验证，失败自动回滚。",
              "手动开 IDE：交付页签「打开工程」，或在 IDE 里打开工程点 Build（Keil5 快捷键 F7 / CCS 菜单 Project → Build）。",
            ],
          },
          {
            type: "note",
            label: "自动编译的前提",
            text: "STM32 装 Keil5（设置页 uv4_path 可留空自动探测）；MSPM0 装 CCS（gmake 工具链）。「一键体检」会逐一列出缺哪一项。",
          },
        ],
      },
      {
        title: "第一次接线：一共四根（SWD）",
        blocks: [
          {
            type: "p",
            text: "烧录走 SWD 调试接口，只有 4 根线：供电 3V3、共地 GND、数据 SWDIO、时钟 SWCLK。两款板都是独立排针，不在主排针上。",
          },
          {
            type: "table",
            head: ["平台", "调试器", "4 根线接哪", "板上位置（看套件实物图为准）"],
            rows: [
              ["stm32", "ST-Link（SWD），OpenOCD / st-flash 驱动", "3V3 / GND / SWDIO=PA13 / SWCLK=PA14", "上缘独立 4P 弯针；也可 BOOT0 跳线走 Type-C 串口烧录"],
              ["mspm0", "XDS110 探针（CCS 自带 DSLite 烧录）", "3V3 / GND / SWDIO=PA19 / SWCLK=PA20", "独立 DEBUG 排针；另有 BSL 烧录排针（备选）"],
            ],
          },
          {
            type: "note",
            label: "备件",
            text: "ST-Link 常见 ST-Link V2 迷你版即可，四根杜邦线；不同批次板卡排针位置可能有差异，接线以你的套件文档为准。",
          },
        ],
      },
      {
        title: "第一次烧录",
        blocks: [
          {
            type: "p",
            text: "点「烧录到板子」按钮（结果区 / 任务卡上都有）——工具自动定位固件产物（STM32 → user/Objects/*.hex，MSPM0 → Debug/*.out）、自动探测本机烧录器并执行，中文回报结果。",
          },
          {
            type: "ul",
            items: [
              "STM32：OpenOCD 优先、st-flash 兜底（都是 ST-Link 驱动，装一个即可；设置页可填路径）。",
              "MSPM0：XDS110 走 CCS 自带的 DSLite.exe——装了 CCS 就有，一般零安装（找不到时在设置页填 dslite_path）。",
              "烧录前确认板子供电正常（独立供电或调试器供电，看套件说明）。",
            ],
          },
          {
            type: "note",
            label: "烧录报错先看速查表",
            text: "超时 / 找不到烧录工具这类问题，先对照本节下方「常见报错速查」；结果区有「复制烧录命令」，可提出命令手动执行排查。",
          },
        ],
      },
      {
        title: "常见报错速查",
        blocks: [
          {
            type: "p",
            text: "编译 / 烧录卡住时，先对照这张表——九成情况是下面几条之一。",
          },
          {
            type: "table",
            head: ["症状", "原因与对策"],
            rows: [
              ["生成 / 编译提示「未检测到工具链」，自动编译被跳过", "到「设置」点「一键体检」看缺哪项：STM32 装 Keil5（uv4_path 可留空自动探测）；MSPM0 装 CCS（gmake 工具链）；装完重跑体检再自动编译。"],
              ["烧录超时（180s）", "探针没接好或板子没电：核对 SWD 四线（3V3 / GND / SWDIO / SWCLK）与供电后重新点烧录。"],
              ["找不到 DSLite（MSPM0）", "DSLite 由 CCS 自带——装 CCS 即可；已装仍找不到，在设置页填 dslite_path。"],
              ["找不到 OpenOCD / st-flash（STM32）", "先装 ST-Link 驱动（STSW-LINK009），再装 OpenOCD 或 st-flash 其一；设置页可填路径。"],
              ["未找到固件产物", "还没编译成功：先完成编译（第 10 步修复中心 / 交付「打开工程」手动 Build）；产物 STM32 在 user/Objects/*.hex、MSPM0 在 Debug/*.out。"],
              ["「母版未导入（生成前需导入）」", "母版库没就绪：到「设置 → 库目录」核对母版库目录 = 工具包根目录\\library\\masters（install.bat 已自动填好）；仍不行到「母版」页确认 stm32 / mspm0 母版已导入。"],
              ["提示端口 8000 被占用", "关掉占用该端口的程序，重新双击 start-app.vbs（本工具不会自动换端口）；日志在 %USERPROFILE%\\.contest_generator\\webapp.log。"],
            ],
          },
        ],
      },
      {
        title: "上板后先做什么",
        blocks: [
          {
            type: "p",
            text: "烧录成功 = 程序进板了，不等于功能全对。先跑任务推进里的「上板自检清单」（任务卡自带，逐项勾选验证），再按赛题功能点逐项演示——这才是检验「做对了没」的正道。",
          },
          {
            type: "jump",
            label: "去任务推进过上板自检",
            tab: "generate",
            focus: "revise-panel-tasks",
          },
        ],
      },
    ],
  },
  deliver: {
    title: "交付与收尾：拿得出手的报告",
    intro: "做题最后一步：把过程整理成交付物。本工具已自动帮你起草了两份材料，收尾还有三个动作。",
    sections: [
      {
        title: "报告与演示：自动附带的两份草稿",
        blocks: [
          {
            type: "p",
            text: "生成工程时，工程根会自动附带两份草稿：",
          },
          {
            type: "ul",
            items: [
              "「设计报告草稿.md」——AI 按你的工程写的报告框架与要点（有 AI 结果时生成），补上实测数据就能用；",
              "「演示脚本.md」——演示流程建议（恒在），演示前照着过一遍不慌。",
            ],
          },
          {
            type: "note",
            label: "草稿不等于终稿",
            text: "报告要你自己验证改写——以工程实测数据为准，别直接交草稿。",
          },
        ],
      },
      {
        title: "交付页签：收尾三件事",
        blocks: [
          {
            type: "p",
            text: "第 11 步里有「交付」页签（先在「修订与深化」卡加载输出目录即可用），三个动作：",
          },
          {
            type: "ul",
            items: [
              "交付检查：逐项核对——还有哪些步骤没完成、能否打包；",
              "一键打包：把工程打成 zip，演示前 / 上交前备一份；",
              "打开工程：STM32 直接拉起 Keil5；MSPM0 在资源管理器中打开工程文件夹（CCS 需要手动导入工程）。",
            ],
          },
          {
            type: "note",
            label: "交之前打个勾",
            text: "回到结果区过一遍「评分点核对」清单（生成成功后就在结果区，逐条可勾选）——没勾完的评分点就是待验证项；任务推进里「评分点覆盖总览」标红的评分点，先补任务再交。",
          },
        ],
      },
      {
        title: "交接提示词：把上下文带走（可选）",
        blocks: [
          {
            type: "p",
            text: "第 12 步「交接提示词」把这次生成的全部上下文（题面 / 平台 / 模块 / 引脚 / 代码与修复状态）打包成一段话，复制给外部 AI 继续打磨。",
          },
          {
            type: "ol",
            items: [
              "在生成页第 12 步点「生成交接提示词」；",
              "点「复制」拿到那段提示词；",
              "粘贴到外部 AI（比如网页版 DeepSeek），让它基于上下文接着干。",
            ],
          },
          {
            type: "note",
            label: "用不用它",
            text: "工具内已有「和 AI 商量」「参数速调 AI 咨询」——多数情况不必外接；交接提示词适合你想把题目交给第二个 AI 深度打磨时用。",
          },
        ],
      },
      {
        title: "工程在哪 / 怎么停 / 下一题",
        blocks: [
          {
            type: "ul",
            items: [
              "工程目录 = 第 9 步选的输出位置（常见桌面，目录名形如 2024H_Auto_Car_STM32，平台后缀区分）；生成页顶部「最近生成」可一键复制路径继续做。",
              "收工：双击 stop-firstep.bat 停服务；数据都在 %USERPROFILE%\\.contest_generator\\ 里，下次双击 start-app.vbs 回来接着做。",
              "下一题：直接粘贴新题再走一遍；或到「赛题库」拿历年真题，点「取题面」一键填入生成页。",
            ],
          },
          {
            type: "jump",
            label: "去赛题库挑一道题",
            tab: "topic",
          },
        ],
      },
    ],
  },
};

/** 表格块渲染（窄屏横向滚动包裹）。 */
function tableHTML(block) {
  const head = '<tr>' + block.head.map((h) => "<th>" + esc(h) + "</th>").join("") + "</tr>";
  const rows = block.rows.map((r) =>
    "<tr>" + r.map((c) => "<td>" + esc(c) + "</td>").join("") + "</tr>").join("");
  return '<div class="guide-table-scroll"><table class="guide-table"><thead>'
    + head + "</thead><tbody>" + rows + "</tbody></table></div>";
}

/** 单块渲染：p / note / ul / ol / table / jump。 */
export function guideBlockHTML(block) {
  switch (block.type) {
    case "p": return "<p>" + esc(block.text) + "</p>";
    case "note":
      return '<div class="guide-note">'
        + (block.label ? "<strong>" + esc(block.label) + "</strong> " : "")
        + esc(block.text) + "</div>";
    case "ul": return "<ul>" + block.items.map((i) => "<li>" + esc(i) + "</li>").join("") + "</ul>";
    case "ol": return "<ol>" + block.items.map((i) => "<li>" + esc(i) + "</li>").join("") + "</ol>";
    case "table": return tableHTML(block);
    case "jump":
      return '<button type="button" class="guide-jump" data-jump-tab="'
        + esc(block.tab) + '"' + (block.focus ? ' data-jump-focus="' + esc(block.focus) + '"' : "")
        + ">" + esc(block.label) + "</button>";
    default: return "";
  }
}

/** 章（子页签面板）标题 + 小节序列组装；chapter 缺省返回空串（占位保留）。 */
export function guideChapterHTML(chapter) {
  if (!chapter) return "";
  return '<h3 class="guide-chapter-title">' + esc(chapter.title) + "</h3>"
    + (chapter.intro ? '<p class="guide-chapter-intro">' + esc(chapter.intro) + "</p>" : "")
    + chapter.sections.map((s) =>
      '<h4 class="guide-sec-title">' + esc(s.title) + "</h4>"
      + s.blocks.map(guideBlockHTML).join("")).join("");
}

/** 章内全部块的扁平序列（测试遍历单源：块类型判别只在此遍历一次，
 * 各消费方（渲染/校验/文案提取）只做自己的块级处理）。 */
export function guideBlocksOf(chapter) {
  if (!chapter || !Array.isArray(chapter.sections)) return [];
  return chapter.sections.flatMap((s) => s.blocks || []);
}

// window 桥（fx 模块通用兼容层，见 fx/core.js：44）：供 index.html 直调 /
// 旧脚本内联引用的同名全局；node 测试环境无 window。
if (typeof window !== "undefined") {
  Object.assign(window, {
    GUIDE_TABS, GUIDE_CHAPTERS, guidePanelFor, guideTabNext,
    guideBlockHTML, guideChapterHTML, guideBlocksOf,
  });
}
