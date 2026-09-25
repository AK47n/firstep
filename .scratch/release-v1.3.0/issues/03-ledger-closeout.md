# 03 — 账本收口：`local-environment` 第 0 节 + VERSIONS.md + CHANGELOG + backlog

**要做什么：** 发完当场把「main 与线上发布包的落差」那张表清空，并把本轮的会话事实
（网络中断、闸门缺陷、上板仍未做）写进 `docs/agents/local-environment.md`——
`CLAUDE.md` 明文要求：改了它描述的东西（发新版），当场回去改那份文件。

**被谁阻塞：** 02（要等 Release 真的上线，账本才能写「已发布」）。

**状态：** resolved

- [x] `docs/agents/local-environment.md` 第 0 节：线上最新改成 v1.3.0；七批落差表**清空**并
      注明「本版已带走」；补本轮会话事实（网络中断、闸门缺陷、上板仍待办）
- [x] `VERSIONS.md` 与 `CHANGELOG.md` 对账（CHANGELOG 由 post-commit 自动补录，中文）
- [x] `.scratch/release-v1.3.0/` 的 spec + 三张工单落 resolved
- [x] `git status` 干净；本轮所有证据入库

## Comments

### 落地事实（2026-09-25）

- 第 0 节的落差表从「七批」清成「零批」，并把三条**下一轮必须知道**的事实留下：
  ① 本版是「硬件检测」整块能力的第一次发布；② 真机上板验收（`hwcheck-acceptance/05`）
  仍未做——页面上凡涉及实测现象的地方都标着「未上板」；③ `github.com:443` 在本轮出现过
  一次连不上（`api.github.com` 正常），推送重试即好，与 gh 认证无关。
- 顺手记下本轮量准的**闸门缺陷**（已在 `01` 里修）：`test_js_gate.py` 那条用例没 stub
  第三支浏览器门禁，而真浏览器套件已长到 183.7 秒 > pytest 全局 180 秒超时。
  这与 `local-environment` 早先记的「`-n auto` 下并行争用偶发」**不是同一件事**——
  本轮把根因量准了，旧说法同时更正。
