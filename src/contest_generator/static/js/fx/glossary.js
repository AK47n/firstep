// fx/glossary.js — 新手词表纯函数（工单 newcomer-glossary/01）：
// 生成页底部「新手词表」折叠卡的数据与 HTML 单源：10 个高频黑话 →
// 一句人话（spec「词表数据」逐字对应）。与渲染解耦：UI 层把
// glossaryHTML() 注入 #glossary-card，测试直接驱动纯函数。
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
];

/** 词表 HTML：details 默认收起（无 open），term 加粗 + 半角冒号 + plain 直述。 */
export function glossaryHTML(terms = GLOSSARY_TERMS) {
  const items = terms
    .map((t) =>
      '<div class="glossary-item"><b>' + esc(t.term) + "</b>：" + esc(t.plain) + "</div>"
    )
    .join("");
  return '<details class="card-details"><summary>新手词表（' + terms.length + ' 个高频词 → 一句人话）</summary>'
    + '<div class="card-details-body">' + items + "</div></details>";
}

if (typeof window !== "undefined") {
  Object.assign(window, { GLOSSARY_TERMS, glossaryHTML });
}
