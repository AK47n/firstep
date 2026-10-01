# 02 — 三套门禁（浏览器门禁单独跑）+ 对比度冻结读数 + 全站不退化

**要做什么：** 在**冻结的 revision**（01 之后的树，产品面零改动）上把三套门禁与读数各跑一遍、落盘成证据：
确认"要发的那棵树"没有退化，且本批的冻结数还是原值。

**被谁阻塞：** 01（版本号就位后跑的读数才对应要发的那棵树）。

**状态：** ready-for-agent

- [ ] 前端门禁 `node --test "tests/js/*.test.mjs"` → `js-gate.txt`
- [ ] **浏览器门禁单独跑**（不与**任何** pytest 并行）`node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`
      → `browser-gate.txt`（≈3 分钟）
- [ ] 全量 `python -m pytest -n auto -q` → `pytest.txt`
- [ ] 对比度冻结读数复跑：`contrast-residue/probe-06-register-readings.py`（渲染方登记 **19** 条）、
      `disabled-forms/probe-00-inventory.py`（`opacity` 活规则 **15** / 未在册 **0**）、
      `contrast-residue/probe-09-cant-readings.py`（`li.cant` 整行 浅 5.25 / 暗 5.67）
- [ ] 全站两支老探针不退化：`ui-density-sitewide/probe-00-survey.py`（裸 px 字号 **0**、`--fs-*` **428** 处）、
      `probe-04-scope-calibers.py`（十四个作用域 0/0、页面尺 **0** 条、整圈完整框 **115**）
- [ ] 读数落盘时间戳**晚于**最后一次改产品面（三条纪律第 1 条）
- [ ] 摘要写进票尾；提交信息中文

## 读数落盘怎么跑

```powershell
python .scratch\hwcheck-hygiene\readings.py js-gate --out-dir .scratch\release-v1.4.3 -- node --test "tests/js/*.test.mjs"
```

（别用 PowerShell 的 `>` / `Tee-Object`：写出来是 UTF-16LE，`read` 工具拒读。）

## Comments

### 落地事实

（做完填：三套门禁条数 ＋ 三张对比度读数 ＋ 两张全站读数）
