# 01 — 样式块面：描边登记簿 + 类别表 + 守卫腿⑥ + 合成红证

**要做什么：** 让「`index.html` 样式块里哪些整圈完整框算例外」变成**可对账的数据**，并让守卫看着它。
盘上 115 条整圈完整框逐条登记为 `[作用域, 剥注释后的选择器, 类别]`（10 类），
守卫新增**腿⑥**（三向对账 + 一条透明不变量 + 类别表形状自检），带合成红证；
探针一条命令复算"登记簿 ↔ 盘上"的双向差、每类条数与口径分列（115 / 94 可见框 / 21 非框）。
**产品面零改动**——这一单只立数据与判据。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-09-29；结论 / 读数 / 双轴评审处置见文末）

## 验收标准

- [ ] **登记簿落地**：`tests/js/css-tokens.test.mjs` 里新增 `BORDER_REGISTER`，**恰好 115 条**，
      按作用域分组；每条 `[作用域, 选择器, 类别]`，选择器是**剥掉前导块注释、空白归一**后的形态。
      与盘上双向对账 **0 差**（多一条、少一条都算未完成）。
- [ ] **类别表落地**：`BORDER_KINDS` 10 类，每类一句判据；10 类都有成员；
      分布与 spec 的类别表逐条一致（`block 3 / control 38 / tag 15 / alert 19 / modal 8 /
      float 3 / doc 6 / editor 2 / nonbox 9 / placeholder 12`）。
- [ ] **腿⑥ 判据（纯函数，四条）**：① 盘上 ⊆ 登记簿；② 登记簿 ⊆ 盘上；③ `placeholder` ⟺ 取值含
      `transparent`；④ 类别表形状（登记项的类别必须在表里、每类至少一条）。
      判据写成纯函数（可内存注入），照本文件 `scopeTableProblems` / `actionWeightProblems` 的既有形状。
- [ ] **合成红证**（照文件末尾那条既有自检的形状，锚点取自真实源码并断言锚点还在）：
      塞一条未登记的新框 → 判红；改一个已登记的选择器名 → 判红；删一条已登记的规则 → 判红；
      把一条 `placeholder` 的取值改成可见 → 判红；塞未知类别 / 掏空一个类别 → 判红；
      **复原后逐条转绿**。用例名里的腿数随本单更新。
- [ ] **读数复算**：`.scratch/border-guard/` 下的探针能从**守卫源码**解析出登记簿与类别表
      （单源，不另抄一份；格式变化大声失败），报双向差 / 每类条数 / 口径分列
      （115 = 94 可见框 + 21 非框）＋一条"悬停态框"的脚注读数；读数落盘，
      时间戳晚于最后一次改产品面。
- [ ] **产品面零改动的机器证明**：`scope_lib.full_borders` 在本单前后报**同一个 115**，
      `git status src/contest_generator/static` 为 **0 行**。
- [ ] **门禁**：前端门禁（`node --test "tests/js/*.test.mjs"`）全绿且**比本单前多出本单的用例**；
      定向 pytest（`tests/test_repo_language.py` / `tests/test_ps1_encoding.py` 这类结构守卫）不红。
- [ ] **双轴评审**（`code-review`：Standards + Spec 并行）跑过，发现逐条处置并在票尾记账。

## 备注

- 口径锚 = `.scratch/ui-density-sitewide/scope_lib.py` 的 `full_borders`（**判据一字不动**）；
  本单的新入口站在它上面（只加"剥注释 + 归类别人"这一步）。
- 类别是**人判后写进数据**的，守卫**不重推类别**——"这是语义告示还是内层框"机器判不了（spec 明写）。
- 类别的判定出处 = 上一轮 spec 的例外 ①–⑥ 与七张工单的逐层清单；票尾要写清核对方式。

## 结论（形状 / 读数 / 门禁 / 评审处置 / 账）

### 形状

- `tests/js/css-tokens.test.mjs` 新增两张单源表：`BORDER_KINDS`（10 类，每类一句判据）+
  `BORDER_REGISTER`（115 条 `[作用域, 剥注释的选择器, 类别]`，按作用域分组）。
- 新增判据纯函数 `fullBorderEntries()`（盘上侧，`full_borders` 的跨语言镜像）与
  `borderRegisterProblems()`（腿⑥ 四条：盘上 ⊆ 登记簿 / 登记簿 ⊆ 盘上 /
  `placeholder` ⟺ 含 `transparent` / 类别表形状）+ 一条腿⑥ 用例 + 合成红证。
