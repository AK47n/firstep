# 交付集成（delivery-suite）spec：打开工程 / 交付检查 / 一键打包

## 问题陈述

逐步深化做完后，用户要交付/继续调试时缺三样：① 想打开 Keil / CCS 或工程文件夹
却没有入口（要自己开资源管理器找路径）；② 交付前不知道整体状态（哪些步还没做、
哪步失败——只能逐卡看）；③ 想交工程给别人/归档，只能手动画 zip。

## 目标

任务推进区（第 11 步）新增「🚀 交付」卡：一键打开工程（Keil 工程 / 文件夹）、
交付前检查（清单完成度汇总）、一键打包 zip（排除内部文件）。

## 用户故事

1. 我点「打开工程文件夹」，资源管理器打开该工程目录（或定位到 .uvprojx）。
2. STM32 工程点「在 Keil 中打开」，直接拉起 Keil uVision 加载 .uvprojx。
3. 我点「交付检查」，看到：任务完成度（已验证 N / 已跳过 N / 未完成 N）、
   未完成任务清单（标题 + 状态徽章，失败的一眼看到）、有没有未拆解清单的提示。
4. 我点「打包」，工程被打成 zip（排除 .contest_* 内部文件与 *.tmp），
   结果显示 zip 完整路径与大小；已有同名 zip 时加时间戳不覆盖。
5. 打包/检查前没有任何清单也可以打包（用户可能没拆解），但检查会明确提示
   「尚未拆解任务清单」。
6. 打开工程/打包失败（目录不存在 / 无平台 / 无 Keil）→ 400 中文提示，不白屏。

## 实现决策

- **新域模块 src/contest_generator/delivery.py**（from task_progress import
  TaskError / errors.py 登记 DeliveryError → 400 中文）：
  - `open_project_dir(output_dir, *, uv4_path="") -> dict`：`_infer_platform`
    （context_manifest 复用）→ stm32：找 `.uvprojx`（glob 首个）；优先
    `uv4_path` 覆盖 > `C:\Keil*\UV4\UV4.exe` 探测（glob）> `os.startfile` 关联
    打开；UV4.exe 找到 → subprocess.Popen([uv4, str(proj)])（不等待）；
    失败（无 UV4 / startfile 异常）→ explorer 兜底 + mode="folder"。mspm0：
    explorer 打开目录（mode="folder"）。返回 `{"mode": "ide"|"folder",
    "target": 路径, "message": 中文}`。Windows only（本机工具；非 Windows
    返回 mode="folder" + explorer 不可用时 message 提示）。
  - `delivery_check(output_dir) -> dict`：read_task_plan（None → ok=False +
    message「尚未拆解任务清单…」）；否则 stats = {verified, skipped,
    unverified, failed, pending, doing} 计数 + incomplete = 状态不在
    {verified, skipped} 的任务 [{id, title, status}] + ok = 无未完成。
    同时检查 main.c 存在（不存在 → 提示）。
  - `package_project(output_dir) -> dict`：zipfile 打包 output_dir 全部文件，
    跳过：`.contest_*` 前缀文件、`*.tmp`、`*.bak`、打包产物自身（父目录不在
    扫描范围，天然排除）。zip 名 = `{dirname}-交付-{YYYYMMDD-HHMMSS}.zip`，
    放 `output_dir.parent`。返回 {zip_path, size, files}。不存在目录 →
    DeliveryError。
- **webapp.py 三路由**（POST，同步，flash 端点同构）：
  `/api/delivery/open-ide {output_dir}` → {mode, target, message}；
  `/api/delivery/check {output_dir}` → {ok, stats, incomplete,
  plan_present, message}；`/api/delivery/package {output_dir}` → {zip_path,
  size, message}。`_require_str` + is_dir 校验；config 传 uv4_path（覆盖）。
- **前端**：
  - fx/delivery.js（纯函数 + window 桥 + fx-guard）：`deliveryActionsHTML()`
    （三个按钮：btn-delivery-open-folder / btn-delivery-open-ide /
    btn-delivery-check / btn-delivery-package？——拆成 check 与 package 两
    个动作按钮 + 打开组）+ `deliveryCheckHTML(result)`（统计行 + 未完成列表
    + 徽章）+ `deliveryPackageHTML(result)`（zip 路径 + 大小，转义）。
    按钮显示策略：open-ide 按钮仅 stm32（平台探测前端不知道 → 服务端
    open-ide 响应已按平台自适应；前端两个按钮都显示，「在 Keil 中打开」由
    后端 stm32 才试 UV4——mspm0 时后端直接 folder 模式。简化：按钮
    「打开工程」一个（后端自动选 IDE/文件夹）+「在文件夹中打开」一个。
    最终按钮：`打开工程（IDE/文件夹）` + `交付检查` + `一键打包`。
  - ui/delivery.js：busy 守卫（tasksSetBusy 共享闸——写 zip/启动进程不写
    main.c，但防弹窗堆叠）；调 API → 渲染结果到卡内容器；委托 + 跨簇重置
    （revise-context-loaded / tasks-invalidated 清结果）。
  - index.html：tasks-box 内新 card-group「🚀 交付」（在参数速调后、拆解按钮
    行前或后？——语义上交付是收尾，放任务区**底部**（tasks-grid 之后）或
    顶部？放「⚙️ 参数速调」之后、拆解行之前与想法区一致都是工具卡。定：
    参数速调卡后）。#delivery-result / #delivery-msg 容器 + CSS。
- **测试**：tests/test_delivery.py（模块单测：check 状态统计 / package 排除
  规则 + 时间戳不覆盖 / open-ide 平台分支——subprocess 与 explorer 用
  monkeypatch，uv4 探测路径可注入）+ webapp 三端点（200/400 分级）；
  tests/js/delivery.test.mjs（HTML 渲染/转义/空清单）+ fx-guard 登记。

## 测试决策 / 范围外

- 不做「打开编译后自动打开」；不做打包后上传/分享链接；不打包 .contest_*
  内部状态（保留在工程目录原处，只是不进 zip）。
- open-ide 的 Keil 路径探测仅在 stm32 且未配置 uv4_path 时进行；CCS 不尝试
  拉起（CCS 是 Eclipse 工作区模型，直接 explorer 打开目录 + 工程内含
  .ccsproject，用户手动导入即可——message 说明）。
