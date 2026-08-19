# 02 — 裁决端点 + 前端灰色改读数据（消镜像）

**What to build:** 后端出 per-role 可绑脚清单（复用 resolve_bindings 能力分级，抽成不抛错的 try 原语）；前端灰色逻辑（pinCanHost / pinIsTypeLevel / mspm0PwmAllowed / roleInstances / pinSupports / pinMissReason）改读该数据，删除规则镜像。能力判定收敛到后端单实现。

**Blocked by:** 01

**Status:** deferred

**Deferred 理由（2026-08-16，更正触发前提）：** 01 校验端点已修掉 green→400（真 resolve_bindings 兜底，镜像漂了也会被 validate 在生成前拦下）。02 是防未来漂移，无当前 bug。**更正：** 原写「触发 = pin-full-unlock 03/04 启动时」——但 03/04 其实 2026-08-15 已合 main（PR #80/81/82），且已核实前端 pinIsTypeLevel / mspm0PwmAllowed 与后端 resolve_bindings 类型级口径当前完全同步（04 跨族放开两边都体现），镜像未漂。故 defer 仍成立，理由改为「当前同步 + 无后续矩阵改动计划」；若未来再有矩阵改动，02 作其 prefactoring 先行。

- [ ] 裁决端点给定 {platform, slugs} 返回每角色的可绑脚清单（含 reason）
- [ ] 前端灰色渲染改读裁决数据；删除 pinIsTypeLevel / mspm0PwmAllowed / roleInstances / pinSupports / pinMissReason 的规则镜像
- [ ] 对全库角色 × 母版路径穷举：裁决数据的 can_host 与 resolve_bindings 单绑定该 (角色, 引脚) 的成功/失败一致
- [ ] 引脚候选高亮 / 灰显行为与迁移前一致（既有前端用例绿）