- `scope_lib.py` **只加不改**：`full_borders` 判据本体一字未动（diff 只多 4 行 docstring），
  新入口全部追加在后（`strip_lead_comments` / `full_border_entries` /
  `load_border_kinds` / `load_border_register`）。
- 新增结构守卫 `tests/test_border_register_mirror.py`：钉住 JS ↔ Python 那**四块口径**
  （`DEAD_BORDER` / 整圈完整框正则 / transparent 正则 / 剥注释正则）。
- **产品面零改动**：`git status --porcelain src/contest_generator/static` = **0 行**。

### 读数（全部落盘在 `.scratch/border-guard/`，时间戳晚于最后一次改产品面/工具）

| 面 | 读数 | 出处 |
|---|---|---|
| 盘上整圈完整框 | **115**（与 08 账逐字相同） | `probe-00-borders.txt` / `probe-03-register.txt` |
| 登记簿 ↔ 盘上双向差 | **0 / 0** | `probe-03-register.txt` |
| 类别分布 | block 4 / control 37 / tag 15 / alert 19 / modal 8 / float 3 / doc 6 / editor 2 / nonbox 9 / placeholder 12 | 同上 |
| **口径分列** | 115 = **94 可见框** + **21 非框**（12 placeholder + 9 nonbox） | 同上 |
| 非框里状态态会上色的 | **10 / 21**（全是 placeholder；nonbox 9 条 0 条） | 同上（脚注） |
| 解析口径对账（整文件 vs `<style>`） | 规则 1607 vs 1593，**描边这一面逐条相同** | `probe-02-caliber-styleblock.txt` |
| 上一轮那三支探针 | 14 个作用域 **0/0**、页面尺 **0 条**、`fullBoxes` **115**（不退化） | `after-01-probe-04.txt` |

### 门禁（浏览器门禁本单不需要——产品面零改动）

| 门禁 | 读数 |
|---|---|
| 前端门禁 | **1841 / 0**（起点 1840，+1 = 腿⑥ 用例） |
| 全量 pytest | **5663 passed + 11 skipped**（起点 5659，+4 = 跨语言镜像守卫） |
| 反证：镜像守卫 | 4 处注入**全红**、复原 sha256 逐字节相同、复跑绿（`probe-05-mirror-red.py`） |
| 反证：`generate-01 --check` | 2 处注入**全红**、复原逐字节相同（`probe-06-generator-check-red.py`） |

### 双轴评审（`code-review`：Standards + Spec 并行）的发现与处置

两轴各审一遍，**两轴都真跑过**（Standards 自己跑了前端门禁与产品面核对，Spec 自己在盘上
复算了 115 / 十类分布 / 双向差 / 分组顺序，结论与票面一致）。逐条处置：

