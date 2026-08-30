# 04 — 数字识别模板落地（真实模块）

**要做什么：** library/modules/k230 成为完整 AI 数字识别方案：新增 digit 模板（CanMV main_digit.py 推理脚本 + assets 部署包），manifest 声明模板条目（dependencies=["digit_uart"]），选中后产物 = 工程根渲染 main.py + mp_deployment_source/（deploy_config.json + kmodel 8 类数字模型）+ 主控挂 digit_uart；README.md 产物清单补 mp_deployment_source 行。

**被谁阻塞：** 01（帧契约）、02（模板级依赖）、03（资产分发）。

**状态：** resolved

- [x] 模型资产入库：21F 8 类数字 kmodel（7,596,008 字节）复制至模块 assets/，改名 `digit8_anchorbase_320.kmodel`；deploy_config.json 资产化（kmodel_path 指向新名，类别/阈值/anchors 与 21F 一致）
- [x] code/main_digit.py 模板：CanMV 风格与 blob 模板同构（中文注释头 + try/except/finally + 契约占位符不重抄字面量），推理管线（libs.PlatTasks.DetectionApp + libs.PipeLine）参考 21F det_uart.py；运行期读 /sdcard/mp_deployment_source/deploy_config.json；帧发送按 DIGIT 契约（帧头 + 每目标一行 + 空行帧尾，0 目标也发帧头）；显示模式变量带注释（默认与 21F 一致）
- [x] k230 manifest：python_artifact.templates 加 digit 条目（id=digit、name=AI 数字识别、description 说明 8 类数字与部署包、dependencies=["digit_uart"]、assets=2 个部署文件）；blob/rect 条目保持零改动
- [x] 真实库集成测试：选 k230 + python_templates={k230: digit} → 产物 = 渲染后 main.py（帧契约占位符已注入且与契约常量逐字一致）+ mp_deployment_source/ 两文件（字节大小/内容断言）+ 主控文件集含 digit_uart 不含 coord_detect；选 blob/rect → 产物与基线逐字节一致
- [x] README.md 产物清单：加 mp_deployment_source 行（部署包说明）+ 摘要文件行含资产
- [x] 编译冒烟：digit 模板产物 stm32 / mspm0 编译矩阵 0 error（复用既有 compile_runner 回归）

**实现备注（code-review 双轴驱动，2026-08-30）：**

- kmodel 与 21F 原模型逐字节一致（SHA256 校验过，7,596,008 字节）；deploy_config.json 除 kmodel_path 外与 21F 完全一致（categories 1~8、confidence_threshold 0.4、anchors 三组）。
- main_digit.py 相对 21F 例程的两处有意改进：① **0 目标也发帧头**（`--- frame N | 0 targets ---\n\n`）——主控每帧稳定帧界；解析端 count=0 帧不参与最佳帧比较，不污染。② 删去 21F 未消费的 `nms_option` 死读（spec 评审 (c)）；保留 `model_type == "AnchorBaseDet"` 防御分支（config 驱动，与参考例程一致）。
- 渲染安全：契约格式串经 render_python_artifact 的 replace 注入不被二次解释，模板 .format(n=.., m=..) 自行消费 {n}/{m} 与字段名占位（spec 评审确认无双重 format 风险）。
- **编译冒烟验证范围**（spec 评审 (a)：本机无 Keil UV4 / gmake，无法真跑编译矩阵）：生成侧全部静态门禁（include 解析 / 自包含 / 死依赖）经真实库 generate_project 双平台跑通；C 侧主体 = digit_uart（module-polish/04 编译矩阵已 0 error 过）+ main.c 三行调用；CanMV 侧 main_digit.py 语法过 py_compile，真机行为（libs 管线 + 模型推理）留待 K230 上板验证。
- blob/rect 基线补强（spec 评审 (a)：原只断言 rect 走 find_rects）：rect 继承模块级 coord_detect（无 digit_uart + 无部署包）断言进测试；blob 无部署包断言已有。
- 测试 79 用例绿（04 新增 5：manifest 形状 / 模板占位符与素材 / stm32 生成 / mspm0 生成 / blob 无部署包）；全量回归 2946 passed；py_compile + JSON 解析校验通过。
