# 01 — 骨架/编译编排归位（run_skeleton + run_compile）

**What to build:** 抽 run_skeleton（skeleton.py）与 run_compile（compile_runner.py）域函数，把 /api/skeleton 的 main_mode 分支 + 冒烟守卫 + 分派、/api/compile 的工具链探测 + done 组装收进去；两条路由缩成薄壳。照 run_recommendation / run_fix_round 先例。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] run_skeleton 直测：main_mode 分派 / 冒烟守卫（缺 oled + debug_uart → 400 域错误）/ 返回 dict 与迁移前一致
- [x] run_compile 直测：工具链缺失 400 / done 组装 11 字段与迁移前一致
- [x] 两条路由缩成薄壳（_require_* + 调 run_* + 返回 / run_sse(run_*)）
- [x] 既有端点测试（test_webapp）照常绿，行为零变化

## 实施记录

- **skeleton.py**：新增 `SkeletonError`（登记 errors.py → 400 中文）+ `run_skeleton`
  （main_mode 分支 + 冒烟守卫 + generate_skeleton / generate_smoke_main 分派，
  返回 `{main_c, intercepted}`）。冒烟守卫与 main_mode 非法值从路由 HTTPException
  改抛域错误。
- **compile_runner.py**：低层子进程 `run_compile` 改名 `run_compile_command`
  （腾出名字给编排函数）；新增 `resolve_compile_toolchain`（find_uv4/find_make +
  缺失 400，起流前判定单源）与 `run_compile`（compile_start → collect_build_log →
  parse_compile_errors → done 11 字段，经 emit 发 compile_start/done）。
  **工具链探测拆成独立 `resolve_compile_toolchain` 而非并进 `run_compile`**——
  工具链缺失必须在起流前判 400（前端据此置灰按钮，`test_compile_no_toolchain_400_chinese`
  钉死），run_sse 内抛错只会转流内 error 事件；故探测留在路由（run_sse 前）调
  域函数，`run_compile` 收已解析工具链跑流内编排（照 fix-errors 的 output_dir
  起流前检查留路由先例）。
- **webapp.py**：两条路由缩成薄壳（_require_* + 装配输入 + 调 run_* + 返回 /
  run_sse(run_*)）。移除 webapp 对 collect_build_log / compile_passed /
  parse_compile_errors / summarize_compile_output / EVENT_COMPILE_START /
  ProgressEvent / generate_skeleton / generate_smoke_main 的直接 import。
- **测试**：test_compile_runner.py 加 run_compile / resolve_compile_toolchain 直测
  （真实 SseEmitter + Queue，11 字段逐字 + 缺失 400 + 结构异常抛错）；test_skeleton.py
  加 run_skeleton 直测（smoke/skeleton 分派 + 冒烟守卫 400 + main_mode 400 + 错误登记）；
  test_webapp.py 9 处工具链 monkeypatch 目标从 webapp 迁到 compile_runner（行为不变，
  只动测试 seam）。全量 1728 绿 + mypy 45 文件干净。
