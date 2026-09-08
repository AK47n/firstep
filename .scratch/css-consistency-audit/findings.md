# CSS 一致性审计（视觉语言散乱证据）

- 仓库：`src/contest_generator/static/`
- CSS 全部在单文件 `index.html` 的 `<style>`（约 3000+ 行）内，无独立 .css；JS 为纯函数渲染 HTML（可能带内联 style）。
- 主题令牌定义位置：`:root`（index.html:29-58）、`html[data-theme="light"]`（60-83）、pin 色 `:root`（935-947）。
- 令牌已覆盖基础色/阴影/动效，但大量"裸露值"散落在规则与 JS 内联中，未走 `var(--*)`。

---

## 1. 圆角语言

`border-radius` 值分布（index.html 内约 137 处）：
- `999px`（胶囊）：搜索框165、brand-cn 121、mc-offtag/plat/deps/pa 245/252/257/259/294、sugg-discuss-toggle 426、sugg-discuss-input 451、chip 464、btn-global-chat-action 471、sugg-discuss-send 474、sugg-discuss-custom 480、参数 chip 560、#btn-score-export 745、pin-avg 981、task chip 1089、master-health-pill 1137、ov-chip 1198/1249、ov-fill/ov-generate 1285/1290、#btn-recent-refresh 1304、recent-platform 1319、card-step-status 1331、revise-tab 1361/1370、step-nav 1533、#btn-theme 1706。
- `50%`（正圆）：step-no 130、env-badge 192、spinner 788、stepper dot 801、radio 884/893、ov-dot 1254、recent-status-dot 1313。
- `8px`（标准卡片/控件）：.card 153、input 162、button 175、platform-card 200、.item 215、module-card 235、add-section 340、#compile-banner 352、param-card 536、distill-progress 796、instance-mod 1016、recent-wf-summary 837、res-table 1410、score-point-table 1428、topic-edit 1112 等。
- `10px`（半大面板）：.badge 206（chip!）、.fix-tag 369、score-panel 573、group-card 579、sp-summary 725/735、prog-warning 817、topic-card 1077、pin-capture 967/971、#readiness-check 1518、card-group 1346。
- `12px`（大圆角）：chip.rec code 384、sugg-discuss-box 430、sugg-msg 437、sugg-panel 460、lib-chip 642、task-dialog 1243、ov-panel 1300。
- `6px`（控件/行）：button 175、textarea/input 162、module-info-off 283、lib-edit-old 320、fix-row 364、decision 774、pin-role 955、res-table td 1416、score-point 1434、task-check-details 1446、diff-hunk 1496、code-line 1636。
- `4px`（小控件）：ref-pick-row 597、file input 882、小 text 902、topic-kw 1109、code-zoom-btn 1656、inline img 1759。
- `3px`（极小微）：.prog-bar 811、.pin-legend .dot 952、.role-type 963。
- `2px`：nav 下划线 142。`99px`：tasks-overview-bar 1398。`0`：226、1650。

**发现清单**：
1. 卡片/面板三种半径并存（8/10/12），无语义规则。同类"border 1px+padding 卡"：`.card`=8px，`.score-panel`/`.group-card`/`.topic-card`/`#readiness-check`=10px，`.lib-chip`/`.sugg-discuss-box`/`.sugg-panel`=12px。同是卡片半径却 8/10/12 三档。
2. 徽章/标签半径分裂：`.badge`(206)=10px、`.fix-tag`(369)=10px、`.lib-chip`(642)=12px，而 mc-offtag/plat/deps/pa、`.recent-platform`、`.revise-tab-badge`=999px，`.role-type`(963)=3px。同一个"小标签"概念用了 3/10/12/999px 四档。
3. 按钮半径分裂：base button + `.primary`(175/178)=6px 方角；而小字胶囊、ov-actions、discuss、#btn-score-export/#btn-recent-refresh、#btn-theme 全=999px。按钮并无统一半径。
4. 输入控件分裂：text/textarea/select=6px，search=999px，file input/小 text=4px。
5. `99px` 与 `999px` 并存（1398 用 99px，全文件仅此一例）；`3px` 与 `4px` 微圆角并存（pin-legend dot/role-type=3，但 ref-pick-row/file-input=4）。

