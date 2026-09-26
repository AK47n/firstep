# 09 — 同一条事实的三处副本收成「一句 + 双端断言」（Standards 轴整改）

**要做什么：** 「这批检测还没在真板上验证过」这条事实，页面、README、配方数据三处**说的是同一句**——
改一处漏两处会当场红，而不是靠人记得。

**被谁阻塞：** 无（`01`–`07` 的产物）。

**状态：** resolved

**来源**：`docs/improvement-review-hwcheck.md` 的 P0-1 落地后，Standards 轴评审（2026-09-26）判定的
**唯一一条硬违规**：`README.md:91`、`static/js/fx/hwcheck.js` 的 `hwcheckUnverifiedNoteHTML()`、
`library/hwcheck_recipes.json` 的 note 里各写一份同一事实，规范化比对后**互不相等**——
平行副本，而 `spec.md` 明写"同一句措辞，别再写第二种"。

**为什么不能真的单源**（写清楚，免得下一轮又当缺陷改一遍）：三个落点在**三个运行时**里——
Markdown（README，静态文本、无人生成）、JS（页面文案）、JSON（库内数据）。
跨语言"同文"在本仓库的既有做法是**刻意同文 + 双端断言**（先例：`fix_errors.SYSCFG_CONFLICT_NOTICE`
与 `ui/fix-center-core.js` 的 `syscfgConflictStateText`）。本单照那条先例办。

## 验收标准

- [x] 定一句**规范句**（不带嵌套引号、可逐字匹配）：
      `本栏目的配方与探测小节尚未在真板上验证过：现有证据只到「能生成 + 能编译」这一步。`
- [x] 页面（fx 的 `hwcheckUnverifiedNoteHTML`）与 README 的 FAQ 条目**都逐字含这句**，
      各自剩下的补充句分工不同（页面：判 FAIL / 判 OK 怎么读；README：加一句"每一格的平台说明里也写着未上板"）。
- [x] 配方数据的每一格末条除「**未上板**」标记外，还要含**同一条子句**「真机上板验证还没做」
      （`servo` 那两格现在写的是"manifest 没有上板验证记录"——补齐子句，别另立第二种说法）。
- [x] **双端断言**（新增用例）：
      ① 读真 README 与真 fx 源码，规范化（去换行/缩进/JS 拼接符/强调标记）后**都必须含规范句**；
      ② 真库 57 格的末条 note 必须含「**未上板**」+「真机上板验证还没做」。
- [x] 反证：把规范句里任意一处改掉（页面 / README / 某一格 note）→ 对应用例必须红；
      复原后逐字节相同（读数落 `.scratch/hwcheck-hardening/probe-09-red.txt`）。
- [x] 顺手改掉 `hwcheck.py` 里那句**已经过期**的注释（"检测页那几行文案都控制在 16 列内"——
      实测 165 行里 88 行数值进不了 16 列；03 单已把读数行改成值优先）。
