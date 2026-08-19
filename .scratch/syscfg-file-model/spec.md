# spec — syscfg 文件模型（架构评审 ② 落地）

## Problem Statement

mspm0.syscfg 的「文件格式知识」散在三处：prune 拥有实例声明文法、pinwriter 拥有 `$assign` 文法与路径匹配、槽位身份在 pin_bindings 又实现了一遍。prune→rewrite 的先后依赖靠一句注释维持，prune 还反向 import pinwriter 只为拿一个文件名常量。下一批工单（mspm0 同族/跨族迁移）正好落在这套分裂的代码上。

## Solution

一个 mspm0.syscfg 文件模型模块：独占文法 + 一次解析 + 槽位身份。prune 与 rewrite 消费同一次解析，先后关系由单一 pipeline 保证，不再靠注释。

## User Stories

1. As 生成器维护者, I want prune 与 rewrite 消费同一次 syscfg 解析, so that 文件格式知识不再散在三个模块。
2. As 引脚绑定开发者, I want 槽位身份（哪个 syscfg 实例/路径）只有一个实现, so that 校验与写侧不会因口径漂移而一个放行一个拒绝。
3. As 下一批工单（同族/跨族迁移）的实现者, I want syscfg 改写集中在一处, so that 改外设族/实例只需碰一个模块。
4. As 维护者, I want prune→rewrite 顺序由构造保证而非注释, so that 调换顺序不会被静默放行。
5. As 测试维护者, I want 文件模型在文本进/文本出的既有接缝上测试, so that 迁移前后产物逐字节一致可断言。
6. As 维护者, I want prune 不再只为文件名反向 import pinwriter, so that 模块依赖不再因字面量耦合。

## Implementation Decisions

- 新模块持有 syscfg 文法（实例声明 addInstance + 模块声明 addModule + `$assign` 赋值）与一次解析产物。
- 槽位身份（binding → syscfg 实例/路径）收敛为一个原语，校验侧与写侧共用。
- prune 与 rewrite 是对同一解析的两个操作，一个 serialize。
- MSPM0_SYSCFG_FILENAME 迁入新模块，prune 不再 import pinwriter。
- 迁移用 expand–contract：先新增模块（旧代码零改动、逐字节等价），再逐批切换，最后删旧文法。
- 逐字节契约不变：全默认 / 未改绑定输出与母版逐字节一致。

## Testing Decisions

- 文本进 / 文本出的纯函数接缝（照 test_syscfg_prune / test_pin_bindings / test_pin_unlock_mspm0_* 先例）。
- 关键断言：新模块对母版 syscfg 的 parse+prune+rewrite 输出与旧 prune→rewrite 顺序逐字节一致。
- 迁移每步跑 mspm0 相关测试套件（pin_unlock_mspm0_same / _cross / test_pin_bindings / test_syscfg_prune）保持绿。

## Out of Scope

- stm32 pin_config.h 写侧（render_pin_config）不动，仍归 pinwriter。
- 不改 syscfg_instances 的实例↔模块数据表本身（那是数据，不是文法）。
- 不新增跨族迁移功能（那是下一批工单，本 spec 只做让它们更好落地的收敛）。
- 前端裁决接缝（架构评审 ①）另立项。
- 校验侧 `_mspm0_same_slot`（数据级两绑定槽位相等）与写侧 `syscfg_path_matches`（绑定→路径匹配）是不同层的不同谓词，仅共享 INSTANCES_BY_SLUG 数据（已单源）——不强行合一；槽位收敛只发生在写侧入模型时（工单 03）。

## Further Notes

- 本 spec 源自架构评审 ②「syscfg 文件模型」；评审 ① 另行立项。
- 迁移完成后 CONTEXT.md 增「syscfg 文件模型」词条。