**建议动作**：建 radius 令牌（`--radius-xs:4px / --radius-s:6px / --radius-lg:8px / --radius-xl:12px / --radius-pill:999px / --radius-circle:50%`）。卡片统一 `--radius-lg(8px)`（把 10/12 卡片归并）；徽章/标签统一 pill(999) 或 `--radius-s`；输入统一一个档次；按钮归并方角/胶囊两档；99px→999px；3px/4px 微圆角收敛为一档。

---

## 2. 间距节奏

基准刻度集中在 4/6/8/10/12/14/16/20/24。偏离的"魔法值"——5/7/9/3px 高频散布在 margin/padding。

**发现清单（文件:行号 + 值 + 问题）**（index.html，除注明外）：
1. `index.html:175` `button { padding: 7px 14px }` —— 全局基底按钮垂直 7px（奇数），且与下方小字按钮的 pad 无关联。
2. `index.html:343` 加区按钮 `padding: 9px 12px` —— 9px 偏离 4/8/12 刻度。
3. `index.html:955` `.pin-role { padding: 7px 12px }`、`364` `.fix-row { padding: 7px 12px }`、`437` `.sugg-msg { padding: 7px 11px }` —— 7px 垂直/水平。
4. `index.html:190` `.env-row { padding: 5px 0 }`、`283` `.module-info-off { padding: 5px 10px }`、`749` `.sp-item { padding: 5px 8px }`、`859` `.ref-files-list li { padding: 5px 14px }`、`871` `.ref-files-filter { padding: 5px 8px }`、`1285` `.ov-fill { padding: 5px 14px }`、`1290` `.ov-generate { padding: 5px 16px }` —— 5px 垂直档大量使用。
5. `index.html:1249` `.ov-chip { padding: 4px 9px 4px 5px }` —— 9 与 5 同现。
6. `index.html:485` `.btn-param-ref { padding: 1px 7px }`、`264` `.mc-add { padding: 1px 7px }` —— 7px 水平（同族小胶囊是 8px）。
7. `index.html:1706` #btn-theme 内联 `padding: 6px 9px` —— 9px。
8. `index.html:1158` `.master-copy-btn { padding: 3px 12px }` —— 3px 垂直。
9. 散落 `margin-top: 3px`(`960`/`753`)、`margin-top: 2px`(大量)、`margin-bottom: 2px` —— 2/3px 未归一。
10. JS 内联 `margin-top/bottom: 2/3/4/5/6/8/10px` 反复出现（见第 6 节）。

**建议动作**：定义 space 刻度（`--sp-1..--sp-4: 4/8/12/16`，或加 `--sp-05:2px`）。把 5/7/9/3 收敛到最近刻度；不同档的按钮/胶囊分别统一（1px·8px / 3px·12px / 5px·14px / 7px·14px 各定一档）；`margin-top:3px/5px` 并入 4px 或 6px。

---

## 3. 颜色（裸色值 vs var(--*) 令牌）

**发现清单**（均为：index.html:行号（未注明则为 .html）+ 值 + 问题）：

### #04222b（on-accent 文字色，既有约定）
出现 7 处：`130` `.step-no color`、`178` `.primary color`、`179` `.primary:hover`、`476` `.sugg-…-send color`、`479` `send:hover`、`889` checkbox 勾 `border`、`893` radio `background`。
- 问题：值一致（好事），但硬编码、无 `--on-accent` 令牌，任何暗/亮主题都无法在此统一调整。

### #0096c7（亮色 --accent）
`66` 为 `--accent` 令牌（合法）；`1665` `.tok-tag`、`1671` `.tok-kw` 硬编码复制了该值。
- 问题：语法高亮块重复硬编码 accent，未用 `var(--accent)`。

### 渐变硬编码（非令牌）
- accent 青族 `#00d4ff/#00a8cc/#33dcff/#00b8de/#0094b5`：`1041/1045/1060/1217/1234/1264/1268/1539`——重复 accent 令牌值。
- 绿"完成"族 `#34d399/#059669`：`1221/1234/1268`——**完全不在令牌集**（ok 令牌是 `#3fb950`/`#7ee787`），是第三方值当"完成绿"渐变用。

