# 04 — 括号彩虹色（嵌套深度着色）

**要做什么：** 括号配对按嵌套深度着色：一次扫描计算每个配对括号的深度（与既有 bracketPairAt 配对数据共用扫描，不重复 O(n)），标记层按深度映射色环（6-8 色 CSS 变量，深浅主题各一套）；当前光标对保持既有描边高亮，其余按深度着色；未配对/字符串内括号不误着色；仅 c/xml/md 编辑态（与既有括号门控一致）。

**被谁阻塞：** 无（与 11 性能工单在前置扫描复用上有交集——若 11 先落地增量，需兼容其缓存；本工单默认独立实现并保持深度计算 O(n) 一次）。

**Type:** task
**Status:** resolved

## Answer

已实现并验证（提交 97641dec，CHANGELOG 自动 e71cade8）：

- fx/code-brackets.js：新 `_bracketPairScan` 单次正向扫描产出 [{openPos, closePos, openChar, closeChar, depth, openLine/openStart/closeLine/closeStart}]（栈深 0 基、行列 1 基/0 基，跳过字符串/注释/字符，仅配真对）；`_bracketPairsOf`（bracketPairAt 配对表）与 `bracketDepthMarks` 均由它派生——假括号跳过规则单源，满足工单「共用扫描」；`bracketDepthMarks` 输出 {line,start,end,kind:"bracket-depth-N"}，N=深度%8（8 色环颜色索引），只输出真正配成的开闭字符（未配对/字符串/注释内不误着色）；
- ui/codeeditor.js：currentMarks 追加彩虹标记（bracketRainbowMarks 按 tab.content 引用缓存——光标移动零重算；门控 bracketRainbowLang = 可编辑 c/xml/md）；折叠视图经 marksForView 行号映射自动兼容；
- CSS：--bracket-rainbow-0..7 深浅主题各一套（:root 深色 rgba .33 / html[data-theme="light"] 亮色 rgba .30），kind 直出 .code-mark-bracket-depth-N；
- 优先级：bracket-depth-* 不登记 MARK_PRIORITY = 默认 0（最低，注释说明）——当前对描边 bracket(1)/选中词 word(1)/查找 hit(2)/current(3) 重叠时让位，「当前对描边优先」达成；
- 双轴审核整改：Standards 硬违规 0（最重 Duplicated Code：两栈扫描 → 已收敛 _bracketPairScan 共用；CSS 变量名 --br-* → 对齐工单 --bracket-rainbow-*；隐性优先级 → 注释明示）；Spec 无缺失/蔓延/错误（md 门控与「与既有括号门控一致」的张力——工单自身矛盾，实现向验收项「xml/md 生效」倾斜，注释说明取舍）；
- 验证：node 单测 15/15（深嵌套/字符串注释跳过/未配对不输出/8 色环取模/跨行）；全量 1219 pass；CDP 冒烟 smoke-04 9/9（深度 0..3 颜色互异 + 双主题 + 注释/字符串假括号不误色 + plain/txt 无 + md 编辑态生效 + 光标对描边仍优先）。

## 实现要点

- fx 纯件：括号深度计算（栈式一次扫描，跳过字符串/注释；输出配对表附带深度），node 可测（含字符串、注释、不配对、多层嵌套）。
- 标记层渲染分支：codeMarksHTML 输出带深度 class 的括号 span；CSS 变量 --bracket-rainbow-0..N（浅/深主题各一组）。
- 与既有单对描边高亮共存（当前对描边优先于彩虹色）。

## 验收 checklist

- [ ] `if(){while(){...}}` 多层括号逐层颜色不同；深浅主题均可见（各截图一张）。
- [ ] 未配对/字符串/注释内括号不误着色；xml/md 生效、plain/txt 不生效。
- [ ] 括号自动闭合/配对高亮/折叠无回归；node 单测深度计算全绿。

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
