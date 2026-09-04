# 03 — 路由改读 VERSIONS.md（/api/changelog → {releases}）

**要做什么：** `GET /api/changelog` 数据源从 CHANGELOG.md 换成 VERSIONS.md，
返回 `{"releases": [{version, date, summary, items: [{kind, text}]}]}`；
VERSIONS.md 缺失 / 损坏 → `{"releases": []}`（纯展示数据不阻塞）。
tests/test_webapp.py 的更新记录路由测试同步为新契约。

**被谁阻塞：** 02（解析器就绪）。

**状态：** ready-for-agent

- [ ] 路由返回 `{"releases": [...]}`，字段与 02 契约一致
- [ ] VERSIONS.md 缺失 → `{"releases": []}`
- [ ] tests/test_webapp.py 更新记录测试改为断言新形状（实况 VERSIONS.md）