### 其它散落裸色
- `#8b5cf6`（143 nav active 渐变紫）—— 无令牌、无亮色变体。
- `#e2e8f0`（724 `pre.result` 文字）—— 硬编码浅灰、无亮色覆盖 → 亮色主题下代码结果可读性差。
- `#fff`：105（selection 文字）、192（env-badge）、805（stepper done）、1122（tooltip bg）、1759（inline）。
- `#001018`/`#04170c`：1216/1220/1263 —— 渐变文字色，硬编码。
- 紫色族散落 **5 个不同值**：`#8b5cf6`(143)、`#bc8cff`(1662/1664)、`#d2a8ff`(`--pin-exti` 943，暗色独有)、`#a371f7`(`--pin-uart` 939)、`#8250df`(1666, light tok)。

### .tok-* 语法高亮整族硬编码（1660-1672）
- 部分复制已有令牌：`--muted #8b949e`(`1661`)、`--ok #3fb950`(`1660`)、light `--warn #9a6700`(`1667/1669`)、light `--ok #1a7f37`(`1668`)、light `--muted #59636e`(`1670`)、light `--accent #0096c7`(`1665/1671`)。
- 部分为新值：`#d29922`(1660/1664)、`#bc8cff`(1662/1664)、`#8250df`(1666)。整块远离其它令牌定义区。

### rgba 裸值大量（未走 --*-dim 令牌）
- accent 青 `rgba(0,212,255,.xx)` 约 25 处：`85?/105/114/116/144/1043/1046/1048/1054/1055/1061/1064/1065/1070/1212/1215/1218/1261/1265/1341/1366/1368/1375/1534/1540`；亮色 `rgba(0,150,199,.xx)`：`66/81/85/106`。
- 灰 `rgba(139,148,158,.xx)` 约 10 处：`212/213/255/258/297/360/373/392/572/686/1405/1406`。
- 遮罩 `rgba(0,0,0,.6/.88)`：`268/310/784/847/996/1405?`。
- 问题：`--accent-dim/--ok-dim/--warn-dim` 已有，但 glow/阴影/选中/遮罩仍用裸露 rgba，且灰 rgba(139,148,158) 没有对应令牌。

### 内联 fallback 色值与令牌冲突
- `index.html:1974` 与 `fx/flash.js:52/54`：`var(--warn, #e6a23c)` —— 兜底 `#e6a23c` 既非暗 `--warn(#e3a341)` 也非亮 `--warn(#9a6700)`，是第三方值。
- `index.html:2620`/`1759`：`var(--border, #333)` 与 `var(--border, #ccc)` —— **两个不同的兜底**。
- `ui/generate-recommend.js:905`：内联 `background:#d1fae5`（轻绿）—— `index.html:617` 注释称 JS 内联 `#d1fae5` 需 !important 反压。硬编码 + 反压，双处维护。

**建议动作**：新增令牌：`--on-accent:#04222b`、`--code-text`、`--syntax-*`（整族进 :root，暗/亮各一套）、`--accent-glow/--overlay-mask`；把渐变青/绿族收进 :root；合并紫色族为一枚 `--purple/--purple-soft`；内联 fallback 统一为与暗令牌一致（`var(--warn, #e3a341)`、`var(--border, #30363d)`）；删除 JS 里 `background:#d1fae5` 的硬编码或用 `var(--ok-dim)`。

---

## 4. 字体

任务给定"标准系列"= 11/11.5/12/12.5/13/14/15/16。偏离值：
- `10px`：mc-offtag/plat/deps/pa `245/252/257/259/294`、`.stepper .dot` `803` —— 低于 11 的微标签档。
- `10.5px`：`.sugg-msg .muted` 449、`.param-current-label` 561、`.ov-chip .ov-dot` 1256、`.revise-tab-badge` 1370。
- `13.5px`：add-section-head 344、`.score-row` 577、ref-detail 609、`.es-title` 1071、`.topic-detail-problem` 1111 —— 内容正文本，与 13/14 并存。
- 大 glyph 档：`.ref-files-close` 18px(856)、header h1 20px(110)、`.es-icon` 30px(1069)；code 用 `1em`(1594/1601，正常)。

