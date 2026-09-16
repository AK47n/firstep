# A4 — GitHub Actions CI（windows 全套 + ubuntu 快速面）

**要做什么：** push 与 PR 上自动跑测试；没配 `core.hooksPath` 的 clone（别人、或换台机器）也有一道网；红的判据与本地一致。

**被谁阻塞：** A1、A2、A3。

**状态：** pending

- [ ] `.github/workflows/ci.yml`：**windows-latest 跑全套** `python -m pytest -n auto`（与用户机同平台：路径长度 / 编码 / CRLF 字节口径都能覆盖）
- [ ] 第二个 job（ubuntu-latest）跑快速面：`tools/preflight.ps1` 的等价 Python 部分（版本号一致 / `.settings` 在库 / offline 文档检查）+ `tests/test_repo_language.py` + `tests/test_ps1_encoding.py`
- [ ] **不联网、不吃 secret**（仓库既有约定 `tests/fakes.py`）；Python 版本与 `pyproject.toml` 的 `requires-python` 对齐
- [ ] 依赖装得动：只装跑测试需要的（跑一次确认，缺什么补什么，不盲目全量装 5 GB 那一套）
- [ ] 真机验证：故意推一个破坏守卫的提交 → CI 红且点名；还原 → 绿
- [ ] README 或 `docs/agents/workflow.md` 加一句「CI 在哪、跑什么、红了怎么办」
