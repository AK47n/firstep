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
            text: "进生成页后顶部有「就绪总览」卡，列出各项是否就绪；里面的「一键补齐」能下载参考文件与模块库（首次建议点一次，可重复点）。",
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
              ["11 修订与深化", "生成后继续打磨：答疑修订 / 任务推进 / 参数速调 / 交付", "各 AI 动作要 AI（应用与编译本地）"],
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
            text: "工程生成后，你写逻辑的主路径不是打开 IDE 手抄代码，而是回到生成页第 11 步——里面有几个页签：修订（补赛题答疑）、任务推进（主路径）、参数速调（改参数）、交付（打包）。",
          },
          {
            type: "ul",
            items: [
              "「任务推进」把功能拆成一张张任务卡，按顺序实现 main.c 里的逻辑；每张卡有「和 AI 商量」入口，做完可即时编译验证。",
              "卡片之间有前置依赖：前置没做完，做下一步时会有温和提醒（可跳过，但建议按顺序）。",
              "完成一张卡后，卡上会出现「下一步 →」提示并高亮下一张，照着走即可。",
              "生成成功后结果区也有「下一步」指引（编译横幅 / 烧录按钮 / 任务卡列表）。",
            ],
          },
          {
            type: "note",
            label: "还要外部 AI 吗",
            text: "工具内已有「和 AI 商量」「参数速调 AI 咨询」，一般不需要第二个 AI。第 12 步「交接提示词」只在你确实想把上下文复制给外部 AI（比如网页版 DeepSeek）时用。",
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
