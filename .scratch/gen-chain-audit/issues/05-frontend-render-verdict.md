# 05 — 前端：`pinCanHost` 改为渲染后端判据（+ 缓存 / 降级）

**状态：** resolved（2026-08-xx；`fx/pin-model.js` + `ui/generate-pins.js` 接线；
真机 P1 转绿，见工单 06）

## 交付（实现后的实际形状）

- 新增纯函数模块 `fx/pin-model.js`（`pinModelEntry` / `pinModelVerdict` /
  `pinModelMissReason` / `pinRoleChannel` / `pinInstanceTokens` / `pinSelectableByType`），
  node 单测 `tests/js/pin-model.test.mjs` + `fx-guard` 登记（防双源回退）。
- `ui/generate-pins.js`：删掉 `pinIsTypeLevel` / `pwmRoleChannel` / `mspm0PwmAllowed`
  三条镜像规则（**判据不再复制**）；`pinCanHost` = 命中模型 `selectable` 且求值
  `constraint`；`pinMissReason` 优先显示后端逐字原因；`pinRoles()` 给 decl 挂
  `roleKey`（判定要按角色键查模型）。
- 模型取用：`syncPinModel(roles)` 在每次 `renderPinCard` 比对载荷键（平台 + 角色集 +
  `collectBindings` 观测绑定，排序后序列化），命中缓存直接用、变了才发一次
  `POST /api/bindings/matrix`；取到后重渲染一次。
- 降级：模型未到 / 拉取失败 → 退回类型级口径（不假拦），板题注追加
  「（正在核对可绑引脚…）」/「（判据加载失败：暂按类型级显示，生成前仍会校验）」。
- pwm 通道口径：**两脚各自按本脚通道过滤后取实例基名比交集**（本脚通道取角色键尾、
  对脚通道取 `constraint.pair` 键尾），与后端 `_check_mspm0_pwm_channel_pairs`
  逐字同口径——少这一步就是 24 条假绿（用例钉住）。

## 要做什么（原工单）

`ui/generate-pins.js` 的 `pinCanHost` / `pinMissReason` 不再自己判「能不能绑」，改为
**消费 `/api/bindings/matrix` 下发的判据**：

- 模型拉取：角色集 / 平台 / 观测绑定（`collectBindings` 同源）变化时拉一次；按
  `(platform, slugs.join(), JSON.stringify(observed))` 缓存，命中不重复请求。
- `pinCanHost(pin, decl)` = `eligible.includes(pin.name)` **且** `constraint` 谓词成立：
  - `{kind:"port", port}` → `pin.name[1] === port`；
  - `{kind:"instance", instances}` → 该脚的类型实例 token 与 `instances` 有交集
    （pwm 按实例基名比）。
- `pinMissReason(pin, decl)`：判据块挡住时显示后端逐字中文 `reason`。
- **降级**：模型未到 / 请求失败 → 退回旧「类型级」口径（不假拦），并在 `#pin-config-msg`
  提示判据加载失败；`renderPinCard` 在模型到达后重渲染一次。
- 观测绑定 = 界面当前绑定（`pinBindings`，`collectBindings(expanded slugs…)`），换绑后
  重新拉一次（组/pair 谓词随状态变）。

## 步骤（TDD）

1. `tests/js/` 加纯函数用例：新抽的 `pinVerdictFromModel(model, pin, key)`（放
   `fx/pin-model.js`，纯函数、可在 node 里测）——`eligible` 过滤 / port 谓词 /
   instance 谓词（含 pwm 基名）/ 模型缺失时降级 true / `constraint:null` 全放行。
2. 接入 `generate-pins.js`：`loadPinModel()` + 缓存 + `pinCanHost` 改为查模型。
3. 纯件用例覆盖请求节流：同一 `(platform, slugs, bindings)` 连点不重复发请求（打桩 fetch）。

## 验收

- `node --test "tests/js/*.test.mjs"` 绿（含新用例）。
- 真机（工单 06 的 P1 节）：板图上 A 口的 step_motor 候选**当场灰显**且菜单给出后端原因；
  把 C1 绑到同实例脚后 C0 的候选集**当场变宽**。

## 不做

- 多实例选脚（`instancePinTarget`）候选过滤仍走「模块首 pin 能力」旧口径。
- 不放宽 `pinListsType`（菜单第一层仍由前端过滤，后端 `eligible` 只作权威复核）。
