# 02 — 打包（更新包 + 完整包）→ 打 tag 推送 → Release 上传 → 联网自检

**要做什么：** 把 v1.4.1 的八件套发到用户手上：两个 zip + 两份清单 + 两份 sha256 + 删除清单，
Release 说明按模板写（头两行给新用户 / 已装用户）。

**被谁阻塞：** 01（版本号同步与自检先过）。

**状态：** resolved（2026-09-30）

- [x] 更新包：`powershell -File tools\pack-update.ps1 -Tag v1.4.1 -Baseline …v1.4.0.files.txt`
- [x] 完整包：`powershell -File tools\pack-full.ps1 -Tag v1.4.1 -Baseline …full-v1.4.0.manifest.json`
- [x] 包内抽检（VERSIONS 首块 / `__version__` / 不该进包的三处 / `00-START-HERE.txt`）
- [x] 本地打 annotated tag `v1.4.1` → `288e2907`（打包那一刻的 CHANGELOG 提交；tag 对象 `8537534f`）
- [x] 推送 `main` + `v1.4.1`（钉 IP；**第一次被掐断**，换 IP 后成功）
- [x] `gh release create` + 八件资产上传 + **服务端 size 逐件对账**
- [x] 联网自检 `python tools\check-download-docs.py` → **PASS**

## 读数

| 项 | 值 |
|---|---|
| 更新包 | `301,967,062` B（288.0 MB）；产品文件 **2939** 条 / 候选 7151；删除清单 2231 条；sha256 `c846a380…` |
| 完整包 | `791,826,449` B（**单卷** 755.1 MB）；包内 **8212** 个文件（原始 1030.6 MB）；资料库 12 批次 / 5066 文件；sha256 `dc499d35…` |
| 包内抽检 | `VERSIONS.md` 首块 = `## v1.4.1 (2026-09-30)`；`__init__.py` = `1.4.1`；`.scratch/` / `.venv/` / `sources/materials` 命中 **0**；`00-START-HERE.txt` 在完整包内 |
| tag / 远端 | annotated `v1.4.1` → 对象 `8537534f`，解引用 = `288e2907`；推送报告 `08e5d524..288e2907 main -> main` ＋ `[new tag] v1.4.1` |
| Release | `https://github.com/AK47n/firstep/releases/tag/v1.4.1`；**八件资产服务端 size 与本地逐件相同（8/8、0 处不一致）** |
| 联网自检 | `tools\check-download-docs.py` **PASS**（三组全 `[OK]`；`/releases/latest` = v1.4.1、资产 8 件）——读数 `post-publish-check.txt` |
| 下一版基线 | 更新包 `firstep-update-v1.4.1.files.txt`；完整包 `firstep-full-v1.4.1.manifest.json`（都在 `%USERPROFILE%\Desktop\firstep-pack`） |

## 网络那条（本轮实测，下次直接用）

1. **推送前一次性验了 6 个候选 IP**：本轮 **6 个全部通过** `ls-remote`（含上一轮 reset 过的
   `4.208.26.197`）——验过的 IP 只保证"那一刻"，**失败就换一个**。
2. **第一次推送被掐断**：`curl 55 Send failure: Connection was reset` ＋
   `send-pack: unexpected disconnect`（`-c http.postBuffer=524288000` 已带）；pre-push 闸门
   **在掐断前已经整套跑完并全绿**（输出尾 = `5689 passed + 11 skipped`）。
3. **换 IP 后一次过**：`140.82.114.3` → **`20.27.177.113`**，同一条命令即成功
   （`main` + tag 一起推上去了）。
4. **第二次推送明确跳过了重跑**：`FIRSTEP_PREPUSH=select-only`——同一棵树、中间零提交，
   重跑只是重复（它照旧打印了"本来会跑什么"，见 job 输出）。这一条是**明写的例外**，不是默认。
5. ⚠ **`git rev-parse v1.4.1^{commit}` 在 PowerShell 里会被吃掉**：`^` 是 PowerShell 的转义符
   （实测报 `ambiguous argument`）。要看 tag 指向谁用 `git rev-list -n 1 v1.4.1`，
   或用单引号把整个参数包起来。
6. ⚠ **`gh --jq` 里带 `\(…)` 插值的表达式会被 PowerShell 拆参数**（`accepts at most 1 arg(s)`）；
   要读资产清单就走 `gh release view --json assets` + 脚本解析（本轮用 Python 对账）。
