# 03 — 想法商量写加固：模型调用那几秒里别人的改动不许丢

**要做什么：** 学生发起一轮"全局商量"（等几秒），期间在另一处采纳一条全局结论；
商量结束后**采纳的结论与这轮对话都在**。参数商量是另一份文件，两份记录各自独立、不共锁。

**被谁阻塞：** 01（共享原语）。

**状态：** resolved（2026-09-27；读数、双轴评审处置见文末）

## 现状（实测，带 file:line）

- 写实现：`src/contest_generator/idea_chat.py:164-174`——`path.with_name(filename + ".tmp")`
  → `tmp.replace(path)`，**固定临时名、无锁、无 try/finally**。
- 两个文件共用一套读写：`.contest_idea_chat.json` = `IDEA_CHAT_FILENAME`（`:36`）、
  `.contest_params_chat.json` = `PARAMS_CHAT_FILENAME`（`:40`）。
- 三条读-改-写路径（全在 `webapp.py`）：
  1. `POST /api/tasks/idea/chat/send`（`:4629`）：读 `4671` → **LLM `discuss_global_idea` 4676-4686（慢）**
     → append `4690-4691` → 写 `4692`；
  2. `POST /api/params/chat/send`（`:4362`）：读 `4398` → **LLM `discuss_params` 4403-4408（慢）**
     → append `4412-4413` → 写 `4414`（另一份文件）；
  3. `POST /api/tasks/idea/chat/adopt`（`:4695`）：读 `4712` → `set_chat_note`（纯函数）`4713` → 写 `4714`（无慢操作）。
- 后果（代码事实）：两个 send 并发 → 后写那份整份盖掉先写那笔的 messages；
  send 与 adopt 并发 → send 手上是 `4671` 的老 note，`4692` 整份写回会盖掉 adopt 在 `4714` 写的新 note。
- 只读不写（**不改**）：`/chat/read`（`4612-4627`）、`/api/params/chat/read`（`4346-4360`）、
  `_read_global_note`（`:1439-1446`，被任务执行/直接修正两条 SSE 长路径调用，但只读 note）。

## 验收标准

- [x] `idea_chat.py` 新增 `update_idea_chat(output_dir, merge, filename=IDEA_CHAT_FILENAME) -> IdeaChat`
      （锁 + 重读 + 合并 + 落盘）；`write_idea_chat` 内部改走 `atomic_io.atomic_write_text`
      （字节格式逐字不动）。
- [x] **合并语义定案 = 在新读到的记录上追加**（不是 `hwcheck-hygiene/03` 的"base 变了就不写"）：
      聊天是**追加型日志**，追加重放能同时保住两笔；理由写进代码 docstring 与本票结论段。
      → 两条 send 都改成：LLM 调用在锁外 → `update_idea_chat(..., lambda latest: append(latest, user, reply))`。
- [x] adopt 端点改走 `update_idea_chat`（merge = `set_chat_note`）。
- [x] **锁按文件区分**：两份历史的写不共锁（`path_lock` 键含文件名，见工单 01 的判据）——
      加一条用例：两份文件并发写，互不阻塞、各自内容正确。
- [x] 域层用例（`tests/test_idea_chat.py`）：① 原子写无残渣；② 写失败无残渣 + 原异常；
      ③ 并发写不互抢；④ **跨慢窗口合并**：模型调用期间别人采纳结论 → 商量结束后
      **新 note 与本轮两条消息都在**（这条是本单的主判据）；⑤ 两份文件名互不共锁。
- [x] 端点级用例（`tests/test_task_progress.py`，家 = 既有 `test_tasks_idea_chat_send_read_adopt_flow:3102`
      附近）：send 与 adopt 并发，判据取**最终落盘**（note + messages 都在）；撤锁注入下实测变红。
      **两条**：慢窗口那条（模型调用期间采纳）+ 串行那条（卡在合并里，撤锁必须红）。
- [x] 反证探针 `.scratch/record-write-hardening/probe-03-red.py`（逐条声明 + 对账；**五段**）。
- [x] 读数落盘：定向 + 全量 `.txt`。

## 结论（读数、评审处置、账）

**形状。** `write_idea_chat` 的落盘改走 `atomic_io.atomic_write_text`（唯一临时名 + `finally` 清残渣）；
新增 `update_idea_chat`（`path_lock` + 重读 + 合并 + 落盘，键**含文件名** → 两份历史各拿一把锁）；
两个 send 端点改成"**模型调用留在锁外** → `update_idea_chat(..., 追加本轮两条)`"，
adopt 改成 `update_idea_chat(..., set_chat_note)`；两个 send 的"一轮 = 两条"提到域层
`append_chat_round`（初审的重复代码发现，见下）。

**合并语义为什么是"追加"而不是"base 变了就不写"**：聊天是**追加型日志**——两条商量并发时，
后来者若因为"base 变了"整轮不写，学生这一轮问答就白问了；追加重放（在新读到的记录上再追加
自己这两条）能同时保住两笔。adopt 只碰 note，重读后覆盖同理。理由同写在
`idea_chat.update_idea_chat` 的 docstring 里。

