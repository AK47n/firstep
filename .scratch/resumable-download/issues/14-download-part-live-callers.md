# 14 — `materials_task.download_part` 还有没有活口：量清调用点与对外承诺，再决定删还是留

**要做什么：** 把工单 10 第七节那条「顺手发现、**未处理**」的账还掉——
`src/contest_generator/materials_task.py` 里的**模块级公开函数** `download_part`
（256 KB 分块那支，返回 sha256 hex）自工单 03 起已不是缺省下载器（缺省换成
`download_resume.resumable_download`）。本单要**量清**它今天到底还有没有执行路径、
有没有对外承诺，然后**二选一处置**：

- **删**（连死 import 一起）：必须先证明**行为零变化**（相关用例绿 + 逐文件全套绿）；
- **留**：把「为什么留」与判据写回本单，按 `wontfix` 关掉。

**被谁阻塞：** 无——可立即开始。工单 10 第七节记的账（`3fc218b4`）、工单 12 备注末条
与评审第 13 条记的账（`4fc27282`）都明文把它留作独立一单。

**状态：** wontfix（**处置 = 留**：不删函数；随手把结论钉在被问的那一处）

- [x] **先量再动**：把「谁定义 / 谁 import / 谁调用 / 谁只是提它」逐处列清——四个类别分开数
      （定义处 / `from … import` / 真调用（`download_part(`）/ 只在注释与文档里出现），
      量具落盘可复跑，模板 = `.scratch/resumable-download/measure-12-twin-candidates.py`。
      扫描面要**包含 `.scratch/`**（它是 tracked 的，且本仓把它当证据工具的存放地），
      也要**显式记下扫描面本身**（哪些目录被跳过、为什么）。
- [x] **判据强度**：把 `download_part` 换成抛异常的炸弹，跑 `tests/test_materials_task.py`
      + `tests/test_full_task.py`（必要时连 `tests/test_download_status_surface.py`）——
      **每格先自证注入生效**；若无人红 = 测试侧确实没有执行路径。探针失效 / 超时如实记，
      **不许折算成绿**。
- [x] **删之前先查它有没有对外承诺**（**本单的关键一条，别跳过**——它是**模块级公开函数**，
      风险等级高于工单 12 删的私有类静态方法）：六条逐条给证据（见「三」）。
- [x] **处置**：按上面二选一落地，并**如实写明它的代价**（见「四」）。
- [x] **零行为变化**：本单没有走「删」那条路，`tests/` **零改动**；相关用例与逐文件全套都跑了
      （见「五」）；`git diff --numstat tests/` 为空，故「删除行逐行说明」一节无从执行——
      **如实记为「无删除行」**。
- [x] 双轴评审（Standards / Spec 各自独立跑，用 `code-review` skill）；判定记进「验收记录」（见「六」）。

## 口径与纪律（承自工单 09/10/11/12）

- 改动前那份**从 `git show <改动前提交>:<文件>` 取**，不读工作区现状（否则重排后数字自己变了）。
- 跑测试一律 `python -m pytest`（裸 `pytest` 走全局 editable 安装 = 沙箱源码，工单 10 踩过）。
- 证据文件落 **UTF-8**、由脚本落盘（模板 `run-12-evidence.py`），**别用 `Tee-Object` / `>`**。
- 工单 / 提交信息一律中文（`.githooks/commit-msg` 会拦英文）。

## 初查线索（开工前 5 分钟的粗扫，**待正式量具复核**，别当结论）

- `download_part` 在 `src/` 内的调用点看起来是 **0**；`tests/test_materials_task.py` 只 import 不调用。
- **但 `.scratch/` 下有粗扫可见的活口**：`probe-01-resume.py`（`--impl plain` 与 `auto` 兜底）、
  `probe-01-negative.py`（反证用的对照实现）、`full-download/e2e_full_download.py`。
- `.scratch/resumable-download/spec.md` 明文写着「**`download_part` 保留**」，理由两条
  （「`download_resume` 内部调用它」/「既有的 `full_task.download_part` monkeypatch 点继续有效」）
  ——这两条**今天是不是还成立**要单独验证。
- 发布包白名单 `tools/pack-update.ps1` 第 60 行注释明写 `.scratch` 不进清单
  （但 `src` 进）——这一条对「活口算不算用户可见」的判断很关键，要复核另外两个打包脚本。

---

## 验收记录（2026-09-13）

