# 05 — 架构深化 v5：参考全文读取与标签格式归 reference_library（候选 6）

**What to build:** 第五轮架构深化（2026-08-09 grilling 共识定稿，候选 6，源自 architecture-review-20260809-102431）。参考条目的全文读取（路径安全 + 二进制跳过 + 文件名标注）住在推荐域 selection.py（`read_reference_fulltext`，:207），条目形状所有者 reference_library 只持形状不持读取；generator 的 `_make_fulltext_reader` 闭包（:214）绕经 selection 接线；LLM 可见的标签格式 `"// ---- {name} ----"` 三处拷贝（library._assemble_code :478 / reference_library._assemble_material :416 / selection.read_reference_fulltext :228+:230）——改格式要三处同步，漏一处模型就逐功能看到不同格式；预算常数 `JUDGMENT_CONTENT_CAP`（llm.py:186，判定域名）实际管着全部嵌内容（赛题 / 接口块 / 文件全文 / 参考素材 / 参考全文）。本轮收口：**全文读取归 reference_library 作 store 方法，标签格式单源 = library.file_label，预算常数域正名**。行为零变化（拼装字节 / 截断值 / 错误文案逐字不变）。

1. **`read_fulltext` 归 reference_library**（store 自持读取）：
   - reference_library 新增 `read_fulltext(reference_root: Path, entry: ReferenceEntry) -> str`——selection.py:207-231 的语义逐字搬移（docstring 原样：二进制跳过标注 / 文件缺失 / 相对路径非法大声失败），**名称从 read_reference_fulltext 改 read_fulltext**（模块域内自明；唯一消费方是 generator）；
   - selection.py 删 `read_reference_fulltext` 定义 + **清闲置 import**：`is_unsafe_path`（entry_store，:33，仅此函数用）与 `ReferenceError`（:36 里的名字，仅此函数用）——grep 坐实后删，`ReferenceEntry` / `search_references` 保留（associated_references 用）；
   - generator.py：`:29` 的 `read_reference_fulltext` 从 selection import 移除，并入 `:25` 既有 `from .reference_library import ...` 行（加 `read_fulltext`）；`_make_fulltext_reader`（:214-223）闭包体改直传 `read_fulltext(reference_root, entry)`——**少一层跳板**（card 原文：闭包只剩直传）。
2. **标签格式单源 = `library.file_label`**：
   - library 新增公开函数 `file_label(name: str, note: str = "") -> str`，返回 `f"// ---- {name} ----{note}\n"`（docstring：库族素材拼装的共享文件名标注——模块源码 / 参考素材 / 参考全文共用，prompt 可见契约单源，改格式只改这一处；曾三处各抄一份）；
   - 三处消费：library._assemble_code（:478）改 `"\n".join(file_label(name) + content ...)`；reference_library._assemble_material（:416）同款；reference_library.read_fulltext 普通形 = `file_label(rel) + content`、二进制形 = `file_label(rel, "（二进制素材，未嵌入全文）")`；
   - reference_library 从 library import `file_label`——**依赖方向事实**：reference_library → library 边已存在（`list_modules`，:46），同向加名无新边无环；**不可反向往 reference_library**（library → reference_library → library 成环）。
3. **预算常数域正名**：llm.py:186 `JUDGMENT_CONTENT_CAP = 4000` → `EMBEDDED_CONTENT_CAP = 4000`——域中性名（该常数管全部嵌内容截断，非判定专属：判定文件全文 :374 / 模块代码 :606 / 参考素材 :668 / 参考全文 :1506 / 赛题与清单 :1472）；:185 注释与 :216 docstring 同步改域中性表述；值不变。**不拆用**（按域拆多个常数 = 行为变化，无需求支撑，YAGNI）。
4. **测试**：test_selection.py 的 4 个 fulltext 用例（:298-350：拼装标注 / 二进制跳过 / 缺文件报错 / 路径非法）**随迁** test_reference_library.py（import 改 `from contest_generator.reference_library import read_fulltext`，断言原样——字节级）；test_selection.py:32 删该 import；test_llm.py 的 `JUDGMENT_CONTENT_CAP` 全部改名（:27 import + :730/:734/:737/:840/:844/:854/:858/:2309 使用 + :2423 注释）；新增结构测试（防回退，先例 errors.py / 04 工单）：selection 无 `read_reference_fulltext` 属性；src 内 `"// ---- "` 字面量唯一出处 = library.py（`file_label` 定义处，grep 式断言）；reference_library 有 `file_label` 属性（消费 pin）。
5. **CONTEXT.md 词表更新**（同批提交）：「参考文件库」主要实现列改"两级注入装配在 generator.py（TopicContext）+ selection.py（清单段）+ reference_library.py（全文回读 read_fulltext，store 自持：路径安全 + 二进制跳过 + 标签单源）"；「架构要点」补一句：库素材拼装标签格式单源 = library.file_label（模块源码 / 参考素材 / 参考全文共用）。

