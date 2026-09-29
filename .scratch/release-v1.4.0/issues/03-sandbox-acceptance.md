# 03 — 沙箱「模拟用户机」真机验收 + 当场回写 local-environment.md

**要做什么：** 按 `docs/agents/local-environment.md` **第 1 节**的四个落点（工具根 / 数据目录 / 端口 /
入口）在沙箱上做一次真机验收：**真进程 + 真浏览器 + 真数据目录**，看的是"用户打开工具会看到什么"，
而不是夹具里跑出来的东西。结论**当场回写**第 1 节（沙箱当前状态）与第 0 节（交接区）。

**被谁阻塞：** 01（沙箱要从"要发的那棵树"造出来）。

**状态：** resolved

- [x] 造一份干净沙箱：`python .scratch\full-download\make_sim_sandbox.py`
      （工具根 `C:\Users\luoji\Desktop\firstep-sim`、数据目录 `C:\Users\luoji\.contest_generator_sim`；
      **先收 8020**——重建会整树删掉工具根，带着进程删会 `WinError 32`）
- [x] `FIRSTEP_LAUNCHER_PORT=8020` 起沙箱（入口 `sim-run.py`，理由见第 1 节：生产入口的配置路径
      写死在真身数据目录）
- [x] 验收第 1 步：`GET /api/health` 版本 = **1.4.0**（盘上的代码就是这一版）
- [x] 验收第 2 步：真浏览器逐页看**观感**（本轮主角）——十二个页签各取关键元素的**计算样式**：
      字号落在六档角色（20/16/14/13/12/22）内、间距走令牌、一屏一层完整描边
- [x] 验收第 3 步：**更新面板的体积数字**是实测口径（约 800 MB / 约 0.7 GB），不再是 6.2 GB / 5 GB+
- [x] 验收第 4 步：真身数据目录**零触碰**（`~\.contest_generator` 的 mtime 未变）
- [x] 收尾：收 8020、查无残留 `contest_generator.webapp` 进程、确认 8000/8020/8021 都没在听
- [x] **当场回写** `docs/agents/local-environment.md` 第 1 节（当前状态：盘上 = v1.4.0 / 8020 已释放）
      与第 0 节（交接区：这一批"到用户手上了"要等 04 发布之后才写——本单先写真机验收的结论）
- [x] 提交信息中文

## Comments

### 落地事实（2026-09-29）

| 项 | 值 |
|---|---|
| 沙箱（重造后） | `C:\Users\luoji\Desktop\firstep-sim`，**2701 个文件 / 292.1 MB**；`sim-run.py` 按 `.scratch/update-restart-stale-service/sandbox-entry-sim-run.py` 补回（975 B） |
| 数据目录 | `C:\Users\luoji\.contest_generator_sim`（构建脚本重造：`updates/` + `config.json` + `recent.json` + `tasks-simulated.json`）；**资料库基线没有**（构建脚本不写 `.materials-manifest.json` ⇒ 沙箱里"资料库更新"报版本未知，故意不真实） |
| 版本读数 | `/api/health` → `{"app":"contest-generator","version":"1.4.0","ok":true}` |
| 真机验收 | **33 / 33 全过**（`sandbox-accept.txt` / `.json`）——十二页正文基准 14px、有文字元素字号 ⊆ 六档；设置页显示 v1.4.0 且体积文案为实测口径；版本记录页首块 = v1.4.0 且主题句逐字一致 |
| 收尾 | 8020 已释放、无残留 `sim-run` 进程；**真身 `~\.contest_generator\config.json` mtime = 2026-09-10 23:28（零触碰）**——注意 8000 上有一个**真身实例在跑**（PID 47924，13:07 起，不是本轮起的） |

### 第一次跑的 5 条"红"是**判据口径**问题，不是产品问题（值得记）

第一版探针把**所有可见元素**都算进"字号档位"，于是 5 个页签各红一条：`input` 的 computed
`font-size` = **13.3333px**（浏览器对表单控件的默认值，`-webkit-small-control`）。
按本仓库的纪律（"看着像" ≠ "量出来"）另起一支 `probe-input-font-detail.mjs` 量清楚：

- **9 个例外全是 `checkbox` / `radio`**（generate 1 / hwcheck 2 / settings 1 / library 2 / reference 3），
  而且**自己的文字为空、子元素文字长度 = 0**——它们是自绘控件（`appearance: none` + 15×15px），
  字号根本不影响渲染（读数 `sandbox-input-detail.txt`）。
- 口径改成"**有文字的元素**"（文本型 `input` / `select` / `textarea` / `button` 按定义算有文字，
  其余要求**直接文本子节点非空**），并把每个页签的**折叠区全展开**后再量（否则"默认收起的输入框"
  永远在射程外）→ 复跑 **例外 0 个**（`sandbox-input-detail2.txt`）、整套 **33/33**
  （`sandbox-accept.txt`）。

**产品面一行没改**（`git status src/contest_generator/static` 在本单为空）：本单只改探针口径 +
文档。这与 12 单账第 5 条（`scrollWidth` 判溢出不可靠）是同一类教训：**量具的口径要先自证**。

### 另一张不作判据的读数（口径别混）

每页"整圈完整框"的**渲染元素数**：generate 91 / hwcheck 32 / settings 35 / guide 33 / reference 31 /
library 20 / master 14 / topic 9 / code 9 / pdf 7 / md 7 / changelog 1。
**这是 DOM 元素口径，与 `probe-04` 的 115（样式规则数）不是同一把尺**——本单不拿它判"一屏一层"
（描边那条线本来就靠逐层清单 + 人眼，见 08 账第 1 条）。
