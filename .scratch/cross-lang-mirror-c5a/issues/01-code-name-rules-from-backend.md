# 01 — 文件名校验规则改由后端下发（CODE_TREE_NAME_ILLEGAL 裸镜像退场）

**要做什么：** 在代码栏新建文件 / 文件夹 / 重命名时，前端弹窗就地拦下非法名称所依据的规则
（非法字符集 + 120 字符上限），不再是前端自己那份硬编码，而是**后端随打开目录的响应下发的同一份**；
源码里的同名字面量退化为「后端尚未下发时的启动兜底」，并由一条源码字面量守卫钉住与后端一致。
端到端行为：改后端规则 → 前端拦下的名字自动跟着变；改前端兜底值而没改后端 → pytest 变红。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 后端判据单源落成具名常量（非法字符集 + 120 上限），名称校验与载荷投影读同一个常量——
      不接受「校验用常量、下发用另一处字面量」的写法。
- [x] `POST /api/code/open` 响应新增名称规则字段，值为前端可直接吃的形态（非法字符集字符串 + 上限数字）；
      既有断言（`root` / `files` 逐条字段）零改动、仍全绿。
- [x] 前端 `fx/code-tree-ops.js` 增加装载入口（吃后端下发的规则）与模块级运行时状态；
      `treeNameValidate` 按运行时状态判定；源码常量退化为兜底，**常量名与 `typeof` 不变**
      （`tests/js/fx-guard.test.mjs` 的登记表零改动）。
- [x] `ui/codeview.js` 在拿到 `/api/code/open` 响应后把规则交给纯函数模块；下发缺失或形状不对时
      保留兜底值（不抛错、不静默清空）。
- [x] `tests/js/code-tree-ops.test.mjs` 补「按后端下发的规则拒绝」用例：含 `\` 这类易漏字符、
      上限边界（= 上限通过 / 上限 + 1 拒绝），断言的是校验结论而非常量来源。
- [x] 源码字面量守卫（pytest）读 `fx/code-tree-ops.js` 真源码，抠出两个常量与后端常量按
      **集合 / 整数**对账（不做字符串逐字比对，避免 JS 转义写法差异误判）。
- [x] **红证**：守卫第一次写出来时，把前端兜底常量故意改错一个字（或改后端常量）→ 该测试必须变红；
      恢复后变绿。证据（改动 + 红/绿两次输出）留 `## Comments`。
- [x] `CONTEXT.md` 代码查看器行补一句单源事实（规则由该端点下发、前端只求值），不留待办。
- [x] `python -m pytest` 全绿 + `node --test "tests/js/*.test.mjs"` 全绿；提交信息中文。

## Comments

### 实现记录（claim → tdd）

**红证 1（验收项：规则下发与规则执行同源）**。写「下发集合的每个字符都真被后端拒」时，
`create_code_entry` 直接没红——实测发现**两个既存缺口**，比评审说的「注释互指」更实：

```
create_code_entry(d, "file", "x"*130 + ".c")  → 成功建出 130 字符的病态文件名
create_code_entry(d, "file", "a*b.c")         → OSError [Errno 22] Invalid argument
                                                 （未登记异常 → 500，既不是 400 也不是设计拒绝面）
```

根因：**只有 `rename_code_entry` 走 `_validate_entry_name`，`create_code_entry` 不走**。
端点契约与校验函数并不同源。补口做法与取舍：

- 名称判定排在 `_resolve_in_root` **之后**——`../x` / `C:/x` / `src\x` / `src/` 的错误面与文案
  保持原样（既有 `test_create_code_entry_rejects_unsafe_path` 6 例全绿，未被新规则改写成
  「名称不合法」）。
- 逐段校验（`_validate_entry_names`）：中间段是目录名，与末段同样直达 `mkdir`，必须同拦。
- 红证过程：新用例最初 8 红（`create_code_entry` 完全无校验）；补口后 112 passed。

**红证 2（验收项：源码字面量守卫真的会红）**。故意把 JS 兜底常量去掉一个字符
（`CODE_TREE_NAME_ILLEGAL` 尾部删 `|`）：

```
E  AssertionError: fx/code-tree-ops.js 的 CODE_TREE_NAME_ILLEGAL 与后端 CODE_NAME_ILLEGAL 不一致：
   JS='/\\:*?"<>' Python='/\\:*?"<>|'
E  Extra items in the right set: '|'
tests/test_codeview.py::test_js_name_rules_fallback_mirrors_backend  FAILED
```

恢复后该用例绿。

**红证 3（前端装载接线守卫）**。临时删掉 `ui/codeview.js` 刷新路径的那句装载：

```
✖ ui/codeview.js：每个 /api/code/open 响应都装载名称规则
  AssertionError: 第 549 行的 /api/code/open 响应未装载名称规则
```

恢复后绿。

### code-review 整改（双轴评审后）

| 发现 | 处理 |
|---|---|
| 400 文案仍写死「≤120 字符、不含 / \ : * ? " < > |」= 规则的第二份字面量（Standards 硬违规） | 文案改为由常量现拼，且分支理由各点名（哪个字符 / 多少长度）；新增 `test_rename_code_illegal_name_message_names_the_char` |
| docstring「每一段都过 `_validate_entry_name`」与实现（只校验末段）自相矛盾，且 `a*b/x.c` 中间段仍 500（两轴都报了） | **改实现而不是改注释**：新增 `_validate_entry_names` 逐段校验；新增 4 例中间段参数化用例 + 半成品断言 |
| `test_ui_code_open_response_installs_name_rules` 用源码子串计数（测实现细节） | 删除该 pytest 用例，移到 `tests/js/code-tree-ops.test.mjs` 的前端源码守卫，**形态无关**（窗口内出现 `setCodeTreeNameRules(` 即可，改名变量/两步走都通过）+ 红证 |
| `CODE_TREE_NAME_RULES_DEFAULT` 那条 deepEqual 恒真（构造即通过） | 重写为「复装后校验结论回到兜底口径」的行为断言 |
| 缺 `\` 的下发路径用例（spec 点名） | 新增「下发值含反斜杠 / 上限边界逐字生效」用例 |
| `send_name_rules()` 名称与语义不符（不发送） | 更名 `name_rules_payload()`，与 `list_code_tree` / `read_code_file` 同族 |
| pytest 守卫 shell 出 node（偏离 spec 与先例，新缝） | 改回**读 JS 真源码抠字面量**（`ast.literal_eval`），零子进程；形态变了大声失败不静默跳过 |
| fx 层模块级可变状态与 `fx/core.js` 约定相抵 | 在 `fx/core.js` 头部补**显式例外条款**（唯一一处 `let`、理由：同步就地校验需要调用点生效） |
| `create_code_entry` 补口是用户可见契约变更，spec 未列 | 已记入本票与 `CONTEXT.md`；写进 spec「实现决策 一」的对应条目 |
| webapp docstring 半角冒号 | 改回中文全角 |

**测试结果（整改后）**：`python -m pytest -n auto` **全绿**；
`node --test "tests/js/*.test.mjs"` **1691 passed**（含新增 3 条：下发反斜杠、UI 装载守卫、
复装口径）。
