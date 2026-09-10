# 第十六轮 · E2 `start-app.bat` 三态实测（2026-09-10）

来源工单：`.scratch/newcomer-onboarding/issues/02-launcher-chinese-feedback.md`
挂账单项：`.scratch/real-acceptance/issues/01-real-machine-acceptance.md` E2。

## 实测（真跑 `cmd /c start-app.bat`，判据 = exit code + 分支耗时 + 端口实况）

| # | 态 | 前置 | 实测 | 判定 |
|---|---|---|---|---|
| 1 | **端口被占**（非本应用） | 停掉 webapp；起占位服务 `.scratch/newcomer-onboarding/port-holder-16.py`（`/api/health` 返回非 JSON 纯文本） | `exit code = 1`，用时 **7.1s** | ✅ 走 `:port_busy` 分支（前 4 步 Python / 版本 / 依赖 / netstat 全过，health 判定失败 → 弹中文弹窗「端口 8000 已被其他程序占用…请先关闭占用该端口的程序」并 exit 1） |
| 2 | **本应用已在跑** | webapp 真起在 8000（`/api/health` → `{"app":"contest-generator","version":"1.0.0","ok":true}`） | `exit code = 0`，用时 **2.1s** | ✅ 走 `:open` 分支（netstat 命中 → health 判定是本应用 → `start "" http://127.0.0.1:8000` → exit 0）；**不重复起服务** |
| 3 | **启动超时**（20s 轮询未就绪） | 需要「端口空闲但服务起不来」 | **未实测** | ⚠️ 如实留口：要造这个态须让 `python -m contest_generator.webapp` 起得来但 20s 内不响应 `/api/health`（本机依赖齐全、启动 ~2s，正常路径造不出），属「干净机器/劣化环境」场景 |

## 旁证（文案与门，纯件级）

- `install.bat` 两态文案在盘：`没有找到 Python` ×1、`版本太旧` ×1、`3.13` ×3、`Add python.exe to PATH` ×1
  （`tests/test_onboarding_docs.py:27` 文本守卫在库）。
- Python 版本门实测：`sys.version_info >= (3,13)` → exit 0（本机 3.14.6）；阈值抬到 `(99,0)` → exit 1
  （= `:old_python` 分支的判定确实由这条命令驱动）。
- 依赖自检 `import fastapi,uvicorn,pypdf,PIL,fitz` → exit 0。

## 未实测项的诚实边界

- 「干净机器 `install.bat` → `.venv` → `start-app.vbs` 全流程」（E1）与「启动超时态」（E2-3）
  需要一台没有全局 Python、或服务劣化的机器——本机是开发机（全局 Python 3.14.6 + 依赖齐全），
  跑 `install.bat` 会在仓库根新建 `.venv` 并 `pip install -e .`（改本机环境 + 联网数分钟），
  按「不动用户环境」原则**不做**，留人工在干净机器/虚拟机上验。
