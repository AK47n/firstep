# 交付集成：后端 delivery.py + 三路由（delivery-suite/01）

## 状态
Status: resolved

## 目标
新域模块 src/contest_generator/delivery.py：打开工程目录 / 交付检查 / 一键
打包；webapp 三路由（flash 端点同构，同步 POST）；DeliveryError 登记 errors.py。

## 实现
- delivery.py（from task_progress import TaskError 防环；errors.py 登记
  DeliveryError → 400 中文）：
  - `open_project_dir(output_dir, *, uv4_path="") -> dict`：`_infer_platform`
    （context_manifest 复用）→ stm32：找 `*.uvprojx`（glob 首个）；优先
    uv4_path 覆盖 > `C:\Keil*\UV4\UV4.exe` 探测（glob）> `os.startfile`；
    UV4.exe → subprocess.Popen([uv4, proj]) 不等待；失败（无 UV4 /
    startfile OSError / 非 Windows）→ explorer `subprocess.Popen(["explorer",
    str(output_dir)])`（非 Windows 直接返回 mode="folder" + message 提示
    手动打开，不 Popen explorer）。mspm0 → explorer 目录。返回 {"mode":
    "ide"|"folder", "target", "message"}。平台未知 → DeliveryError
    （_infer_platform 抛 ContextError → 转 DeliveryError 400）。
  - `delivery_check(output_dir) -> dict`：read_task_plan（None → ok=False,
    plan_present=False, message 中文；已拆解 → stats {verified, skipped,
    unverified, failed, pending, doing} + incomplete [{"id","title","status"}]
    （状态不在 {verified, skipped}）+ ok = 无未完成）。main.c 缺失 → message
    追加提示。返回 {ok, plan_present, stats, incomplete, message}。
  - `package_project(output_dir) -> dict`：zipfile（压缩 deflate）打包
    output_dir 下全部文件（rglob），跳过：文件名 `.contest_*` 前缀、
    `*.tmp`、`*.bak`；zip = output_dir.parent /
    f"{output_dir.name}-交付-{_now_stamp()}.zip"（YYYYMMDD-HHMMSS，时间戳
    保证不覆盖）；返回 {zip_path: str, size: int, files: int}。
- webapp.py：`from .delivery import ...` + 三路由（flash_flash 路由后、
  模块库段前）：
  - POST /api/delivery/open-ide {output_dir} → **同步** {mode, target, message}；
    uv4_path = config.uv4_path（_current_config）。
  - POST /api/delivery/check {output_dir} → {ok, plan_present, stats,
    incomplete, message}。
  - POST /api/delivery/package {output_dir} → {zip_path, size, files, message}。
  公共校验 = _require_str + Path.is_dir（空目录 → DeliveryError「输出目录
  不存在」）；_map_errors 装饰。
- tests/test_delivery.py：open-ide 三分支（stm32+uv4 探测 monkeypatch
  subprocess.Popen / stm32 无 UV4 → explorer fallback / mspm0 → folder /
  平台未知 400）——subprocess 均 monkeypatch 不真启动；check（无清单 /
  全完成 ok / 部分未完成 incomplete 列表 / failed 计入未完成）；package
  （排除规则：.contest_tasks.json 不进 zip、.tmp 不进、main.c 进；时间戳
  命名；缺失目录 400）；webapp 端点 200/400 分级（test_delivery.py 同族
  惯例）。
- 提交前：全量 pytest；双轴评审。

## 交付
- 双轴评审 → 整改 → 全量 → 提交（中文，spec/issues 01 随提）。
