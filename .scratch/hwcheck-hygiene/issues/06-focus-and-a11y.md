# 06 — 焦点与可达性：勾完还在原位、键盘能用、长任务有话说

**要做什么：** 学生连续勾十几项时**光标还停在刚勾的那一项上**（不再被整块重绘甩回页面开头）；
用键盘也能完成同样的选择；三个只有 placeholder 的输入有真正的无障碍标签；
编译 / 烧录这类要等的动作有可被读屏念出、可被看到的忙碌态。

**被谁阻塞：** 无——可立即开始。**拆分单（11）被它真阻塞**（焦点与 aria 的行为要在大文件里先落地，
拆完再改会让 diff 散在四个新文件里）。

**状态：** resolved

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

- [x] **焦点恢复**：勾选类重绘后焦点回到"刚操作的那一项"（记住 id → 重绘 → `.focus()`）；
      覆盖三处：上板清单、检测页器件集、`#my-devices-list`。
- [x] **键盘可达**：器件卡可 Tab 到达、Enter/Space 生效（照平台卡已有的 `role`/`tabindex`/keydown 先例）；
      生成页 / 库页的器件卡行为**不回归**（既有用例全绿）。
- [x] **无障碍标签**：3 个输入进 `INPUT_A11Y_LABELS`（照该表既有条目写法）；
      表单校验失败时错误与输入**有关联**（`aria-describedby` 或等价物）。
- [x] **长任务有话说**：编译 / 烧录状态行加 `role="status"`（或 `aria-live="polite"`）；
      动作进行中按钮**禁用**（防重复提交）；板侧刷新有可见的忙碌态。
- [x] **真浏览器用例**（测试缝已与用户确认：进真浏览器门禁，不新增源码串断言）：
      ① 勾一项 → `document.activeElement` 仍是那一项；② 键盘 Tab + Enter 能完成勾选；
      ③ 三个输入有 `aria-label`（按可访问名断言，不断言源码串）；
      ④ 编译 / 烧录进行中状态行有 `aria-live` 且按钮 `disabled`。
- [x] **反证**：撤掉焦点恢复 → 对应用例红；复原后逐字节相同
      （`.scratch/hwcheck-hygiene/probe-06-red.mjs` / `probe-06-red.txt`）。
- [x] 读数：`node --test "tests/js/*.test.mjs"` 与
      `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` 两个读数落盘
      （本单动 `static/js/ui/` 与 `static/js/fx/module.js`，两者都在浏览器门禁落点里）。

## 结论（读数与账）

**改了什么（三块）。**

| 那一块 | 落点 | 做法 |
|---|---|---|
| 焦点恢复 | `ui/hwcheck.js` 新增 `pendingFocusSelector` / `selectorValue` / `applyPendingFocus` | **谁触发重绘谁写目标**，渲染函数收尾统一落焦点；三处：上板清单勾选（回那一项）、器件集（加进→它的 chip / 移除→网格里那张卡）、`#my-devices-list`（加选→那一行 / 删除→「新建」按钮，因为那一行已经不在了） |
| 键盘可达 | `fx/module.js` 的**卡片**与 **chip** 加 `role="button" tabindex="0"`；`ui/generate-recommend.js`（模块网格 + 推荐 chip）与 `ui/hwcheck.js`（器件网格 + 器件 chip）各加 keydown 委托 | Enter/Space 与点击同义；`.mc-info` / `[data-mod-info]` 是真按钮，**排掉**免得一次按键开两次弹窗 |
| 无障碍与忙碌态 | `ui/a11y.js` 三条标签、`fx/my-devices.js` 表单错误 `id` + `aria-describedby`、`fx/hwcheck.js` 编译/烧录状态行 `role="status"`、`ui/hwcheck.js` 预览按钮进行中禁用 | 预览与生成**同一套** busy 规矩（按钮可见地不可点，函数内部那道早退只是兜底） |

**真浏览器用例（新 3 条，进 `tests/browser/hwcheck.spec.mjs`）**：无障碍名 / 焦点与可达性（勾选保焦点 +
器件卡 Tab→Enter→Space）/ 动作进行中按钮禁用。后两条**各自自带前提**（共用一张页面的用例集里，
前一条会把器件集清空）——第二条自己生成一遍检测工程再验。

**反证（三处注入，逐条点名 + 逐字节复原）**：撤掉焦点恢复 → 「焦点与可达性」红；撤掉卡片的
`role/tabindex` → 同一条红；撤掉标签表里「搜索要测的器件」那一条 → 「无障碍名」红。三次复原
sha256 全部逐字节相同、复原态回绿（读数 `probe-06-red.txt`）。

**读数（本机实跑，落盘在本目录）**：

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 前端门禁 | `node --test "tests/js/*.test.mjs"` | **1818 passed / 0 fail** | `probe-06-js.txt` |
| 浏览器门禁 | `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` | **48 passed / 0 fail**（≈246s；上一单 45，+3 = 本单新用例） | `probe-06-browser.txt` |
| 全套 pytest | `python -m pytest -n auto -q` | **5600 passed + 11 skipped**（≈218s；本单没加 pytest 用例，与上一单同数） | `probe-06-pytest-full.txt` |

**评审整改（Standards + Spec 轴，2026-09-26，**全部已改**）**：

- 硬：两个输入**无差别**打 `aria-invalid="true"`（实际只有一句校验理由）→ 去掉 `aria-invalid`，
  只留 `aria-describedby`（验收要的是"错误与输入有关联"，没说"两个都错"）。
- 硬：给**结果容器**也加了 `role="status"`（没被要求）→ 去掉，只留两条状态行。
- 判：空清单早退**不清**待办焦点 → 陈旧选择器会污染下一次无关重绘的焦点；已清。
- 判：卡片上的 `aria-pressed` 恒为 false（`moduleGridFilter` 本来就把已选模块剔掉了）→ 删掉
  （chip 才是两态的那个，它的 `aria-pressed` 留着）。
- 判：键盘用例自己 `.focus()` = 把"够不够得着"绕过去了 → 改成**从搜索框起真按 Tab** 走到卡片。
- 判：反证只覆盖两条用例 → 补第三处注入（标签表去掉一条）。
