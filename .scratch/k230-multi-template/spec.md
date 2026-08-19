# spec：k230-multi-template —— K230 .py 多模板（首批矩形识别）

## 问题陈述

K230 视觉副控目前只有「色块追踪」一种能力模板（k230 模块 python_artifact 单模板），资料包（sources/materials/k230资料）里的矩形识别（04 例程）、AI 数字识别（09_2 + 2023E 题例）、线段识别（05）、激光回中（07/12）等大量例程无法被生成器利用——新题（如矩形定位类）学生只能手改 main.py。用户定调：扩充 K230 .py 模板，首批按「单模块多模板」形态做矩形识别。

## 方案

### 机制：python_artifact 多模板（向后兼容）

- manifest 的 `python_artifact` 支持两种形状：
  - 旧形状（现状）：`{"template": ..., "output": ...}`——解析为单模板（id = "default"），存量 manifest 逐字节兼容。
  - 新形状：`{"templates": [{id, name, description, template, output}...], "default": <id>}`——多模板声明。
- 解析层统一为模板列表；缺省选择 = default 模板（旧形状 = 唯一模板）。
- 生成请求新增可选载荷 `python_templates: {slug: <template_id>}`：按选中模板渲染对应 .py 写出；缺省 = default；非法 id / 未声明模板的模块带选择 = 大声失败（400 中文）。
- 渲染管线 `_write_python_artifacts` 按选择读模板（模板文件仍相对模块目录），output 冲突校验照旧（跨模块同名 output 仍拒绝）。

### 首批模板：矩形识别（k230 模块）

- k230 manifest 升级为多模板：`[blob（色块追踪 = 现 main.py，default）, rect（矩形识别）]`。
- 新增 `code/main_rect.py`：04 例程普适化——灰度 → 二值化（阈值可配常量）→ `find_rects` → 取最大矩形 → 组 **B 帧（coord_detect 现有契约，主控零改动）** 经 UART 发送；帧格式 / 波特率走占位符渲染（{{coord_frame_format}} 等），与色块模板同契约单源。
- 依赖不变：rect 模板仍依赖 coord_detect（模板级依赖替换机制留第二批——AI 数字识别才需要 digit_uart）。

### 前端

- 步骤 6 模块卡：选中带多模板的模块（k230）时显示模板下拉（name + description）；选择随生成请求透传；done 载荷回显。

## 用户故事

1. 作为参赛学生，题面要求「识别矩形 / 大矩形并输出位置」——k230 模块模板选「矩形识别」，生成的 main.py 输出 B 帧，主控 coord_detect 解析照旧，我直接在 TODO 区写决策逻辑。
2. 作为参赛学生，不选模板（默认色块）——生成产物与现在逐字节一致，回归护栏。
3. 作为补录者，新增视觉能力 = 在 k230 模块 code/ 加模板文件 + manifest templates 加一条声明，无需改生成器。
4. 作为维护者，模板声明了 name/description——前端下拉与（将来的）AI 推荐都能消费。

## 实现决策

- manifest.py：`PythonArtifactSpec` 扩展（templates 列表 + default id）；旧形状解析为单模板列表（id="default"）；新形状校验（id 唯一非空 / default 必须存在于列表 / template 相对路径 / output 纯文件名，照现有校验口径）；两种形状并存冲突 = ManifestError。
- 选择载荷解析：webapp 生成路由取 `python_templates`（可选 dict），域层校验（slug 是已选模块且该模块声明多模板；id 在模板列表内），非法 = PythonArtifactError → 400；旧请求不带 = 全默认（逐字节兼容）。
- `_write_python_artifacts(manifests, module_library_dir, output_dir, template_choices)`：按选择读模板渲染；缺省 default。
- k230 manifest：templates = blob（现 code/main.py，default）+ rect（新 code/main_rect.py，description 声明能力方向「矩形定位」）。
- main_rect.py：结构照现有 main.py（FPIOA/UART/MediaManager/异常清理骨架），识别段替换为灰度→二值→find_rects→最大矩形→corners 外接框→B 帧；二值化阈值 = 可配常量（注释说明现场标定方法）；帧契约占位符与 k230_render 单源。
- 前端：模块卡渲染模板下拉（python_artifact.templates 长度 > 1 时显示）；默认选中 default；生成请求带 choices；done 载荷回显所选模板。

## 测试决策

- manifest 解析测试：旧形状逐字节兼容 / 新形状解析 / 非法 id / default 缺失 / 形状并存冲突（照 test_manifest 先例）。
- 渲染选择测试（照 test_k230_artifact 先例）：按 id 渲染对应模板 / 缺省 = default / 非法 id 大声失败 / 跨模块 output 冲突照旧。
- 防漂移测试：rect 模板与 blob 模板的帧契约占位符都经 k230_render 渲染后与 C 侧 parse_coord_line 字段序一致（现有防漂移测试扩展到新模板）。
- 生成请求透传测试（照 test_webapp 先例）：带 choices / 缺省 / 非法 id 三条路径。
- 前端逻辑不单测（项目先例：前端由真机验收覆盖）。

## 范围外

- AI 数字识别模板（依赖 kmodel 二进制分发机制——参考库二进制跳过、模块复制只认 manifest files，需新决策）——第二批。
- 线段识别模板（输出线段端点/角度，需定义新帧格式 + 主控侧扩展）——第二批。
- 模板级依赖替换（模板声明自己的依赖，如 digit → digit_uart）：机制设计好但首批两模板依赖相同，暂不实现，第二批启用。
- AI 推荐链路输出模板建议（select 契约扩展）：v1 前端手动选，留后续。
- 多模板同时选中（K230 一次只能跑一个 main.py）：v1 每模块单选。

## 补充说明

- 素材：sources/materials/k230资料/codecao/04矩形识别与常见的图像处理.py（find_rects 用法）、code/05（find_blobs）、code/13（串口通信）已在包内；本次只产出模块库模板文件，不动资料包。
- 语言规范：spec / 工单 / 提交信息中文。