| # | 发现 | 处置 |
|---|---|---|
| Std-1 / Spec-⑤ | `after-01-pytest.txt` 正文是 `No module named pytest`（退出 1）却当读数落盘——**本机 `.venv` 里没有 pytest**，系统 `python` 才有（9.1.1） | ✅ 用 `python -m pytest` 重跑，**5663 passed + 11 skipped**；这条本机事实记进本票与 `local-environment` |
| Std-2 / Spec-⑤ | `after-01-probe-04.txt` 承载数字那几行乱码（`readings.py` 按 UTF-8 解码，而 probe-04 没 `reconfigure`，控制台是 GBK） | ✅ 按 sitewide README 的复跑配方加 `PYTHONIOENCODING=utf-8` 重跑，读数可读 |
| Std-3 | 守卫两处注释写"前导注释 200 字"，实测 `.card-step-status` 是 **35** 字符 | ✅ 按脚本复算改成**最长 465 字符**那个真例子（纪律 3：注释里的数按脚本复算） |
| Std-4 | `probe-03` 自己拼 `index.html` 路径 + `read_text`，绕开 `scope_lib.PAGE` / `read_page` | ✅ 改走 `read_page()`（公共件从口径模块 import） |
| Std-5 / Spec-⑤ | 票状态一直 `ready-for-agent`，没 claim | ✅ 先 claim 再收口（Step 4.1） |
| Std-6 | 三对跨语言镜像只靠注释承诺"逐字相同"，无对拍守卫（CONTEXT 有 mirror 守卫先例） | ✅ 新增 `tests/test_border_register_mirror.py`（4 条）+ **反证探针** `probe-05-mirror-red.py` |
| Std-6 | `register-block.js.txt` + `generate-01` 的 `KIND` 是那张表的第二三份副本，无东西钉住 | ✅ 给两者加"已消费的一次性产物、真源是守卫"的显著说明；`generate-01` 加 **`--check`**（复核生成关系）+ 反证探针 `probe-06` |
| Std-7 / Spec-② | **判据的洞**：`onDisk` 是 `Map`，同一 `(作用域, 选择器)` 再来一条带框规则会被折叠，①②两条对账都判不出；而条数断言的失败文案却称"双向对账本该报出"（不实） | ✅ 盘上侧改成**多重集**并显式报"不止一条整圈完整框声明"；条数断言的文案改准；补 (g) 红证 |
| Std-8 | `probe-01` 的 `re.compile(r".")` 占位规则 + `classify()` 特判；`apply-01` 的 `count('],') - 0` 且把 125 印成"登记项" | ✅ `probe-01` **连同读数一起删掉**（它是被登记簿取代的第二份分类实现，留着只会被误读）；`apply-01` 的打印改成按 `["` 行数真数 |
| Std-9 | `scope_lib` 用法 docstring 没补本轮四个新入口 | ✅ 已补 |
| **Spec-②** | **红证 6 条里 2 条不是真注入**：(a)"塞新框"其实只改了选择器名（与 (b) 同机制）、(c)"删规则"其实只往表里塞了一条 | ✅ 重写成真注入：(a) 往**原本没框**的 `.gen-recent-head` 里真加一条 `border:`（断言盘上侧 115→116）；(c) 真把 `.env-jump` 那条规则从盘上删掉（断言 115→114）；另补 (c2)(f)(g) 三类分支红证 |
| **Spec-④** | **两处类别贴错**：`.gen-recent` 是不可点的 `<div>` 却贴 `control`；`.code-view::-webkit-scrollbar-thumb`（透明）被不变量逼成 `placeholder`，而 `nonbox` 的判据明写"滚动条 thumb" | ✅ `.gen-recent` 改 `block`（分布随之 control 38→37、block 3→4）；滚动条那条**按不变量留着 `placeholder`**，但把 `placeholder` 的判据措辞补上"要么是给悬停/选中态留的位置，要么是浏览器 chrome 的透明声明"，并在登记簿说明块里点名"这两条容易贴错、已经核过" |
| Spec-⑤ | 脚注只扫了 12 条 `placeholder`，spec 写的是"21 处非框" | ✅ 扫描面铺到全部 21 条（结论不变：10/21，nonbox 9 条 0 条） |

### 账（留给下一轮）

1. **本机 `.venv` 里没有 pytest**：跑门禁要用系统 `python`（有 pytest 9.1.1），
   `.venv\Scripts\python.exe` 是**应用运行时**（只有 fastapi/pymupdf 那几件）。
   这条已写进 `local-environment`——**下次别再拿 `.venv` 跑 pytest**（会得到一份"退出码 1
   但没有失败用例"的假读数）。
2. **`probe-01`（分类草稿）已删**：它当时回答的是"115 能不能按类判"（答：能，但类别只能人判），
   结论已落在守卫的 `BORDER_KINDS` + 登记簿里。留着它就是**第二份分类实现**（双轴评审 ⑥/⑧ 点名）。
3. **`.code-view::-webkit-scrollbar-thumb` 的类别是"不变量优先"的结果**：它既是滚动条（像 `nonbox`）
   又是透明声明（是不变量管的 `placeholder`）。本轮选了不变量，理由写在登记簿说明块里；
   **要改的判据是那条不变量本身**（`placeholder` ⟺ 含 `transparent`），不是这一条登记项。
4. **`register-block.js.txt` 与 `apply-01-register.py` 里那两段文本是评审整改前的快照**，
   与守卫**不再逐字相同**（都已在文件头显著标注）。复核走 `probe-03`（从守卫读）或
   `generate-01 --check`（复核生成关系）。
5. **口径边界（明写）**：`border-color` 单声明与悬停/选中态才出现的框**不在射程内**
   （不是"完整框"）——本轮量到非框 21 条里 10 条有状态上色，那是"一屏一层"的合法逃逸。
