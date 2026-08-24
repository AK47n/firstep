# 01 - 后端同键互斥与目录裁决（核心落盘）

Status: resolved

- `generation_output.py`：`GenerationConflictError`（已存在，400）/ `GenerationBusyError`（生成中，409）+ `desktop_topic_dir_verdict`（new/clean/exists 三分支）；`unique_desktop_topic_dir` 标 DEPRECATED（webapp 不再调用）。
- `webapp.py`：AppContext 加 `pending_generations` set + `_generation_lock`；`_generation_guard(key)` contextmanager（已锁 → GenerationBusyError）；`_resolve_generation_output_dir` 返回 (path, verdict)；generate 路由包锁 + verdict 分支（exists 400 / clean 清理 / 失败桌面模式 rmtree）+ 成功 `_open_in_explorer`。
- `errors.py`：登记两个异常（400 / 409 str）。
- 测试：test_generation_output +3（verdict 三分支）；test_webapp +5（半成品清理复用 / 已存在 400 / 生成中 409 / 失败清理 / explorer 打开）并重写旧时间戳唯一化测试；conftest 加 autouse mock Popen（测试不真弹 explorer）。
