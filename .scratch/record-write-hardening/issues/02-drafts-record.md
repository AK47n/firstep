# 02 — 想法草稿写加固：两个入口同时增/删，两笔都在

**要做什么：** 学生在两个标签页同时加草稿、删草稿，**两笔改动都留住**，
工程根不留 `.contest_ideas.json.tmp`。

**被谁阻塞：** 01（共享原语）。

**状态：** resolved（2026-09-27；读数、双轴评审处置见文末）

## 现状（实测，带 file:line）

- 写实现：`src/contest_generator/drafts.py:114-124`——`tmp = path.with_name(path.name + ".tmp")`
  → `tmp.replace(path)`，**固定临时名、无锁、无 try/finally**（写失败留残渣）。
- 读-改-写窗口（调用方全在 `webapp.py`，中间只夹纯函数，**微秒级**）：
  `POST /api/tasks/idea/drafts/add`（`webapp.py:4919`）读 `4934` → 写 `4935`；
  `POST /api/tasks/idea/drafts/delete`（`:4938`）读 `4952` → 写 `4953`。
- 既有测试：`tests/test_drafts.py:47` 有一条**成功路径**的残渣断言；
  无并发用例、无"写失败留残渣"用例。

## 验收标准

- [x] `drafts.py` 新增 `update_drafts(output_dir, merge: Callable[[IdeaDrafts], IdeaDrafts]) -> IdeaDrafts`
      （锁 + 重读 + 合并 + 落盘，照 `hwcheck_triage.py:409-425` 的形状），
      `write_drafts` 内部改走 `atomic_io.atomic_write_text`（字节格式**逐字不动**：`ensure_ascii=False`、
      `indent=2`、尾换行）。
- [x] 两个端点改走 `update_drafts`，merge 复用既有纯函数 `add_draft` / `delete_draft`
      （**去重语义不许变**：同文本仍只存一条，`drafts.py:131` 的既有契约）。
- [x] 域层用例（`tests/test_drafts.py`，形状照 `tests/test_hwcheck_triage.py:554-685`）：
      ① 原子写后目录里除记录文件外**一个文件都没有**（`iterdir` 断言）；
      ② 注入写失败 → 无残渣 + 原异常照抛（哨兵异常同一性断言）；
      ③ 并发写不互抢、不报错、不留残渣；
      ④ **交错不丢**：A 卡在自己的合并里，B 增一条 / B 删一条 → 两笔都在（本单的主判据，两条）。
- [x] 端点级用例：两个请求并发，判据取**最终落盘**（不取响应体）；并在「撤掉 `update_drafts`
      里的锁」注入下实测**变红**（探针 A 段的声明里含它，实得红）。
      **落点更正**：票里写的家是 `tests/test_webapp.py`，但**既有草稿端点用例**在
      `tests/test_drafts.py`（`test_drafts_endpoints_flow`）——照 spec「家 = 既有端点测试文件」
      放在那里，`tests/test_webapp.py` 里确无草稿端点用例。
- [x] 反证探针 `.scratch/record-write-hardening/probe-02-red.py`：逐条声明哪些用例必须红，
      与实得 `FAILED` 集合对账（多出来的红如实打印，不据此判 PASS）。
- [x] 读数落盘：定向 + 全量 `python -m pytest -n auto -q` 各一份 `.txt`（走
      `.scratch/hwcheck-hygiene/readings.py`，UTF-8、带命令 / 时间 / 退出码头）。

## 结论（读数、评审处置、账）

**形状。** `write_drafts` 的落盘改走 `atomic_io.atomic_write_text`（唯一临时名 + `finally` 清残渣）；
新增 `update_drafts`（`path_lock` + 重读 + 合并 + 落盘，形状照 `hwcheck_triage.py:409-425`）；
`webapp.py` 的 add / delete 两个端点改走它，merge 复用既有纯函数（**去重语义不动**）。
**不变量核对**：读侧中文错误文案未动；JSON 字节格式**逐字节相同**——实测同一条草稿分别走
收走前的固定临时名实现与本单实现，落盘字节 `b'{...\r\n}\r\n'` 完全一致（缩进 / `ensure_ascii` /
尾换行 / 文本模式写出的 `\r\n` 都没变）。

