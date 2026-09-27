# 02 — 想法草稿写加固：两个入口同时增/删，两笔都在

**要做什么：** 学生在两个标签页同时加草稿、删草稿，**两笔改动都留住**，
工程根不留 `.contest_ideas.json.tmp`。

**被谁阻塞：** 01（共享原语）。

**状态：** ready-for-agent

## 现状（实测，带 file:line）

- 写实现：`src/contest_generator/drafts.py:114-124`——`tmp = path.with_name(path.name + ".tmp")`
  → `tmp.replace(path)`，**固定临时名、无锁、无 try/finally**（写失败留残渣）。
- 读-改-写窗口（调用方全在 `webapp.py`，中间只夹纯函数，**微秒级**）：
  `POST /api/tasks/idea/drafts/add`（`webapp.py:4919`）读 `4934` → 写 `4935`；
  `POST /api/tasks/idea/drafts/delete`（`:4938`）读 `4952` → 写 `4953`。
- 既有测试：`tests/test_drafts.py:47` 有一条**成功路径**的残渣断言；
  无并发用例、无"写失败留残渣"用例。

## 验收标准

- [ ] `drafts.py` 新增 `update_drafts(output_dir, merge: Callable[[IdeaDrafts], IdeaDrafts]) -> IdeaDrafts`
      （锁 + 重读 + 合并 + 落盘，照 `hwcheck_triage.py:409-425` 的形状），
      `write_drafts` 内部改走 `atomic_io.atomic_write_text`（字节格式**逐字不动**：`ensure_ascii=False`、
      `indent=2`、尾换行）。
- [ ] 两个端点改走 `update_drafts`，merge 复用既有纯函数 `add_draft` / `delete_draft`
      （**去重语义不许变**：同文本仍只存一条，`drafts.py:131` 的既有契约）。
- [ ] 域层用例（`tests/test_drafts.py`，形状照 `tests/test_hwcheck_triage.py:554-685`）：
      ① 原子写后目录里除记录文件外**一个文件都没有**（`iterdir` 断言）；
      ② 注入写失败 → 无残渣 + 原异常照抛；
      ③ 并发写不互抢、不报错、不留残渣；
      ④ **交错不丢**：A 卡在自己的合并里、B 增一条 → 两条都在（这条是本单的主判据）。
- [ ] 端点级用例（`tests/test_webapp.py`，家 = 既有草稿端点测试附近）：两个请求并发，
      判据取**最终落盘**（不取响应体）；并在「撤掉 `update_drafts` 里的锁」注入下实测**变红**。
- [ ] 反证探针 `.scratch/record-write-hardening/probe-02-red.py`：逐条声明哪些用例必须红，
      与实得 `FAILED` 集合对账（多出来的红如实打印，不据此判 PASS）。
- [ ] 读数落盘：定向 + 全量 `python -m pytest -n auto -q` 各一份 `.txt`。

## 备注

- 本单窗口没有慢操作，加锁买的是"两个入口交错"这条（用户双击/双标签页很常见）；
  真正横跨秒级的同类病在工单 03。
