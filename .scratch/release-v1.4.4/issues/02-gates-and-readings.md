# 02 — 三套门禁现跑落盘

**要做什么：** 在**冻结的 revision**（01 之后的树，产品面零改动）上把三套门禁各跑一遍、落盘成证据：
确认"要发的那棵树"没有退化。

**被谁阻塞：** 01（版本号就位后跑的读数才对应要发的那棵树）。

**Status:** resolved（2026-10-02）

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

### 落地事实（2026-10-02，冻结 revision = `9b050b7f` + 它的 CHANGELOG 提交 `1cfdf7f1`）

| 门禁 | 结果 | 文件 | 起跑时刻 |
|---|---|---|---|
| 前端门禁 | **1848 passed / 0 fail**（9.76 s） | `js-gate.txt` | 09:23:57 |
| 浏览器门禁（**单独跑**） | **61 passed / 0 fail**（182.8 s） | `browser-gate.txt` | 09:24:07 |
| 全量 pytest | **5695 passed + 11 skipped / 0 failed**（114.1 s） | `pytest.txt` | 09:28:1x |

- **三套读数与 `pin-type-contrast` 收口那一轮逐项相同**（1848 / 61 / 5695 + 11）——本批产品面零改动，
  这正是预期的读数（对不上才要查）。
- **顺序照纪律走**：三段**串行**跑在**同一个后台任务**里（`js → browser → pytest`），浏览器门禁
  全程没有任何 pytest 并行；三段各自用 `.scratch/hwcheck-hygiene/readings.py` 落盘（PowerShell 的
  `>` 是 UTF-16LE，不能用）。
- 读数落盘时刻（09:23–09:30）**晚于**最后一次改产品面的提交（`9b050b7f`，09:22 那批版本号）；
  此后只改 `.scratch` 证据与单子。
