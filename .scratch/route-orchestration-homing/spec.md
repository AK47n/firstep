# spec — 骨架/编译编排归位（路由变薄壳）

## Problem Statement

/api/skeleton 与 /api/compile 两条路由里嵌着域编排逻辑：骨架路由的 main_mode 分支 + 冒烟守卫 + generate_skeleton / generate_smoke_main 分派；编译路由的工具链探测 + 11 字段 done 组装 + compile_start 事件。这与仓库已确立的「路由 = _require_* + 调域函数 + 返回 / run_sse」先例（run_recommendation / run_fix_round）不一致——域判决应归域模块（skeleton.py / compile_runner.py），路由只做薄壳。

## Solution

照 run_recommendation / run_fix_round 先例，抽 run_skeleton（skeleton.py）与 run_compile（compile_runner.py）域函数，把 main_mode 分支 / 冒烟守卫 / 工具链探测 / done 组装收进去；路由缩成薄壳。

## User Stories

1. As 维护者, I want 骨架与编译的域编排在域模块, so that 路由只剩薄壳、域逻辑有单一归处。
2. As AI 导航者, I want 读路由就能一眼看出它调了哪个域函数, so that 理解端点到域逻辑的跳转不散在闭包里。
3. As 测试维护者, I want done 组装 / 冒烟守卫能经域函数接口直测, so that 不用起 HTTP 才能验证。
4. As 维护者, I want 域逻辑抛域错误而非在路由抛 HTTPException, so that 错误走 errors.py 单表映射。

## Implementation Decisions

- run_skeleton：main_mode 分支 + 冒烟守卫（缺 OLED / debug_uart → 域错误 400）+ generate_skeleton / generate_smoke_main 分派，返回结果 dict。
- run_compile：collect_build_log + parse_compile_errors + done 组装，经 emit 发 compile_start / done。
- resolve_compile_toolchain：工具链探测（find_uv4 / find_make + 平台缺失 400）拆成独立函数——缺失 400 必须在起流前判（前端据此置灰按钮回退贴文本），run_sse 内抛错只会转流内 error 事件（HTTP 200），故由路由在 run_sse 前调、run_compile 收已解析工具链（照 fix-errors 的 output_dir 起流前检查先例）。
- 冒烟守卫的 400 改抛域错误（登记 errors.py，或复用现有类型），不再在路由抛 HTTPException。
- 路由变薄：_require_* + 装配输入 + 调 run_* + 返回（skeleton 同步）/ run_sse(run_*)（compile 流）。

## Testing Decisions

- 照 test_selection（run_recommendation 直测）与 test_fix_errors（run_fix_round）先例：run_skeleton / run_compile 直测（冒烟守卫 400、main_mode 分派、done 组装 11 字段）。
- 既有端点测试照常绿（行为零变化）。

## Out of Scope

- 不改 generate_skeleton / generate_smoke_main / collect_build_log / parse_compile_errors 的内部逻辑（只收拢编排）。
- 不动 /api/generate 的 ccs_tools 探测（那处泄漏更小，本次不碰，避免范围蔓延）。

## Further Notes

- 本 spec 源自架构评审漏判补回（LLM 侦察发现、未排进报告前 8）。
- 与既有 run_recommendation / run_fix_round 同款先例，零新模式。
