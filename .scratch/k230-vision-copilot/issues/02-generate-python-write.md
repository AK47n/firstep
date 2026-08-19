# 02 — 生成写盘机制：选中带副产物模块 → 额外写 `.py`

**What to build:** 生成器在落盘时识别「声明了 Python 副产物」的选中模块，渲染并额外写出一份 `.py` 到输出目录；协议帧格式单源定义（渲染 `.py` 与主控侧解析同吃一份契约，不再各抄一份）。配一个最小 k230 模块骨架走通「选中 → 产物含 `.py`」，此时脚本只需「sensor 初始化 + 串口只发 `N` 无检测帧」即可跑通链路，视觉逻辑留 03。

**Blocked by:** 01 — manifest「Python 副产物」声明能力

**Status:** resolved

完成（分支 k230-vision-copilot/02）：k230_render.py 契约单源（BALL_FRAME_FIELDS/BALL_FRAME_FORMAT 派生 + NO_DETECT_FRAME + UART_BAUDRATE + 占位符渲染纯函数）+ generator.py `_write_python_artifacts`（写工程根，同写阶段 try 内 rmtree 兜底；跨模块同名 output / 模板缺失 / 撞工程既有文件（含 main.c——unlink 因此挪到副产物写盘后，语义不变）→ PythonArtifactError）+ errors.py 登记 + tests/test_k230_artifact.py 18 用例（防漂移：C 源机械提取 parse_ball_line 字段序/前缀守卫/无检测帧 + ml_uart 波特率比对锁定；生成层：选中含 .py / 未选逐字节一致 / 双平台 / 失败路径）。全量 1765 绿（1747 基线 + 18）+ mypy 46 文件干净。code-review 双轴：Spec 轴提的分隔符/前缀防漂移缺口已补测；双轴同提的「output 撞工程既有文件静默覆盖」已修（写时存在性判定 + 测试）。留痕：CONTEXT.md 词条（Python 副产物/帧契约）留 03；render_ball_frame 现仅测试消费（工单 02 checklist 第 2 条「纯函数/常量」载体，03 模板组装复用）；模板读盘 errors="replace" 与模块源同策略（master.py 同规）。

- [x] `generate`（`generator.py`）识别选中模块的副产物声明，渲染并写出 `.py` 到输出目录（落盘顺序与 `_copy_module_files` / patcher 一致，中途失败不留半成品）
- [x] 契约单源：CSV 帧格式常量（`B,<cx>,<cy>,<confidence>,<x1>,<y1>,<x2>,<y2>` / `N`，115200）作为独立可测的纯函数/常量，`.py` 渲染从这里取，不与主控侧解析各抄一份
- [x] 选中带声明的模块 → 生成产物里出现该 `.py` 文件；未选任何带声明模块 → 产物与现在**逐字节一致**
- [x] 新增测试：生成层断言产物含/不含 `.py`，契约纯函数单测
- [x] 全量测试绿 + mypy 干净
