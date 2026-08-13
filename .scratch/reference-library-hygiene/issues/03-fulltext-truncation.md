# 03 — 参考全文回读改逐文件截断：根治"清单吃满配额"失明

**What to build:** 两级注入第二级的参考全文回读（read_fulltext）现在是"全部文件按序拼接 → 注入时整体截 4000 字符（EMBEDDED_CONTENT_CAP）"。files 首位常是素材清单.txt（可 10 万+ 字符），截断配额全被清单/胶水吃光，真正代码一个字符都进不了模型——大条目全文功能实际失效（MSPM0_MOTOR 1630 文件、塔克R3 193 文件都是受害者；工单 01/02 拆条后此问题仍在）。改：read_fulltext 逐文件截断（每文件独立限长，拼接总长放宽）——模块库注入已有同款先例（llm.py:431 按 file.versions 各自 _truncate_content 后求和）。

**Status:** resolved（2026-08-13）

## 现状（已核实 2026-08-13）

- reference_library.read_fulltext：files 按序拼接 file_label + 全文，无截断（"读到什么就是什么"契约在注入处执行）
- llm.py 注入：reference_fulltexts / manual_fulltexts 两个块各 `_truncate_content(fulltext)`（EMBEDDED_CONTENT_CAP=4000，llm.py:250/280）
- 后果实证：MSPM0_MOTOR 素材清单 129575 字符排首位 → 截断只剩 ~40 行清单；MSP_Motor_Ctrl/user.c 排第 36、移植.md 排第 1629，永不可见
- 约束：reference_library 不能运行时 import llm（llm → selection → reference_library → llm 会成环，C1 先例，llm 仅 TYPE_CHECKING）——截断常量/文案挪共享层时注意环
- 测试锚点：tests/test_llm.py ~2858（手动全文段文案与 file_label 标注）、test_generator.py:1242/1778（回读器行为）

## 实施

1. 截断语义下沉 read_fulltext（实施时按仓库惯例落接缝）：
   - reference_library.py 定义逐文件上限常量（建议 REFERENCE_FILE_CAP=20000 字符：单源文件/18KB 移植笔记可全量，超长文件截头带标注）；截断文案沿用 llm._truncate_content 措辞（"……（内容过长，已截断：仅展示前 N 字符，原文共 M 字符；……）……"）——常量/函数挪共享层的取舍注意环约束，文案改动必须同步字节级测试
   - 注入处总截断放宽：llm.py 两段对参考全文的 _truncate_content 改为更大的 REFERENCE_FULLTEXT_CAP（建议 120000 字符）或去掉（read_fulltext 已逐文件限长，总长天然有界 = 文件数 × 单文件上限）
2. 测试：
   - test_reference_library.py：read_fulltext 逐文件截断直测（3 个超长文件 → 每文件开头与截断标注都在、总长 > 4000；短文件完整；二进制跳过不受影响）
   - test_llm.py：同步锚定的两段注入文案（若有改动）；新增长全文用例断言注入块含各文件开头
   - test_generator.py 1242/1778 回读器用例零改动全绿
3. 真机：走一次生成流程选大条目（拆分后的电机例程或塔克R3 任一条）读全文，确认注入上下文含各文件代码开头

## 验收

- [x] pytest 全绿 + mypy src 干净
- [x] 逐文件截断：任一超长条目每文件开头可见；4000 字符总截断不再吞掉尾部文件
- [x] 协议文本（两段全文注入块）改动最小化，字节级测试同步

## 文件边界

`src/contest_generator/reference_library.py`（read_fulltext + 逐文件上限常量）、`src/contest_generator/llm.py`（注入处总截断 + 常量/文案可能的共享层挪移）、`tests/test_reference_library.py`、`tests/test_llm.py`、`tests/test_generator.py`（回归）

**明确不动的：** 模块库注入路径（已有逐文件截断）、webapp、素材库数据。

**依赖：** 与 01/02 无文件交集，可独立执行；真机验证若想用拆分后的条目可放 01/02 之后。

## 实施记录（2026-08-13，Status resolved）