### 一、先量再动：谁定义 / 谁 import / 谁调用 / 谁只是提它

量具 = `.scratch/resumable-download/measure-14-download-part.py`，证据 = `verify-14-callers.txt`，
命令 `python .scratch/resumable-download/measure-14-download-part.py 4fc27282`（**基线从 git 对象取**）。

**扫描面（量具 A 节原样打印）**：`git ls-files` 的 **7486 个 tracked 文件**，含 `.scratch/` 与 `docs/`；
读不了 / 二进制 **0** 个；未跟踪文件不在面内（`__pycache__` 之类不在 tracked 里）。
`.py` 走 AST 判定（**注释与 docstring 天然不进 AST**，故「提及」是机械判出来的，不靠人眼），
`.md/.txt/.json` 一律记「提及」，其余脚本类按行模式判。

**合计**：定义 1 / import 3 / 调用 1 / 取值引用 2 / 模板代码 1 / 提及 31。

| 分区 | 定义 | import | 调用 | 取值引用 | 模板代码 | 提及 |
|---|---|---|---|---|---|---|
| `src/` | **1**（`materials_task.py:88`） | 0 | 0 | 0 | 0 | 2（`download_resume.py:20/57`，两处都只是注释） |
| `tests/` | 0 | 2（同一处 import 语句的两行：`test_materials_task.py:23` + 续行 26） | 0 | 0 | 0 | 1（`test_full_task.py:820` 注释） |
| `.scratch/` | 0 | 1（`full-download/e2e_full_download.py:372`） | **1**（同文件 `:374`） | 2（`probe-01-resume.py:55/76`） | 1（`probe-01-negative.py:35`，写在字符串模板里、落盘执行） | 26 |
| `docs/` | 0 | 0 | 0 | 0 | 0 | 2（本单自己新写的 locenv 行） |

「模板代码」这一类是量具**自己先漏过、再补上**的：`probe-01-negative.py` 的对照实现写在
`RUNNER_TEMPLATE` 字符串里（落盘后执行），纯 AST 只看得到「一个字符串常量」，
第一版把它算成「提及」——量具自己制造的假账，已单列一类（并补 `PYTHONIOENCODING`
与续行口径两处）。**运行时取证**（`verify-14-guard-strength.txt` 第三节）另证这四处活口
**都解析到同一个产品函数对象**（`is` 判等 True），不是 grep 假象。

> **与上游复核的差异（重要）**：任务书里的复核说「`download_part(` 在全仓只有**定义处**一处出现，
> **没有任何调用**」。**量出来不是**——`.scratch/full-download/e2e_full_download.py:374`
> 是一处**真调用**（配 `:372` 的真 import），另有 2 处取值引用与 1 处模板 import。
> 上游那句只对 `src/` + `tests/` 成立。**这正是「别照抄结论、自己量」的值所在**，
> 也直接改变了本单的处置（见「四」）。

### 二、判据强度（配对证据：死目标绿 + 活目标红，且红必须来自「炸弹被执行」）

探针 = `.scratch/resumable-download/probe-14-guard-strength.py`，证据 = `verify-14-guard-strength.txt`。
逐文件跑、每文件 120s 上限；每格先**自证注入生效**；**并数「炸弹被执行 N 次」**——
因为红的理由可以是「身份断言不相等」，也可以是「炸弹真被执行」，**只有后者能替绿背书**。

| 格 | `test_materials_task.py` | `test_full_task.py` | `test_download_status_surface.py` |
|---|---|---|---|
| `download_part_boom`（靶子 = 死代码） | **绿** 20 passed，炸弹执行 **0** 次 | **绿** 33 passed，炸弹执行 **0** 次 | **绿** 30 passed，炸弹执行 **0** 次 |
| `resolve_boom`（阳性对照，靶子 = 缺省下载器这条活路） | **红** 2 failed / 18 passed，炸弹执行 **1** 次 | **红** 5 failed / 28 passed，炸弹执行 **4** 次 | （不跑，见下） |

**这一格阳性对照栽过两次，两次都是探针失真（第五、六次），如实记下来：**

1. **第一版打错了靶子**：炸弹装在 `download_resume.resumable_download` 上，跑出 5 + 12 failed
   ——**红的全是身份断言**（用例里 `assert task._download is resumable_download` 两侧取到不同对象），
   **没有一条是「下载路径被执行」**。那格红不为绿背书，等于阳性对照失效。*（Spec 轴评审当场翻出。）*
