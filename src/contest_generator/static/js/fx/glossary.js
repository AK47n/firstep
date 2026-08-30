// fx/glossary.js — 新手词表纯函数（工单 newcomer-glossary/01）：
// 生成页底部「新手词表」折叠卡的数据与 HTML 单源：高频黑话 → 一句人话
//（工单 ux-walkthrough-02/18 增 自备/词表/重推/选型/补问）。与渲染解耦：
// UI 层把 glossaryHTML() 注入 #glossary-card，测试直接驱动纯函数。
import { esc } from "./core.js";

export const GLOSSARY_TERMS = [
  { term: "母版", plain: "每平台一个「空工程底盘」——电路板的基础工程，已能编译烧录，你的代码从这里开始。" },
  { term: "模块", plain: "可复用的驱动代码包（如超声波测距、OLED 显示）；选中后自动编译进你的工程，AI 推荐会替你匹配。" },
  { term: "多实例", plain: "同一个简单模块装多个（比如 3 个 LED），每个实例单独命名、单独配引脚。" },
  { term: "平台警告", plain: "这个模块在你选的板子上没实际验证过（或标记为硬件绑定）——能用但有风险，心里有数。" },
  { term: "收敛循环", plain: "AI 推荐模块时反复对照题面自查（删脑补、补遗漏），最多 4 轮，直到不再改。" },
  { term: "库外建议", plain: "库里没有能实现该功能的模块，只给你推荐外设（如 K230 视觉模块）——仅参考，不自动进工程。" },
  { term: "引脚角色", plain: "模块需要哪些引脚（如「电机方向」），你在第 7 步把它们绑到板子的具体引脚上。" },
  { term: "骨架", plain: "AI 生成的 main.c 草稿——初始化好你选的模块，具体赛题逻辑留给后面的任务推进。" },
  { term: "任务推进", plain: "把赛题逻辑拆成一个个小任务，逐个写代码 + 编译验证 + 上板自检（第 11 步的「任务推进」页签）。" },
  { term: "交接提示词", plain: "把本次生成的全部上下文打包成一段话，复制给另一个 AI 继续打磨——工具内已能「和 AI 商量」，一般用不上。" },
  { term: "评分点", plain: "赛题给分点。结果区有「评分点核对」清单（逐条勾选验收）、任务推进有「评分点覆盖总览」（每个评分点对应哪些任务，没覆盖标红 = 丢分风险）。" },
  { term: "参数速调", plain: "AI 扫描 main.c 里可调的数值（阈值 / 速度 / 频率…），给出建议范围；改完应用并自动编译验证，还能问 AI 该调哪个（第 11 步「参数速调」页签）。" },
  { term: "TODO", plain: "代码里「还没写完、留待补充」的占位标记——AI 深化时会按功能需求把 TODO 替换成具体实现并编译验证。" },
  { term: "增量", plain: "在现有代码上再加一小段，而不是推倒重写。任务推进的每个任务 = 一段可独立实现的 main.c 增量。" },
  { term: "自备", plain: "模块库里没有、需要你自己准备的外设（如某些传感器）——列表会标「需自备」，可在买件商量里问 AI 选型。" },
  { term: "词表", plain: "硬件词表：工具内置的硬件外设清单（型号 / 类别）——AI 只推荐词表内型号，库外建议按类别展示（不编造型号）。" },
  { term: "重推", plain: "改动题面或平台后让 AI 重新推荐模块——旧推荐结果会被清空，从新题面重新收敛。" },
  { term: "选型", plain: "对库外建议 / 自备件问 AI「买哪个」（入口叫买件指引 / 选型参考）：给出可行性、推荐型号与注意点，结论可带进生成。" },
  { term: "补问", plain: "AI 推荐时拿不准会反向问你一句（题面没写清的点），你补充回答后它带着答案继续。" },
];

/** 词表 HTML：details 默认收起（无 open），term 加粗 + 半角冒号 + plain 直述。 */
export function glossaryHTML(terms = GLOSSARY_TERMS) {
  const items = terms
    .map((t) =>
      '<div class="glossary-item"><b>' + esc(t.term) + "</b>：" + esc(t.plain) + "</div>"
    )
    .join("");
  return '<details class="card-details"><summary>新手词表 · ' + terms.length + ' 词一句人话</summary>'
    + '<div class="card-details-body">' + items + "</div></details>";
}

if (typeof window !== "undefined") {
  Object.assign(window, { GLOSSARY_TERMS, glossaryHTML });
}
