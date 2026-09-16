# A4 — GitHub Actions CI（windows 全套 + ubuntu 快速面）

**要做什么：** push 与 PR 上自动跑测试；没配 `core.hooksPath` 的 clone（别人、或换台机器）也有一道网；红的判据与本地一致。

**被谁阻塞：** A1、A2、A3。

**状态：** claimed（工作流已推上线，等远端真跑一轮的结论）

- [x] `.github/workflows/ci.yml`：**windows-latest 跑全套** `python -m pytest -n auto`（与用户机同平台：路径长度 / 编码 / CRLF 字节口径都能覆盖）
- [x] 第二个 job（ubuntu-latest）跑快速面：`python tools/preflight.py` + `tests/test_repo_language.py` + `tests/test_ps1_encoding.py` + 闸门自身用例（prepush / prepush_hook / preflight / ci_workflow）
- [x] **不联网、不吃 secret**（`tests/test_ci_workflow.py` 明令断言：正文不许出现 `secrets.`，第三方 action 只允许 checkout / setup-python）
- [x] 依赖装得动：**干净 venv 实测** `pip install -e ".[dev]"` → 全套 **4527 passed / 44 秒**（证明声明的依赖够用，CI 不必再列一份）
- [ ] 真机验证：等 GitHub 上这一轮的结论（红了就修配置，绿了才算成）
- [x] 文档：`docs/agents/workflow.md` 新增「闸门：推之前与合并之前」一节（三道闸门的时机 / 命令 / 绕过方式 + 钩子必须无 BOM 的踩坑）

## Comments

**为什么 windows 那份必须存在**：本仓库的真风险都在 Windows 语义上——包内路径长度上限
（`full_pack.MAX_ENTRY_PATH_CHARS`）、`.ps1` 必须带 BOM、`*.bat` 必须 CRLF、
`git archive` 的 `core.autocrlf` 字节口径。ubuntu 那份只做「不装运行依赖也能跑的机械守卫」，
省时间也不假装能覆盖平台差异。

**Python 版本**：CI 钉 `3.13`（`requires-python = ">=3.13"` 的最低线，也是用户机 `install.bat`
最可能拿到的版本）；本机开发用的是 3.14——两代都跑得通这件事由 windows job 的 3.13 兜住。

## CI 首轮抓出来的东西（这就是加它的理由）

**第一轮：20 条红，本地全绿。** 逐条归因（全部已修，除最后一条）：

| 类别 | 用例数 | 真因 | 修法 |
|---|---|---|---|
| **夹具没入库** | 12 | 用例读 `.scratch/real-run/` 下的真机产物（buildlog / 推荐缓存），而那两份**没加 `.gitignore` 例外**——本机有、任何新 clone 没有 | `.gitignore` 加例外（注意 git 规矩：父目录被排除时里面的 `!` 不生效，要逐层放行）+ 入库两份夹具；新增用例 `test_real_repo_files_are_readable_from_a_clean_checkout` 用 `git ls-files` 判「测试读的夹具必须在索引里」 |
| **用例把环境当夹具** | 2 | `test_module_intro.py` 裸 `create_app()` → 读 `~/.contest_generator/config.json`；本机有配置所以绿，CI 上 `/api/modules` 直接 **400「未配置 AI API」** | 夹具改成注入最小配置（真库 + 临时配置路径 + 假 key），与 `test_webapp.py` 同一姿势 |
| **用例依赖本机资料库** | 1 | `test_motor_manifests_match_mirror_subdirs` 拿 `sources/materials/`（688 MB，**不进 git**）当基准 | 沿用仓库既有写法：目录不在就 `pytest.mark.skipif` 跳过（`test_full_pack.py` 先例） |
| **用例依赖 git 历史形态** | 4 | `core.hooksPath` 在新 clone 上是空的；`HEAD~1..HEAD` 在 checkout 上可能是空的（合并提交 / CHANGELOG 自动提交） | 钩子用例改成「配了就必须配对，没配不算红（CI 兜底）」；选择器用例改成**自建两提交小仓库**，改动自己造，任何 checkout 都成立 |
| **CHANGELOG 锚点** | 1 | 锚点指向那笔提交在浅克隆里不存在 | 无缺陷：推后面几轮时锚点已在历史里，自愈机制本来就有 |
| **本轮新增用例自己写错** | 1+1 | ① `test_preflight` 拿**本机完整工作区**当基准（CI 没有完整工作区）②下载文档检查失败时输出被截断，CI 上等于没有诊断信息 | ① 改成**临时完整副本**当基准 ② 失败时带出子进程完整输出 |

**第二轮：`ubuntu` 快速面还红一次**——原因是我自己忘了：快速面 job 跑 `python -m pytest`
却**没装 pytest**（为了省时间不装 `.[dev]`，结果连测试运行器都没有）。修法：装 `.[dev]`。

**这轮改造还顺手把两处「假绿风险」修实了**：
- `test_prepush.py` 里两条用例原本拿本仓库 `HEAD~1..HEAD` 当输入——**在 checkout 上会假红**，
  现在自建仓库，判据完全不依赖被检出的历史；
- `preflight.py` 的失败输出从「最后 4 行」改成「完整 stdout + stderr」——**CI 上截断的尾巴
  等于没有诊断信息**（本轮为定位一条 Windows 专属失败，光靠被截断的输出没法定案）。

## 后面几轮又抓到的（都不是产品缺陷，但全是「只有 CI 才暴露」的）

| 轮次 | 现象 | 真因 | 修法 |
|---|---|---|---|
| 第三轮 | Windows 全套：`preflight` 的下载文档检查红，输出被截断看不到原因 | 子进程按 **cp1252**（CI runner 的控制台代码页）输出中文 → `UnicodeEncodeError` | 拉子进程时钉 `PYTHONIOENCODING=utf-8` + `PYTHONUTF8=1`（**这是用户机同样会中的真缺陷**：任何非 UTF-8 代码页的 Windows 上，发版自检会把编码问题误报成「文档不一致」） |
| 第四轮 | Windows 全套：pytest 自己 **INTERNALERROR** 打断整场（跑到 63% 崩） | `test_build_material_manifest_stat_failure_marks_minus_one` 里我上一版加固时写了 `target.exists()` —— `exists()` 内部就调 `Path.stat`，被全局补丁拦到 → **无限递归** | 改成纯 `resolve()` 字符串比较 + 递归护栏（调用数上限）+ 命中计数断言 |
| 第四轮 | 一条用例连改三次都还是老样子 | **函数重名**：新版加在前面、旧的留在后面，pytest 静默只用最后一个 | 删旧版 + 新增守卫 `test_no_duplicate_test_function_names`（反向验证：加一个重名函数即红） |
| 第二轮 | ubuntu 快速面红 | 快速面 job 为了省时间不装 `.[dev]`，结果**连 pytest 都没装** | 装 `.[dev]` |

**教训一句话**：本地绿 + CI 红，八成是「用例把本机状态当夹具」；而**修这类问题时最容易再制造
新问题**（这轮我自己就在 CI 上连踩两回）。所以判据要写成「不依赖任何本机状态」，并且
**跑一次 CI 才算数**。