**读数（本机实跑，全部 UTF-8 落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 定向 pytest | `python -m pytest tests/test_drafts.py -q` | **15 passed**（收走前 9 条） | `probe-02-tests.txt` |
| 反证（三段） | `python .scratch/record-write-hardening/probe-02-red.py` | **PASS**：A 撤临界区 → 交错增 / 交错删 / 端点并发三条红；B 撤共享原语（唯一临时名 → 固定名、`finally` → `pass`）→ 并发与"写失败留残渣"两条红；C 端点退回旧形状 → 端点并发红。逐条声明与实得 `FAILED` 对账、每段复原 sha256 逐字节相同、复原后 15 passed | `probe-02-red.txt` |
| 全量 pytest | `python -m pytest -n auto -q` | **5617 passed + 11 skipped / 88.16s**（收走前基线 5611 + 11） | `probe-02-pytest.txt` |

**双轴评审（2026-09-27，`code-review` 跑在工作树 vs 固定点 `e5121a13`）与处置。**

| 轴 | 发现 | 处置 |
|---|---|---|
| Spec ① / Standards ① | 读数没绑当前字节（判据文件在三条读数之后又改过） | **属实，已修**：判据冻结后三条读数**全部重跑**（上表即重跑后的读数，`probe-02-red.txt` 头部记的判据 sha256 与盘上一致） |
| Spec ② / Standards ⑤ | 票里写端点用例的家是 `tests/test_webapp.py`，实际在 `tests/test_drafts.py` | **属实**：既有草稿端点用例本就在 `tests/test_drafts.py`（spec「家 = 既有端点测试文件」）——票面「验收标准」已就地更正，代码不动 |
| Spec ③ | spec 故事 1 是"一页加、一页删"，只测了 add + add（半条） | **属实，已修**：补 `test_update_drafts_does_not_lose_a_concurrent_delete`（"删了的那条又回来了"），并进探针 A 段的声明 |
| Spec ④(c)① | `update_drafts` docstring 抄了 triage 的"别人改过的字段原样带过去"——add / delete 是**整集重建**，没有字段级合带 | **属实，已修**：改成"并发的另一笔已经落盘的改动会被读到、一起带进合并结果，不会被旧快照盖回去" |
| Standards ② | **反证没打在 bug 机制上**：B 段撤的是 `drafts.py` 的调用，而判据的注入点是 `atomic_io.os` → 两条红一条是"压根没抛异常"、一条是 30 秒等待自爆（读数 31.53s），与"抢临时名"无关 | **属实，已修**：B 段改为撤在**原语所在的模块**里（`atomic_io.py`：唯一临时名 → 固定名、清残渣 → `pass`）→ 两条都是机制红（该段 1.55s，真断言失败） |
| Standards ③ | docstring 把**计划**写成**现状**：`update_idea_chat` 本单还不存在（`idea_chat.py` 只有 read / write / append / set_note） | **属实，已修**：改成"工单 03 要建的 `update_idea_chat`，本单尚未存在" |
| Standards ④（判断项） | Duplicated Code：残渣断言 5 种写法、并发脚手架三份 | **部分采纳**：抽了 `_residue()` / `_run_in_thread()` 两个本地小工具收掉重复（形状照 `tests/test_atomic_io.py:29`）；三段并发脚手架各自注入点不同、且是 spec 点名的形状，保留显式写法 |
| 备注（前一批的坑） | `hwcheck-hygiene/03` 被评审抓过"端点用例撤锁照样绿 = 测不出锁" | **已满足**：端点用例在探针 A 段（撤锁）下**实测红** |

**两条留下的记账：**

1. `drafts.py` 哪天若不再走共享原语，域层用例**仍会红**（注入点不被走到 → 没抛异常 / 等待超时），
   但那是"没测到机制"的红；**静态守卫在工单 06**（扫 `os.replace(` / `Path.replace(` 站点 + 白名单）。
2. 端点用例的确定性依赖端点函数体内 `from .drafts import add_draft` 的**调用时导入**
   （若哪天把导入上提到模块层，注入会失效——那种情况下用例会红，不会静默）。

## 备注

- 本单窗口没有慢操作，加锁买的是"两个入口交错"这条（用户双击/双标签页很常见）；
  真正横跨秒级的同类病在工单 03。
