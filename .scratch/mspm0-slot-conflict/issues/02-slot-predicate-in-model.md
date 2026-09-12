# 02 — 判据模型补「槽位互斥」谓词 `slot`（后端下发 + 前端求值，端到端）

**要做什么：** 板图上 `huidu.R3` 与 `pid.GRAY_D7` 同槽位（默认同为 PB6）时：同伴若在这份
bindings 里（含「显式绑回默认脚」的 no-op 条目），本角色就只能绑 PB6——改绑别的脚当场
**灰显 + 后端逐字原因**，不再走到「生成工程」才被 400；同伴都没被绑时整组仍可一起搬脚
（第一步不许灰）。判据由后端下发，前端只求值「引脚名相等」。

**被谁阻塞：** 无——可立即开始（spec：`.scratch/mspm0-slot-conflict/spec-slot-model.md`）。

**状态：** resolved（2026-08-xx；后端 `pin_bindings.py` + 前端 `fx/pin-model.js`；
用例 `tests/test_bindings_matrix.py` 6 条新增 + `tests/js/pin-model.test.mjs` 3 条新增）

## 交付（实现后的实际形状）

- `pin_bindings.py` 新增 `_slot_peer_roles`（角色 → 同槽位同伴索引，判据本体复用
  `_mspm0_same_slot`，照 `_port_group_roles` 先例「只回组、不抛错」）+ `_slot_constraint`
  （按观测绑定出 `{kind:"slot", pin, peers, reason}` 或 `None`）；
- `build_bindings_matrix` 加第三级谓词；槽位组**只在 mspm0 算**（stm32 给 slot 组 = 一片假红）；
- 前端 `fx/pin-model.js` 的 `pinModelVerdict` 加 `slot` 分支（引脚名相等）；
  `pinModelMissReason` 无需改（天然复用 `constraint.reason`）；
- parity 用例的前端求值镜像 `_selectable` 同步加 `slot` 分支（**必须同单进**——不同步会让
  既有对拍用例当场报假绿）；
- `webapp.py` 端点文档串补 slot 谓词，并顺手改掉写成 `eligible` 的旧字段名（实际是
  `selectable`）。

## 实现期修正（每条都被当场抓出来，记下来防重犯）

1. **不能写成 `elif` 链**。第一版把三级判据写成 `if port / elif mate / else slot`，结果
   `huidu.R3` 一条 slot 谓词都不出现——`huidu` 八路灰度默认跨 A/B 口，端口组那一级
   `len(ports) != 1`（合法的「无解 → 不给约束」松弛）把第三级整个吞掉了。改成「每一级各自
   判本级有无定解、`constraint is None` 才往下走」。用例
   `test_slot_group_survives_when_port_group_has_no_answer` 钉住。
2. **同伴「在不在观测里」要按角色键字符串比**。同伴索引的键是 `(slug, role_id)` 元组，
   而 `bindings` 载荷的键是 `"<slug>.<role>"` 字符串——直接 `peer in observed` 恒 False
   （同样静默：谓词一条都不出）。两处形状混用是本次最容易踩的坑。
3. **严格规则会挡住「整组搬家」的第一步**（实测：加入严格规则后 huidu+pid 有 480 次、
   adc 槽有 52 次「整组本可搬到同一新脚」被误挡）。定稿为：同伴全未绑 → `None`（整组可
   一起搬）；同伴有效脚唯一 → 出谓词；同伴之间不一致 → `None`（无解不假红）。
4. **槽位谓词语义与门禁的边界**：`_check_slot_conflicts` 只在**被绑定**的角色之间判——
   所以「同槽位同伴走默认」时后端并不拒，谓词也**不能**出（出了就是假红）。反过来
   「同伴显式绑回自己的默认脚」（载荷里保留 no-op 条目，既有政策明确允许）后端**会**拒，
   谓词必须出。两种情形在 `pid.GRAY_D7` 这一个角色上就同时存在（绑 PB6 vs 不绑），
   用例 `test_slot_constraint_only_when_peer_is_observed` 把这一对钉在一起。

## 验收（全部达成）

- [x] `tests/test_bindings_matrix.py` 新增 6 条 slot 语义用例全绿：同伴被观测绑定（含绑回
      默认脚）→ `{kind:"slot", pin:"PB6"}`；同伴全未绑 → `null`（整组可搬）；≥3 成员组
      同伴之间不一致 → `null`（无解不假红）；同伴绑到候选脚同一脚 → 放行；端口组无解时
      slot 谓词仍在；stm32 不给 slot 谓词。
- [x] `tests/js/pin-model.test.mjs` 新增 3 条 `slot` 求值用例全绿（命中 / 不命中 / 随观测
      换指向 / 无模型降级 / reason 逐字）。
- [x] 既有对拍用例（全脚枚举 744 / 115 / 158 锚）仍绿。
- [x] 复现脚本 ⑤ 从 `判定 = True` 变 `判定 = False` 并给出 slot 原因（③ 是「按空观测看」的
      对照相，本就不该变——它的价值是证明单绑定口径收、累积态口径拒）。
- [x] **反向验证**：临时让 `build_bindings_matrix` 传空 `slot_peers` → `test_bindings_matrix.py`
      的 6 条 slot 用例里 4 条当场红、复现脚本当场红（共 7 failed / 19 passed，证据
      `.scratch/mspm0-slot-conflict/reverse-verify-slot-disabled.txt`）→ 恢复 → 26 passed。
- [x] `python -m pytest -q` = 4186 passed；`node --test "tests/js/*.test.mjs"` = 1516 passed；
      `node tests/browser/gen-chain-audit.mjs P` = FAIL 0 / WARN 0 / PASS 15。

## 不做（守住边界）

- `_check_slot_conflicts` / `_mspm0_same_slot` 一字未动（只加下发）。
- `resolve_bindings` / validate / auto / generate 的请求响应形状与文案未动。
- 未做「整组一起搬」的批量交互。
- 未修全库 `pair` 类既有分歧（188 条，见 spec 范围外）。