2. **第二版只换 `task_download` 那份绑定**：自证立刻如实报「探针失效」——因为**缺省这条路有三个绑定**：
   ① 构造期 `__init__` 读**任务模块自己的**模块名；② 两个任务类的**类属性** `_download`；
   ③ 解析期算 `is_default` 用 **`task_download`** 那份。只换 ③，实例属性仍是真实现 →
   解析走 `return instance, False` 那一支，炸弹根本没上。现改为三处一起换，
   自证 = 拿**真任务实例**跑一遍 `resolve_task_download`，断言「结果就是炸弹」**且**「被认成缺省实现」。

**结论**：`download_part` 在 `src/` 与 `tests/` 的**执行路径为零**（三文件全绿 + 炸弹执行 0 次），
而同一套注入机制打在**生产缺省下载器**那条路上会红、且**炸弹真被执行 1 / 4 次**——
「绿」不是探针装饰造成的。

### 三、对外承诺面：六条逐条查（删之前必须查，本单最硬的一节）

| # | 查什么 | 量出来的 | 判读 |
|---|---|---|---|
| D1 | `__all__` / 显式导出 | 模块里**没有** `__all__`（改动前 / 现状都是） | 不是显式导出面 |
| D2 | 文档点名（`docs/` + `CONTEXT.md` / `README` / `CHANGELOG` / `VERSIONS`） | `git grep 4fc27282` 命中 **0**（口径 = 基线 ref，不是工作区） | 没有面向用户的文档承诺 |
| D3 | 发布包白名单 | `pack-update.ps1` 顶层白名单 21 项：含 `src`=True、`.scratch`=**False**；`pack-full` → `full_pack.py`：`TOP_LEVEL_ENTRIES` 含 `src`=True、`SKIP_DIR_NAMES` 含 `.scratch`=**True**；`pack-materials` 只打 `sources/materials` | **它随包发布（`src` 进包）**；但**四处活口一个都不进包**——用户拿到的是一份没人调用的公开函数 |
| D4 | 其它模块的 import | `src/` 分区 import 命中 **0** | 生产侧零耦合 |
| D5 | spec 里的声明 | `.scratch/resumable-download/spec.md` 明文「**`download_part` 保留**」，理由两条：①「`download_resume` 内部调用它」②「既有 monkeypatch 点 `full_task.download_part` 继续有效、零改动」 | **这是唯一的「写下来的承诺」**，但它不是对外契约（`.scratch` 不进发布包） |
| D6 | 那两条理由今天还成立吗（**独立验证，不照抄 spec**） | ① `download_resume.py` 里的**调用行 = []**（只有两行注释提到它——spec 断言的「内部调用」**从来没实现**，而且按工单 04 的分层守卫它**本来就不该**被实现）；② `full_task.py` 里 `download_part` 的命中 = **False**（工单 03 换缺省下载器时一并去掉） | **两条理由都已失效**——spec 的「保留」结论当时建立在一个假前提上（已在 spec 里逐句更正） |

历史（量具 E 节）：`def download_part` 只被 `786dc450`（materials-update/04）创建过一次；
它**确实当过公开契约**——`189d105c`（full-download/03）把名字 import 进 `full_task` 当缺省下载器，
`tests/` 里也 patch 过 `full_task.download_part`；**这一切在 `22d0f643`（工单 03）结束**。
`-S` 命中 10 次提交，无一次是「改了这处忘了那处」。

### 四、处置：**留**（不删），为什么不是「删」

**数据支撑的三条**（不是「不想动」）：

1. **删不掉「零代价」**：它的活口是**证据工具**（不是生产、也不是测试）——
   本特性红基线探针的 `--impl plain`、反证探针的对照实现、完整包 e2e 脚本的一处真调用。
   删它就要改 3 支 `.scratch` 脚本（还要把「改之前」的实现拷进探针里）、
   改 2 处 `download_resume.py` 的对照注释、再改 spec——**换来的只是 `src/` 少 22 行**
   （函数 19 行 + 因此变成死导入的 `hashlib` / `urllib.request` 两行）。
2. **它的「不对」有判据兜着，不会静默害人**：不判截断这件事，正是工单 01 探针的**红基线**
   本身——spec 与探针的 docstring 都写着「它既不报错也不校验 Content-Length」。
   删了反而少一件「可执行的旧行为参照物」。
