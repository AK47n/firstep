// ui/a11y.js — 输入可访问名（工单 ux-walkthrough-02/19）：静态标记里大量
// 裸输入（无 label 关联/只有独立 label 无 for）补 aria-label——名称与可见
// placeholder / 卡片标签一致。启动时对 DOM 已有且缺 aria-label 的
// input/textarea/select 逐一补齐；幂等（已带或元素不存在则跳过）。
// 纯数据 + 幂等应用，无事件绑定；测试直接断言 INPUT_A11Y_LABELS 的 id
// 全部存在于 index.html（防死键）。
export const INPUT_A11Y_LABELS = {
  "problem": "赛题原文",
  "problem-file": "选择赛题文件（PDF/Word/图片）",
  "topic-id": "历史赛题编号",
  "ref-search": "搜索参考资料",
  "qa-text": "赛题 Q&A 澄清文本",
  "module-search": "搜索模块以添加",
  "main-c": "main.c 代码编辑区",
  "fix-center-log": "编译输出日志",
  "fix-errors-text": "粘贴编译报错全文",
  "revise-dir-input": "历史输出目录",
  "revise-problem-text": "赛题原文",
  "revise-qa-new": "新发布赛事答疑 Q&A",
  "revise-confirmed-slugs": "确认的模块集（逗号分隔）",
  "tasks-idea-input": "新想法 / 发现的问题",
  "handoff-text": "交接提示词",
  "lib-search": "搜索模块库",
  "new-slug": "模块 slug（英文标识，即目录名）",
  "new-desc": "模块一句话简介",
  "new-deps": "依赖模块（逗号分隔）",
  "ref-filter": "搜索参考文件库",
  "ref-title": "参考条目标题",
  "ref-type": "参考条目类型",
  "ref-anchor-kind": "锚定类型",
  "ref-anchor-topic": "锚定值（赛题编号）",
  "ref-anchor-kit": "锚定值（套件型号）",
  "ref-desc": "参考条目简介",
  "pdf-filter": "搜索 PDF 资料库",
  "topic-filter": "搜索赛题库",
  "topic-pdf": "选择赛题 PDF 文件",
  "project-dirs": "历史工程目录列表",
  "set-base-url": "DeepSeek 接口地址（base_url）",
  "set-model": "模型",
  "set-api-key": "API key（留空 / 掩码保持不变）",
  "set-ds-in-hit": "DeepSeek 输入单价·缓存命中（元/百万 token）",
  "set-ds-in": "DeepSeek 输入单价·缓存未命中（元/百万 token）",
  "set-ds-out": "DeepSeek 输出单价（元/百万 token）",
  "set-local-in": "本地模型输入单价（元/百万 token）",
  "set-local-out": "本地模型输出单价（元/百万 token）",
  "set-lib-dir": "模块库目录",
  "set-masters-dir": "母版库目录",
  "set-uv4-path": "Keil UV4 路径（留空自动探测）",
  "set-gmake-path": "gmake 路径（留空走 PATH）",
  "set-ccs-sdk-dir": "CCS SDK 目录（留空自动探测）",
  "set-ccs-compiler-dir": "CCS 编译器目录（留空自动探测）",
  "set-ccs-sysconfig-cli": "SysConfig CLI 路径（留空自动探测）",
  "set-openocd-path": "OpenOCD 路径（STM32，留空走 PATH）",
  "set-stflash-path": "st-flash 路径（STM32 备选，留空走 PATH）",
  "set-dslite-path": "DSLite 路径（MSPM0/XDS110）",
  "set-local-llm-base-url": "本地 LLM base_url",
  "set-vision-base-url": "视觉 base_url",
  "set-vision-model": "视觉模型",
  "set-vision-api-key": "视觉 API key（跟随上方选择自动填）",
};

export function applyInputA11y(root) {
  const doc = root && root.querySelector ? root : document;
  for (const [id, label] of Object.entries(INPUT_A11Y_LABELS)) {
    const el = doc.querySelector("#" + id);
    if (!el || el.hasAttribute("aria-label")) continue;
    el.setAttribute("aria-label", label);
  }
}

if (typeof window !== "undefined") {
  Object.assign(window, { INPUT_A11Y_LABELS, applyInputA11y });
}
