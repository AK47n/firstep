# 15 — 生成页 · 生成 + 评分清单 + 交付：static/js/ui/generate-core.js

**要做什么：** generate tab 的「生成执行 + 评分清单 + 交付（handoff）」簇迁入 `static/js/ui/generate-core.js`（generateMain / 成功区渲染 / 桌面输出开关 / 产物树 / 评分清单渲染与同步导出 / 交接说明行）。**被谁阻塞：** 02（app.js）

**状态：** 已实施（resolved）

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数（4135-4663）：generateMain 4135 / renderGenerateSuccess 4181 / desktopTopicOutputEnabled 4213 / renderArtifacts 4366 / renderScoreChecklist 4409 / scoreChecklistIdsNow 4423 / scoreChecklistSyncCurrent 4429 / scoreChecklistExportNow 4441 / initScoreChecklist 4445 / handoffPlatformLabel 4477 / handoffPlatformIde 4481 / handoffModuleLines 4484 / handoffWarnings 4495 / handoffPinLines 4499 / handoffReferenceLines 4510。
- 依赖：`$` / apiPost / apiGet / state（app.js）；fx 域件：fx/generate.js（generationOutputDirPayload / collectBindings / formatResModules / conflictDirName / isConflictError 等）+ fx/module.js（instancePayload(expanded, instances)！）+ fx/score.js（scoreChecklist* 15 件）+ fx/topic.js?；跨簇：refreshRecent（ui/recent.js，工单 11——import）；renderSelected / renderWarnings（A 簇状态读——import 自 ui/generate-recommend.js）。
- 结构钉：score-points-format.test.mjs 钉 renderScorePointPanel(scorePoints) 调用点（generateMain / renderScoreChecklist 内）→ 重指向本文件。
- 评分清单 markup：#rec-score-points 等（grep 确认 id；score-points-format 测试曾删 `id="rec-score-points"` 断言——id 随迁后不存在于 index.html，本票后仅模块内字符串）。

## 检查表

- [x] 新建 `static/js/ui/generate-core.js`：上述 15 函数逐字搬移 + import（app.js / fx/generate.js / fx/module.js / fx/score.js / fx/core.js / ui/recent.js / ui/generate-recommend.js）+ export（generateMain / renderGenerateSuccess / initScoreChecklist / renderScoreChecklist / scoreChecklistSyncCurrent / scoreChecklistExportNow）+ 头部注释
- [x] index.html：CRLF 感知行区间删除（4135-4663 内目标名；**物理升序**）+ 顶部 import 行追加
- [x] 结构钉重指向：score-points-format.test.mjs → 本文件
- [x] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 生成实况（生成一次到骨架前——smoke 基线）+ grep 零残留（16 名无定义）
- [x] 中文提交

## 实施记录（2026-05 工单 15）

### 行号复核（grep 起止锚；工单 12/13/14 删除后整体前移 ~1791）
15 函数实际位于 2344-2738；簇体（含 SKELETON_MODES + 监听器）= 2335-2443（A 段）+ 2563-2853（B 段）。函数表：generateMain 2344 / renderGenerateSuccess 2390 / desktopTopicOutputEnabled 2422 / renderArtifacts 2575 / renderScoreChecklist 2618 / scoreChecklistIdsNow 2632 / scoreChecklistSyncCurrent 2638 / scoreChecklistExportNow 2650 / initScoreChecklist 2654 / handoffPlatformLabel 2686 / handoffPlatformIde 2690 / handoffModuleLines 2693 / handoffWarnings 2704 / handoffPinLines 2708 / handoffReferenceLines 2719。issue 正文行号（4135-4663）为阶段 1 时代编号，以 grep 复核为准——与本单无关的校对修正。

### 搬迁边界（比 issue 的「15 函数」更完整）
- 迁入 ui/generate-core.js（458 行 LF）：SKELETON_MODES + 15 函数 + 8 处顶层监听器（btn-skeleton / btn-smoke / desktop-topic-output change + output-dir·btn-pick-output-dir disabled 初始化 / btn-pick-output-dir / btn-handoff / btn-handoff-copy / btn-copy-dir——import 时绑定，同 generate-recommend 先例）。
- 留 host（2444-2561 原位）：btn-generate 覆盖重发监听器——依赖 host 内联 `readinessState`（4230，readiness 簇）；经 host 顶部 import 调本模块 renderGenerateSuccess。
- 接缝：`setGenerateCoreDeps({ startFixCenter, compileBanner, toolchainsGet })`（index.html 启动区 3951 注册；工单 16 迁出修复中心后改静态 import）。renderGenerateSuccess 内 3 处原位改写：`(toolchains || {})[chosenPlatform]` → `(coreDeps.toolchainsGet ? coreDeps.toolchainsGet() : {})[chosenPlatform]`、`setTimeout(() => startFixCenter(), 100)` → `setTimeout(() => coreDeps.startFixCenter(), 100)`、`compileBanner("notool", …)` → `coreDeps.compileBanner("notool", …)`。其余函数体逐字搬移（apply-15.mjs 切片提取，零手抄）。
- 导出面（8 名）：generateMain / renderGenerateSuccess / desktopTopicOutputEnabled / renderScoreChecklist / scoreChecklistSyncCurrent / scoreChecklistExportNow / initScoreChecklist / setGenerateCoreDeps。**偏离检查表说明**：检查表 6 名中 generateMain / renderScoreChecklist / scoreChecklistSyncCurrent / scoreChecklistExportNow 当前无 host 调用点（监听器随簇迁入），按检查表导出为模块 API；desktopTopicOutputEnabled（readiness 4070/4235 用）与 setGenerateCoreDeps 是检查表漏列、host 实际必需。
- host 改动：①2246 新 import 行；②2242 A 簇 import 补 `currentTopicId`；③3951 setGenerateCoreDeps 注册；④两处簇体→注记（2335-2443 / 2563-2853）。markup id 一概未动（btn-generate / btn-skeleton / btn-handoff / btn-copy-dir / res-score-points / desktop-topic-output 均在）。

