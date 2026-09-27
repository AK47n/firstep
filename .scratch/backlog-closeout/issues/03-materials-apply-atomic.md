# 03 — 资料库解包走共享原语：不留 `.update-tmp`、不互抢固定临时名

**要做什么：** 学生/维护者更新电赛资料库时，解包**失败不在库里留 `.update-tmp` 残渣**，
两个写者也不互抢同一个固定临时名；全仓"手搓原子写"的站点再少一处。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

## 现状（实测，带 file:line）

- `src/contest_generator/materials_apply.py:103-106`（`_extract_zip`）：
  `tmp = target.with_name(target.name + ".update-tmp")` → 流式写入 → `os.replace(tmp, target)`。
  **固定临时名、无锁、无 `finally`**：两个写者抢同一个临时名；写失败/中断留下 `.update-tmp`。
- 它是 `record-write-hardening` spec 明确"没修"的站点（理由：解包被更新任务锁串行化、风险低一档）。
- **原语现状**：`src/contest_generator/atomic_io.py` 只有 `atomic_write_text`（写字符串）——
  解包写的是**字节流**（`shutil.copyfileobj`，资料库里有大文件，**不能改成先读进内存**），
  所以要给原语加一个"写字节 / 交给回调写"的入口。
- 结构守卫（`tests/test_atomic_io.py::test_only_one_atomic_write_implementation_in_src`）的例外清单里
  `materials_apply.py` 记着 **2 个站点**（造临时名 + 换入）——本单做完它归零，
  **按棘轮必须把那一条删掉**（守卫会点名"清单发霉"）。

## 验收标准

- [ ] `atomic_io.py` 新增**字节/流式**入口（签名与语义写进 docstring），与 `atomic_write_text`
      共用同一份"临时名 + 换入 + `finally` 清残渣"实现（抽内部函数，**不复制第二份**）；
      既有 `atomic_write_text` 行为与字节格式**一字不变**（既有 7 条判据全绿）。
- [ ] `materials_apply._extract_zip` 改走新入口：**仍是流式**（不吃内存）、仍是唯一临时名、
      失败/中断不留残渣、原异常照抛。
- [ ] 域层用例（`tests/test_materials_update*.py` 或 `tests/test_atomic_io.py` 的既有家）：
      ① 解包成功后没有 `.update-tmp` / 任何杂散文件；② 注入写失败 → 无残渣 + 原异常照抛；
      ③ 并发解包不互抢（确定性做法照 `tests/test_atomic_io.py` 的 `SimpleNamespace` + `Event` 那套）。
- [ ] 结构守卫例外清单删掉 `materials_apply.py` 那条；`python -m pytest tests/test_atomic_io.py -q` 绿。
- [ ] 反证探针 `.scratch/backlog-closeout/probe-03-red.py`：撤唯一临时名 / 撤清残渣 → 对应判据红；
      逐条声明 + 与实得 `FAILED` 对账 + 复原 sha256 逐字节。
- [ ] 读数落盘：定向 + 全量 `python -m pytest -n auto -q`。

## 备注

- 解包是**发版/更新链路**的一环：既有 `tests/test_materials_update*.py` 与
  `tests/test_full_update*.py` 是行为守卫，动它要连带跑（尤其"逐条目覆盖 + 备份 + 回滚"三条路径）。
- 与 `record-write-hardening` 的分工：那一批把**记录写**收口了；本单补的是**同一族里唯一的字节写**站点。
