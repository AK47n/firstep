# 01 — 平台卡重复点击/推荐后首选丢失推荐勾选

**要做什么：** `renderPlatforms` 点击处理器无条件清空下游选择；推荐完成后用户点平台卡
（重复点击或推荐后首次选择）会清掉刚勾选的推荐模块。加固：重复点击已选平台 = 无操作；
未选平台首次点击 = 保留选择只重展开；真实切换平台 = 维持清空重来语义。

**被谁阻塞：** 无。

**状态：** resolved

## 验收标准

- [x] `platformClickAction(current, clicked)` 纯函数：same（相等）/ first（null 当前）/
      switch（其余），tests/js/platform-click-action.test.mjs 单测绿（先红后绿）。
- [x] 点击处理器 `renderPlatforms`（index.html 约 1624-1647）改造：same → return；
      first → 保留 selectedSlugs/instances、清 expanded/warnings、unmark 6-12
      （5 保持）、runExpand()；switch → 原逻辑不动（unmark 5-12 + 全清）。
- [x] node --test tests/js 全绿（127 pass）；Python 全量 2257 passed（无 Python 改动）。
- [x] 提交信息中文。

## 实施记录

2026-08-24（用户报告「推荐好模块之后没有自动帮我选上」）：
- 排查：CDP 实测磁盘代码 + 真实 done 载荷（8/24 12:55 覆写的
  recommend_2024H.json）下自动勾选正常（`after: [motor,pid,led_beep,xunji]`）；
  根因 = `renderPlatforms` 点击处理器无条件清空下游（1631 行），用户推荐完成后
  点过平台卡（含重复点击）→ 推荐勾选被清，chips 区不受影响 → 呈现"没选上"。
- 修复：新增纯函数 `platformClickAction`（same/first/switch 三态）+ 点击处理器
  按三态分支（same 直接 return；first 保留选择并 runExpand；switch 维持原清空语义）。
- 验证：tests/js/platform-click-action.test.mjs（3 绿，先红后绿）；
  node --test tests/js 127 绿；pytest 2257 绿；
  CDP 端到端（headless Edge + 真实服务 + 真实缓存载荷）：afterRec/afterFirst/
  afterSame 均保持 4 模块，无报错。

## 评审记录

2026-08-24 自审通过：
- 三态分支与"换平台语义"兼容：switch 分支代码与原逻辑逐行一致（仅包进分支）；
- first 分支 unmark 不含步骤 5（推荐已完成不退步），`if (selectedSlugs.length)`
  守卫避免未推荐时误报"请先选择至少一个模块"；
- first 分支保留 instances（AI 回填的实例卡不被清），仅清 pinBindings 重取板定义；
- 静态文件改动即时生效（无需重启服务），但浏览器需刷新（Ctrl+F5）加载新 JS。
