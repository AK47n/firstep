# 01 — 设置页「视觉服务」下拉：DeepSeek / 智谱一键切换

**Status:** resolved

**What to build:** 设置页视觉通道段顶部加「视觉服务」下拉（DeepSeek 视觉 / 智谱 GLM / 自定义），选中自动填 base_url 与模型名；切 DeepSeek 清空 key 框（防智谱 key 误发）、切智谱回填已存 key 掩码（沿用旧值）；打开页面按 base_url 推断当前模式；手动改字段自动转自定义。**后端零改动**（base_url 驱动复用判定 + 掩码沿用均已具备，见 spec「实现决策」）。spec：`.scratch/vision-provider-switch/spec.md`（用户已确认下拉形态 + 智谱 key 自动沿用）。

**Definition of done:**
- [x] index.html 视觉段加下拉 + 提示区（id=`set-vision-provider` / `vision-provider-hint`），三输入框字段 id 零改动
- [x] 回显后按 base_url 推断模式（bigmodel.cn → zhipu；api.deepseek.com 或空 → deepseek；其它 → custom），不覆盖用户字段
- [x] 切换：deepseek → 填预设 + key 清空；zhipu → 填预设 + 掩码回填；custom → 字段不动；placeholder/hint 随模式更新
- [x] 手动改 base_url/模型与预设不符 → 自动转 custom（`visionApplyingPreset` 防回调；key 手改不触发）
- [x] PUT 组装零改动（仍读三输入框，掩码沿用走既有 `_masked_optional_key`）
- [x] 全量 pytest 回归（后端未动，应 2123 绿）；手工路径清单写 Comments；Status 改 resolved

## 背景

- 视觉通道已切 DeepSeek（vision-deepseek-native/01）：默认 `https://api.deepseek.com` + `deepseek-v4-flash-vision-exp`；视觉 key 空 + DeepSeek 官方端点 → 复用主 key；自定义端点须自备 key。判定全部 base_url 驱动——本工单无需触碰。
- 用户 config.json 现仍存智谱三件套（bigmodel.cn / 智谱 key / glm-4.6v-flash）——打开设置页应推断为「智谱 GLM」模式，与用户所见一致。
- 用户已确认：下拉形态 + 切智谱自动沿用已存 key（掩码回填）。

## 测试决策

仓库无前端测试体系 → 无红证可写（显式声明跳过 TDD 红绿循环，理由：纯静态 HTML+JS 无测试挂载点）。验收 = 全量 pytest 回归 + 手工路径清单。

## Comments

**2026-08-21 实施（纯前端，index.html 一个文件三处改动）**

### 改动

1. **视觉段 HTML**：`<h2>视觉通道（可选）</h2>` 下新增「视觉服务」下拉（`set-vision-provider`：deepseek / zhipu / custom）+ 提示区（`vision-provider-hint`）；三个输入框字段 id 零改动；key 框 placeholder 改为运行时空（由模式填充）；底部 muted 说明整段重写（一键切换语义 + 手动改自动转自定义 + 不配置 = 关闭）。
2. **回显（loadSettings）**：回显三字段后追加 `visionZhipuMask = s.vision_api_key || ""`（掩码存档）与 `syncVisionProviderFromFields()`（按 base_url 推断模式：bigmodel.cn → zhipu；api.deepseek.com 或空 → deepseek；其它 → custom；只动下拉与提示，不覆盖已存字段）。
3. **新 JS 块**（loadSettings 后）：`VISION_PRESETS` / `VISION_HINTS` 两表 + `syncVisionProviderFromFields` + `applyVisionPreset(mode)` + 两个事件绑定：
   - 下拉 change → applyVisionPreset：deepseek → 填预设 + **key 清空**（安全必需：显式 key 优先，不清空会把旧智谱 key 发给 DeepSeek）+ placeholder「留空 = 复用主 DeepSeek key」；zhipu → 填预设 + key 回填 `visionZhipuMask`（掩码 PUT → 后端 `_masked_optional_key` 沿用旧值）+ placeholder「智谱开放平台 API key」；custom → 字段不动 + placeholder「自定义服务 API key」。
   - base_url / model 的 input 监听：`visionApplyingPreset` 标志屏蔽预设填充期；与当前预设不符 → 下拉自动转 custom + 提示更新（key 手改不触发）。
4. **PUT 组装零改动**：仍读三个输入框（`vision_base_url` / `vision_api_key` / `vision_model`），掩码沿用走既有 `_masked_optional_key`。

### 自检

- 内嵌 `<script>`（唯一块）经 node --check 语法 OK；五个相关元素 id 均唯一。
- 修复过程记录：首版 edit 曾误吞「本地模型下拉联动」两行（函数头），已当场补回并经 node --check 确认无损。
- 交互逻辑核对：用户现 config（bigmodel.cn + 智谱 key）→ 打开设置页下拉显示「智谱 GLM」✓；切 DeepSeek 保存 → 视觉走 DeepSeek 复用主 key ✓；再切回智谱 → 掩码沿用 ✓；手动改 base_url → 自动转 custom ✓。

### 测试

全量 pytest：**2123 passed**（102.58s，3 个既有 SyntaxWarning 来自 tests/test_fix_errors.py 转义，与本次无关）。后端零改动，回归全绿。

### 手工路径清单（留用户真机验收）

1. 打开设置页 → 视觉服务下拉显示当前模式（智谱 config → 「智谱 GLM」）
2. 切「DeepSeek 视觉」→ base_url/model 自动填 DeepSeek 预设、key 框清空 → 保存 → 上传 PDF，图注走 DeepSeek 视觉（telemetry provider=deepseek）
3. 切「智谱 GLM」→ 自动填智谱预设、key 掩码回填 → 保存 → 上传 PDF 走智谱
4. 手动改 base_url 为任意值 → 下拉自动转「自定义」，提示更新


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
