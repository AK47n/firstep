// ui/glossary.js — 新手词表胶水（工单 newcomer-glossary/01）：
// 把 fx/glossary.js 的词表 HTML 渲染进生成页底部 #glossary-card；
// 纯静态展示，无交互（详情折叠由原生 details 处理）。
import { $ } from "/js/app.js";
import { glossaryHTML } from "/js/fx/glossary.js";

export function initGlossary() {
  const slot = $("glossary-card");
  if (!slot) return;
  slot.innerHTML = glossaryHTML();
}
