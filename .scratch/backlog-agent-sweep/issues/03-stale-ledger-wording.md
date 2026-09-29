# 03 — 两处过期旧账的措辞结清（probe-01 / `#rec-progress` 图）

**要做什么：** 把两条**已经做完、但账上还写着"没做/留给下一轮"**的措辞改成事实口径——
下一个人照着旧账会白推一遍（§23/§24 记过同一个坑）。

**被谁阻塞：** 无。

**状态：** resolved

- [x] 先**读盘核实**（不信旧账）：① `.scratch/ui-density-sitewide/probe-01-scope-draft.py` 是否已
      `from scope_lib import …`；② `shots/` 里 `10-{light-light,dark-dark}-rec-progress.png` 是否在盘、
      且 `git check-ignore -v` 对其**零输出**（= 真入库）
- [x] 改 `issues/08-closeout.md` 账第 9 条：写明 09 单已对齐（并保留"当初为什么记这条"的一句）
- [x] 改 `.scratch/ui-density-sitewide/README.md` 巡检图索引段：把"留给下一轮"换成"09/10 单已拍"，
      并指到文件名
- [x] `README.md` 的「当前读数」段同族的过期句（"7 处内联字号留给 08 收尾单"）一并更正
- [x] 提交信息中文

## Comments

### 读盘核实（2026-09-29，不信旧账）

| 旧账说 | 盘上事实 |
|---|---|
| 08 账第 9 条：「`probe-01` 仍是草稿探针，自带一份 `rules_of` / `scope_of` / `load_backlog`」 | **09 单已对齐**：`probe-01-scope-draft.py:36` = `from scope_lib import load_backlog, load_scopes, scope_of  # 单一出处（09 单对齐）` |
| README：「生成页 `#rec-progress` 这一趟没拍……留给下一轮」 | **10 单已拍**：`10-light-light-rec-progress.png` / `10-dark-dark-rec-progress.png` —— 在盘、`git ls-files` 命中、`git check-ignore -v` 零输出 |
| README：「`static/js/**` 里 7 处内联字号……留给 08 收尾单」 | **08 单已收**（收进 `var(--fs-tag)`，并给守卫加了第五条腿） |

### 改了哪三处（纯文档，产品面零改动）

1. `issues/08-closeout.md` 账第 9 条 → 追加一段 ✅ 结清（引 09 单的落点与"输出逐字节相同"）；
   原文保留（它是"当初为什么记这条"的现场）。
2. `.scratch/ui-density-sitewide/README.md` 巡检图索引段 → 换成"09 / 10 两单已拍 + 四张图带
   computedStyle 断言 + 2026-09-29 用 `git ls-files` / `git check-ignore` 复核过"。
3. 同文件「当前读数」段 → 「7 处内联字号留给 08 收尾单」改为「**08 单做完了**」；
   下面那段"剩下的是 08 收尾单"改成"08 收尾单也已做完，本轮 `01`–`12` 全部 resolved"。

**为什么值得单独走一张单**：`backlog.md` §23/§24 记过同一个坑——**修完没人回改标记**，
下一个人照着旧账会白推一遍（本轮我自己就先按旧账把 `probe-01` 与那张图列进了待办，读盘才发现都已做完）。
