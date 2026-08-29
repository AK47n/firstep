# 01 — 新手 README + install.bat

**What to build:** 仓库根目录新增 **README.md**（人话说明书）与 **install.bat**（一键安装引导），消除「拿到手→打开」空白：纯新人克隆/解压后，照着 README 三步装好、双击 start-app.vbs 即用。README 只讲用户需要知道的事，不写开发细节。

**Status:** resolved（2026-08-29 实施完成，评审记录见文末）

## 决策记录（spec.md / clarify 2026-08-29，用户确认）

1. **Python 门槛不动**：pyproject.toml `requires-python = ">=3.13"` 保持原样；install.bat / start-app.bat **只做检测 + 中文指引**（含 Python 官网下载链接），不自动装 Python、不换更高版本。
2. **.venv 优先**：install.bat 在仓库根建 `.venv` 虚拟环境（`pip install -e .`）；start-app.bat 优先用 `.venv\Scripts\python.exe`，缺失回退系统 python。
3. **README 内容**（人话）：这是什么（贴赛题→出可编译工程，双平台）；需要什么（Python 3.13+ 及下载链接、DeepSeek API key 获取（platform.deepseek.com，网页右上角注册/登录→左侧 API keys）、板子与 IDE 一句话：STM32F103C8T6 最小系统板 + Keil5 / 地猛星 MSPM0G3507 开发板 + CCS；步骤 1 双平台可先只备一款）；三步安装（install.bat → start-app.vbs → 设置页配 key）；常见问题（双击没反应看 webapp.log；端口占用；key 哪里填）。
4. **模块 manifest 的 kit/source_url 大多为空**（已核实 adc/beep/config/coord_detect/debug_uart 全为 ""）——README **不引用模块购买链接**，板子只写平台级名称（STM32F103C8T6 最小系统板 / 地猛星 MSPM0G3507）。
5. **install.bat 流程**（幂等，可重复跑）：检测 `python`（无 → 中文提示 + 官网下载链接 https://www.python.org/downloads/ → exit）→ 版本 ≥3.13 检查 → 建 .venv（已存在跳过）→ `.venv\Scripts\python -m pip install -e .`（后台窗口可见输出）→ 导入自检（fastapi/uvicorn/pypdf/PIL/fitz，失败 → 提示重跑/看输出）→ 成功中文提示「安装完成，双击 start-app.vbs 启动」。
6. **编码**：README.md = UTF-8；install.bat = GBK/ANSI（与现有 start-app.bat 一致，中文提示在 CMD 不乱码）。
7. **守护测试**：`tests/test_onboarding_docs.py`（沿用 test_repo_language.py 思路）——README.md 存在、非空、含关键中文词（Python / API key / 板子 / IDE）、含 install.bat 与 start-app 指引节；install.bat 存在且含中文提示字节（GBK 下 `python` 检测与 `pip install -e .`）。

## 实施

1. 根目录写 `README.md`（UTF-8，中文，结构见上文决策 3；技术术语保留英文，如 Keil5 / CCS / API key）。
2. 根目录写 `install.bat`（GBK 编码！用 PowerShell `[System.IO.File]::WriteAllText(path, content, [System.Text.Encoding]::GetEncoding(936))` 落盘；流程见决策 5；中文提示；每步失败 exit /b 1）。
3. 写 `tests/test_onboarding_docs.py`：README 与 install.bat 存在性 + 关键内容断言（先红后绿：先写测试断言 README 存在 → 跑 pytest 红 → 再写 README 绿？不必——README 与测试同工单一次落地，红证记录为「实施前 README 不存在 → 断言失败」）。
4. 跑 `pytest tests/test_onboarding_docs.py tests/test_repo_language.py` 全绿；mypy 无涉（纯文档）。

## 验收标准

- [ ] README.md：纯新人独立阅读可完成安装启动（三步），无开发术语门槛
- [ ] install.bat：新机器（无 python / 有旧版 / 无 .venv）三场景中文提示正确；幂等重跑不报错
- [ ] pytest：test_onboarding_docs.py + test_repo_language.py 全绿
- [ ] 真机：本机全新 .venv 装一遍 → 双击 start-app.vbs 能起

## 文件边界

- **改**：`README.md`（新增）、`install.bat`（新增）、`tests/test_onboarding_docs.py`（新增）
- **不动**：pyproject.toml（requires-python 保持 >=3.13）/ start-app.bat（02 工单）/ 后端代码 / 前端

## 实施记录（2026-08-29）

- README.md：UTF-8 中文说明书（这是什么 / 四样东西 / 三步装好 / 30 秒上手 / 常见问题 / 开发者），板子只写平台级名称（模块 manifest kit/source_url 大多为空，不引用购买链接）。
- install.bat：GBK(936) + CRLF；流程 = 检测 python（无→中文提示+官网链接）→ 版本 ≥3.13 → 建 .venv（已存在跳过）→ pip install -e . → 导入自检（fastapi/uvicorn/pypdf/PIL/fitz）；幂等；每步失败 pause + exit /b 1。
- 验证：pip install -e . 实测可解析（无 [build-system]，pip 26.1.2 默认 setuptools 回退）；install.bat「无 Python」分支实测走到中文提示（GBK 解码正确）；全量 pytest 2824 无回归。
- 教训：write 工具写的是 LF 行尾——cmd 批处理必须在转换编码时同时转 CRLF（LF-only 会让 `if ()` 块解析错乱，表现为命令被拆分报 'xxx is not recognized'）。

## 评审记录（双轴，2026-08-29；整改已随 02/03 提交落地）

- **Standards 轴**：无硬违规（README 中文/编码、install.bat 流程与幂等、守护测试均合约定）。判断项 3 条，裁定不修：bat 内探针/弹窗逻辑与 install.bat 重复（批处理无模块系统，保持显式）；Popup 五行子例程化（带参子例程引号不可靠）；_cjk_count 与 test_repo_language.py 重复定义（孤立测试文件可接受）。
- **Spec 轴**：R3（欢迎卡）缺失——本 spec 分三期，R3 由工单 03 补齐并已实施；README「开发者」节超出 spec（README 面向人）——已删；README 常见问题缺编译工具链（uv4_path/gmake_path）——已补；spec 决策 49 mshta 弹窗方案实施后漂移——已修正为 powershell WScript.Shell.Popup（详见工单 02 实施记录）。
