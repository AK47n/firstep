# 02 — 三套门禁现跑落盘

**要做什么：** 在**冻结的 revision**（01 之后的树，产品面零改动）上把三套门禁各跑一遍、落盘成证据：
确认"要发的那棵树"没有退化。

**被谁阻塞：** 01（版本号就位后跑的读数才对应要发的那棵树）。

**Status:** pending

- [ ] 前端门禁 `node --test "tests/js/*.test.mjs"` → `js-gate.txt`（预期 **1848 / 0**）
- [ ] **浏览器门禁单独跑**（不与**任何** pytest 并行）`node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`
      → `browser-gate.txt`（预期 **61 / 0**，≈3 分钟）
- [ ] 全量 `python -m pytest -n auto -q` → `pytest.txt`（预期 **5695 passed + 11 skipped**）
- [ ] 读数落盘时间戳**晚于**最后一次改产品面（本批产品面零改动，故只需晚于 01 的版本号提交）
- [ ] 摘要写进票尾；提交信息中文

## 读数落盘怎么跑

```powershell
python .scratch\hwcheck-hygiene\readings.py js-gate --out-dir .scratch\release-v1.4.4 -- node --test "tests/js/*.test.mjs"
```

（别用 PowerShell 的 `>` / `Tee-Object`：写出来是 UTF-16LE，`read` 工具拒读。）

## Comments

### 落地事实

（做完回填）
