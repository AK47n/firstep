# 02 — 「一键自动配置」真能解默认脚冲突（mspm0 撞脚一键消解）

**要做什么：** 引脚配置卡的「自动配置」按钮现在对**默认×默认**撞脚（双方都没绑过脚）
什么也不做——实测 `auto_assign_bindings(manifests, "mspm0", board, {})` 增量与 `fixed`
皆空（`.scratch/pin-conflict-gate/verify-01-red.txt` ③ 段）：它只修**显式绑定**的角色
（唯一校验 `resolve_bindings` 只校验传入的绑定）。本单让它把这类冲突也解开：确定性地
让每组冲突里的**一个**角色让位，移到能力匹配且不制造新冲突的空闲脚；合法共享一律不动。
端点与载荷形状不变（前端零改动）。

**被谁阻塞：** 01（门禁的判据复用同一份 `_shared_groups` 判定；02 的验收用 01 的门禁
当「解开了没有」的判据——两单互相钉住）。

**状态：** resolved

## 落地记录（本轮）

- `pin_bindings.auto_assign_bindings` 新增关键字参数 `resolve_default_conflicts`（**缺省关**
  = 旧行为逐字节）+ 三个内在件：`_repair_binding_conflicts`（原算法逐字抽出）、
  `_resolve_default_pin_conflicts`（消解相）、`_first_pin_without_conflict`（候选脚）；
  `_role_entries` 抽出「角色键 → 生效引脚」单源（`_shared_groups` 与消解相共用，
  免得两处各写一遍漂移）。`/api/bindings/auto` 传 `resolve_default_conflicts=True`
  （唯一有选中集语义的调用方）；前端零改动、载荷形状不变。
- **真机探针修正了两处初稿设计**（`probe-03-auto-config-closes-the-loop.py`）：
  1. 候选脚必须**空闲**（选中集内没有别的角色落脚）——初稿只查「不制造 conflict 组」，
     而同一 syscfg 实例的三条落点被 `kind=share` 判为合法共享 → 真机上把 oled 的
     DC/RES/CS 三条**全搬到 PA0**（接线错，SysConfig 也过不去）；
  2. 让位方要**按偏好序逐个试**——UART TX/RX 成对，单搬一个过不了 `resolve_bindings`
     成对校验，只钉第一个候选会在真机留下解不掉的两组（2026H 的 PA28/PA31）。
- **真机结果**：
  - 旧行为（缺省关）：12 模块选中集增量空、7 组 conflict 只标注（现场 `verify-03-*.txt` 首段）；
  - 开开关：解开 **4 组**（oled DC/RES/SCL + l298n EN → 空闲脚），**恰好用尽该选中集的
    4 个空闲脚**；剩 3 组（PA7 / PB18 / PA31）**物理不可解**——角色落点需求 42 个
    （含合法共享的重复落点）vs 板上可用 IO 31 脚，母版默认布局的上限使「全模块同选」
    本就不可实现（这也是真机 7 条冲突的根，更坐实 01 门禁 + 「去掉冲突模块」这条出路）；
  - 可解形态（motor + servo）：`servo.SERVO_PWM_C0 → PA0`，解完 zero conflict，
    产物 syscfg 复算无同脚多实例；
  - **真机编译**（`run-02-real-machine.py` → `generate_check.py --reuse-recommend
    --drop … --bindings {"servo.SERVO_PWM_C0":"PA0"} 2026H`）：生成通过 + 产物门禁全过 +
    **gmake exit=0（0 错误 0 警，9.1s）**（`verify-02-real-machine-generate-check.txt`）。
- **测试**：`tests/test_pin_bindings.py` 新增 5 条（默认撞脚解开 / 开关缺省零变化 /
  合法共享不动 / 让位方随选中清单序 / 全显式不动 + 混合只搬没绑过的一侧）；
  全量 `pytest` 绿、`node --test tests/js/*.test.mjs` 绿、`mypy` 零问题。

## 验收标准

- [x] 红证：真机 13 模块集 + 空 bindings → 现状增量空、7 个 `kind=conflict` 脚一个没动
- [x] 落地后同一输入：解开 4 组；**剩余 3 组是物理不可解**（空闲脚用完 + 角色落点
      42 > 可用 IO 31），如实留在标注里（跨单闭环：01 的门禁对同一输入仍报这 3 组）
- [x] 合法共享逐条不动：`huidu` / `pid` 的 6 个脚（PA23-26 / PB6 / PB7，同一 HUIDU 实例）
      与 `kind="share"` 组一律不进增量
- [x] 让位规则确定：选中清单顺序换一下 → 让位方随之改变（可预测、可复现）
- [x] 前端契约不变：`/api/bindings/auto` 仍返回 `{ok, bindings, fixed, shared}`，
      前端应用路径零改动（既有 test_webapp 用例不红）
- [x] 真机：带增量的 `generate_check.py` → 生成通过 + **gmake 0 错误 0 警**
- [x] 全量 `pytest` + `node --test tests/js/*.test.mjs` 绿

