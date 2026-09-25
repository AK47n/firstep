# 01 — 配置缺失时回退随包库 + 配置路径覆盖口

**要做什么：** 把仓库 clone 到一台**没有任何 `~/.contest_generator`** 的机器上，起服务时**库的位置**
从缺省位置也认得出来（不再一律报「未配置」）；同时给一条**显式**的配置路径环境变量，让夹具 / CI /
高级用户能指到自己的配置，而不必伪造 `HOME`。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 配置文件**缺失**且**随包库在场**时，`load_config` 回退到随包库根
      （`<工具根>/library/modules` 与 `<工具根>/library/masters`，判据复用 `tool_root.find_tool_root` 单源）
- [x] 配置文件**缺失**且**随包库不在**（站点包安装等）时，**保持既有行为**（仍报原来的「未配置」错），不假装有库
- [x] 配置文件**存在**时一律按配置走（用户写了什么就是什么，不静默覆盖）；`api_key` 空仍按引导态处理
- [x] 新增配置路径环境变量（`FIRSTEP_CONFIG_PATH`）：合法（非空字符串）时用它，否则用缺省路径
- [x] 缺省路径的解析从「导入期绑定」改为「调用期解析」——否则夹具在子进程里设的环境变量不生效
- [x] 默认参数语义逐字节兼容：`load_config` / `save_config` / `raw_library_dirs` 的既有显式传参调用零改动
- [x] `tests/test_config.py` 补用例（回退随包库 / 随包库不在仍报原错 / 显式路径不回退 / 环境变量覆盖 /
      **走 `AppContext()`+`create_app()` 的真实应用路径**）
- [x] 中文提交

## Comments

### 落地事实（2026-09-25）

**交付的东西**（`src/contest_generator/config.py` + `webapp.py`）：

- `config_path()` + `CONFIG_PATH_ENV = "FIRSTEP_CONFIG_PATH"`：**调用期**解析缺省路径。这是本单
  最有用的一半——夹具只要把环境变量指到自己的种子配置就能在干净 runner 上起服务（已实测：
  BOM 干净的 JSON + 真 key ⇒ `/api/bindings/matrix` 200）。
- `bundled_library_dirs()`：复用 `tool_root.find_tool_root` 单源，给出 `<工具根>/library/{modules,masters}`
  ——与 `install.bat` 第 49 行写给用户的是**同一对**路径。
- `load_config(None)` 在「缺省位置 + 文件不在 + 随包库在场」时返回随包库配置。

### 两处**评审改了实现**的地方（都留了守卫，别再合）

1. **回退在生产路径上曾经完全不可达**（评审实测抓到，是我自己写错）。错法值得记：
   "这是不是缺省位置"在**两处各记了一次账**——`__post_init__` 里解析一次、
   `_current_config` 里再 `isinstance(sentinel)` 判一次，两处口径不一致 ⇒ `is_default` 恒 False，
   `load_config(None)` 那条分支没人调用。而单测只直调 `load_config()`，
   于是**整组用例全绿、CI 那条红原封不动**——假绿形状与它要修的那条同源。
   现在判据只有一处（`ctx.config_path == config_path()`），并补了一条**不猴补、真走
   `AppContext()` + `create_app()`** 的用例钉住主路径。
2. **回退判据曾经过宽**：`except ConfigError` 会把"坏 JSON / 缺 api_key"也吞成回退，
   于是用户手上写坏的配置被静默换成随包库，与 spec「配置存在就一律按配置走」相左。
   现在判据是 `path.is_file()`——**只有"文件不在"才回退**，坏配置照旧大声抛错。

### 顺带修掉的两处既有缺陷（同一发版链上，不修就是半截口子）

- `save_config` / `raw_library_dirs` 的缺省参数从写死 `DEFAULT_CONFIG_PATH` 改成 `config_path()`：
  否则设了环境变量时**读一处、写另一处**（设置页保存会把改动写回用户主目录）。
- `_require_config` 的判据从 `config is not None` 改成 `config is not None and bool(config.api_key)`：
  随包库回退给的是"库路径齐全 + api_key 空串"的引导态。只看 `is not None` 的话，
  干净机器上 `/api/recommend` 会**拿空 key 直接 200 往下跑**（实测），既误导也真会打出去。
  同时 `/api/env/status` 与体检端点的 `api_configured` 改用同一判据，消掉
  「`api_configured` 说 True 而 `/api/recommend` 答 400」的自相矛盾。

### 边界（如实记，已另开 `04`）

本单给的是**库在哪**，不是**没配 key 也能浏览库**：库相关的只读端点（`/api/modules`、`/api/masters`、
`/api/topics`、`/api/references`）与另外 42 处共用 `_require_config` 那道"先配 API"的闸，
空 key 下仍答 400（实测四件全 400）。这是**既有产品行为**，不在本单射程——
那张单见 `04-库相关端点不该被-api-key-闸住.md`；本单的验收用例里有一条**钉住现状**的断言，
等那张单落地时它会红（那就是该改它的信号）。

### 读数

- `python -m pytest -n auto -q`：**5532 passed + 11 skipped**（改动前 5523；本单净增 9 条）
- `tests/test_config.py` 单文件 **31 passed**
- 现场复核（空 `HOME` + `FIRSTEP_CONFIG_PATH` 指向不存在的文件）：
  `/api/settings` 报的是 `…\firstep\library\modules`（随包库，不再是 `~/.contest_generator/modules`）；
  `api_configured` = False；`/api/recommend` = 400 中文。
