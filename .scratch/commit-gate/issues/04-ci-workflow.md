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
