# 05 — `launcher-reload` 在「复用过的临时 HOME」下会红（现场记录，未定性）

**要做什么：** 查清并修掉 `tests/browser/launcher-reload.spec.mjs` 的一个环境敏感红：
同一份代码、同一个空 `HOME`，**全新临时目录 → 5 条全绿**，**复用过的目录 → 5 条全红**。

**被谁阻塞：** 无——可立即开始（但**先说清它不是 `ci-gate-fixes/02` 的回归**，见下）。

**状态：** ready-for-agent

- [ ] 先按下面的「复现条件」把它稳定复现出来（**先能稳定复现再谈修**；复现不了就别动 spec）
- [ ] 定性：是**产品侧**那条宽限竞态（`pagehide` → `bye` → `_EXIT_GRACE` 内 `register` 没到 ⇒
      `os._exit`）在慢盘 / 冷缓存下变宽，还是**夹具**侧（`test.after` 的 `server.stop()` 与
      下一轮 `before` 的端口 / 目录状态互相干扰）
- [ ] 修掉之后：`launcher-reload` 在「全新」与「复用」两种 HOME 下都要绿；且**不许**把
      「最后一个页面离开 → 服务自己停」这条产品不变量削弱（那是这个 spec 存在的理由）
- [ ] 若定性为"测试环境噪声"而非产品缺陷，就把判据改成对目录状态不敏感，并在文件中写清为什么
- [ ] 中文提交

## Comments

### 现场（2026-09-25，`ci-gate-fixes/02` 排查时撞到）

**现象**：`node --test --test-concurrency=1 "tests/browser/launcher-reload.spec.mjs"`，空 HOME：

| 条件 | 读数 |
|---|---|
| `HOME=%TEMP%\empty-home-ci`（**复用过的目录**，第二轮） | 5 条全红。A = `page.reload: Timeout 30000ms exceeded`（`navigated to http://127.0.0.1:1411/`，卡在 `domcontentloaded`）；B–E = `net::ERR_CONNECTION_REFUSED`（秒级连红） |
| `HOME` 换成一个**全新**空目录 | 5 条全绿（退出码 0） |
| 本机正常 HOME | 5 条全绿 |

后端日志（夹具 `FIRSTEP_BROWSER_SERVER_LOG`）在**绿**那一轮的末尾是：
`GET /api/modules 200` → `POST /api/tabs/bye 200` → `[fixture] 后端进程退出 code=0 signal=null`
——产品按设计自杀了（那正是 spec C 要验的行为），绿的那轮是**后续 register 救回来了**。

> ⚠ **`02` 评审驳回过一个我先前写在这里的对照，别再引用它**：我曾拿"旧夹具 + 空 HOME 也 5 条红"
> 当"非本单引入"的证据——那是**错的**。空 HOME 没有 `config.json` 是**另一个已定性**的根因
> （哨兵判旧后端），它的红与这里的红**签名不同**（3.7 秒快速失败 vs `page.reload` 30s 超时），
> 两者不是一回事。**本单因此不做"是否回归"的判定**。

**本单没定性的部分**：这个签名（`page.reload` 超时 + `ERR_CONNECTION_REFUSED`）在本仓
`local-environment` 第 2 节记的几条老偶发里有前科（并行争用 / 残留服务那一类），
但也可能真是宽限竞态在慢环境下变宽——**先把它稳定复现出来再谈修**，别凭形态猜。

**为什么怀疑宽限竞态**：形态与 `local-environment` 第 2 节记的那条
「F5 重载慢过 1.5 秒会被应用自己关掉」（工单 `launcher-exit-race/01–05` 已修）**同形**——
都是 `pagehide` 的 `bye` 先到、新文档的 `register` 没在 `_EXIT_GRACE=1.5s` 内到达。
该轮修复的判据是「修复后 10/10 全程活着」，但那是**正常 HOME** 下测的；
本单要回答的是**空 / 复用 HOME 下是不是有另一条更慢的路径**（少了预热的目录 / 缓存，
首次请求更慢 ⇒ register 更晚）。

**为什么不并进 `02`**：`02` 的判据（空 HOME + 全新目录）是绿的，CI runner 每次也是全新环境；
这个红只在"同一目录反复用"时出现，成因未定，混在一起会让 `02` 的账读不准。

