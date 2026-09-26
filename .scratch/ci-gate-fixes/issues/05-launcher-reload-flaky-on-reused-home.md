# 05 — `launcher-reload` 会偶发全红（**标题那个"复用 HOME"是误判**，真身是 ~1/3 的宽限竞态偶发）

**要做什么：** 让 `tests/browser/launcher-reload.spec.mjs` **不再偶发全红**：同一份代码、
同一个空 `HOME`，四次有效运行里红一次（5 条全红），而**红的那次后台是应用自己停掉了**
（"最后离开 → 停服务"那条不变量在 1.5 秒宽限内没等到新文档的 `register`）。

**被谁阻塞：** 无——可立即开始（但**先说清它不是 `ci-gate-fixes/02` 的回归**，见下）。

**状态：** claimed

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

## Comments

### 复现与定性（2026-09-26 凌晨，本轮实测）

**① 本单的标题前提（"复用过的临时 HOME"）被推翻。** 逐轮读数（`launcher-reload.spec.mjs`，
`HOME`/`USERPROFILE` 指向临时目录）：

| 轮 | HOME | 读数 |
|---|---|---|
| 1 | `%TEMP%\empty-home-ci`（**新建**） | **5 passed / 0 fail** |
| 2 | 同一个目录（复用） | **0 passed / 5 fail**（复现本单现场） |
| 3 | `%TEMP%\empty-home-ci-b`（**新建**） | **5 passed / 0 fail** |
| 4 | `empty-home-ci-b`（复用） | **5 passed / 0 fail** ← 复用**也绿** |
| 5 | 不设 HOME（= 真身 profile） | 5 fail，但**是我的实验错了**：`USERPROFILE`/`HOME` 都删掉之后后端起不来（`Path.home()` → `RuntimeError: Could not determine home directory.`，exit code 1），**与产品无关** |

- 关键反证：**那个"复用过的"目录跑完是空的**（`Get-ChildItem -Force -Recurse` 计数 0）——
  目录里什么状态都没有，产品也一个字节都没往里写（`02` 之后配置走 `FIRSTEP_CONFIG_PATH`，
  种子配置在 `mkdtemp` 出来的临时目录里）。**"目录状态"这个变量不存在**。
- 于是真相是：**~30–40% 的偶发**（4 次有效运行里红 1 次；现场那次也是撞上了），
  与 HOME 的新旧无关。这也解释了为什么 CI 上四轮跑下来 `launcher-reload` **5 条始终全绿**。

**② 机制（红的那轮后端日志是逐字证据）**：进程**自己退出**（`code=0` = `os._exit(0)`，
即"最后一个页面离开 → 停服务"那条产品不变量真的开火了），随后的用例全部
`ERR_CONNECTION_REFUSED`（B–E 秒级连红），A 卡在 `page.reload` 超时（95 秒 = 三次 30 秒）。
日志里最后一轮的时序是：

```
GET / HTTP/1.1 200            ← 新文档的 HTML（reload）
…（同窗口内还有几十条旧文档的 GET /js/… 在飞）
[fixture] 后端进程退出（端口 3322；code=0 signal=null）   ← 宽限到点，register 始终没到
```

即：旧文档的 `bye` 把"在途退出"布防了（宽限 `_EXIT_GRACE = 1.5s`），而新文档那个
**住在 `index.html` head 内联脚本里的 `register`** 没能在 1.5 秒内到达 —— 页面当时**还在
装载模块图**（日志里那一屏 `GET /js/…`）。合理的成因：**浏览器的同源连接池被旧文档在途的
请求占满**，新文档的 `register` 排队排在它们后面；慢机器 / 冷缓存上更容易越过 1.5 秒。
这正是本单怀疑的那条宽限竞态（`launcher-exit-race/01–05` 修过的那条），只是**换了一条更慢的
到达路径**：修法把 `register` 从"等模块图"挪到了"HTML 解析即可发"，但它仍然要**抢到一个连接**。

### 下一步（未做完的部分，留给接手的人）

1. **做一个确定性红证**（本单要求的"先稳定复现"还没到确定性那一步）：用 `page.route`
   把几条模块请求**人为拖慢**（照用例 B 拖 `boot.js` 的既有先例），让新文档的 `register`
   必然排在后面 —— 若那时应用自杀，机制即被证明，且有了一个秒级可控的红回路。
2. 修法候选（**都要先拿上面的红证验一遍**）：
   - **夹具侧**：`reloadAndReady` 在 `page.reload()` 前等网络静默（`networkidle`）——
     真实用户不会在页面还在装载时按 F5；这不碰产品不变量。
   - **产品侧**：宽限窗口的判据从"固定 1.5 秒"换成"页面**真在装载中**就再等一轮"
     （例如把"最近一次页面请求"纳入判据）——动的是产品语义，得单独论证，别顺手改常量
     （`_EXIT_GRACE` 是刻意留的，关了浏览器实测 1.53–1.65 秒停服，用例 C 拿它当契约）。
3. 判据：修完之后**连续跑 ≥10 轮全绿**（本单的偶发率 ~1/3，跑 3 轮绿说明不了问题），
   且 `launcher-reload` 5 条与"最后离开 → 自停"那条不变量都还在。