### 附带修复（行为 bug，工单 12 遗留）
实况基线探针（probe-15a-baseline.mjs，迁移前）抓到 `skeleton-msg = "currentTopicId is not defined"`：工单 12 迁 A 簇时 `currentTopicId` 未导出、host 2357/2501 引用悬空（ReferenceError 被 try/catch 吞掉，无 EXC 事件、diag 静默）——**骨架/自检冒烟与生成按钮自工单 12 起即坏**。本单修复：generate-recommend.js:45 `let currentTopicId` → `export let`（读取方 import 合法；写入仍经 setCurrentTopicId）+ host 2242 补 import。无需记 backlog（本单若不动，模块 import currentTopicId 也编不过——修复是接缝的必然构成）。基线：迁移前 FAIL（msg=currentTopicId is not defined）→ 迁移后 probe-15a PASS（main-c 28 字符）。

### 结构钉与测试
- score-points-format.test.mjs：`renderScoreChecklist(data.score_points, data.output_dir)` 与 scoreSection 两断言从 html 重指向 coreSrc（阶段 2 工单 15 重指向）；`id="res-score-points"` 断言留 html（markup 不动）。其余读 html 的测试（btn-icons / fx-guard / generate-overwrite / price-reference-clear / recent-workflows-format / recommend-telemetry / topic-cards / topic-detail / score-points-format）断言均在簇外，未受影响。
- import 修正留痕：syncStep7 真身在 ui/step-state.js:62（generate-pins.js:28 同款先例）；diag 曾报「fx/draft.js does not provide syncStep7」→ 已改。diag 首轮另报 `Duplicate export of 'setGenerateCoreDeps'`（export function 声明 + 尾部 export 清单重复）→ 已去函数位 export。

### 验证矩阵（全绿）
- node --test "tests/js/*.test.mjs"：442/442。
- python -m pytest -q：2465 passed（3 warnings 既有噪声：test_fix_errors.py:185 "\p" SyntaxWarning）。
- diag.mjs：零 EXC（favicon 404 既有噪声）；smoke.mjs 11/11。
- probe-15a-baseline.mjs：冒烟生成 PASS（迁移前 FAIL）。
- probe-15.mjs：P0 动态 import / 页面就绪 / 冒烟生成（300s 超时） / 交接提示词真实点击（894-928 字符、空态兜底） / renderGenerateSuccess 假载荷（评分清单 2 项 + 产物 2 chips + 修复中心接缝横幅） / 复制输出路径 toast / 桌面输出开关解锁 / 全程零 EXC。
- grep 零残留：16 名（15 函数 + SKELETON_MODES）在 index.html 无定义；`$("btn-handoff").addEventListener` 等已不在 host。

### 探针教训（追加）
- smoke 冒烟守卫要求 OLED 或 debug_uart 模块（skeleton.py:500：`not {"oled","debug_uart"} & set(slugs)` → 400「自检骨架需要 OLED 或 debug_uart 模块作为输出通道」）——探针须显式选 data-add="oled"/"debug_uart" 卡，不能取第一张。
- 本机有真实工具链（/api/state toolchains.stm32/mspm0 = true）→ renderGenerateSuccess 假载荷走 startFixCenter 接缝分支（假目录 → /api/compile 400 → compileBanner fail），不是 notool 分支——两者均证接缝生效。
- DeepSeek API 往返 ~240s（smoke main_c=3875 字符）——探针 P1 超时须 ≥300s；环境慢非回归（curl 直测端点佐证）。
- CDP exceptionDetails.lineNumber 为 0 基；webapp 静态文件曾与磁盘内容出现瞬时不一致（diag 旧事件误报回归）——以 Invoke-WebRequest 对比磁盘/服务内容为准。

## 风险点

- generateMain 是核心大函数（4135-4180+，含 guard 与载荷组装）：载荷读 A/B 簇状态（selectedSlugs / expanded / instances / pinBindings / chosenPlatform）——均经 import 绑定读（属性/变量读合法；**不得写**）。
- desktopTopicOutputEnabled 4213-4365（~150 行）若拼「桌面输出」二级 UI（generate 成功后区段），markup 在 generate 页——随迁无碍。
- recordLLMUsage 若在 generateMain/评分触发点被调（telemetry 记录），import 自 ui/settings.js。
