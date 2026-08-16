# spec — 前端裁决接缝（架构评审 ① 落地）

## Problem Statement

引脚配置步骤（前端步骤 6/7）的「哪些脚能绑哪个角色」判断，前端用一套 JS 镜像重新实现（pinIsTypeLevel / mspm0PwmAllowed / pinSupports / roleInstances），且只查单脚能力、不跑后端 resolve_bindings 的跨角色门禁（mspm0 槽位 / GPIO 同端口 / PWM 通道对 / 成对角色实例）。结果：UI 能把后端会 400 的绑定画成「可绑」，用户走到 generate 才撞错。同一套规则两处实现，下一批工单（同族/跨族迁移）还要往规则里加东西，镜像只会越漂越远。

## Solution

把后端 resolve_bindings（唯一校验实现）接到前端：新增校验端点，让用户离开引脚步骤时就拿到跨角色错误；再新增裁决端点，让前端灰色候选改读后端算好的「每角色可绑脚清单」而非自己镜像。

## User Stories

1. As 用户在引脚配置步骤, I want 离开步骤时就能看到跨角色冲突错误, so that 不会走到 generate 才撞 400。
2. As 前端维护者, I want 灰色候选由后端裁决数据驱动, so that 改后端能力口径前端不用跟着改镜像。
3. As 引脚绑定开发者, I want 能力判定（类型级 vs strict-all / 实例匹配）只有一个实现, so that 口径漂移不再发生。
4. As 下一批工单（同族/跨族迁移）实现者, I want 前端不再持有类型级分级矩阵, so that 改矩阵只碰后端。
5. As 维护者, I want 校验错误文案与后端逐字一致, so that 前端展示与 generate 400 说的是同一句话。

## Implementation Decisions

- 校验端点：POST 跑 resolve_bindings，返回 {ok, error}，错误文案与 generate 400 逐字一致（同一实现，不复制文案）。
- 裁决端点：给定 platform + slugs，为每个角色返回可绑脚清单（复用 resolve_bindings 的能力分级 + boards.pin_supports / pin_capability_instances，抽成不抛错的 try 原语）。
- 前端灰色逻辑改读裁决数据，删除镜像函数（pinIsTypeLevel / mspm0PwmAllowed / roleInstances / pinSupports / pinMissReason 的规则部分）。
- 跨角色门禁（槽位 / GPIO 同端口 / PWM 通道对 / 成对实例）只在后端 resolve_bindings 一处实现，前端经校验端点消费，不复制。

## Testing Decisions

- 后端：校验端点直测 resolve_bindings（有效 + 各类非法 400 文案逐字）；裁决端点测 per-role 可绑脚清单与 resolve_bindings 的逐脚判定一致（穷举）。
- 前端：照 tests/js 先例做数据驱动渲染用例；前端变薄后无规则逻辑可测，关键正确性由后端裁决测试兜底。
- 关键断言：裁决端点对每 (角色, 引脚) 的 can_host 与 resolve_bindings 单独绑定该 (角色, 引脚) 的成功/失败一致。

## Out of Scope

- 不新增引脚绑定功能（全解已由 ADR 0012 完成）。
- 不改跨角色门禁的判定逻辑（只把已有校验接到前端）。
- 同族/跨族迁移（pin-full-unlock 03/04）仍是独立工单，本 spec 只让它更好落地。
- 不做实时逐键校验（本地工具，离开步骤时校验足够）。

## Further Notes

- 本 spec 源自架构评审 ①「前端裁决接缝」。
- 两票独立：01 校验端点 = bug 修复（green→400，低风险先做）；02 裁决端点 = 漂移治理（清理镜像，改动面大、风险高、可推迟）。
