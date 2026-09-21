# 03 — 两条判据进闸门 ＋ 账本收尾

**要做什么：** 把 01 立的两条判据接进前端门禁（`node --test "tests/js/*.test.mjs"`），**当场生效**：
此后任何人新增一个没人 import 的导出、或把被调用的 `export function` 改成同名常量，
**推之前就红**。然后按仓库口径收尾：账本三处更新（`CONTEXT.md` / `fx-guard` 文件头 /
`backlog.md` 第 10 节两条挂账结清 ＋ 一条更正）、三门禁各跑一遍并记数。

**被谁阻塞：** 02（清点处置 111 处）

**状态：** ready-for-agent

## 验收标准

- [ ] 两条判据进前端门禁，用例住**一处**并说明选择（"缝越少越好"）：优先接在既有守卫文件
      （`tests/js/fx-guard.test.mjs` 是"名字表退化"那件事的现场）还是新开
      `tests/js/export-surface-guard.test.mjs`，在 Comments 里写清取舍。
- [ ] 用例含**正向对照**与"那种绿比红更坏"体检（先例 `ui-dom-contract.test.mjs`）：抽取器一旦静默失效
      必须报出，而不是断言为空导致真空绿；星号导入体检同样进闸门。
- [ ] 判据 T 的**别名正向对照**进闸门（`export const x = 别的函数名;` 必须不报——防假红），
      连同再导出链感知各一条。
- [ ] **共享解析器那处修复要有闸门内的直接单测**（工单 01 Comments ②）：`parseModuleImports` 对
      `import * as ns from "…"` 与 `export * as ns from "…"` 必须解析出 star 边（修复前两者**整条
      静默丢弃**，星号体检等于空转），`export * from "…"` 照旧。
- [ ] **账本三处**：
      ① `CONTEXT.md`「前端纯函数单源」那一行的口径更新——旧的"类型维度与死导出不再守"要改成
      "**fn 轴已由判据 T 守（调用位 ⇒ 函数形态）；零消费者导出由判据 D 守；常量形态（number/string/object）
      仍不守**"；
      ② `tests/js/fx-guard.test.mjs` 文件头同样的口径更新（那段"代价如实记账"）；
      ③ `.scratch/backlog.md` 第 10 节末两条挂账**结清**，并写进那条**更正**：
      "更该做的是清点后删掉它们"是在"这 7 个是死代码"的假设下写的——实测它们是**活的定义 ＋ 多余的
      `export`**（都被本模块内部或 window 桥用着），真正该删的只有 1 个；且真实体量是 **111** 而不是 7。
- [ ] **三门禁各跑一遍并记数**：`python -m pytest -n auto -q`、
      `node --test "tests/js/*.test.mjs"`、`node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`
      ——读数（passed / failed / 耗时）写进 Comments。
- [ ] **未顺手做**（与 spec「范围外」一致，逐条列进 Comments）：常量形态恢复、C6（555 个 id 耦合）、
      C7（73 个私有符号）、`.scratch` 一次性探针的失效修复、导出面的 API 重设计、
      `import-usage-guard` 口径扩展、工单 `frontend-boot-module/01-05` 的其它挂账。

## Comments
