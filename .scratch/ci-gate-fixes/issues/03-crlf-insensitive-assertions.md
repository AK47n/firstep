# 03 — 两处 CRLF 敏感断言改为换行无关

**要做什么：** CRLF 检出（CI windows 腿的真实形态）下前端门禁全绿；本工作树 LF 检出同样全绿。
现在有两条断言拿 `\n` 当锚点，遇到 CRLF 就不匹配。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `tests/js/ai-action-refs.test.mjs` 那条（生成骨架 / 生成工程收尾路径含 `aiActionStop`）改成换行无关
- [x] `tests/js/module-intro-detail.test.mjs` 那条（点掉 chip 后的时序）改成换行无关
- [x] 改法照本仓**既有口径**：`tests/js/tab-register-guard.test.mjs:276` 的原话——
      锚点用**不含缩进与换行**的子串（带 `\n` 的锚点会静默不落上，第一版就是这么假红的）
- [x] **反向验证**（先红后绿）：干净 clone（`core.autocrlf=true`）改前 **1794 passed / 2 fail**，
      改后 **1796 passed / 0 fail**
- [x] LF 检出（本工作树）同样 **1796 passed / 0 fail**——两个方向都要跑
- [x] 断言强度不缩水：两条用例判的仍是「这两处调用是成对的 start/stop」这件事本身
- [x] 中文提交

## Comments

### 落地事实（2026-09-25）

**改法**：两条 `\n` 锚点换成 `[^\n]*\r?\n[ \t]*`——
`[^\n]*` 吃掉行尾的 `\r`（CRLF 那一半）与行尾注释/空白，`\r?\n` 兼容两种检出，
`[ \t]*` 只吃同行缩进（**不用 `\s*`**：它能跨空行，会把"两处在相邻行"放宽成"隔多远都行"，
那就是断言强度缩水）。判的仍是那件事：`bannerReleased = false;` 与
`aiActionStart("生成工程")` 按序落在**相邻两行**上 / `renderRecommendResult(lastRecommend, false);`
与 `runExpand();` 同理。

> 首版用的是 `[^\n]*\n\s*`，评审指出 `\s*` 可跨空行 ⇒ 比既有先例
> （`tests/js/my-devices.test.mjs:155` 的 `;\r?\n`）松，已按上面收紧。

**反向验证（先红后绿，都在 CRLF 检出下）**：

| 步 | 读数 |
|---|---|
| 干净 clone（`core.autocrlf=true`）改前 | **1794 passed / 2 fail**（正是那两条） |
| 把新锚点**换回**旧 `\n` 锚点（逐字节备份后注入，再复原） | **1794 / 2 fail** —— 红的**恰好是同样两条**，判据确实在判那件事 |
| 复原（新锚点）+ CRLF 检出 | **1796 passed / 0 fail** |
| 本工作树 LF 检出 | **1796 passed / 0 fail** |

> CRLF 复现口径（copy 会把文件重置成 LF，所以必须**显式把被判读的源码转 CRLF**）：
> `src/contest_generator/static/js/ui/generate-core.js` 与 `.../generate-recommend.js`
> 转成 CRLF 后再跑 `node --test "tests/js/*.test.mjs"`。

### 流程更正（评审抓到的）

本单的代码随 `fbfa2357` 一起提交了，但工单当时**没落 resolved、验收框也没勾**——
违反 `docs/agents/workflow.md` Step 4「先 claim、干完置 resolved」。这一条按事实补齐。
（教训：`commit-msg-01.txt` 那次提交把三张单的文档一起带上了，顺手提交 ≠ 顺手收口。）
