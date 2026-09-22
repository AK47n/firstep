# 03 — 结构钉：webapp 模块级不再有可变全局与 global（判据 + 合成红证 + 真红证）

**要做什么：** 把 01/02 收走的那件事变成**闸门里会变红的判据**：`webapp` 模块级不许再出现
「会话态形状」的赋值（空容器 / `None` 占位）与 `global` 语句；那三个名字不许回到模块级、也不许
回到测试的跨缝 import 里；正向钉住 `AppContext` 拥有这三个字段。判据写成纯函数（源码进、事实
出），带合成红证与真红证。

**被谁阻塞：** 01、02（判据要在这两单落地之后才是绿的）

**状态：** ready-for-agent

## 验收标准

- [ ] 新增 `tests/test_webapp_state_home.py`（先例 `tests/test_release_channel_home.py` /
      `tests/test_hwcheck_assembly_home.py`：判据纯函数 + 守卫用例 + 合成红证同文件）
- [ ] 判据①：`webapp` 里 `global` 语句数 = 0
- [ ] 判据②：模块级无「会话态形状」赋值（空 `set()` / `{}` / `[]` / `dict()` / `list()` / `None`）；
      非空常量表不误判（平台展示名那类仍在，且如实记账这条口径）
- [ ] 判据③：三个名字不出现在 `webapp` 的模块级赋值与 `global` 名单里，也不出现在 `tests/`
      对 `webapp` 的跨缝 import 里
- [ ] 判据④（正向）：`AppContext` 的 dataclass 字段含这三个名字——防「把状态删干净」式假绿
- [ ] 判据⑤：合成红证——把收走前的写法（模块级 `X = set()` / `{}` / `None` + `global X`）喂进
      同一套判据当场认出
- [ ] 真红证留档 `.scratch/webapp-state-into-ctx/probe-01-pin-red-proof.py`：base **显式钉**
      收走前那个提交 `5c9fc8b0`（**不写 HEAD**——提交后 HEAD 就是新代码，红证会静默变绿），
      带 `--base` 覆盖与 **base 自校验**（base 里若已找不到那三处模块级状态就大声失败）；
      `red-proof.txt` 记读数：base → 3 条违规，当前树 → 0 条
- [ ] `python -m pytest -n auto -q` 全绿
- [ ] 未改动：除新增判据文件与 `.scratch/` 证据外零改动

## Comments