3. **没人会顺手用错它**：D3 已证四处活口全在 `.scratch`（不进发布包），D4 证生产侧零 import，
   而函数 docstring 现在**开门见山**写着「它已经不在生产链路上 / 别拿它当下载器 / 它不判截断」。

**将来会不会漂（工单第 4 条点名要答的那一问）——正面答**：

- **会不会漂？会。而且漂了没有任何判据会红**——本单的炸弹格刚证明了这一点
  （三文件全绿 + 炸弹执行 0 次）。它**唯一的第二处口径**是 `download_resume.py` 里那两行
  注释（分块大小 256 KiB 与 UA `firstep-materials` 各写了一遍，不是引用）。
- **为什么不因此就删**：它今天的角色不是「一份实现」而是「一份冻结的证据对照」；
  真有人去「改进」它（比如补上截断判定），损害的是**红基线的历史可比性**，
  而不是生产行为。这一层口径已写进函数 docstring（`wontfix` 的理由、`别拿它当下载器`）。
- **残余风险如实记**：没有任何自动判据守「它必须保持朴素」。要守就得给探针加断言
  （例如断言它**不**校验 `Content-Length`）——**那是另一件事（给探针加判据），本单不做**，
  记在这里备查。
- 另有一处**已在 spec 里更正的假前提**（D6）：spec 原来写「`download_resume` 内部调用它」，
  而按工单 04 的分层守卫（下载域不许知道任务层）那条实现**根本不可能存在**；
  现在 spec 那段下面有一块 ⚠️ 补记逐句更正，指向本单。

**本单实际落下的改动**（`wontfix` 不等于零改动，但改动只有「把结论钉在被问的那一处」）：

| 文件 | 变化 | 为什么 |
|---|---|---|
| `src/contest_generator/materials_task.py` | `download_part` 的 docstring **+10 行**（零行为变化） | 下次谁再问「它还有没有活口」，答案就在函数上；同时钉住「不判截断，别当下载器」 |
| `.scratch/resumable-download/spec.md` | 那段「保留」下面**+12 行 ⚠️ 补记** | 那两条理由已失效，不更正会误导下一个读者（工单 06/08 已立同款先例） |
| `docs/agents/local-environment.md` | 特性表 **+1 行 / 改 1 行** | 本机环境文件记「下载抗断」特性的durable 产物；本单新增了这一行结论与三份证据文件 |

### 五、「零行为变化」逐条对过

| # | 关注点 | 来源 | 结论 |
|---|---|---|---|
| 1 | `tests/` 有无改动 | `git diff --numstat tests/` | **空**——本单走「留」，没删函数、也没动那颗死 import；故工单第 5 条要求的「删除行逐行说明」**本节记「无删除行」**（口径不是放弃，是这条验收项在本处置下无内容） |
| 2 | 那颗**死 import** | 量具 | `tests/test_materials_task.py:23`（跨行到 26）**只 import 从不调用**。**本单不动它**：删 import 属于「连死 import 一起删」那条路的连带项，本单没走那条路。*（它的副作用是：将来真要删函数时，这个 import 会当场炸出来提醒——留着也不坏。）* |
| 3 | 产品行为 | 判据 | 只改了 docstring（不参与执行）；`tests/` 三条相关文件 **83 passed**（改动前同数） |
| 4 | 相关用例 | 判据 | `python -m pytest tests/test_materials_task.py tests/test_full_task.py tests/test_download_status_surface.py` → **83 passed** |
| 5 | 逐文件全套 | 判据 | `python .scratch/resumable-download/run-11-suite.py 120` → **文件 196：绿 196 / 红 0 / 卡住 0**（321.9s，落盘 `verify-14-suite.txt`） |
| 6 | 快照 / 状态面 / 载荷 | 读码 | 三处一个字未动（本单只碰 docstring 与文档） |

### 六、双轴评审结论（2026-09-13，两轴各自独立跑）

