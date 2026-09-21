# 02 — 清点处置 12 处死 import ＋ 1 处级联（真红证 ＋ 字节级归因）

**要做什么：** 让新判据从 **12 处违规**变成 **0 处**，且**行为零变化**：按 spec「处置规则」摘掉
11 条语句里的死名 ＋ 整条删 1 条空语句（`ui/code-compile.js:27`）＋ 1 处**级联**
（`fx/core.js:115` 摘 `export ` 前缀——它的唯一消费者正是本轮摘掉的那条死 import，
不摘判据 D 会从 0 变 1）。正文（函数体 / 监听器 / markup / CSS / 555 个 id / `window` 探针桥）一字不动，
**尾换行与行尾逐字节不变**。

**被谁阻塞：** 01（判据单源与合成红证）

**状态：** ready-for-agent

## 验收标准

- [ ] `.scratch/module-import-usage/apply-removal.mjs`（清点执行器）：**逐处内容锚定**（12 处死名所在语句的
      原文切片 ＋ 级联那 1 处的声明行原文），改一处报一处；**任何一处对不上就整体拒绝写盘**；
      产出 `verify-removal.txt`。
- [ ] **字节级证据（本单的硬判，不用归一化比对）**：对每个改动文件，取 base `f1c9e1c7` 的**原始字节**，
      按脚本记录的**删除区间**重放一次 → 结果必须与该文件落盘后的**原始字节逐字节相等**；
      并逐文件断言**行尾写法与尾部换行字节数未变**。读数落 `verify-removal.txt`。
- [ ] 改动面：**11 处摘名 ＋ 1 处整条删 ＋ 1 处级联**，落点与 spec 表逐条一致；
      `git diff --name-only` 只含 `src/contest_generator/static/js/**` 与本工单产物（`.scratch/module-import-usage/**`）；
      且**行数只减不增**（摘名/整条删/摘 `export ` 前缀都不新增行）。
- [ ] **既有判据全 0**（清点后复跑，逐条打印）：`graphBreaks` / `reachable.orphans` /
      `wiringViolations` / `registryProblems` / `bareLoads` / 判据 D / 判据 T / 星号体检 / 取数面体检 /
      `unusedImports`（装载根）。**特别复跑** `tests/js/fx-guard.test.mjs`（orphans）与
      `tests/js/ui-dom-contract.test.mjs`（`unreachableModules`）——**不许把任何模块变成孤岛**。
- [ ] 真红证 `probe-02-base-red-proof.mjs` → `red-proof.txt`（退出码 0；失败非零并打印 base 身份）：
      ① **base 显式钉 `f1c9e1c7`**（**不写 HEAD**）＋ **base 自校验**：12 个钉子名各自的 import 语句
      在 base 上逐条内容锚定对上、级联那处 `export function downloadedPercent` 仍在、base 上既有判据全 0
      ——**选错 base 当场大声失败**；
      ② 判据在 base 上红 **12** 处（逐条点名，并标出哪 7 处是工单 02 的口径看不见的）；
      ③ **当前工作树绿（硬判）**：判据 0 处 ＋ 全部既有判据 0 违规；
      ④ 合成自检全过（**import 01 的 `synthetic-cases.mjs`**，不抄第二份用例表）。
- [ ] 独立机械证据 `probe-03-diff-proof.mjs` → `diff-proof.txt`：逐文件把 base（`git show f1c9e1c7:<path>`）
      与工作树比，**每一行都必须归得了因**（未改动老行 / 摘名 / 整条删 / 级联），并单独一行报
      **"尾部换行不一致的文件：0 个"**（口径与工单 02 §③ 的教训一致：不许折叠尾随差异）。
- [ ] **三门禁各跑一遍并记数**（读数写进 Comments）：`node --test "tests/js/*.test.mjs"`（基线 1688）／
      `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`（基线 26，本轮改到
      `static/js/ui/` → **必跑**）／`python -m pytest -n auto -q`（基线 5049 passed + 1 skipped）。
- [ ] **未顺手做**：常量形态 / C6 / C7 / `.scratch` 探针修复 / 零调用私有死函数 /
      新判据接闸门（03 的交付）。

## Comments

（实现时补：逐条销账、字节级重放读数、清点后既有判据读数、红证读数、diff 归因、三门禁读数、双轴评审整改。）
