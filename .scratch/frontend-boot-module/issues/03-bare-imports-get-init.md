# 03 — 裸装载退场：5 个"加载即接线"的模块给出显式 init()

**要做什么：** 修订簇 / 任务簇 / 参数簇 / 参数咨询 / 交付卡这 5 个模块（今天靠
`import "/js/ui/x.js"` 被加载才接线）各自导出一个显式 `init*()`，接线语句从求值期搬进去，
由 boot 显式调用；裸装载从清单里消失。"import 即接线"这条隐式边在这 5 个模块上退场。

**被谁阻塞：** 02（装载根搬家）

**状态：** ready-for-agent

## 范围（实测清单见 spec「实现决策」）

| 模块 | 求值期副作用 |
|---|---|
| `ui/generate-revise.js` | 11 条（`analyzeCancel.onClick` / `execCancel.onClick` / 9 条 `$("btn-revise-*")`、`#revise-dir-input`、`#revise-problem-text` 绑定） |
| `ui/generate-tasks.js` | 24 条（`tasksCancel.onClick` / 20+ 条 `#btn-tasks-*` `#tasks-*` `document` 绑定 / 2 条 `window` 自定义事件） |
| `ui/params.js` | 7 条（`paramsCancel.onClick` / `#btn-params-scan` `#params-grid` `#params-result` / 2 条 `window`） |
| `ui/params-chat.js` | 7 条（`chatCancel.onClick` / `#btn-params-chat` `#params-chat` ×2 / 3 条 `window`） |
| `ui/delivery.js` | 5 条（首帧写 `#delivery-actions` / `bindDeliveryActions()` / 2 条 `window` / `Object.assign(window, …)` 挂桥） |

## 验收标准

- [ ] 5 个模块各导出显式 `init*()`（名字与既有导出不冲突，命名照各模块既有风格），
      上述列 0 副作用语句**逐条**搬进 init 函数体
- [ ] 被其它函数读的模块作用域声明（`analyzeAbort` / `chatCancel` / `tasksAbortSlot` 等）
      **留在原地**——只搬副作用，不搬声明（搬错 = 别处引用断）
- [ ] `ui/delivery.js` 的 `Object.assign(window, {...})` 随接线进 init：语义不变
      （仍在上线前装好；探针按全局名取用照旧），**不是**"顺手删桥"
- [ ] boot.js 里这 5 条裸装载换成具名 import ＋ 接线区显式调用，**调用顺序 = import 顺序**
- [ ] 判据自证：`boot-contract` 的"列 0 副作用"判据对这 5 个模块报 0 条（探针桥除外）
- [ ] 真浏览器冒烟（改前 / 改后各一次）：加载期监听器记账里这 5 个模块的绑定**逐条相同**
      （target + 事件类型都对得上）；`#delivery-actions` 仍被写；delivery 的 window 桥仍在；
      `#btn-params-chat` 真点击仍有行为反应；0 pageerror
- [ ] `node --test "tests/js/*.test.mjs"` 全绿、浏览器门禁 26 条全绿

## Comments

（实现时补：各模块 init 名、冒烟对照读数）
