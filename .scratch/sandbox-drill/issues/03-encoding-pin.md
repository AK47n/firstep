# B3 — 编码钉落点实证：生成 mspm0 工程里有 UTF-8 编码设置

**要做什么：** 把「v1.2.1 修好了乱码风险」从**包内有这两个文件**升级到**生成出来的 CCS 工程里有编码钉**——判据落在生成产物上。

**被谁阻塞：** B1（用升好级的沙箱）。

**状态：** resolved（2026-09-18，**判据全部成立：PASS**）

- [x] 在沙箱真调生成链路（`POST /api/generate`，平台 `mspm0` + 最小模块集 `servo`，payload 照真实历史产物 `.scratch/real-run/out_16_mspm0_min/.contest_context.json`）→ 产物 22 个文件到一个一次性目录
- [x] 断言产物里有 `.settings/org.eclipse.core.resources.prefs` 与 `.settings/org.eclipse.cdt.codan.core.prefs`，正文含 `encoding/<project>=UTF-8`（实测 `eclipse.preferences.version=1\nencoding/<project>=UTF-8\n`）
- [x] 与母版源文件 sha256 对照（生成产物 = 母版文件，未被改写）：两件**都相等**；再与**官方 v1.2.1 完整包清单**里的同名 sha256 三方对照，**也相等**（`6c355f2f86ad…` / `1a5b17d8a429…`）
- [x] 诚实边界写进证据：**这证明的是「落点正确」，不是「CCS 实际读取行为」**——本机没有可交互 CCS 工作区实测条件，不外推（`notes` 与正文各一处）
- [x] 脚本 `.scratch/verify-gate-drills/drill-03-encoding-pin.py` + 原始输出 `verify-03-encoding-pin.txt/.json`；产物副本（两个 `.settings` + `.contest_context.json` + `main.c` + 文件清单）落 `.scratch/verify-gate-drills/artifacts-b3/`
- [x] 落点没问题 → 未开缺陷单

## 演练自身踩的两个坑（写下来省下一轮）

1. 沙箱自己那份 `config.json` 是手搓的旧键（`deepseek_api_key` / `modules_dir`），任何需要配置的端点都会 400（`配置缺少 api_key`）→ **不去改沙箱配置**，改用一次性配置副本（拷真身那份、库目录指沙箱 `library`）+ 一次性入口。
2. `/api/generate` 的 500 只回一句通用中文，栈在服务端 stderr；定位靠临时探针直调 `generate_project`。真正的错因是 harness 把 `config_path` 当**字符串**传进 `AppContext` → 端点内部 `load_config(path).read_text()` 抛 `AttributeError('str' object has no attribute 'read_text')`。harness 已修（传 `Path`）。
