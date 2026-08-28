# 参数速调 UI 网格卡片流：前端实现（param-grid/01）
Status: resolved

## 背景

fx/params.js `paramListHTML` 现为单列行布局（.param-table/.param-row，12 参数 = 12 行）。用户确认改为网格卡片流（spec 见 `.scratch/param-grid/spec.md`）。

## 改动

### 1. fx/params.js `paramListHTML`
- 行结构 → 卡结构（签名 `paramListHTML(params, opts={running, emptyScan})` 与 opts 契约不变）：
```
<div class="param-grid">
  <div class="param-card [param-stale]">
    <div class="param-card-head">
      <span class="slug">NAME</span>
      <span class="param-label" title="全文">含义截 24 字…</span>
    </div>
    <div class="param-card-body">
      <input class="param-input" id="params-input-NAME" value=old [disabled] />
      <button class="btn-params-apply" data-param-name="NAME" [disabled]>改并验证</button>
      <!-- valid=false 时按钮换 <span class="badge param-stale-badge">锚已失效</span> -->
    </div>
    <div class="param-hint">范围：…　单位…</div>  <!-- 空则无此段 -->
  </div>
</div>
```
- label：`truncate(label || oldValue, 24)` + `title` 全文本；slug 不截断。
- hint：range_hint 有 → 「范围：」前缀；unit 有 → 独立小段；两段用 「　」 连接（沿用原拼接）。
- 空态两分支 / data-param-empty / id 契约注释（`params-input-<name>` 两处同步）全部保留。

### 2. index.html CSS
- 删旧规则：`.param-table`、`.param-row`、`.param-row:last-of-type`、`.param-row .slug`、`.param-label`、`.param-input`（旧 110px）。
- 新增：`.param-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:8px}`、`.param-card{border:1px solid var(--border);border-radius:8px;padding:8px 10px;background:var(--panel-2);display:flex;flex-direction:column;gap:6px}`、`.param-card-head{display:flex;align-items:baseline;gap:6px;min-width:0}`、`.param-card-head .slug{font-family:var(--mono);color:var(--accent);font-size:12px}`、`.param-card-head .param-label{flex:1;min-width:0;font-size:13px;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}`、`.param-card-body{display:flex;gap:6px}`、`.param-card-body .param-input{flex:1;min-width:0;font-family:var(--mono)}`、`.param-card .btn-params-apply{white-space:nowrap}`。
- 保留：`.param-hint{font-size:12px}`、`.param-stale{opacity:.65}`、`.param-stale-badge{background:var(--warn-dim);color:var(--warn)}`、`.btn-params-apply{font-size:12px;padding:2px 10px}`。
- 全部既有变量（--border/--panel-2/--text/--muted/--accent/--warn*/--mono），零新硬编码色。

### 3. tests/js/params.test.mjs
- 6 处既有调用断言全部跑一遍，引用 .param-row/.param-table 的改为 .param-grid/.param-card。
- 补断言：卡数 = 参数数；label 截断 + title 全文；hint 两段（「范围：」/「单位」）；invalid 卡内 badge 无按钮。

### 4. fx-guard
- paramListHTML 已登记，签名不变，无需改。

## 验证

- `node --test tests/js/params.test.mjs` → 全绿；JS 全量 597+。
- 实机探针 .scratch/param-grid/probe-param-grid.mjs（playwright file:///，加载 2024H 工程目录）：参数卡以网格渲染（≥2 列），改值→应用→结果面板正常，回滚恢复现场；截图看效果。
- 双轴评审（standards + spec 子代理）→ 整改 → 提交（中文提交信息，spec/issues 随提，探针不提交）。
