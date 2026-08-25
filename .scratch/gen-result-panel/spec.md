# 生成结果面板重做：两列网格（B1）

## 问题陈述

生成完成结果区（#generate-result，index.html ~1143）现在是纵向平铺：编译横幅 → h3「生成完成」→ 输出目录行 → 产物 → include path → 模块文件 → 评分点 → 构建提示 → h3「工程结构」→ 结构树 pre。信息密度低、层级不清：路径/产物/评分点/结构树混在一列里，宽屏大量留白。

## 方案（两列网格，已与用户确认）

宽屏两列：左列 = 工程文件（输出目录 / include path / 模块文件 / 构建提示）+ 自动附带产物 + 评分点；右列 = 工程结构树。窄屏（<1180px）自动回落单列。每块加 `.res-label` 小标题提升可读性。

## 用户故事

- 生成完成后一眼分区：左边看「工程在哪、哪些文件、评分点有哪些」，右边看「工程长什么样」。
- 复制路径按钮仍在输出目录行内，位置不变。

## 实现决策

1. **只动 HTML + CSS，JS 零改动**：保留全部既有 id（res-dir / res-includes / res-modules / res-score-points / res-build-hint / res-structure / res-artifacts / btn-copy-dir / compile-banner），JS 填充/显隐逻辑（~3951-3962 + renderArtifacts ~4002）原样工作。
2. 结构：`#generate-result` 内 = `#compile-banner` + `.res-grid`（`.res-main` + `.res-side`）；每个信息项包 `.res-block`（`.res-label` + `.res-value`）。
3. res-artifacts 容器本身是 `.res-block`（保留 id），renderArtifacts 的 hidden 切换不变。
4. 结构树 pre.result 保留原样式（代码底色），放进右列 block。
5. CSS：`.res-grid { display:grid; grid-template-columns: 1fr 380px; gap:14px }` + `@media (max-width:1179px) { grid-template-columns:1fr }`；`.res-block` 面板底色/边框与页面卡片同令牌。

## 测试决策

- 无新纯函数（纯结构重排）：回归 node --test tests/js/*.test.mjs 全绿 + headless 冒烟截图目检。

## 范围外

- 改动 JS 数据填充逻辑（工时/评分点文案生成等）。
- 新增「打开资源管理器」按钮（本地网页不引后端打开接口，保持复制路径）。