**主要散乱**：
1. "正文/说明"字号 13 / 13.5 / 14 / 15 四档混用（同一角色：body 内容 13-13.5、说明/卡片正文 14、ref-detail-title 15）。
2. "次要/微标签"字号 10 / 10.5 / 11 / 11.5 四档混用。
3. 标题无统一阶梯：h1=20 / h2=16 / h3=13 / `.ref-detail-title`=15 / `.es-title`=13.5。
4. 12px 与 12.5px 被当作两种"次要文字"并存（.muted=12、sugg-note=12.5、lib-stats=12.5 等），几乎无区分度。

**建议动作**：定文字等级（`--fs-xs:10.5 / --fs-sm:11.5 / --fs-base:13 / --fs-md:14 / --fs-title:16 / --fs-head:20`）；13.5 归并到 13 或 14；10/10.5 归并到 11；标题建阶梯。

---

## 5. 过渡动效

- 18 处 `transition:` 中 **16 处**已用 `--dur-*/--ease-ui` 令牌（良好）。
- 未用令牌的 2 例：
  - `index.html:813` `.prog-bar > div { transition: width .4s; }` —— 硬编码 `.4s`，无统一 ease。
  - `index.html:1541` `.rc-… { transition: width .4s ease; }` —— 硬编码 `.4s ease`。
- 另有 5 例 `transition: all …`：`1200/1206/1252/1258/1364` —— 虽用令牌，但 `all` 属性面过宽（性能/精确度差）。

**建议动作**：`.4s(=400ms)` 归入 `--dur-slow(300ms)` 或新增 `--dur-x2:400ms`；`transition: all` 改为具体属性（transform/opacity/color/border-color）。

---

## 6. 内联样式（fx + ui）

