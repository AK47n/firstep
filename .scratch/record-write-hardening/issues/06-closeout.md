# 06 — 收口：结构守卫 + 反证汇总 + 台账翻牌

**要做什么：** 这一批做完后，让"全仓只有一个原子写实现"这件事**被机器盯住**，
把四条反证读数与全量闸门读数落盘，并把 `backlog.md` §24 翻牌——**连同"还有哪些站点没修"一起写清楚**。

**被谁阻塞：** 02、03、04、05。

**状态：** ready-for-agent

## 验收标准

- [ ] **结构守卫**（新用例，家可选 `tests/test_atomic_io.py` 或既有结构测试文件）：
      扫 `src/contest_generator/**.py` 里的原子写站点（`os.replace(` / `Path.replace(` 形态），
      要求每一处要么**调用共享原语**、要么在**白名单**里且**逐条带中文理由**
      （形状照 `tests/test_library_invariants.py::SINGLE_PLATFORM_REASONS` 的先例）。
      白名单初始条目与理由：
      `codeview.py`（pid 后缀 + 清理，编辑保存路径带 mtime 冲突检查）、
      `recent_jobs.py`（`tempfile.mkstemp` 唯一名 + 清理）、
      `hwcheck_triage.py`（本批原语的来源，已是正确实现）、
      `materials_apply.py`（解包被更新任务锁串行化）、
      `master_store.py` 的**目录**换入（`os.replace(target_dir, …)`，不是文件写）。
      守卫要能抓住"新写的记录文件又手搓一个固定临时名"（**加一条正向对照**：临时塞一个反例文件进去 → 红）。
- [ ] **反证汇总**：四张单的 `probe-0X-red.py` 读数汇总成一份
      `.scratch/record-write-hardening/probe-06-red-summary.txt`，每条**逐条声明 + 与实得 `FAILED` 对账**
      （多出来的红如实打印，不据此判 PASS）；每条都要有"复原后回绿"的读数。
- [ ] **台账翻牌**：`backlog.md` §24 标 ✅ 已收口，并**如实列出未修的站点**
      （`materials_apply._extract_zip`、`entry_store.write_json` 的裸写、跨进程并发、强杀残留清扫），
      附一句"下次复核按直接读盘核对的模式，不信本节旧标记"——§23 那个坑（修完没人回改标记）不许重演。
- [ ] **读数落盘**：全量 `python -m pytest -n auto -q` 一份 `.txt`；
      并写明"落点不在 `static/` 或 `tests/js/`，故未跑前端 / 浏览器门禁"（或如实说明为何跑了）。
- [ ] **边界记账**（写进 spec 或本票结论段）：跨进程并发不在射程（单进程应用）、
      锁表只增不减、强杀残留不扫——三条都要有落脚处，别只留在会话里。
- [ ] `docs/agents/local-environment.md`：若本批改变了"这台机器 + 此刻"的任何事实
      （端口 / 沙箱 / 发版落差），当场回改；没有则不动（别为凑数改文件）。

## 备注

- 这一批**不改用户可见文案**，故预期 CHANGELOG 只有"内部加固"类条目（提交信息照实写中文即可）。
- 收口时顺手核一眼：四处的错误文案与 JSON 字节格式有没有被顺手改掉
  （spec 的「不变量」段列了三条，逐条核）。
