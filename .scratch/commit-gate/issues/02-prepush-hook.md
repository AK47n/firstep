# A2 — `.githooks/pre-push` 接上选择器

**要做什么：** 真推一次代码时，如果改动破坏了既有守卫，push 被拦下并**点名失败的用例**；推 tag（发版）自动跑全套；钩子自己坏了不许卡住维护者。

**被谁阻塞：** A1。

**状态：** resolved——`.githooks/pre-push` + `tests/test_prepush_hook.py`（11 例）+ 两次真 push 演练

- [x] `.githooks/pre-push` 存在且索引模式 `100755`，调用 `tools/prepush.py --stdin-refs` 并透传 stdin 的 refs
- [x] 测试红 → 非 0 退出（push 被拒）+ 打印失败用例名与「怎么复跑 / 怎么绕过」
- [x] 推 tag（`refs/tags/*`）→ 整套，不看子集
- [x] `FIRSTEP_PREPUSH=full` → 全套；`=off` → 跳过（明写「仅限你确知自己在做什么时」）；`=select-only` → 只选择不执行
- [x] 钩子自身故障（无 python / 读不到 refs / 选择器抛错）→ 打印原因并**放行**（`safe_main` 兜底）
- [x] 真机验证两次真 push（正常放过 / 破坏守卫被拦下并点名）

## Comments

**真机演练（2026-09-16，临时 bare 远端 + 从本仓库克隆）**：

| 场景 | 结果 |
|---|---|
| 正常推送（新分支，远端 refs 全零） | 放行，远端收到 2791 提交 ✅ |
| **破坏守卫**（删掉 `tests/test_master_template_config.py`）→ 修之前 | ❌ **被放过去了**（远端 2792）——见下面的真缺陷 |
| 同场景 → 修之后 | ✅ **拦住**：退出码 1、远端 0 提交、点名 `test_every_family_file_exists` 等 16 条红 |
| 线上真 push（本仓库 → origin） | ✅ 判据跑完（这套改动命中「工具改动 → 整套」，4517 passed），`0482e6a4..ff775b46` 推上去 |

**演练抓到的两个真缺陷（都已修 + 各有回归用例）**：

1. **推新分支时基点取值退化**：原实现拿 `origin/main` 当基点，而本机克隆里 `origin/main`
   正好 = 本地 HEAD → `diff` 恒空 → 闸门报「没有守卫要跑」→ **静默放行**。修法：基点改取
   远端默认分支（`origin/HEAD` → `origin/main` → `main` → `master`）并用
   `merge-base --is-ancestor` 验它是祖先，不可用则退 `HEAD~1`；另加一条「认得出 refs 却算出
   零改动 → 倒向整套」的退化判据。
2. **钩子带 UTF-8 BOM 时 git 直接 spawn 失败**（`error: cannot spawn .githooks/pre-push:
   No such file or directory`），而**成功 push 时 stderr 是静默的**——排查时一度以为"钩子跑了
   只是没选中"。实测矩阵：`write-ascii` 跑通 / `write-utf8bom` 失败 / 从别处拷来的带 BOM 文件
   失败。本仓库现有三个钩子都是无 BOM（首字节实测 `23 21 2F` = `#!/`），**以后新增钩子请用
   LF + 无 BOM**，别用 PowerShell 5.1 的 `-Encoding utf8`（会加 BOM）。

**一处测试自身的设计修正**：钩子契约用例第一版直接跑真钩子，而正常 push 的 refs 会算出一整套
（58 秒）→ 撞上 `pyproject.toml` 的 180s 超时把整场拖红。修法是给选择器加 `--select-only` /
`FIRSTEP_PREPUSH=select-only`（**只选择、绝不执行**；产品侧也有用：想知道「这次 push 会跑
什么」而不想真跑），用例借它验契约——判据一个字没松，耗时从超时变成 2 秒。