**fx/*.js**（约 25 处）：
- 绝大多数是 spacing 覆盖：`style="margin-top/bottom: 2/3/4/6/8/10px"` 加在 `.muted/.item/.row/.reason/.seg` 上：`diff.js:42`、`flash.js:28/32/64/74/102/104/106`、`module.js:32/181`、`params.js:102`、`task.js:99/126/134/185/198/212/223/235/272/286/353/361/389/484/515/554/622/644/647/664/819/862/881/913/915`。
- `flash.js:52/54` 内联 `color:var(--warn, #e6a23c)`（兜底错值，同第 3 节）。
- `task.js:272` `width:${…}%`（动态，合理）；`flash.js:28/39` `font-weight:600`。
- **问题**：是"重复魔法间距"，未走 space 刻度，且大量重复（margin-top:6px 出现 ~15 次）。

**ui/*.js**：
- `ui/generate-pins.js:872` 内联重写 `.pin-legend .dot` 已在 CSS 定义的几何（`width:10px;height:10px;border-radius:3px`）—— 内联复制类定义而不是复用 `.dot`（`488/501` 才是正确复用 `.dot`）。
- `ui/files.js:19-21` 手搓关闭按钮 `style="position:absolute;right:4px;top:4px;font-size:11px;padding:2px 6px"` —— 裸值按钮，未用任何按钮类。
- `ui/generate-recommend.js:905` 内联 `background:#d1fae5`（硬编码轻绿 + CSS 反压）。
- `ui/generate-pins.js` 大量内联动态着色 `color:${st[0]}/background:${var}/border`（`488/501/704/708/712/714/717/723/872/888/892`）—— 部分动态色属合理内联，但 `.dot` 复用混乱。
- `ui/reference.js`、`ui/master.js`、`ui/generate-revise.js`、`ui/topic.js`、`ui/library.js`、`ui/generate-tasks.js`：大量 spacing（margin-top/bottom 4/6/8/10/12）、`flex:1`、`width`、`cursor:pointer`、`display:none` 内联。
- `ui/master.js:31`：`class="danger"` + `style="padding:2px 8px"`（内联覆盖按钮 padding）。

**建议动作**：抽一组工具类（`.mt-2/4/6/8`、`.flex-1`、`.row-gap-*`、`.cursor-pointer`、`.text-xs`），把静态 layout/spacing/font 内联换掉；只有动态色/宽度（pin 色、`width:${%}`）保留内联；`files.js` ✕ 与 `master.js` 移除钮改用 `.btn-icon/.btn-pill`；`.dot` 一律复用 CSS 类。

---

## 7. 按钮形态

`.btn-*` 与 `button.primary/danger/pin-overview-on`、`#btn-*`、各 `.ov-*/.rc-*` 实际分成 **至少 6 档**：

| 档 | 定义（行号） | 值 |
|---|---|---|
| F 全局基底 | button 175, primary 178, danger 180, pin-overview-on 182 | `7px 14px`, 半径`6px` |
| A 小字胶囊 | btn-task-dialog-adopt/clear 463, btn-global-chat-action/send 469, btn-params-chat-send 469, btn-task-edit-save/cancel 506, btn-task-more 508, btn-param-ref 485, btn-draft-* 529, btn-params-apply/rollback 554, btn-params-reset 566 | 多为 `font 12px, 1px 8px, 999px` |
| B 强调发送 | btn-task-dialog-send/global-chat-send/params-chat-send/sugg-discuss-send 473 | `13px, 8px 18px, 999px, accent bg` |
| C 自定义 | sugg-discuss-custom 480 | `12.5px, 7px 14px, 999px` |
| D ov-actions | ov-fill 1285, ov-generate 1290 | `12.5px, 5px 14px / 5px 16px, 999px` |
| E 小型动作钮 | #btn-score-export 745, #btn-recent-refresh 1304, pin-toggle-optional 962, rc-recommend/rc-go 1532 | `12px, 3px 12px / 3px 10px / 2px 10px, 999px` |

**发现清单**：
1. 圆角分裂：F 档 6px，其余全 999px —— 没有"按钮半径"统一。
2. 小字胶囊档（A）内部不一致：
   - `btn-param-ref`(485) `1px 7px`（应 8px 同族）；`btn-params-apply/rollback`(554-555) `2px 10px`（应 1px 8px）；`btn-params-reset`(566) `font 11.5px`（应 12px）；`master-copy-btn`(1158) `3px 12px`（大幅偏离）。
   - 同一类 `.btn-global-chat-send/.btn-params-chat-send` 在 469 与 473 **两条规则里被定义两次**（小字 + 发送覆盖），靠覆盖关系维持，维护易错。
3. 图标钮：`button .btn-ico`(931) is 15×15 SVG glyph（fx/btn-icon.js）；`.code-zoom button`(1654) `22×22, 4px`；`#btn-theme`(1706) 内联 `6px 9px, 999px` —— 图标钮几何/半径各不相同。
4. 手搓内联按钮：`ui/files.js:21`（✕）、`ui/master.js:31`（移除钮 `class="danger" + style`）、`#btn-theme`(1706) —— 均未走按钮类。

**建议动作**：收敛为 3 个语义类：`.btn`（方角 base，`--radius-m`）、`.btn-pill`（999 胶囊，分 `.btn-pill--sm`(12px/1px8) 与 `.btn-pill--md`(12.5px/5px14)）、`.btn-icon`（统一 24px 或 28px + `--radius-s`）；每档统一 padding/font/radius；废除内联样式按钮（#btn-theme / files.js ✕ / master.js 移除钮）改用上述类；删除 469/473 的类重复定义，改单一规则。

---

## 结论（跨维度）
- 主题令牌框架**已存在且较完善**（色/阴影/动效均令牌化），但**执行不彻底**：圆角（8/10/12 卡片、999 vs 6 按钮、3/4/10/12 标签）、间距（5/7/9/3px 魔法值）、字号（10/10.5/13.5 越档、4 档正文）、颜色（on-accent #04222b 7 处裸值、语法高亮整族、渐变族、rgba 裸值、内联 fallback 错值）、过渡（2 处 .4s 硬编码、5 处 `all`）、JS 内联（大量 spacing/布局/cmd 内联）均未走令牌或类。
- 统一钥匙：新增 radius/space/font/on-accent/syntax/glow 令牌 + 一组工具类；按钮收敛为 3 类；把 6 档按钮、3 档圆角卡片、4 档正文字号各归并。
