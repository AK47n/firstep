# 03 — 想法商量写加固：模型调用那几秒里别人的改动不许丢

**要做什么：** 学生发起一轮"全局商量"（等几秒），期间在另一处采纳一条全局结论；
商量结束后**采纳的结论与这轮对话都在**。参数商量是另一份文件，两份记录各自独立、不共锁。

**被谁阻塞：** 01（共享原语）。

**状态：** ready-for-agent

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

- [ ] `idea_chat.py` 新增 `update_idea_chat(output_dir, merge, filename=IDEA_CHAT_FILENAME) -> IdeaChat`
      （锁 + 重读 + 合并 + 落盘）；`write_idea_chat` 内部改走 `atomic_io.atomic_write_text`
      （字节格式逐字不动）。
- [ ] **合并语义定案 = 在新读到的记录上追加**（不是 `hwcheck-hygiene/03` 的"base 变了就不写"）：
      聊天是**追加型日志**，追加重放能同时保住两笔；理由写进代码 docstring 与本票结论段。
      → 两条 send 都改成：LLM 调用在锁外 → `update_idea_chat(..., lambda latest: append(latest, user, reply))`。
- [ ] adopt 端点改走 `update_idea_chat`（merge = `set_chat_note`）。
- [ ] **锁按文件区分**：两份历史的写不共锁（`path_lock` 键含文件名，见工单 01 的判据）——
      加一条用例：两份文件并发写，互不阻塞、各自内容正确。
- [ ] 域层用例（`tests/test_idea_chat.py`）：① 原子写无残渣；② 写失败无残渣 + 原异常；
      ③ 并发写不互抢；④ **跨慢窗口合并**：模型调用期间别人采纳结论 → 商量结束后
      **新 note 与本轮两条消息都在**（这条是本单的主判据）；⑤ 两份文件名互不共锁。
- [ ] 端点级用例（`tests/test_task_progress.py`，家 = 既有 `test_tasks_idea_chat_send_read_adopt_flow:3102`
      附近）：send 与 adopt 并发，判据取**最终落盘**（note + messages 都在）；撤锁注入下实测变红。
- [ ] 反证探针 `.scratch/record-write-hardening/probe-03-red.py`（逐条声明 + 对账）。
- [ ] 读数落盘：定向 + 全量 `.txt`。

## 备注

- **别把模型调用放进临界区**：那会把"学生填一条"的写按住一整个模型调用
  （`hwcheck-hygiene/03` 的评审记过这条，见 `hwcheck_triage.py:416-419`）。
- `_read_global_note` 是只读路径，本单不动它；它的读语义（`read_idea_chat` 单源）保持不变。
