# 参数速调 UI 改版为网格卡片流（param-grid）

## 问题陈述（用户反馈）

参数速调卡现状（工单 param-tune/02）：`paramListHTML` 每个参数一行——`参数名 | 含义 | 输入框 | 建议范围 | 「改这个并验证」按钮`（.param-table 单列行布局）。2024H 实机识别出 12 个参数 = 12 行，垂直空间占用大、一行内信息密度低（每行只有名字/值/按钮三个有效元素）。用户提问「如果把它做成长片的话会不会更省空间更好看一点」，经确认选择**网格卡片流**（用户多选答案：网格卡片流（推荐），明确否决横向长条滚动与单行压缩）。

## 目标

1. 参数从「一行一个」改为「一卡一格」的响应式网格：宽屏 3 列、窄屏 2 列、手机 1 列（`repeat(auto-fill, minmax(230px, 1fr))` 实现——无需断点手写，自适应）。
2. 每卡视觉层级清晰：参数名（等宽小字）+ 含义（小字截断、title 全文）+ 输入框（卡宽）+ 建议范围/单位提示（小字）+ 「改这个并验证」按钮。
3. 无效参数（valid=false）处理不变：卡置灰 + 输入禁用 + 「锚已失效」徽章。
4. 行为零变化：id 契约（`params-input-<name>`）、按钮 data-param-name、事件委托、busy 禁用、空态两分支全部保持——只改呈现层（fx 纯函数 HTML 结构 + CSS）。

## 实现决策

### fx/params.js
- `paramListHTML` 行结构 → 卡结构（函数签名与 opts 契约不变）：
```
<div class="param-grid">
  <div class="param-card [param-stale]">
    <div class="param-card-head">
      <span class="slug">NAME</span>
      <span class="param-label" title="全文">含义截断…</span>
    </div>
    <div class="param-card-body">
      <input class="param-input" id="params-input-NAME" value=... [disabled] />
      <button class="btn-params-apply" data-param-name="NAME" [disabled]>改并验证</button>
      <!-- valid=false: 按钮位置换成 <span class="badge param-stale-badge">锚已失效</span> -->
    </div>
    <div class="param-hint">范围：…　单位…</div>   <!-- 空则无此行 -->
  </div>
</div>
```
- 含义 label 截断：`truncate(label, 24)` + title 全文（悬停看全）；slug 不截断（等宽小字，超长 title）。
- hint 组装不变（range_hint + unit 拼接），前面加「范围：」前缀（有 range_hint 时）；unit 单独段（有 unit 时）——语义更清楚。
- 空态两分支、data-param-empty、id 契约注释全部保留。

### index.html CSS
- 新增：`.param-grid`（display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:8px）、`.param-card`（border:1px solid var(--border); border-radius:8px; padding:8px 10px; background:var(--panel-2); display:flex; flex-direction:column; gap:6px）、`.param-card-head`（flex align-items:baseline gap:6px）、`.param-card-body`（flex gap:6px；input flex:1 min-width:0）、`.param-card .param-input`（width:100% 或 flex:1）、`.param-card .btn-params-apply`（white-space:nowrap）。
- 保留既有类（.param-stale 置灰 / .param-stale-badge / .param-hint / .btn-params-apply 字号）语义不变；删 .param-table/.param-row/.param-row:last-of-type/.param-row .slug/.param-label/.param-input 旧规则（或改写在 .param-card 作用域下）。
- 全部用既有 CSS 变量（--border/--panel-2/--text/--muted/--accent/--warn*），零新硬编码色。

### 测试
- tests/js/params.test.mjs：现有断言若引用 .param-table/.param-row 结构 → 改为 .param-grid/.param-card（卡数 = 参数数；卡内含 slug/label/input/按钮/失效徽章）。补断言：label 截断 + title 全文、hint 两段（范围：/ 单位）、网格容器结构。
- fx-guard：paramListHTML 已登记，签名不变，无需改。

## 范围外
- 参数分组（按功能域分类折叠）——需要后端识别加 category 字段，本期不做。
- 编辑入口（直接在卡上改名/改锚）——参数表由 AI 识别生成，手动编辑锚有风险，不做。
- 横向滚动长条 / 单行压缩（用户已否决）。

## 交付
- `.scratch/param-grid/issues/01-frontend-grid.md`（fx + CSS + 测试 + 探针）
- `.scratch/param-grid/issues/02-docs-regression.md`（CONTEXT.md 词条 + 全量回归）