**明确不动的（边界，勿越）**：行为零变化（拼装输出字节逐字不变——既有 summarize/validate 消息断言原样过；截断值 4000 不变；错误文案逐字不变）；llm.py 只改常数名与注释（prompt 文本零改动）；selection 其余 API（reference_suggestions / associated_references / 清单段装配）零改动；reference_library 其余 API 零改动；不引入新模块（file_label 住 library，见 2 节环事实）；webapp 路由零改动。

**Status:** resolved（2026-08-09 同批 PR 勾选，818 绿 + mypy 干净）

## 验收

- [x] 全量 pytest 绿（基线 815 → 818，+3：结构测试；4 个 fulltext 用例随迁后原样过——拼装字节逐字不变，summarize/validate 既有断言原样过）+ mypy 干净
- [x] `grep -rn "read_reference_fulltext" src` 无结果（旧名清零；read_fulltext 唯一出处 reference_library.py）；tests 仅剩结构测试的 pin 断言（hasattr 引用旧名是工单结构测试要求本身）
- [x] `grep -rn "// ---- " src` 唯一出处 = library.py:481（file_label 定义处）
- [x] `grep -rn "JUDGMENT_CONTENT_CAP" src tests` 无结果（EMBEDDED_CONTENT_CAP 全量改名）
- [x] 结构测试过：selection 无 read_reference_fulltext 属性；src "// ---- " 单址断言过；reference_library.file_label 消费 pin 过（等号引用 library.file_label，无新边无环）
- [x] CONTEXT.md 两处更新到位（参考文件库实现列 + 架构要点新 bullet）

## 实施提示词（新会话用）

```
工单：.scratch/architecture-deepening-v5/issues/05-reference-fulltext-ownership.md（架构深化 v5：参考全文读取与标签格式归 reference_library，候选 6）

先读工单全文，按 1-5 节执行。独立 worktree（勿在主检出改，必须 -b 形式）：
git worktree add -b v5-05-reference-fulltext ../firstep-v5-05 main

1. reference_library 加 read_fulltext（selection.py:207-231 语义逐字搬移，改名 read_fulltext，docstring 原样）；selection 删定义 + 清 is_unsafe_path/ReferenceError 闲置 import（grep 坐实）；generator import 改从 reference_library（并入 :25 既有行），_make_fulltext_reader 闭包体直传
2. library 加 file_label(name, note="") 公开函数；三处消费（_assemble_code / _assemble_material / read_fulltext 两形）；reference_library 从 library import file_label（既有边，勿反向）
3. llm.py 常数改名 JUDGMENT_CONTENT_CAP → EMBEDDED_CONTENT_CAP（定义 + :185 注释 + :216 docstring + 全部引用，值 4000 不变）
4. 测试：4 个 fulltext 用例随迁 test_reference_library（断言原样）；test_selection 删 import；test_llm 改名；新增结构测试（工单 4 节清单）
5. CONTEXT.md 按工单 5 节更新
6. 全量 pytest 绿 + mypy 干净 + 验收全勾后提交（refactor 一条 + docs 一条，风格照仓库）→ PR base 指 main

注意：编辑前先确认 cwd 在 worktree；勿串行做别的工单。
```

## Comments

（2026-08-09 立项，grilling 共识定稿：候选 6 参考全文归位。用户委托技术选型（"深度思考然后选择"），逐项复核后定稿。D1 全文读取归 store：read_fulltext 迁 reference_library（改名，docstring 原样），selection 只留清单段装配——两级注入各归其主；generator 闭包只剩直传。D2 标签单源住 library.py：依赖图事实决定——reference_library → library 边已存在（list_modules），file_label 住 library 无新边无环；反向住 reference_library 会成环（library → reference_library → library）；不新建叶子模块（一个字符串格式不值得，wordlist/treewalk 都是真概念）。D3 预算常数正名不拆用：JUDGMENT_CONTENT_CAP 实际管全部嵌内容（赛题/接口块/文件全文/参考素材/参考全文，llm.py 六处引用坐实），改名 EMBEDDED_CONTENT_CAP 域中性；拆用 = 行为变化无需求支撑（YAGNI）。D4 测试随迁 + 结构防回退（selection 无 read_reference_fulltext / "// ---- " 单址 / file_label 消费 pin）。报告：architecture-review-20260809-102431.html。）

（2026-08-09 实施留痕：按 1-6 节执行完毕。refactor 提交：read_fulltext 迁 reference_library（selection 删定义 + 清 is_unsafe_path/ReferenceError 闲置 import，grep 坐实仅该函数用）；generator import 并入 reference_library 既有行、闭包体直传；library.file_label 单源（_assemble_code / _assemble_material / read_fulltext 两形三处消费，标签格式逐字不变）；llm.py 常数域正名 EMBEDDED_CONTENT_CAP（值 4000 不变，注释 / docstring 同步域中性表述）。测试：4 个 fulltext 用例随迁 test_reference_library（断言原样、函数名随改名——旧名清零语义）；test_selection 删 import；test_llm 全量改名；新增 3 个结构测试（selection 无 read_reference_fulltext / "// ---- " 单址 library.py:481 / file_label 消费 pin）。docs 提交：CONTEXT.md 两处 + 工单文件闭环。818 绿 + mypy 干净。）
