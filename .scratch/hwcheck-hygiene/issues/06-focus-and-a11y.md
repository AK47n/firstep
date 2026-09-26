# 06 — 焦点与可达性：勾完还在原位、键盘能用、长任务有话说

**要做什么：** 学生连续勾十几项时**光标还停在刚勾的那一项上**（不再被整块重绘甩回页面开头）；
用键盘也能完成同样的选择；三个只有 placeholder 的输入有真正的无障碍标签；
编译 / 烧录这类要等的动作有可被读屏念出、可被看到的忙碌态。

**被谁阻塞：** 无——可立即开始。**拆分单（11）被它真阻塞**（焦点与 aria 的行为要在大文件里先落地，
拆完再改会让 diff 散在四个新文件里）。

**状态：** ready-for-agent

**来源**：评审 P2-8（Y4）。

## 现状（实测）

- **勾选后丢焦点**：清单 / 器件集回调整块 `innerHTML` 重绘（`ui/hwcheck.js` 的
  `renderHwcheckChecklist` / `renderHwcheckDevices` 一带），刚按下的复选框被替换、焦点回 `body`；
  `#my-devices-list` 重绘同理。**ui 层全文零 `.focus()`**，而其它 15 个 ui 模块有先例
  （`codeeditor.js` 17 处、`codeview.js` 6 处、`confirm.js` 5 处 …）。
- **器件卡鼠标专用**：器件卡是 `div`、chip 是 `span`（`fx/module.js:333` / `:395`），无
  `tabindex` / `role` / 键盘；而**平台卡**补了 `role` / `tabindex` / keydown
  （`fx/hwcheck.js:90`、`ui/hwcheck.js:1032`）——同一页两套标准。
- **3 个输入没进无障碍表**：`#hwcheck-device-search`、`#hwcheck-parent`、`#hwcheck-symptom`
  只靠 placeholder（`static/index.html:4091` / `:4103` / `:4162`）；`INPUT_A11Y_LABELS`
  （`static/js/boot.js:497`）里零 hwcheck 条目。
- **长任务无进度 / 无 aria**：选器件 / 换平台期间的板侧刷新无 loading、无禁用；
  编译 / 烧录状态行（`fx/hwcheck.js:352-355`）无 `role="status"` / `aria-live`。

## 已拍板（spec 实现决策）

**改共享渲染件**：器件卡住在生成页 / 库页 / 检测页共用的 `fx/module.js` 里，
本轮**连它一起改**（一处改三处受益），改动同时受生成页与库页既有用例约束。

## 验收标准

- [ ] **焦点恢复**：勾选类重绘后焦点回到"刚操作的那一项"（记住 id → 重绘 → `.focus()`）；
      覆盖三处：上板清单、检测页器件集、`#my-devices-list`。
- [ ] **键盘可达**：器件卡可 Tab 到达、Enter/Space 生效（照平台卡已有的 `role`/`tabindex`/keydown 先例）；
      生成页 / 库页的器件卡行为**不回归**（既有用例全绿）。
- [ ] **无障碍标签**：3 个输入进 `INPUT_A11Y_LABELS`（照该表既有条目写法）；
      表单校验失败时错误与输入**有关联**（`aria-describedby` 或等价物）。
- [ ] **长任务有话说**：编译 / 烧录状态行加 `role="status"`（或 `aria-live="polite"`）；
      动作进行中按钮**禁用**（防重复提交）；板侧刷新有可见的忙碌态。
- [ ] **真浏览器用例**（测试缝已与用户确认：进真浏览器门禁，不新增源码串断言）：
      ① 勾一项 → `document.activeElement` 仍是那一项；② 键盘 Tab + Enter 能完成勾选；
      ③ 三个输入有 `aria-label`（按可访问名断言，不断言源码串）；
      ④ 编译 / 烧录进行中状态行有 `aria-live` 且按钮 `disabled`。
- [ ] **反证**：撤掉焦点恢复 → 对应用例红；复原后逐字节相同
      （`.scratch/hwcheck-hygiene/probe-06-red.mjs` / `probe-06-red.txt`）。
- [ ] 读数：`node --test "tests/js/*.test.mjs"` 与
      `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` 两个读数落盘
      （本单动 `static/js/ui/` 与 `static/js/fx/module.js`，两者都在浏览器门禁落点里）。
