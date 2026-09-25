# 04 — 库相关的只读端点不该被「先配 API」那道闸挡住

**要做什么：** 没配 API key 的时候，**库本身**（模块库 / 母版库 / 赛题库 / 参考文件库的浏览与读取）
仍应可用——用户拿到工具第一件想做的事是"看看里面有什么模块"，而不是先被要求填 key。
AI 相关的端点照旧中文拒绝。

**被谁阻塞：** 无（`ci-gate-fixes/01` 已把"库在哪"这件事修好，本单只动那道闸的射程）。

**状态：** ready-for-agent

- [ ] 盘清 `_require_config` 的 46 处调用点，**逐个分成两类**：真的需要 AI（推荐 / 生成 / 蒸馏 /
      修订 / 参数 / 排障……）与其实只需要"库在哪"（模块库读写列表、母版库、赛题库、参考库、
      PDF / Markdown 资料库、代码查看器……）。分类要写进工单 Comments 当判据，不能只改代码
- [ ] 只把后一类改成用"库目录解析"（`_library_dir(ctx)` / 新抽一个 `_require_library_dir(ctx)`），
      **不动前一类**——AI 端点仍是"没 key 就 400 中文"
- [ ] 引导态（`install.bat` 写的那份：库路径齐全 + key 空串）与"随包库回退"两种来源走**同一条路**
- [ ] `tests/test_config.py::test_app_context_resolves_default_path_at_construction` 里那条
      **钉住现状**的断言（`/api/modules` == 400）必须跟着改——它红了就是本单落地的信号
- [ ] 逐端点补一条"未配 key 也能读"的用例（至少：`/api/modules` 列表 + 单文件、`/api/masters`、
      `/api/topics`、`/api/references`），并保留一条"AI 端点未配 key 仍 400"的用例防反向
- [ ] 前端确认：设置页/首页在"未配置"态下不再因为库端点 400 而空窗（必要时只需文案，不必改结构）
- [ ] 中文提交

## Comments

### 立项事实（2026-09-25，量自 `ci-gate-fixes/01` 的现场）

空 key（无配置文件、随包库在场）时四个库端点的实测读数：

| 端点 | 现在 |
|---|---|
| `/api/modules` | **400** 未配置 AI API |
| `/api/masters` | **400** 未配置 AI API |
| `/api/topics` | **400** 未配置 AI API |
| `/api/references` | **400** 未配置 AI API |
| `/api/settings` | 200（报的是随包库路径） |
| `/api/env/status` | 200（`api_configured=False`） |

即：**库的位置已经知道，但浏览不了**。这是既有行为（不是 `ci-gate-fixes/01` 引入的），
射程 = `webapp.py` 里 46 处 `_require_config(context)`。本单价值在于让"从干净检出起服务"
这件事真的**有得看**，而不只是"位置对了"。
