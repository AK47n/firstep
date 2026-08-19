# 03 — k230 模块落地 + 真实视觉模板（色块追踪/球检测）

**What to build:** 在模块库里落一个真实的 `k230` 模块，选中后主控侧自动挂上 `ball_detect` 串口解析（依赖展开），K230 侧得到一份**真可跑**的 CanMV `main.py`：sensor 采图 → find_blobs 色块追踪 → 组 CSV 帧 → UART 发送。协议与主控 `ball_detect` 解析严格对齐。

**Blocked by:** 02 — 生成写盘机制

**Status:** resolved

- [x] 新建 `k230` 模块（`library/modules/k230/`）：manifest 声明 `dependencies: ["ball_detect"]`（主控侧串口解析 + 引脚由 ball_detect 提供，k230 自身**不重复声明串口 pins**——避免与 ball_detect 的 UART 实例 / 共享串口机制相撞）+ Python 副产物声明 + 双平台条目（files 空 = 主控侧无自有 C 文件）
- [x] `.py` 模板为完整可跑 CanMV 脚本：FPIOA 串口映射 → Sensor 初始化 → find_blobs 色块追踪 → 组 `B,<cx>,<cy>,<confidence>,<x1>,<y1>,<x2>,<y2>` / `N` 帧 → UART 写出；开机自启动（`main.py`）
- [x] 帧格式严格对齐 `ball_detect` 解析（字段顺序 / 逗号分隔 / 换行结尾 / `N` 无检测分支）——两侧从契约单源派生，测试断言一致
- [x] 素材来源：`k230资料/code/05色块追踪与线段识别.py`（find_blobs）与 `k230资料/code/13_与天猛星串口通信.py`（FPIOA + UART 发送），识别结果组帧与 `ball_detect` 契约对齐
- [x] 生成层测试：选中 `k230` → 产物含主控侧 `ball_detect` 解析（依赖自动展开）+ K230 侧 `.py`，`.py` 内容断言（含 sensor / find_blobs / 组帧 / uart）
- [x] 全量测试绿 + mypy 干净

完成（分支 k230-vision-copilot/03）：manifest 双平台 files 空 + pins 空（串口由依赖 ball_detect 提供）+ python_artifact（template code/main.py → output main.py）+ dependencies:["ball_detect"]；main.py 模板 = FPIOA UART2（11/12 脚，照 13_与天猛星串口通信）→ Sensor 1024x768（照 05 色块追踪）→ find_blobs（阈值/ROI/步长/像素阈值照 05）→ 最大色块组帧（FRAME_FORMAT.format，cx/cy/confidence=1.0 恒值带注释/x1/y1/x2/y2 = x/y/x+w/y+h）→ uart.write(frame+"\n") / N+"\n"、50ms 节流；帧格式/无检测帧/波特率全走占位符渲染（模板不重抄字面量，测试断言 BALL_FRAME_FORMAT 不在模板正文）。

测试（test_k230_artifact.py 工单 03 段 + 防漂移锁扩双平台）：manifest 形状 + 真实模板契约渲染（FRAME_FORMAT 渲染后与契约逐字一致、kwarg = 字段全集、四要素齐备）+ generate_project 双平台依赖展开断言（stm32：ball_detect_stm32.c/.h 落盘 + main.py；mspm0：ball_detect.c + DIGIT_UART 实例保留 + main.py）；C 侧防漂移三锁 parametrize 扩 mspm0 ball_detect.c + 新增 mspm0 syscfg DIGIT_UART.targetBaudRate 波特率锁。test_module_independence.py：依赖形态两分——零 C 文件的纯 Python 副产物模块豁免死依赖检查（豁免限声明 python_artifact 的模块），k230 是首个该形态模块。CONTEXT.md 补「Python 副产物」词条（工单 02 留痕 03）。全量 1774 绿（1765 基线 + 9）+ mypy src 46 文件干净（tests 侧 14 个错误全在既有未动文件，非本工单引入；改动文件零错误）。CHANGELOG 23:22 词条。

留痕：kit/source_url 留空待人补填（K230 套件型号与购买链接，AI 不猜——照 ball_detect 先例）；verified:false（.py 未上板真机验证，编译矩阵不适用）；真机验收属人工验收（spec Testing Decisions）；置信度恒 1.0（色块识别无置信度，识别类能力后续给真值）；数字识别能力（digit_uart 对端）留工单 04 前的能力扩展。
