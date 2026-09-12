# 05 — 真机验收：真浏览器点一遍「说明」入口（playwright）

**要做什么：** 把「点说明弹窗」这条链从「静态断言」升级为「真机作证」：真 python
后端 + 真 /api/modules + 真 SSE 解析 + 真渲染 + 真点击。纯函数测试能证明
「HTML 里有 data-mod-info」「代码写了 stopPropagation」，证明不了**点下去究竟
发生了什么**——本单第一版正是在这里翻车的（见下）。

**被谁阻塞：** 03。

**状态：** resolved

- [x] 真机夹具：起真后端（`FIRSTEP_LAUNCHER_PORT` 覆盖端口，不动用户默认端口；
      按进程树收服务），playwright chromium 驱动页面。
- [x] 零 LLM 额度：只拦 `/api/recommend` 回合成 SSE（线格式同 `sse._sse_frame`），
      其余全真；不直接调渲染函数（ui/* 按 app.js 规则 3 不挂 window 桥，从按钮走
      才是唯一不打洞的入口，也顺带把「按钮 → 载荷 → 渲染」整条链一起验了）。
- [x] 6 条用例：① 推荐 chip 点说明弹窗且**不移除模块**；② 弹窗四问分段 + 推荐理由 +
      引脚表/源码文件；③ Esc 与点遮罩都能关；④ 组卡成员行点说明**不误选 radio**；
      ⑤ 需求清单灰注 + 已选清单行同样能开；⑥ 回归：点 chip ✕ 仍移除模块。
- [x] 不进默认测试跑（`tests/js/*.test.mjs` 不含它）：改动推荐区交互时手动跑
      `node --test tests/browser/module-intro.spec.mjs`。

**真机验收当场抓到的 bug（本单最值钱的一条）：** 说明按钮嵌在 `.chip.rec`
（带 `data-remove`）里，第一版在容器上挂**冒泡阶段**委托并 `stopPropagation`
——真机点了之后**模块真的被移除了**（已选清单里 ir_beam 没了）。根因：chip 的移除
监听**挂在 chip 本体上**，与目标同元素的监听属 **target 阶段**，先于容器的冒泡
监听执行；冒泡阶段再拦已经晚了。改**捕获阶段**（`addEventListener(..., true)` +
`stopImmediatePropagation`）后 6/6 绿。

**这条 bug 为什么静态测试没抓到**：静态断言检的是「dist 里有 data-remove」「代码里
写了 stopPropagation」「按钮 HTML 里有 data-mod-info」——三条全过，而真实行为是错的。
**两个监听器的执行先后是运行时事实，不是文本事实。**