| # | 轴 | 问题 | 处置 |
|---|---|---|---|
| 1 | **Spec** | **阳性对照没打到靶子**：炸弹装在 `download_resume.resumable_download` 上，红的是身份断言、不是下载路径——那格红不为绿背书 | **当场重做**：靶子改到「缺省下载器这条路的三个绑定」，自证加「`resolve_task_download` 结果就是炸弹」；并给判据加**「炸弹被执行 N 次」**一列（死目标 0 / 活目标 1 与 4） |
| 2 | **Standards** | **探针第三节在本机 GBK 控制台下会崩**（`UnicodeEncodeError: '\ufffd'`、退出码 1、整节判据丢失，而半截输出看着像「跑完了」） | **当场修**：活口子进程补 `PYTHONIOENCODING`；探针自身 stdout `reconfigure(utf-8, errors="replace")` 兜底；落盘器也补设 env |
| 3 | Standards | docstring 里写死了 `.scratch/resumable-download/spec.md` 路径（正是工单 12 评审第 14 条刚删掉的形状） | **当场修**：源码 docstring 去掉路径，只留「工单 14」与工具名；路径留在工单 / spec / 证据文件里 |
| 4 | Standards + Spec | 「唯一调用点」这句清单抄在三处（docstring / spec / locenv），**漏了第三处活口**（`e2e_full_download.py` 的真调用），且把「取值引用」写成了「调用」 | **当场修**：三处按量具口径统一改写（真调用 1 + 取值引用 2 + 模板 import 1，共 3 个文件 4 处） |
| 5 | Standards | `measure-14` 里「第二参数 = 证据文件」的 stdout 转向分支是**死代码**（落盘走落盘器的内存捕获） | **已删**（连用法行一起） |
| 6 | Standards | locenv 列了 `verify-14-suite.txt` 而磁盘上当时没有 | **评审那一刻属实**（套件还在跑）；本单随后跑完并落盘（196/196/0/0），该行现在与磁盘一致 |
| 7 | Standards | 新脚本与工单 12 的三支逐字同形（判定词表已第四份，有漂移风险） | **有意保留**：工单模板明写「模板 = measure-12」，工单 12 评审第 16 条已判「一次性分析工具优于参数化」；本单把「卡住 / 探针失效」的口径在本探针里写死，避免再分叉 |
| 8 | Standards | 落盘器里的 `PROBE_NOTE` 是**人工写的结论**，混在探针输出后面，读起来像量具产出 | **保留但标明**：该节标题就写着「补充：探针设计与……（脚本里写死，不走 shell 追加）」；本单把它写实（三处已修的失真 + 两版靶子） |
| 9 | Spec | 「验收记录是占位符 / `Status` 仍 `claimed`，结论先于台账」 | **如实记**：确实是先落的结论（docstring / spec / locenv）再补台账；本记录落盘时一并关闭（`wontfix`），顺序问题记在这里备后人照流程走 |
| 10 | Spec | `download_part` 是**死 import 的连带项**却没记 | 已在「五」第 2 条明写（含「本单为何不动它」） |
| 11 | Spec | 量具 B′ 标题自称「读 git 对象」，而 D2 用的是 `HEAD`（含工作区改动） | **已修**：D2 改用基线 ref 并在标题标明口径；D6 明写「读的是工作区现状」 |
| 12 | Spec | 「冻结」是叙述不是判据；「将来会不会漂」没正面答 | 已在「四」正面回答（会漂、且漂了没有判据会红；残余风险与将来的补法都写明） |

**两轴另各有一条判为「无需改」**：① 量具的「模板代码」这一类是**本单量具自己的盲点**
（`.py` 里作为字符串嵌入的代码），已单列一类而不是塞进「提及」——它让活口清单从 3 处变 4 处，
是本单**结论方向**的依据之一；② 「另跑一格 `resolve_boom` 打到 `test_download_status_surface.py`」
没做——那一格问的是「下载路径会不会被执行」，状态面文件不下载，跑了也是绿，徒增噪音。

## 备注

- **`wontfix` 在这里的确切含义**：**不删** `download_part`（删这条处置被否决），
  而不是「本单什么都没干」——改动清单见「四」，全部是文档与 docstring，零行为变化。
- **先证明判据会红再用它判绿**：本单的「绿」由**配对证据**背书（死目标绿且炸弹执行 0 次 /
  活目标红且炸弹执行 1 与 4 次）。**探针第一版的红是假的**（红在身份断言），
  已记进「二」与「六」——工单 11/12/13 的教训在这里第五、六次重演，模式完全一样：
  **探针自己失真，不是产品行为**。
- **别把这条结论读成「`download_part` 有用」**：它在生产与测试里都没有执行路径；
  留它的唯一理由是「证据工具需要一份冻结的旧实现当对照」，以及「删它的连带改动面大于收益」。
  真要删，先跑 `.scratch/resumable-download/measure-14-download-part.py` 与
  `probe-14-guard-strength.py` 复核这两条是否还成立。
