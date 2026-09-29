# 02 — 发版前三套门禁（浏览器门禁单独跑）+ 全站读数（probe-00 / probe-04）

**要做什么：** 在**冻结的 revision**上把三套门禁与全站读数各跑一遍，落盘成证据——
验收线：两张尺（页面尺 `SITEWIDE_BACKLOG` / 取值尺 `FROZEN_FONT_SIZES`）**0 / 0**、裸 px 字号 **0**。

**被谁阻塞：** 01（版本号就位后跑的读数才对应要发的那棵树）。

**状态：** claimed

- [ ] 前端门禁 `node --test "tests/js/*.test.mjs"` → 落 `readings/js-gate.txt`
- [ ] **浏览器门禁单独跑**（不与全量 pytest 并行）`node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`
      → 落 `readings/browser-gate.txt`
- [ ] 全量 `python -m pytest -n auto -q` → 落 `readings/pytest.txt`
- [ ] `probe-00-survey.py` → 落 `readings/probe-00.txt`（家底普查）
- [ ] `probe-04-scope-calibers.py` → 落 `readings/probe-04.txt`（逐作用域三口径；
      **两张尺 0/0、裸字号 0** 在这里读）
- [ ] 落盘读数的时间戳**晚于最后一次改产品面**（三条纪律第 1 条：读数是照片不是结论）
- [ ] 读数与三张门禁的摘要写进票尾；提交信息中文

## Comments

（做完补：三套门禁读数、两张尺与裸字号读数、已知本机偶发有没有出现）
