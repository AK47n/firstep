# 01 — 塔克R3两驱小车底盘资料拆分为 6 条独立条目

**What to build:** 现条目「塔克R3两驱小车底盘资料」把 6 个互相独立的完整工程装成一条（193 文件 1.4MB）：DB20_1 直流电机调速 / DB20_2 编码器数据采集 / DB20_3 PID 速度控制 / DB20_4 PID 位置控制 / DB20_5 舵机角度控制（STM32F10x 标准库，各含 Doc/User/X-SOFT 全套）+ 编码器电机小车控制源码V1.0.230626（STM32F4xx）。一条 entry 的后果：标题/简介只覆盖"底盘资料"整体，搜"舵机角度"命中不了；全文回读被 4000 字符总截断卡死在前几个文件，后 5 个工程模型永远看不见。拆成 6 条（driverlib 每例一条同款先例），每条独立标题/简介/文件集，搜索、推荐、全文三处可精确命中。

**Status:** resolved（2026-08-13，验收闭环）

## 验收记录（2026-08-13）

- 拆分脚本 `.scratch/split_tarkbot.py`（幂等：旧 id 目录不存在即跳过、目标条目已存在即红；前置自检 = 旧条目 193 文件按 6 子工程 + 2 顶层文件完全划分且数量逐条对齐 31/31/31/33/33/32；并集自检 = 6 条 files 回挂旧前缀取并集 vs 旧条目 files 并集逐条对照不丢不重，红证即退）。新条目走 add_reference 结构校验入库、旧条目走 delete_reference 删除；写库自动提交照常触发（7 条），事后 squash 成一条（未碰 config.json，与 rename_mspm0_refs.py 先例的差异点在实施时改走 squash）。
- 数据：147→152 条；6 条新 id（塔克R3-DB20-直流电机调速 / 塔克R3-DB20-编码器数据采集 / 塔克R3-DB20-PID-速度控制 / 塔克R3-DB20-PID-位置控制 / 塔克R3-DB20-舵机角度控制 / 塔克R3-编码器电机小车控制源码），type=小车底盘例程、platform=stm32、anchor=none；素材清单.txt 全文复制进每条（6 份一致，索引同源 PDF/zip），O 资料更新记录.txt 归入 DB20_1 条目。旧条目目录已删除（git 历史保留）。
- 简介逐条手写：通读各子工程 Doc/readme.txt + main.c 例程说明 + 驱动 API（ax_kinematics/ax_robot/ax_speed）；速度环（DB20_3，编码器增量反馈）与位置环（DB20_4，编码器绝对值反馈）区分写明；各条含 MCU 与标准库（F103 + 标准外设库 V3.5.0 / F407 OpenCTR H60）。
- 测试 `tests/test_reference_library.py` +4（真库数据不变量，与 tests/test_module_collision.py 同款）：6 条在 / 旧条不在 + list_references 全库结构校验不抛；逐条 files 只含本子工程路径（首层目录 ∈ Doc/User/X-SOFT/Driver/Robot）+ 类型/平台/锚定对齐 + O 资料更新记录仅 DB20_1 持有；6 条 files 回挂旧前缀并集 == 193 文件且逐前缀数量对齐 + 6 份素材清单全文一致；搜索「舵机」精确命中 塔克R3-DB20-舵机角度控制。
- **pytest 1264 全绿**（基线 1260 + 新增 4，无回归）；**mypy src 干净**（36 文件，src 零改动）；mypy src tests 另报 8 条 error 全在 test_selection/test_autocommit/test_webapp（本工单未触碰文件，既有基线噪声，非本工单引入）。
- 边界遵守：未碰 sources/materials 镜像、src/、其他条目、模块库；旧条目 PDF/zip 素材仍由 sources/materials/塔克R3两驱小车底盘资料/ 镜像按素材清单索引（新条目标题变化后逐文件下载该路会 400，素材清单文件名搜索不受影响——工单定案 6 条共享无害）。

## 现状（已核实 2026-08-13）

- 条目 id/title=「塔克R3两驱小车底盘资料」，type=小车底盘资料，anchor=none，platform=stm32，193 文件
- 6 个子工程文件集：DB20_1/2/3 各 31 文件、DB20_4/5 各 33、编码器电机小车 32 + O 资料更新记录.txt + 素材清单.txt
- 5 个 DB20 各带 31 个相同 X-SOFT 驱动（重复 5 次——拆条后各自保留，内容自持优先）
- 素材清单.txt 由原始桌面目录生成（表头写 Desktop/塔克 l R3…），索引 PDF/zip/视频（zip 是完整工程保真件）
- 模块库 kit 词表无「塔克R3」（现有 kits：MPU6050、ALX-AOA-FIT…），新条目 anchor 维持 none
- src/ 与 tests/ 无对该条目 id 的硬引用（grep 已验）——纯数据改动

## 实施

1. 写 `.scratch/split_tarkbot.py`（幂等可重跑：skip-on-exist + 集合自检，参照 rename_mspm0_refs.py 风格）：
   - 读旧条目 reference.json，按 6 个子工程目录拆分 files
   - 6 条新条目：id 由标题生成（中文直观名，如「塔克R3 DB20 直流电机调速」「塔克R3 DB20 编码器数据采集」「塔克R3 DB20 PID 速度控制」「塔克R3 DB20 PID 位置控制」「塔克R3 DB20 舵机角度控制」「塔克R3 编码器电机小车控制源码」）；type=小车底盘例程；platform=stm32；anchor=none
   - 简介逐条写：通读各子工程 Doc/readme.txt + 文件集摘要（模板：做什么 / 什么 MCU 与标准库 / 文件构成 / 与其余 DB20 的关系；速度环与位置环要写清区分）
   - 每条目带 素材清单.txt：复制旧清单全文（自持优先；索引同源 PDF/zip，6 条共享无害）；O 资料更新记录.txt 归入其中一条（如 DB20_1），保证并集不丢
   - 走 add_reference 结构校验入库 → delete_reference 删旧条目
2. 手动校对 6 条简介与文件集
3. 测试：tests/test_reference_library.py 加拆分不变量（6 条 id 存在、旧 id 不存在、各条 files 只含本子工程路径、6 条 files 并集 == 旧条目 files 并集）；list_references 全库结构校验不抛

## 验收

- pytest 全绿 + mypy src 干净（src 零改动）
- library/references 下 6 条新条目 + 旧条目删除；git 历史保留旧条目（不做历史重写）
- 浏览器 /api/references 浏览：6 条标题可见、简介准确；搜索「舵机」命中 DB20_5 条目
- 不丢数据：脚本自检打印 6 条 files 并集 vs 旧 files 对照

## 文件边界

`library/references/塔克R3两驱小车底盘资料/`（拆分后删除）、`.scratch/split_tarkbot.py`（新增）、`tests/test_reference_library.py`（新增用例）

**明确不动的：** sources/materials 镜像、src/、其他条目、模块库。
