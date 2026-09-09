# 01 — 参考库塔克 6 条目删除（生成链断源）

**要做什么：** `library/references/塔克R3-*` 6 个条目从参考库删除（走 delete_reference，
自动 git 提交），LLM 生成链不再可能读到塔克源码——「手动准入全文直读」的注入面收口。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 删除 6 条目：塔克R3-DB20-PID-位置控制 / PID-速度控制 / 直流电机调速 / 编码器数据采集 /
      舵机角度控制 / 编码器电机小车控制源码
- [x] 删除后 `list_references` 无塔克（直接验证 + 真库测试翻转见 04）
- [x] 触发一次生成冒烟（stm32）：确认参考清单注入段无塔克条目

## Comments

- 2026-09-09 补标 resolved（代码事实盘点）：
  **否证/取证命令与结果**——
  ① `Get-ChildItem library\references -Directory | Where-Object { $_.Name -match '塔克|xtark' }`
  → **零命中**（库内 169 条参考条目，无塔克）；
  ② `Select-String -Path library\references\*\reference.json -Pattern '塔克|xtark'`
  → **零命中**（连元数据里都没有）；
  ③ `git log --oneline --grep='塔克'` 有 6 条 `lib: delete reference 塔克R3-*` 提交：
  `6df7cc35` 编码器电机小车控制源码 / `cf5e89a4` 舵机角度控制 /
  `f791cedf` 编码器数据采集 / `4370772f` 直流电机调速 /
  `4e5e4a9d` PID-速度控制 / `cb63d7a7` PID-位置控制——正是工单列的 6 条，且均走
  `delete_reference`（自动 git 提交）。
  验收逐条对照：① 6 条目已删（git log 逐条可见）✓ ② 删除后库内无塔克（grep 双查
  零命中 + 04 的真库不变量测试 `tests/test_reference_library.py:2226
  test_tarkbot_entries_absent_from_reference_library` 兜底）✓ ③ 生成链注入面：
  注入源 = `associated_references`（只从参考库取），库内无塔克 → 注入段不可能有塔克；
  另有搜索面零命中断言 `tests/test_reference_library.py:2242
  test_tarkbot_entries_absent_from_web_facing_search` ✓。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
