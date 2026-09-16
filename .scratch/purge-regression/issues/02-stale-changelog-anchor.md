# 02 — 自动补录锚点在历史重写后失效（静默静止）

**要做什么：** 历史重写之后 CHANGELOG 自动补录能自己恢复，而且失效时**出得了声**；
「重写完忘了重新落锚」由用例当场抓住。

**被谁阻塞：** 无——可立即开始（与 `purge-regression/01` 同因：历史重写的连带损伤）。

**状态：** resolved

## 症状与根因

**症状**：2026-09-15 20:57（`c0f33697`「从全部历史里删掉编译产物」）之后的所有提交
**都没进 CHANGELOG**，且 `post-commit` 钩子每次都只打印一句 `CHANGELOG up-to-date`——
看不出任何异常。本轮连做三笔提交、三次都拿到这句话才发现。

**根因**：CHANGELOG 头部的自动补录锚点
`<!-- changelog-auto: last-commit=2bdead56… -->` 指向的是**重写前**的提交，
而 `filter-branch -- --all` 把**所有 commit hash 都换掉了** → 该 sha 在本仓库里不复存在
（`git cat-file -e` 直接报 unknown revision）。`update_changelog` 拿它算
`git log <sha>..HEAD` → git 报错 → `_git_log_commits` 返回 `[]` → 当成「无新提交」直接
`return False`。

**为什么静默**：`update_changelog` 的兜底原本是给「git 暂时不可用 / 文件缺失」设计的
（注释原话：尽力而为、绝不抛）。但「锚点不存在」不是暂时故障，而是**永久状态**：
它把「没有新提交」和「我根本查不了」混成一件事，于是机制一旦失效就再也不会自己好。

## 修法

- `changelog._commit_exists(repo, sha)`：新增，判「锚点还作不作数」（`git cat-file -e <sha>^{commit}`）。
- `update_changelog`：锚点**有效**才走 `sha..HEAD`；失效则按文件内最新日期兜底扫，
  并把锚点换成当前 HEAD（自愈），同时**往 stderr 说一句**——失效不再是哑的。
- 兜底不会写重复：`_merge_commits` 按 (时间, 文本) 去重（已核实）。
- 守卫三条（`tests/test_changelog.py`）：失效锚点 → 必须走日期兜底 + 换锚 + 出声；
  有效锚点 → 仍走 sha 区间（别让兜底变常态）；**真文件** → 锚点必须在本仓库存在
  （无 `.git` 的发布包副本跳过）。

## 验收

- [x] 单测三条：失效兜底 / 有效区间反向 / 真文件锚点存在性
- [x] **反证（真文件）**：修之前跑守卫 → 红，报
      「CHANGELOG 锚点 2bdead56 在本仓库里不存在」；跑一次
      `PYTHONPATH=src python -m contest_generator.changelog` → 自愈 → 绿
- [x] 补录结果：09-15 那笔重写提交（`20:57`，此前一直没进记录）与 09-16 三笔全部入账；
      锚点更新为 `35b98e35`
- [x] 全套：`tests/test_changelog.py` 32 passed；整支全套本轮实跑绿（数量见当日 2.5c 记录）

## Comments

- 与 `purge-regression/01` 是**同一个根因家族**：一次历史重写同时打断了两条静默机制
  （母版同步守卫没被打断、只是当场变红没人看；补录被打断后连红都不会红）。
  教训一致：**看起来"尽力而为"的静默兜底，必须能把「没东西可做」与「我做不了」分开**。
- 这类锚点/游标失效在别处是否还有？本轮只查了 CHANGELOG 这一处；
  资料库基线（`.materials-manifest.json` 的 version 字段）与 `VERSIONS.md` 不依赖 commit hash，
  暂未见同类风险。
