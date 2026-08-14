# 01 — index.html 文字 UI 美化 / 格式优化重做（上批被 reset 抹掉）

**What to build:** 之前并行会话在**共享检出**（主检出）上做的一批 index.html 文字 UI 美化 / 格式优化，被主会话 `git reset --hard origin/main` 抹掉（未提交改动不进对象库，无副本可恢复——事故记录在 pin-board-config/03 Comments）。本工单在最新 main 基础上重做。

**Blocked by:** 无（基于最新 main 开工——main 已含板级引脚配置全套：卡 7 板图 / 旋转 / 绑定 / 板载共用警示，美化不得回退这些功能）

**Status:** 待实施

## 需求

1. 在最新 main 的 `src/contest_generator/static/index.html` 上做文字 UI 美化 / 格式优化（用户上批的意图：文字排版、格式、观感类优化——具体项以用户当面需求为准，重做时向用户确认清单）。
2. **不得**回退或改动板级引脚配置功能（卡 7 板图点选 / 旋转 90°/180° / 绑定菜单 / ⚠ 警示清单 / bindings 载荷）与既有深色主题令牌体系——美化只动文字/排版/样式层。

## 文件边界

- `src/contest_generator/static/index.html`：唯一文件（零后端、零 boards 数据改动）
- 铁律：**独立 worktree**（从最新 main 建），不在主检出编辑；完工 `git fetch origin && git rebase origin/main` 后再推 PR

## 验收

- [ ] node --check 过（脚本段提取）
- [ ] pytest 零扰动（基线 1457 绿）
- [ ] 浏览器人工验收：美化项逐项过 + **引脚配置卡回归**（选平台出板图、旋转按钮、点引脚绑角色、板载共用 ⚠ 警示、改绑定生成 UV4 0 错）
- [ ] 独立 worktree + 提交（`style:` 前缀）+ PR

## 实施提示词（复制到新会话）

```
实施 UI 美化重做工单 .scratch/index-html-ui-redo/issues/01-ui-redo.md：
1. 读工单文件 + 最新 main 的 src/contest_generator/static/index.html
2. 背景：上批文字 UI 美化/格式优化在并行会话的共享检出上做，被主会话 reset --hard 抹掉
   （未进 git，无副本可恢复）——本次重做；main 上现已含板级引脚配置全套代码
   （卡 7 板图/旋转/绑定/警示），美化必须在最新 main 基础上做，不得回退这些功能
3. 铁律：独立 worktree（git worktree add ../firstep-ui-redo main），不在主检出编辑；
   文件边界 = index.html 单文件；完工后 git fetch origin && git rebase origin/main 再推 PR
4. 验收：node --check 过（脚本段提取）；pytest 1457 零扰动；浏览器人工验收——
   美化项逐项过 + 引脚配置卡回归（选平台出板图、旋转 90°/180°、点引脚绑角色、
   板载共用 ⚠ 警示、改绑定生成 UV4 0 错）
5. 提交（style: 前缀）+ 推送开 PR
注意：8000 端口当前空闲可自起服务；勿动后端与 boards 数据
```

## Comments

- 2026-08-14 立项（用户点名："之前那批文字 UI 美化格式优化之类的优化"——对应 index-html-ui-redo-pending 待办）。