**不变量核对**：读侧中文错误文案未动；`_read_global_note` 与其余只读路径未动；
JSON 字节格式**逐字节相同**——实测同一份聊天分别走收走前的固定临时名实现与本单实现，
落盘字节完全一致（`…"note": ""\r\n}`，**无尾换行**，文本模式写出的 `\r\n` 照旧）；
参数商量那条 send 保留了 LLM 调用**之前**的预读（坏记录仍在读侧 400，不先烧一次模型调用）。

**读数（本机实跑，全部 UTF-8 落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 定向 pytest | `python -m pytest tests/test_idea_chat.py tests/test_task_progress.py -q` | **114 passed** | `probe-03-tests.txt` |
| 反证（五段） | `python .scratch/record-write-hardening/probe-03-red.py` | **PASS**：A 撤临界区 → 跨慢窗口 + 端点串行两条红；B 锁键去掉文件名 → "两份历史不共锁"红；C 端点退回旧形状 → 两条端点判据红；D 重读挪到锁外 → 跨慢窗口 + 端点串行两条红；E 撤共享原语（唯一临时名 → 固定名、`finally` → `pass`）→ 写失败留残渣 + 并发抢临时名两条红。逐条声明与实得 `FAILED` 完全一致、每段复原 sha256 逐字节相同、复原后 114 passed | `probe-03-red.txt` |
| 全量 pytest | `python -m pytest -n auto -q` | **5624 passed + 11 skipped / 102.67s**（上一单基线 5617 + 11 → 本单 +7 条用例） | `probe-03-pytest.txt` |

**双轴评审（2026-09-27，`code-review` 跑在工作树 vs 固定点 `44f9e6fe`）与处置。**

| 轴 | 发现 | 处置 |
|---|---|---|
| Spec ① | 票未翻牌、勾选框全空、无结论段（docstring 有理由、票里没有） | **属实**：本段即补齐（翻 `resolved` + 勾选 + 读数表） |
| Spec ② | 探针缺"撤掉 `write_idea_chat` 原语迁移"那一段 → 域层 ②③ 没有撤修读数；① 在旧实现下本来就绿（守卫，无鉴别力，**不许**声明必须红） | **属实，已修**：补 **E 段**（撤在 `atomic_io.py` 里，保住判据的 `os.replace` 注入缝）→ ②③ 两条机制红；① 如实不声明 |
| Spec ③ | "两个 send 并发 → 后写互盖"没有独立判据 | **记账不补**：同一机制（重读 + 追加）由"跨慢窗口合并"与端点串行那两条盖住，不另立用例 |
| Spec (b) | `write_idea_chat` docstring「本文件没有尾换行」与 spec:55「三个记录文件有尾换行」打架 | **实现正确、上位文案有误**（实测这两份聊天记录确实没有尾换行；只有 drafts / params 加 `"\n"`）——见下面「账」第 2 条，工单 06 收口时按实际字节核 |
| Standards ① | 尾换行那句里 `params` 撞名（同一函数写的参数商量文件也没有尾换行，读成 `.contest_params.json` 才自洽）；「字节格式逐字不动」没有读数钉住 | **属实，已修**：docstring 点全名（`.contest_idea_chat.json` / `.contest_params_chat.json`）；本段补实测字节 |
| Standards ② | `drafts.py` 里「工单 03 要建的 `update_idea_chat`，本单尚未存在」——本单已建，反向过期 | **属实，已修**：改成"（`idea_chat.update_idea_chat`，工单 record-write-hardening/03）" |
| Standards ③（判断项） | Duplicated Code：两个 send 的合并 lambda 逐字相同 | **采纳**：提到域层 `append_chat_round(chat, user_content, reply)`——"一轮 = 两条、先 user 后 assistant"只写一处 |
| Standards ④ | 参数商量那条 send 去掉了 LLM 前的预读 → 坏记录从"调用前 400"变成"烧一次模型调用后 400"，与全局那条不再同构 | **属实，已修**：预读改回（带注释说明为什么留着），与新形状并存 |
| Standards ⑤ | 端点用例依赖端点体内 `from … import` 的**调用时导入**这条账没记 | **已记**：见下面「账」第 1 条 |

**账（留给后面的人）：**

1. 本单端点用例的确定性依赖端点函数体内 `from .idea_chat import append_chat_round` 的**调用时导入**
   （若哪天把导入上提到模块层，注入会失效——那种情况下用例会红，不会静默；工单 02 记过同一条）。
2. **spec:55「三个记录文件有尾换行」与实测不符**：`.contest_idea_chat.json` /
   `.contest_params_chat.json` **没有**尾换行（drafts / params 才有）。实现以**实际字节**为准，
   字节未动；工单 06 核"JSON 字节格式"这条不变量时要按四个文件的**各自实际**核，别按那句话核。
3. 两条 send 并发互盖的判据没有单列（同一机制由"跨慢窗口合并"与端点串行两条覆盖）。

## 备注

- **别把模型调用放进临界区**：那会把"学生填一条"的写按住一整个模型调用
  （`hwcheck-hygiene/03` 的评审记过这条，见 `hwcheck_triage.py:416-419`）。
- `_read_global_note` 是只读路径，本单不动它；它的读语义（`read_idea_chat` 单源）保持不变。
