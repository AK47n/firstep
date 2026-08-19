# 09 — 生成流程页 UI + 端到端装配

**What to build:** 用户完成一次完整生成：贴题或传文件 → 选平台 → 看 AI 推荐与理由并可增删调整 → 选输出目录 → 拿到完整工程文件夹。FastAPI 装配全部后端能力，形成可用产品。

**Blocked by:** 02 — Keil 工程修改器；04 — LLM 赛题→模块选择 + 依赖解析 + 配置；05 — main.c 骨架生成 + 函数自检；06 — 赛题文本抽取（PDF/Word）

**Status:** resolved

- [x] 首页生成流程完整可走通（对已注册的平台）
- [x] AI 推荐展示理由，用户可增删后重新生成
- [x] 平台缺失 / 硬件绑定警告在界面上明确呈现
- [x] 生成结果输出到用户所选目录：工程结构、include path、main.c 就位
- [x] 尚未落地的平台在界面显示"暂不可用"而非报错
- [x] 设置页接入：API 配置即时生效

## Comments

- 2026-08-05: 工单 09 完成（**FastAPI 薄壳 + 单页前端，装配 01–08 全部后端能力**）。
- 新增 `src/contest_generator/webapp.py`：`create_app(context)` 工厂（测试注入 tmp 目录 / 假 LLM），`python -m contest_generator.webapp` 或 `contest-generator` 命令启动本地服务。
  - 生成流程：`/api/extract`（文件上传 → PDF/docx/txt 抽取）→ `/api/recommend`（AI 推荐 + 理由）→ `/api/selection/expand`（依赖展开 + 三类平台警告 missing/unverified/hardware_bound）→ `/api/skeleton`（main.c 骨架 + 静态自检拦截清单）→ `/api/generate`（生成到用户所选目录，返回结构 / include path / 模块文件）。
  - 模块库（07 装配）：浏览 / AI 录入（草稿 → 校验入库）/ 编辑简介 / 多平台版本 / 删除。
  - 母版（08 装配）：扫描 → AI 提炼报告（可改 merge 来源）→ 确认入库（staging 落盘 + 结构分析）→ 浏览 / 删除。
  - 设置：GET 掩码 key，PUT 保存落盘并即时生效（后续请求即用新配置）；掩码提交沿用旧 key。
  - 错误映射：业务失败 400（message 原样），LLM 服务失败 502。
- 平台"落地"判定：母版库里有该平台母版 → 可用；否则界面显示"暂不可用：尚未导入母版"并禁用选择（不报错）。
- 配置扩展（`config.py`）：`LLMConfig` → `AppConfig`，新增 `module_library_dir` / `masters_dir`（默认 `~/.contest_generator/modules` 与 `masters`），旧配置文件缺省字段自动取默认。
- 前端 `static/index.html`：单页四页签（生成 / 模块库 / 母版 / 设置），无构建链。
- 测试 `tests/test_webapp.py`：26 个端到端用例（TestClient + 假上下文），全量 273 绿；mypy 干净。
- 依赖：`fastapi` / `uvicorn` / `python-multipart`（运行时）、`httpx`（dev，TestClient）。
