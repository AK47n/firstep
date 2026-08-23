# 工单 04：生成中阶段播报

- Status: pending
- 依赖：无

## 目标

生成期间不再「干等」：`#gen-status` 显示阶段文案轮播 + 等待计时；修复中心
（fix 流 SSE）显示编译/修复/验证真实阶段。后端零改动（决策见 spec）。

## 实现

1. 纯函数（tests/js 可抽取）：
   - `genStageTexts(i)`：文案数组 `["正在选配模块…","正在定位母版…",
     "正在生成工程骨架…","正在写入工程文件…","正在生成摘要…"]`，
     返回 `texts[i % texts.length]`（i 非法兜底 0）；数组字面量内联。
   - `fmtWait(seconds)`：`0 → "0 秒"`、`1-59 → "N 秒"`、`≥60 → "M 分 N 秒"`；
     入参非法（NaN/负数）→ "0 秒"。
2. btn-generate 点击流程改造（L3131-3220）：
   - 校验阶段：`/api/bindings/validate` 请求前 `genStatus("正在校验引脚绑定…")`；
   - 生成阶段：`apiPost("/api/generate")` 期间起 `setInterval` 轮播
     （1.8s 切换 `genStageTexts`）+ 每秒更新计时 `fmtWait`（累计秒）；
     文案形如「正在生成工程… 已等待 12 秒」+ 当前子阶段；
   - 完成/失败/校验失败：`clearInterval` + 计时复位；成功时
     「工程生成完成，正在渲染结果…」（短促，随即清空，现状清空逻辑不变）。
   - 统一 `genStatus(text)` helper 写 `#gen-status`（保留 spinner 结构）。
3. 修复中心阶段播报（startFixCenter 现有 SSE 消费处）：
   - 读 fix 流事件：compile_start → 「正在编译…」；fix_start → 「正在应用修复…」；
     verify_result → 「正在验证…」；done → 「编译通过」/「仍有错误」。
     只读事件字段，不改 fix 流契约；写入修复中心横幅 `#fix-status`
     （无则建）。事件类型字符串以内联字面量匹配。
4. prefers-reduced-motion 不影响（无动画）。

## 测试

- tests/js/stage-report.test.mjs：genStageTexts（循环、越界、负数）、
  fmtWait（0/59/60/125/NaN/负数）各用例。
- 契约测试不动（#gen-status 结构不改）。

## 验收

点生成 → 状态区先「校验」再「生成中+子阶段轮播+计时」；完成后清空；
修复中心显示编译/修复/验证阶段；CDP 截图目检。
