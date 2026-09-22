# 03 — 结构钉：webapp 模块级不再有可变全局与 global（判据 + 合成红证 + 真红证）

**要做什么：** 把 01/02 收走的那件事变成**闸门里会变红的判据**：`webapp` 模块级不许再出现
「会话态形状」的赋值（空容器 / `None` 占位）与 `global` 语句；那三个名字不许回到模块级、也不许
回到测试的跨缝 import 里；正向钉住 `AppContext` 拥有这三个字段。判据写成纯函数（源码进、事实
出），带合成红证与真红证。

**被谁阻塞：** 01、02（判据要在这两单落地之后才是绿的）

**状态：** resolved

## 验收标准

- [x] 新增 `tests/test_webapp_state_home.py`（先例 `tests/test_release_channel_home.py` /
      `tests/test_hwcheck_assembly_home.py`：判据纯函数 + 守卫用例 + 合成红证同文件）
- [x] 判据①：`webapp` 里 `global` 语句数 = 0
- [x] 判据②：模块级无「会话态形状」赋值（空 `set()` / `{}` / `[]` / `dict()` / `list()` /
      `None` 占位 / **可变容器构造** / **裸注解**）；非空常量表不误判（平台展示名那类仍在，
      且如实记账这条口径）
- [x] 判据③：三个名字不出现在 `webapp` 的模块级赋值与 `global` 名单里，也不出现在测试的
      **跨缝 import** / **monkeypatch 路径字符串** / **模块对象别名直改**里
- [x] 判据④（正向）：`AppContext` 的 dataclass 字段含这三个名字——防「把状态删干净」式假绿
- [x] 判据⑤：合成红证——把收走前的写法（模块级 `X = set()` / `{}` / `None` + `global X`）喂进
      同一套判据当场认出；**每条腿各有一条自己的红证**（含「只靠 global」「裸注解」「真树扫描」
      这三条容易被别的腿兜住的）
- [x] 真红证留档 `.scratch/webapp-state-into-ctx/probe-01-pin-red-proof.py`：base **显式钉**
      收走前那个提交 `5c9fc8b0`（**不写 HEAD**——提交后 HEAD 就是新代码，红证会静默变绿），
      带 `--base` 覆盖与 **base 自校验**（base 里若已找不到那三处模块级状态就大声失败）；
      `red-proof.txt` 记读数：base → **6 条（4 类）**，当前树 → 0 条
- [x] `python -m pytest -n auto -q` 全绿
- [x] 未改动：除新增判据文件与 `.scratch/` 证据外零改动（`git diff HEAD -- src tests` 为空）

## Comments

### 2026-09-22 落地读数

- **判据强度自检**（`.scratch/webapp-state-into-ctx/probe-02-guard-strength.py` →
  `guard-strength.txt`）：把 13 条判据腿**逐个 stub 掉**再跑守卫 → **13/13 变红**、基线绿
  （7 passed）、**逐字节复原**（sha256 一致）。这条不是走过场：对抗性验证就是靠它抓出**两条
  没有红证的腿**（见下）。
- **真红证对读**（`probe-01-pin-red-proof.py` → `red-proof.txt`）：base `5c9fc8b0` → **6 条 /
  4 类**（global 3 处、模块级会话态 3 个、三名字回到模块级、AppContext 缺三字段，外加测试侧
  2 条）；当前树 → **0 条**；`--base HEAD` → 自校验大声失败（exit 2，不产假绿）。
- **全量**：`python -m pytest -n auto -q` → **5070 passed + 1 skipped / 100.88s**
  （5063 + 本单 7 条）。
- **评审三轮**（固定点 `3a360fda`，Standards + Spec 双轴并行；作者整改后再加**一轮对抗性
  验证**逐条证伪）：
  - **Standards 两条硬违规**：① 「`global` 只声明、模块级无同名赋值」那条腿没有独立红证；
    ② 探针自己拼了一份聚合逻辑且**已经漂移**（丢了 global 名单腿）→ **修法：聚合收成唯一一个
    `state_violations`，守卫与探针共用**（先例 `release-channel-dedupe` 的教训）；补
    global-only 形状的合成红证。
  - **Standards 的判据强度实测**（评审亲手跑出的绕过形状）：注解式 `dict()` / `defaultdict(set)`
    / `dict.fromkeys([])` / `try:`·`if:`·`with:`·`for:` 块内 / 元组展开 `A, B = set(), None` /
    海象 / 裸注解 / 模块对象别名直改 / `from … import webapp` → **逐条补上**；不可变容器
    （`()` / `frozenset()`）与**已知盲区**（`set() | set()`、`setattr`、拼接或 f-string 路径）
    如实记账（盲区那三条断言写明「不是契约，是边界记录；判据变强时该反过来写」）。
  - **Spec 轴**：① 工单与 spec 写的「base → 3 条」与实测 6 条不符 → 两处都改成 **6 条（4 类）**；
    ② 扫描面只扫顶层 `test_*.py` → 改 `tests/**/*.py`（**224** 个文件，含 `conftest.py`、
    `fakes.py` 与子目录）；③ 死常量 `_EMPTY_CONTAINER_CALLS` → 删掉并按名称接线；④ 探针 ① 段
    的引用计数属「人读读数」→ 标题补「人读读数，不是判据」（与 `release-channel-dedupe` 的
    普查段同款）。
  - **对抗性验证（第三轮，专证伪整改）**：13 条腿 stub 普查发现**两条腿仍无红证** ——
    `global_names`（被「模块级名字」那条腿兜住）与 `_test_sources`（对空 mapping 真空通过）
    → 各补一条独立合成红证（**只靠 `global` 的形状**；把扫描根指到一个真含跨缝引用的临时目录）；
    另一条**口径错误**：我曾在断言注释里把裸注解说成「判据②已覆盖」，实际只有「模块级名字」腿收
    → **裸注解纳入判据②**（形状标签 `annotation`），断言改真。
  - 另修一条证据编码：`red-proof.txt` 第一版是 PowerShell `>` 重定向的 **UTF-16LE**（`read`
    工具当二进制拒读）→ 探针加 `--out`，自己按 **UTF-8** 落盘。
- **零改动核对**：`git diff HEAD -- src tests` 为空——本单只新增判据文件 + `.scratch` 证据，
  01/02 的代码一字未动。
