# 03 — 账本收口：落差归零 + 工单置 resolved

**要做什么：** 发完当场把账写对——`local-environment` 第 0 节写清「已发布 v1.3.1、落差归零」，
本目录三张单置 `resolved` 并各带落地读数。

**被谁阻塞：** 02（发布真做完了才能记「已发布」）。

**状态：** ready-for-agent

- [ ] `docs/agents/local-environment.md` §0 交接区按事实更新：v1.3.1 已上线、八件资产齐全、
      `/releases/latest` 指向它；tag 指向的提交与 HEAD 的关系写清（tag 落在打包那一刻的
      CHANGELOG 提交上，其后还有一笔 post-commit 的 `chore: 自动更新 CHANGELOG`）
- [ ] 同节记下本版两个产物的**实测字节数与 sha256**，并写明「下一版基线 = 这两个清单」
- [ ] `VERSIONS.md` / `README.md` / `CHANGELOG.md` 三处与线上一致（README 体积口径、
      Release 说明前两行由 `check-download-docs.py` 校验过）
- [ ] 本目录 `01` / `02` 置 `resolved`，各写「落地事实」段（提交号、读数、文件路径）
- [ ] 本单置 `resolved`
- [ ] 提交信息中文；工作树干净
- [ ] 记一条「下一轮接手要知道」的账：本版**没有任何板上行为被验证**
      （`hwcheck-acceptance/05` 仍 `ready-for-human`）
