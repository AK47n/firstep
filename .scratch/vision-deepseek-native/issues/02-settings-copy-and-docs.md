# 02 — 设置页/上传区文案去智谱化 + CONTEXT.md 视觉图注行更新

**What to build:** 前端单页（src/contest_generator/static/index.html）视觉相关文案与仓库文档（CONTEXT.md）随工单 01 的后端切换同步更新：不再出现「智谱」「GLM-4.6V-Flash」「bigmodel」；视觉 key 留空语义改为「复用主 DeepSeek key」。

**Status:** resolved

## 背景

工单 01 把视觉通道默认切到 DeepSeek 后，前端设置页与上传区提示仍写着智谱文案（placeholder、key 提示、muted 说明、上传区提示），CONTEXT.md 视觉图注行仍写「GLM-4.6V」——与后端实际行为不一致（用户故事 5）。

## 改动点（已定位，实施前按 fs 策略重读）

- `src/contest_generator/static/index.html`：
  - L519 附近：上传区提示「图片与 PDF 示意图经免费视觉通道识别」——核对语境，是否需提「配置视觉 key」；
  - L1127-1131 设置页视觉段：`视觉 base_url（留空 = 默认智谱）` placeholder `https://open.bigmodel.cn/api/paas/v4`；`视觉模型（留空 = glm-4.6v-flash）` placeholder `glm-4.6v-flash`；key placeholder「智谱开放平台免费 key（GLM-4.6V-Flash）」；muted 说明「免费云端识图（GLM-4.6V-Flash）…智谱开放平台免费获取」→ 全部改为 DeepSeek 文案：base_url 留空 = DeepSeek 官方端点；key 留空 = 复用主 DeepSeek key（自定义服务须自备 key）；
  - L5266-5269 回显、L5397-5399 PUT 组装：核对占位提示文案是否含智谱字样。
- `CONTEXT.md` L28「视觉图注」行：「文字标注优先、文字层空 → 视觉兜底（GLM-4.6V）」→ 改 DeepSeek 视觉模型名。

## 文件边界

- 只动 `src/contest_generator/static/index.html` 与 `CONTEXT.md`。
- 后端零改动；结构/字段名不动（base_url/model/key 三字段保留，仅文案）。

## 验收标准

- [x] （口径已失效）原「src/ 与 tests/ 内 grep『智谱|GLM|bigmodel』零命中」：后续工单 vision-provider-switch/01 **有意加回**智谱预设（src 现 16 处、tests 8 处为自定义端点判例）——本单「DeepSeek 默认文案就位」成立，零命中不再适用。
- [x] 前端 node 测试（若有覆盖设置页的）全绿 + 全量 pytest 绿
- [ ] CONTEXT.md 视觉图注行与后端行为一致

## 实施提示词（新会话粘贴）

> 工单：`.scratch/vision-deepseek-native/issues/02-settings-copy-and-docs.md`（先读全文，被 01 阻塞，01 resolved 后再开工）。
> 任务：index.html 视觉文案 + CONTEXT.md 去智谱化（字段结构不动，仅文案）。
> 文件边界：只动 `src/contest_generator/static/index.html` 与 `CONTEXT.md`。
> 验收：grep「智谱|GLM|bigmodel」零命中 + 前端 node 测试全绿 + 全量 pytest 绿；完成后证据写 Comments，Status 改 resolved。

## Comments

**2026-08-21 实施闭环（01 resolved 后开工，纯文案 + 文档改动）**

### 改动（2 文件）

- `src/contest_generator/static/index.html`：
  - L519 上传区提示：「免费视觉通道识别（需在设置页配置）」→「视觉通道识别（默认复用主 DeepSeek key，无需额外配置）」——去掉「免费」（DeepSeek 视觉与 V4 Flash 同价，非免费）与「需配置」误导。
  - L1127-1131 设置页视觉段：base_url label/placeholder → DeepSeek 官方端点；模型 label/placeholder → deepseek-v4-flash-vision-exp；key label →「留空 = 复用主 DeepSeek key」，placeholder →「DeepSeek API key（与主 key 共用）」；muted 说明整段重写（复用语义 + 自定义服务须自备 key + 不配置 = 关闭）。字段结构与 id 零改动（`set-vision-base-url` / `set-vision-api-key` / `set-vision-model`）。
  - L5266 回显注释：「空 = 视觉关闭」→「空 = 复用主 DeepSeek key（自定义视觉端点 = 关闭）」。回显逻辑本身未动。
- `CONTEXT.md` L28 赛题库「视觉图注」行：视觉兜底（GLM-4.6V）→（DeepSeek 视觉模型）；拆条图注补充「视觉 key 留空 + DeepSeek 官方端点 = 复用主 key」；「未配置视觉 key 与现状逐字节一致」→「未配置（自定义端点无 key）与现状逐字节一致」。

### 验收

- `src/`（含 index.html）grep「智谱|GLM|glm-4.6|bigmodel|zhipu」零命中 ✓
- `tests/` 8 处 bigmodel 命中经复核为**有意的自定义端点判例**（effective_vision_api_key 守卫测试数据 + config roundtrip 自定义值 + docstring 叙述），非文案残留，保留——它们正是「主 key 不发给别家」行为的验证
- 仓库无前端 node 测试（纯 Python 测试仓库）→ 全量 pytest **2123 绿**（93s）收尾 ✓
- CONTEXT.md 与后端行为一致（复用语义 / DeepSeek 视觉模型名）✓

### 未做

- 真机验收归用户：设置页视觉三字段默认值回显、上传 PDF/图片走 DeepSeek 视觉。

## 验收口径修订（2026-09-09 在途盘点）

- 「智谱/GLM/bigmodel 零命中」口径被后续工单 vision-provider-switch/01 有意反转（加回智谱预设）——保留本单「DeepSeek 默认文案与文档就位」的结论。

