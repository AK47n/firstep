# 05 — 发布后：CI 浏览器门禁在发布提交上判红（夹具级 `route.continue` 双处理）

**要做什么：** 2026-09-29 的发布提交（`d527c65c`）在 CI 上**浏览器门禁 job 判红**，而**同一份代码本机两次整支 61/61 全绿**。
本单把根因钉到夹具层并处置（发布本身已经完成，这是发布后当场逮到的账）。

**被谁阻塞：** 无——发布（`01`–`04`）已完成。

**状态：** claimed

- [x] 复现不了的先取证：把 CI 失败日志整份落盘、把红点定到具体文件与钩子
- [x] 定位到机制（不是"随机红"）：`tests/browser/hwcheck.spec.mjs` 那条路由桩的迟到 `continue()`
- [x] 按既有先例处置（`launcher-reload.spec.mjs` 的 `.catch(() => {})`），并把 CI 现场写进用例注释
- [x] 本机复跑该 spec，确认没改坏
- [ ] **CI 复跑绿**（只在推送后才知道；本机复现不出来，见下）

## Comments

### 现象（只认 CI 日志原文；`gh run view 36526949726 --log-failed`）

```
# Error: Test hook "before" at tests\browser\hwcheck.spec.mjs:45:6 generated asynchronous
  activity after the test ended. This activity created the error
  "Error: route.continue: Route is already handled!" and would have caused the test to fail,
  but instead triggered an unhandledRejection event.
not ok 3 - tests\browser\hwcheck.spec.mjs      (duration_ms: 201541, failureType: testCodeFailure)
# fail 1   ← 整支 61 条里只红这一条，而且是**文件级**
```

- 同一 job 的 41 条用例（`ok 1` … `ok 41`）**自己全绿**，`ok 43` 起是下一个 spec（`launcher-reload`）也绿。
- 另两条腿全绿：全套 pytest（windows）✓、快速守卫（ubuntu）✓。
- 本机同一份代码同一命令跑了两次（发版前一轮、推 tag 时 pre-push 一轮）都是 **61 / 0**。

### 根因（机制，不是猜测）

`tests/browser/hwcheck.spec.mjs` 的「动作进行中按钮禁用」用例：

```js
await page.route("**/api/hwcheck/preview", async (route) => {
  await new Promise((r) => setTimeout(r, 1500));   // ← 先睡 1.5 秒
  await route.continue();                          // ← 醒来才结算
});
await page.click("#btn-hwcheck-preview");
await page.waitForFunction(() => btn.disabled, …, { timeout: 10000 });
await page.unroute("**/api/hwcheck/preview");       // ← 用例很快就 unroute 了
```

这 1.5 秒里那一发请求**可能已经被别的通路结算**（`unroute` 之后的默认通路；或后续整页 `goto` 把它废掉），
于是迟到的那次 `continue()` 抛 `Route is already handled!`。它发生在 `test.before` 建的那份异步上下文里
⇒ node:test 判定「钩子产生了测试结束后的异步活动」⇒ **文件级**判红。

**同类形态在本仓库已有两处记载**：`ui-density-sitewide` README 纪律第 2 条（"同一个 spec 文件里别混用整页
`goto` 与路由桩——会让文件级抛 `unhandledRejection`，而每条用例自己全绿"），以及本文件 1609 行那条用例
注释（它为此刻意不调 `openTab()`）。**这是同一个病根的第三种发作方式**。

### 处置

```js
await route.continue().catch(() => {});
```

照 `launcher-reload.spec.mjs:240` 的既有先例——**只吞掉这一次"迟到"，语义没变**（请求该走哪条路早走完了）。
同时把 2026-09-29 的 CI 现场写进那条注释（下一次读到的人不必重新推一遍）。

### 读数

| 项 | 读数 |
|---|---|
| 本机复跑该 spec（改后） | **38 passed / 0 fail**（115.5s）— `hwcheck-spec-after-fix.txt` |
| 本机整支（改前，两次） | **61 / 0**（发版前 170.6s；推 tag 时 189.9s） |
| CI（改前，发布提交） | 60 passed + **1 条文件级红**（run `36526949726`） |
| CI（改后） | 待推上去才知道 |

### 一条必须写清的边界

**本机复现不出来**（两次整支 61/61）——所以这次是**按机制去掉**，不是"按复现验证"。
判据只有一条：**CI 复跑绿**。若同一形态再出现，按"文件级 `unhandledRejection`"这条线查
（先看 `route.*` / `resp.text()` 这类没结算的异步），**别去查产品**——41 条用例本身全绿就是证据。
