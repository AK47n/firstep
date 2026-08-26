# 15 — 生成页 · 生成 + 评分清单 + 交付：static/js/ui/generate-core.js

**要做什么：** generate tab 的「生成执行 + 评分清单 + 交付（handoff）」簇迁入 `static/js/ui/generate-core.js`（generateMain / 成功区渲染 / 桌面输出开关 / 产物树 / 评分清单渲染与同步导出 / 交接说明行）。**被谁阻塞：** 02（app.js）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数（4135-4663）：generateMain 4135 / renderGenerateSuccess 4181 / desktopTopicOutputEnabled 4213 / renderArtifacts 4366 / renderScoreChecklist 4409 / scoreChecklistIdsNow 4423 / scoreChecklistSyncCurrent 4429 / scoreChecklistExportNow 4441 / initScoreChecklist 4445 / handoffPlatformLabel 4477 / handoffPlatformIde 4481 / handoffModuleLines 4484 / handoffWarnings 4495 / handoffPinLines 4499 / handoffReferenceLines 4510。
- 依赖：`$` / apiPost / apiGet / state（app.js）；fx 域件：fx/generate.js（generationOutputDirPayload / collectBindings / formatResModules / conflictDirName / isConflictError 等）+ fx/module.js（instancePayload(expanded, instances)！）+ fx/score.js（scoreChecklist* 15 件）+ fx/topic.js?；跨簇：refreshRecent（ui/recent.js，工单 11——import）；renderSelected / renderWarnings（A 簇状态读——import 自 ui/generate-recommend.js）。
- 结构钉：score-points-format.test.mjs 钉 renderScorePointPanel(scorePoints) 调用点（generateMain / renderScoreChecklist 内）→ 重指向本文件。
- 评分清单 markup：#rec-score-points 等（grep 确认 id；score-points-format 测试曾删 `id="rec-score-points"` 断言——id 随迁后不存在于 index.html，本票后仅模块内字符串）。

## 检查表

- [ ] 新建 `static/js/ui/generate-core.js`：上述 15 函数逐字搬移 + import（app.js / fx/generate.js / fx/module.js / fx/score.js / fx/core.js / ui/recent.js / ui/generate-recommend.js）+ export（generateMain / renderGenerateSuccess / initScoreChecklist / renderScoreChecklist / scoreChecklistSyncCurrent / scoreChecklistExportNow）+ 头部注释
- [ ] index.html：CRLF 感知行区间删除（4135-4663 内目标名；**物理升序**）+ 顶部 import 行追加
- [ ] 结构钉重指向：score-points-format.test.mjs → 本文件
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 生成实况（生成一次到骨架前——smoke 基线）+ grep 零残留（16 名无定义）
- [ ] 中文提交

## 风险点

- generateMain 是核心大函数（4135-4180+，含 guard 与载荷组装）：载荷读 A/B 簇状态（selectedSlugs / expanded / instances / pinBindings / chosenPlatform）——均经 import 绑定读（属性/变量读合法；**不得写**）。
- desktopTopicOutputEnabled 4213-4365（~150 行）若拼「桌面输出」二级 UI（generate 成功后区段），markup 在 generate 页——随迁无碍。
- recordLLMUsage 若在 generateMain/评分触发点被调（telemetry 记录），import 自 ui/settings.js。
