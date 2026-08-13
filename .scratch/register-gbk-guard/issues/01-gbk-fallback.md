# 01 — 素材录入脚本 GBK 兜底：杜绝静默丢码

**What to build:** register_materials.py 的 `iter_text_files` 只试 UTF-8、失败**静默跳过**——MSPM0_MOTOR 批次 7 个 GBK 编码核心源码（motor_set_speed.c / motor_crc.c 等）因此漏录、条目名不副实（工单 reference-library-hygiene/02 已修复该条目数据，但脚本缺陷仍在，未来任何含中文注释 GBK 代码的素材批次必再踩）。改：UTF-8 失败后试 gb18030 解码兜底转码入库 + 逐文件警告；仍失败按二进制跳过但**计数汇总打印**（静默变可见）。同款内联模式存在于 register_canmv_k230.py / register_esp32cam.py，顺手同修。脚本幂等 skip-on-exist，改动不触发任何批次重跑。

**Status:** resolved

## 现状（已核实 2026-08-13）

- register_materials.py:107 `iter_text_files`：`read_text(encoding="utf-8")` except UnicodeDecodeError → continue（静默跳过）
- 已发生损失：MOTOR 条目 7 文件漏录（motor_crc.{c,h} / motor_read_enc.c / motor_set_speed.{c,h} / user.h / imu.c），2026-08-13 工单 02 转码补录闭环
- register_canmv_k230.py:51 / register_esp32cam.py:45 同款 utf-8 直读静默跳过模式；register_pid_decision.py:92 用 `errors="replace"`（不丢但乱码，边界外不修）
- register_tarkbot.py 处理的是 zip 文件名 cp437→gbk 解码（`_decode_name`），与本工单不同面，不动
- .scratch 脚本测试先例：tests/test_generate_check_contract.py 用 importlib 加载 .scratch/real-run/generate_check.py

## 实施

1. register_materials.py 的 `iter_text_files` 改三段：
   - utf-8 直读成功 → 照旧
   - 失败 → bytes 试 gb18030（GBK 超集）解码成功 → 行尾归一化（\r\n→\n，与工单 02 转码口径一致）+ print「[转码] <rel>（gbk→utf-8）」→ 入库
   - 仍失败 → 计入 skipped 计数（二进制逐文件不打印，防刷屏）
   - 收尾 print 汇总「[跳过] N 个非文本文件未入库」（N=0 也打一行——可见性本身就是目的）
   - 若脚本尚无 `sys.stdout.reconfigure(encoding="utf-8")` 则补（工单 02 教训：防控制台打花）
2. register_canmv_k230.py / register_esp32cam.py 同款改（各自内联小函数，口径逐字一致）
3. 测试 `tests/test_register_gbk.py`（importlib 加载 register_materials.py，同 test_generate_check_contract 先例）：
   - tmp 目录三件套：UTF-8 文件 / GBK 中文注释文件 / 二进制文件 → `iter_text_files` 返回两件、GBK 转码内容正确（中文注释逐字断言）、capsys 含「[转码]」与「[跳过] 1 个非文本」
   - 判别力红证：monkeypatch 模拟旧逻辑（仅 utf-8）断言 GBK 文件丢失——证明测试抓得住旧缺陷
4. 不重跑任何批次（skip-on-exist 天然保护，跑一遍 register_materials.py 全部 [跳过] 即证）

## 验收

- pytest 全绿（新增 test_register_gbk）+ mypy src 干净（.scratch 不在 src 范围，src 零改动）
- register_materials.py 重跑：全部条目 [跳过]，零副作用
- 工单文件补验收记录；素材保留规则记忆的 GBK 教训由主会话维护

## 文件边界

`.scratch/register_materials.py`、`.scratch/register_canmv_k230.py`、`.scratch/register_esp32cam.py`、`tests/test_register_gbk.py`（新增）

**明确不动的：** src/、其他 register 脚本、库数据、sources/materials 镜像。

## Comments

### 验收记录（2026-08-13）

- 三脚本同改：`iter_text_files` UTF-8 失败 → `_read_transcoded` 按 gb18030 兜底转码（`\r\n` 归一化，与工单 02 口径一致）入库 + 逐文件 `[转码] <rel>（gbk→utf-8）`；仍失败按二进制跳过、收尾 `[跳过] N 个非文本文件未入库` 汇总（N=0 也打一行）；三脚本均补 `sys.stdout.reconfigure(encoding="utf-8")`（hasattr 守卫）
- `tests/test_register_gbk.py` +3 绿（importlib 加载 .scratch/register_materials.py，同 test_generate_check_contract 先例）：三件套 fixture（UTF-8 / GBK 中文注释 / 二进制）→ 返回两件 + GBK 中文注释逐字断言 + capsys 含 `[转码]` 与 `[跳过] 1 个非文本`；判别力红证两条（monkeypatch 模拟旧逻辑断言 GBK 文件丢失 + 临时移除兜底跑主测试实红已恢复）；N=0 也打一行 pin
- pytest 全绿 1276（+3）+ mypy src 干净（src 零改动）
- **意外发现（重跑暴露）**：ENTRIES 里「MSPM0_MOTOR参考例程」是陈旧条目——工单 02 拆条后旧 id 已删，skip-on-exist 失效，首次真机重跑把整棵原始树（1639 文件，含已剥离的 1622 个 SDK 副本树）重新灌回库。已清退恢复（git 撤暂存 + 删条目目录，库回 154 条与 HEAD 一致）+ 删该 spec 并在脚本内注释留痕指向工单 02 的三条拆分条目。此后重跑 4 条全部 `[跳过] 条目已存在`、库零改动。此即本工单要防的「未来任何含中文注释 GBK 代码的素材批次必再踩」形态的实锤。
- 已合 main（PR #57 merged cb81de4）
