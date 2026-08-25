# 工单 01：评分点覆盖清单（勾选 + 进度 + 复制核对表）

Status: resolved
Slug: score-checklist
依赖：无（纯前端 index.html + tests/js；score_points 载荷不动）

## 背景

生成结果评分点从只读文本升级为可勾选核对清单，按工程目录持久化勾选进度，
支持一键复制核对表文本（B3，用户已确认：按目录持久化 + 复制文本）。

## 验收标准

- [x] index.html `#res-score-points` 区块改为：`.res-label`「评分点核对」+
      操作行（`#sp-progress` 进度 + `#btn-score-export` 复制按钮）+ `#sp-list` 清单；
      移除 `white-space:pre-line`。
- [x] 纯函数（自包含、内联 esc，tests/js 抽取范式）：
      `scoreChecklistKey(outputDir)` / `scoreChecklistItemsHTML(points, checkedSet)` /
      `scoreChecklistProgressHTML(checkedCount, total)` /
      `scoreChecklistExportText(points, checkedSet)` / `scoreChecklistParse(storageValue)` /
      `scoreChecklistSave(key, ids, storage)` / `scoreChecklistLoad(key, storage)`。
      （评审后另抽 `scoreChecklistId(p,i)` / `scoreChecklistChecked(set,id)` 消重，
      parse/load 按 spec 返回 Set。）
- [x] 每行 = checkbox + `id｜区（基础/发挥）｜分值｜句子引用｜描述`；id 规则
      与 formatScorePoints 一致（`p.id || "score-"+(i+1)`）。
- [x] 勾选变更实时更新进度 + 写 localStorage（key `score-checklist:<output_dir>`）；
      隐私模式 storage 抛错静默降级。
- [x] 复制按钮 → 剪贴板（clipboard → execCommand 兜底）导出 `☑/□` 行文本 + toast；
      无评分点时 toast info 提示。
- [x] 生成成功回调用 `renderScoreChecklist(data.score_points, data.output_dir)`
      替代原 textContent 赋值；显隐逻辑不变。
- [x] tests/js/score-checklist.test.mjs 覆盖上述纯函数（坏输入/转义/往返/异常）；
      node --test 全绿，既有测试不回归。

## 实现说明

- 事件委托在 `#res-score-points` 上（change + click），不逐条绑。
- 导出文本行格式（对照 formatScorePoints）：
  `☑/□ id｜基础/发挥｜N 分/未标分｜句子 a、b/未关联原文｜描述`。
- 勾选 id 以当前 points 为准：旧目录存储里的过期 id 自然不命中（无害）。

## code-review 落实（双轴）

- Standards：①抽 `scoreChecklistId(p,i)` / `scoreChecklistChecked(set,id)` 消 4 处 id 兜底与
  2 处 indexOf 重复；②parse/load 统一返回 Set（`checkedSet.has`）；③模块网格式样式维护
  「自包含内联 esc」范式（moduleGridHTML 内联 escHtml，不再依赖全局 esc）。
- Spec：①补「内嵌母版」徽标（`!(entry.files||[]).length && !m.python_artifact`，复用
  moduleBadges 判据）；②`.res-label` 恢复为纯「评分点核对」（说明文案移除）；
  ③平台短标签 STM32/MSPM0 为有意偏离（卡片 180px 宽度下 toUpperCase 全名过长，与
  recentPlatformLabel 查表口径一致）——记录于实现说明；④`.sp-item.done` 弱化描边为
  视觉增强（spec 未要求但无损，保留）。
- 验证：node --test tests/js 240 全绿；headless 探针（勾选/持久化/恢复/复制/置灰/搜索/添加）通过。