**落法（与工单要点对照）：**

1. **逐文件截断下沉 read_fulltext**：`REFERENCE_FILE_CAP=20000`（reference_library 常量）——read_fulltext 对每个文件独立截断（截头带标注）；20000 = 单源文件全量、18664 字符移植笔记全量。
2. **截断文案单源**：`TRUNCATION_NOTICE` + `truncate_content(content, cap)` 从 llm 迁入 library.py（共享层，reference_library 已 import library 的 file_label——环约束满足：reference_library 仍不运行时 import llm）；llm 改为导入重出，`_truncate_content` 变薄包装（只绑 EMBEDDED_CONTENT_CAP，~15 个调用点零改动）。fix_errors.py 的同文副本不在文件边界内未动（其注释「与 llm.TRUNCATION_NOTICE 同句」因 llm 重出仍成立）。
3. **注入处总截断放宽**：两段全文注入块改用 `truncate_content(fulltext, REFERENCE_FULLTEXT_CAP)`，`REFERENCE_FULLTEXT_CAP=60000`（llm 常量）。
   - **与工单建议（120000 / 去掉）的偏差及理由**：按真库条目实测倒推——json.dumps 默认 ensure_ascii（中文 6 字节/字符），塔克R3 拆条条目全文头实测 ~1.44 字节/字符；cap=120000 或去掉时，塔克R3 条目请求体 143.7KB > MAX_REQUEST_BYTES 128KB 网关预算 → 选塔克R3 读全文必炸（旧行为是 4000 截断后正常收尾，去掉 = 把可用流程改成硬错误）。60000 = 实测最坏真实条目（塔克R3 头 113.8KB + 提示词开销）留 17KB 余量，覆盖前 18/34 个文件开头（旧 4000 只够 40 行清单）；电机拆分条目（31809 字符）整条全进无截断。
4. **测试**（+4，1273 绿 + mypy src 干净）：
   - test_reference_library：逐文件截断直测（3 超长文件 → 每文件开头与截断标注都在、总长 > 4000、短文件完整、二进制跳过不受影响）+ 截断文案与 library.truncate_content 逐字对拍（单源 pin）。
   - test_llm：2546/2857 两段注入文案测试同步（超旧 4000 上限仍全文在、总上限内不再加截断标注）；新增长全文用例（3 文件每文件开头都进注入块）+ 总截断放宽不是去掉（超 REFERENCE_FULLTEXT_CAP 仍截头带标注）。
   - test_autocommit 分类注册表 +1 条（truncate_content=read，纯字符串变换）。
   - test_generator.py 1242/1778 回读器用例零改动全绿。
5. **真机**：不走 8000 HTTP（当时跑旧代码的服务，进程 CreationDate 先于本次改动）——进程内驱动生产管线（resolve_topic_context + run_recommendation + 真实 DeepSeek，脚本 .scratch/real-run/check_2024H_ref_fulltext.py，2024H mspm0 + 电机控制例程手动参考）：全文 31809 字符 / 13 个文件标注全在、0 个文件需截断（每文件 < 20000 全量直传）。真实网关 3 次运行均放行带全文的第 1 轮请求（无 413 / 无 MAX_REQUEST_BYTES 触发、正常返回并解析）；第 1 次运行第 3 轮、第 2/3 次运行第 2 轮遇 DeepSeek flash 瞬断（连接重置 10054 / 空内容，重试 3 次仍断）——失败轮次每次不同、同尺寸请求体在更早轮次正常返回，属既有已知瞬态（PR #51 重试机制已兜底此形态），与改动无关。另以真实库数据 + FakeTransport 对全部 3 个电机拆分条目做注入级对拍：每文件标注 13/6/1 全在、代码正文（Motor_Set_ClosedLoop / Modbus_ParseFrame / 从站地址 等）在上下文。

**协议文本改动**：两段注入块的段标题 / 清单行 / 围栏格式零改动；唯一变化 = 截断标注出现的时机（4000 → 60000 字符总上限 + 逐文件 20000 标注），旧文案措辞逐字沿用。
