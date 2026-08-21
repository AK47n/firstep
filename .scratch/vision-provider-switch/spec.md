# 视觉服务切换（DeepSeek / 智谱 GLM 一键切换）

## 问题陈述

视觉通道已默认切 DeepSeek（工单 vision-deepseek-native/01），但用户在 DeepSeek 视觉与智谱 GLM 视觉之间切换时仍要手工填写 base_url / 模型名 / key——要记两个服务商的 URL 和模型名，且容易配错（例如把智谱 key 留在框里切到 DeepSeek，显式 key 优先会把智谱 key 发给 DeepSeek）。需求：「便于让用户切换两种 deepseek 和 glm 的视觉模型」。

## 方案

设置页视觉通道段顶部加「视觉服务」下拉，三个预设项：

- **DeepSeek 视觉（推荐）**：自动填 base_url=`https://api.deepseek.com`、模型=`deepseek-v4-flash-vision-exp`，**key 框清空**（关键：避免显式 key 优先把旧智谱 key 发给 DeepSeek），提示「留空 = 复用主 key」。
- **智谱 GLM**：自动填 base_url=`https://open.bigmodel.cn/api/paas/v4`、模型=`glm-4.6v-flash`，key 框自动回填**已保存智谱 key 的掩码形态**（PUT 掩码 → 后端 `_masked_optional_key` 沿用旧值，用户无需重新找 key）。
- **自定义**：三字段保持原样，提示「自备 key；主 key 只在 DeepSeek 官方端点复用，绝不外发」。

打开设置页时按回显的 base_url 自动推断当前模式（bigmodel.cn → 智谱；api.deepseek.com 或空 → DeepSeek；其它 → 自定义），下拉不覆盖用户已存字段。手动修改 base_url / 模型且与当前预设不符 → 下拉自动转「自定义」（key 手改不触发）。

## 用户故事

1. 作为用户，打开设置页就能看到当前视觉模式，不用记任何 URL / 模型名。
2. 作为用户，点一下「DeepSeek 视觉」保存，视觉即走 DeepSeek 并复用主 key（key 框自动清空，不会误发智谱 key）。
3. 作为用户，点一下「智谱 GLM」保存，视觉即走智谱 GLM-4.6V-Flash，key 自动沿用已保存的智谱 key。
4. 作为用户，手动改字段后下拉自动转「自定义」，行为与现状完全一致（自定义端点须自备 key）。
5. 作为用户，不配置 = 视觉关闭，其余功能不受影响（语义不变）。

## 实现决策

- **后端零改动**：vision-deepseek-native/01 的 base_url 驱动判定已天然覆盖两种模式（DeepSeek 官方端点 → 复用主 key；智谱端点=自定义端点 → 须自备 key）；掩码沿用（`_masked_optional_key`）、回显（`_mask_api_key_display`）均已有。本工单纯前端（index.html 一个文件）。
- 切换即填字段（base_url/model），不引入新 config 字段——「用户选了哪个模式」由 base_url 持久化推断，无 schema 迁移。
- 切 DeepSeek 清空 key 框是**安全必需**（显式 key 优先语义），不是可选项。
- 防回调：预设填充期间用 `visionApplyingPreset` 标志屏蔽 input 监听，避免自动转 custom 打架。
- 掩码存档变量 `visionZhipuMask` 在 loadSettings 回显时记录，供切回智谱时回填。

## 测试决策

- 仓库无前端测试体系（纯 Python 测试仓库）→ 本工单无红证可写；验收 = 全量 pytest 回归（后端零改动，应 2123 全绿）+ 手工路径清单（写进工单 Comments）+ 真机验收留用户。
- 手工路径：① 打开设置页下拉显示当前模式（智谱 config → 智谱）；② 切 DeepSeek → 字段自动填 + key 清空 → 保存 → 上传 PDF 走 DeepSeek 视觉（provider=deepseek）；③ 切智谱 → 字段自动填 + key 掩码回填 → 保存 → 走智谱；④ 手动改 base_url → 下拉自动转自定义。

## 范围外

- 不做第三种预设（如 OpenAI / 通义）；下拉之外仍可自由填写任意 OpenAI 兼容端点（即「自定义」）。
- 不改后端复用判定 / 不新增 provider 字段 / 不做自动降级链。
- 不处理智谱 key 的新增配置流程（用户可在智谱模式下直接填入新 key 保存）。

## 补充说明

- 语言规范：工单 / spec / 提交信息中文。
- 关联：vision-deepseek-native/01（默认切 DeepSeek + key 复用）、vision-eyes/01-04（智谱 GLM-4V-Flash 通道，用户已有智谱 key）。