## 修复方向（实施会话定措辞，红证先行）

1. **红证**：真机 13 模块集上 `auto_assign_bindings(..., {})` → 现状 `bindings == {}`
   且 `fixed == ()`，而 `shared` 里 7 个脚是 `kind="conflict"`（PA7 / PA13 / PA22 /
   PA27 / PA28 / PA31 / PB18）——按钮按下去这些脚一个都没动。
2. **新增一相（不新入口）**：`auto_assign_bindings` 在既有「绑定级贪心修复」之后加
   「默认脚冲突消解」相：
   - 判据 = `_shared_groups(manifests, platform, board, 当前 bindings)` 里
     `kind == "conflict"` 的组（`kind == "share"` 一律不动——同一 syscfg 器件实例 /
     同一串口实例 / I2C 总线是合法共享）；
   - 让位方 = 该组成员所属模块在选中清单里**靠后**者（同模块内按 role_key 序最后）；
     每组只动一个角色（确定性，不看 reason 文本、不做打分）；
   - 候选脚 = 板定义引脚序（`board.pins`）里能力匹配（`resolve_bindings` 试绑合法）
     且试绑后**该角色不再出现在任何 conflict 组**的首个脚；已被占用的脚跳过；
   - 产出写进既有 `bindings`（增量）+ `fixed`（说明行，例如
     `motor.BIN2 → PB25（原 PA7 与 servo.SERVO_PWM_C0 冲突，已自动移开）`）。
3. **无解不假绿**：找不到候选脚 → 该组保留在 `shared` 标注里（前端已渲染 ⚠ + 理由），
   不谎报成功；若整轮一个都没解开，行为与现状一致（增量空）——「尽力而为」写在 docstring。
4. **契约零变更**：`AutoAssignResult(bindings, fixed, shared)` 形状、`/api/bindings/auto`
   载荷、前端 `ui/generate-pins.js` 应用增量的路径都不改（前端零改动是本单的硬边界）。
5. **不许平行判定**：候选脚合法性 = `resolve_bindings`；冲突归属 = `_shared_groups`
   （`_role_resource_keys`）——不新写一套同脚判据。

## 文件边界

- `src/contest_generator/pin_bindings.py`（`auto_assign_bindings` 新增相 + 必要的纯助手；
  `resolve_bindings` / `_shared_groups` 语义不动）
- `tests/test_pin_bindings.py`（红证 / 解开 / 合法共享不动 / 让位规则确定 / 无解如实）
- `tests/test_webapp.py`（`/api/bindings/auto` 载荷形状不变，若既有用例断言过 `fixed` 空）
- 前端**不改**；`errors.py` 不改（无新错误类）

## 验收标准

- [x] 红证：真机 13 模块集 + 空 bindings → 现状增量空、7 个 `kind=conflict` 脚一个没动
      （见「落地记录」：真机探针把这个初判证成了**必改**——缺省关时增量恒空）
- [x] 落地后同一输入：解开 4 组（用尽该选中集的 4 个空闲脚）；剩余 3 组物理不可解
      （角色落点 42 > 可用 IO 31），如实留在 `shared` 标注；用 01 的门禁判据复算 = 正是这 3 组
- [x] 合法共享逐条不动：`huidu` / `pid` 的 6 个脚（PA23-26 / PB6 / PB7，同一 HUIDU 实例）
      与 `kind="share"` 组一律不进增量
- [x] 让位规则确定：把选中清单顺序换一下 → 让位方随之改变（可预测、可复现）
- [x] 前端契约不变：`/api/bindings/auto` 仍返回 `{ok, bindings, fixed, shared}`，
      前端应用路径零改动（既有 test_webapp 用例不红）
- [x] 真机：`generate_check.py --bindings '<auto 的增量>' ...` 再生成 → SysConfig +
      gmake 0 error（本机工具链在盘）
- [x] 全量 `pytest` + `node --test tests/js/*.test.mjs` 绿

## 修正与教训（真机探针带回的）

- **初稿规格两处不成立**（已在 spec 用 ★ 标注）：候选脚要「空闲」而非仅「不制造冲突组」
  （合法共享会放过同实例叠脚）；让位方要逐个试而非只钉第一个（UART 成对校验）。
- **「一键解开」不是万能**：超大选中集在这块板上物理不可实现（默认布局铺满 31 IO）。
  这不是缺陷而是母版设计的既定上限——所以 01 的**拦下 + 「去掉冲突模块」出路**必须存在，
  02 只负责把「有解的那部分」一键解开并诚实标注剩余。两单职责由此分清。

## 不做什么（范围外）

- 不改 `resolve_bindings` 的校验语义（「同脚多角色允许」仍是既定事实）。
- 不做生成时静默自动消解（用户没要求的接线不能偷偷改——本单只让按钮真有效）。
- 不做 AI／模糊选脚（确定性贪心，判据只有能力 + 不制造新冲突）。
- 不动 stm32 的默认脚冲突口径（同 01）。
