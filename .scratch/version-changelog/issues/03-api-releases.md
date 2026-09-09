# 03 — 路由改读 VERSIONS.md（/api/changelog → {releases}）

**要做什么：** `GET /api/changelog` 数据源从 CHANGELOG.md 换成 VERSIONS.md，
返回 `{"releases": [{version, date, summary, items: [{kind, text}]}]}`；
VERSIONS.md 缺失 / 损坏 → `{"releases": []}`（纯展示数据不阻塞）。
tests/test_webapp.py 的更新记录路由测试同步为新契约。

**被谁阻塞：** 02（解析器就绪）。

**状态：** resolved

**审查结论（code-review 双轴）与整改：**
- 规格轴：测试未兑现「与 VERSIONS.md 实况」断言——已补 `data["releases"] == []`
  显式断言（首次发布时随 VERSIONS.md 更新）；键断言放宽为 `"releases" in data`
  （对象包裹允许将来扩展）；新增路由级缺失分支测试
  （monkeypatch load_versions → `{"releases": []}`）。范围蔓延：无。
- 标准轴：无明文违规；运行时循环内形状断言目前不可达（空态），保留为
  首次发版后的守卫（docstring 已注明）；`/api/changelog` 命名是 spec 显式
  决策（前端唯一调用方，破坏性变更可接受），不改名；仓库根推导不新增多处。

- [x] 路由返回 `{"releases": [...]}`，字段与 02 契约一致
- [x] VERSIONS.md 缺失 → `{"releases": []}`
- [x] tests/test_webapp.py 更新记录测试改为断言新形状（实况 VERSIONS.md）


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
