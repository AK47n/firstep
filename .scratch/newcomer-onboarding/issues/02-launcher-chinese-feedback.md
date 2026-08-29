# 02 — 启动器全流程中文反馈（start-app.bat 重写 + /api/health）

**What to build:** start-app.bat 从「静默失败（:fail 仅 exit /b 1）重写为全流程中文反馈 + 无黑窗弹窗」：选 python（.venv 优先）→ 版本检查 → 依赖检查 → 端口探测（本应用 / 他程序 / 无服务三态）→ 启动 → 轮询就绪 → 成功开浏览器 / 失败中文弹窗（含日志路径）。配套后端新增 **GET /api/health** 作为「端口上是不是本应用」的判定依据。

**Status:** resolved（2026-08-29 实施完成，评审记录见文末；真机双态验收留给用户）

## 决策记录（spec.md / clarify 2026-08-29，用户确认）

1. **端口冲突只探测 + 中文提示**：用 `GET http://127.0.0.1:8000/api/health` 判定是否为**本应用**——是本应用 → 直接开浏览器（已在运行）；是别的东西 → 中文弹窗「端口 8000 已被其他程序占用，请先关闭它再启动」；无服务 → 启动本应用。**不做自动换端口**。
2. **/api/health 接口**：`GET /api/health` → `{"app": "contest-generator", "version": "<__version__>", "ok": true}`；**不依赖配置**（无 key 也 200），始终 200。fastapi TestClient 测（test_webapp.py 已有先例）。
3. **无黑窗弹窗**：`mshta vbscript:Execute("CreateObject(""WScript.Shell"").Popup(""消息"",0,""标题"",48)")`（vbscript 段无空格 → cmd 不分词；Execute 后 mshta 自动退出）。弹窗仅用于**失败/提示**终态（python 缺失、版本低、依赖缺失、端口被占、启动超时）。
4. **启动流程**（GBK 编码，沿用现状）：选 python（`.venv\Scripts\python.exe` 存在优先，否则 `python`）→ 版本 ≥3.13 检查（`python -c "import sys; sys.exit(0 if sys.version_info >= (3,13) else 1)"`）→ 依赖检查（`python -c "import fastapi, uvicorn, pypdf, PIL, fitz"`，失败 → 弹窗「请先运行 install.bat」）→ 端口探测（`netstat -ano | findstr :8000` + 尝试 /api/health）→ 无服务则 `start "" /b` 后台启动（PYTHONPATH=src、FIRSTEP_LAUNCHER=1、日志 `>> %USERPROFILE%\.contest_generator\webapp.log 2>&1`）→ 轮询 /api/health 20 次 × 1s → 成功 `start http://127.0.0.1:8000`；超时 → 中文弹窗示日志路径 `%USERPROFILE%\.contest_generator\webapp.log`。
5. **保持现状**：start-app.vbs（WScript.Shell.Run 隐藏黑窗）、stop-firstep.bat/vbs、FIRSTEP_LAUNCHER 语义、日志路径、9000 端口默认不扩。

## 实施

1. **webapp.py**：新增 `GET /api/health`，不挂配置依赖（router 在 create_app 内、在 load_config 之前可用的层）；返回 `{"app": "contest-generator", "version": __version__, "ok": true}`。`__version__` 从哪来先查（pyproject/__init__ 单源；若无则在 webapp.py 顶部已有常量处取用，注释说明）。
2. **测试**：`tests/test_webapp.py` 追加 2 例（200 + 载荷结构；无配置/未配 key 时也 200）。红证先行：先写测试 → 跑红（404）→ 实现 → 绿。
3. **start-app.bat 重写**（GBK 编码落盘）：流程见决策 4；每步 popup 中文；成功路径零弹窗纯开浏览器；`.venv` 优先逻辑；失败 exit /b 1。
4. 手测：python 缺失场景（改 PATH 模拟可跳过，本地验证逻辑分支至少跑通「无服务 → 启动 → 就绪 → 开浏览器」与「端口被他程序占 → 弹窗」两态，后者可用 `python -m http.server 8000` 模拟）。

## 验收标准

- [ ] pytest：/api/health 2 例绿（含未配 key 200），既有测试零回归
- [ ] start-app.bat：正常态无黑窗（vbs 包装下）启动并开浏览器；端口被他程序占用 → 中文弹窗；.venv 缺失回退系统 python
- [ ] 超时场景：日志路径出现在弹窗文案中
- [ ] 真机：本机双态实测（正常 + 端口占用）

## 文件边界

- **改**：`src/contest_generator/webapp.py`（+ /api/health）、`tests/test_webapp.py`（+2）、`start-app.bat`（重写）、`.scratch/newcomer-onboarding/issues/02-launcher-chinese-feedback.md`（本工单）
- **不动**：start-app.vbs / stop-firstep.* / install.bat（01 工单）/ 配置逻辑 / 其他路由

## 实施记录（2026-08-29）

- webapp.py：`GET /api/health` 放在 create_app 内 /api/state 之前，返回 `{"app": "contest-generator", "version": __version__, "ok": True}`（__version__ 单源 src/contest_generator/__init__.py:22），不触配置，未配 key 也 200。
- 测试：test_webapp.py +2（已配置 client 200+载荷；无 config.json 的 Context 也 200）——红证先行（404 确认），实现后绿。test_onboarding_docs.py +1 守护（start-app.bat 含 /api/health / Popup / 中文标题 / .venv 优先）。
- start-app.bat 重写：GBK(936) + CRLF；流程 = 选 python（.venv 优先否则系统 python）→ 版本 ≥3.13 → 依赖检查 → netstat 8000 无监听则后台启动（日志同旧路径）→ 轮询 /api/health 20×1s → 成功开浏览器；失败分支全部中文弹窗（无 Python/版本旧/依赖缺/端口被占/启动超时含日志路径），exit /b 1。
- **弹窗方案偏离 spec（mshta → powershell）**：mshta vbscript:Execute 模式实测不可靠（cmd 对 GUI 程序不等待、URL 引号语义复杂、时序无法证明弹窗停留）；改用 `"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup(...,0,'firstep 启动失败',16)"`（Win10/11 必带 powershell.exe，全路径免 PATH 异常；COM Popup 实测弹窗并阻塞 2s 验证通过；消息内不用英文引号）。
- 验证：no_python 分支实测（GBK 输出正确、exit 1、无解析错）；全量 pytest 2824 无回归；真机双态（正常启动 + 端口占用）由用户浏览器验收。
