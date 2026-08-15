# 骨架生成升级：自检冒烟 + 参考实现进骨架——功能规格

> 2026-08-15 grilling 定稿（用户逐轮确认："其他的都按你推荐的来"+ Q4 改 OLED 为主）。

## 愿景

学生拿到的 main.c 从"能编译的 TODO 空壳"升级为"先能自检、再能抄参考"：
1. **自检冒烟模式**——一键生成只做"初始化每个模块 → 读一次/动一次 → OLED/串口打印结果"的 main.c，学生先把硬件通路确认掉，再进入写逻辑阶段。
2. **参考实现进骨架**——正常骨架生成时，把锚定 + 手动选的参考文件全文喂给 LLM，参考里有的功能改写为适配当前模块接口的草稿实现，参考里没有的保持 TODO。

## 决策（grilling 定稿）

1. **独立模式**：步骤 8 放两个按钮「生成骨架」「生成自检骨架」，各自覆盖同一个 main.c 文本框；两阶段目标不同（先验硬件、再写逻辑），不合一。
2. **参考注入范围**：锚定参考（选历史赛题自动命中）+ 手动勾选参考都注入；复用 `TopicContext` / `resolve_topic_context` 装配语义（平台过滤、手动强意图、幻觉 id 大声失败）。
3. **参考实现草稿用法**：prompt 明确要求"参考里有的功能 → 改写为适配当前模块接口的草稿实现；参考里没有的 → 保持 TODO"——可预测、可验收，不产生"不可编译缝合怪"。
4. **自检输出通道（用户定）**：**OLED 为主、串口为辅**——选中 `oled` 模块时初始化 OLED 并逐段打印自检结果；选中 `debug_uart` 时串口同步回显；两者都没选 → 自检骨架请求 400 中文（"自检骨架需要 OLED 或 debug_uart 模块"）。车跑起来看 OLED，不拖串口线。
5. **自检粒度**：全部选中模块逐段自检（初始化 → 读一次/动一次 → 打印结果）；模块无当前平台版本 → main.c 留注释"该模块无 stm32/mspm0 版本，未自检"，与生成门禁语义一致。
6. **工单拆分**：两个工单串行——`01` 自检冒烟；`02` 参考实现进骨架。都碰 `/api/skeleton`，串行避免互踩。
7. **测试接缝（TDD 公开边界）**：
   - `skeleton.generate_smoke_main(llm, ...)` — 自检 main.c 生成入口
   - `skeleton.generate_skeleton(..., reference_fulltexts=None)` — 参考实现草稿注入
   - `webapp /api/skeleton` 增加 `main_mode`（skeleton | smoke）与 `reference_ids` 透传
   - 前端步骤 8 两个按钮 + 步骤 4 选中参考 ids 传给骨架路由

## 数据契约

### `/api/skeleton`（既有路由扩展）

请求体：

```json
{
  "problem_text": "…",
  "platform": "stm32",
  "slugs": ["motor", "oled", "pid"],
  "topic_id": "2026C",
  "reference_ids": ["ref-001", "ref-002"],
  "main_mode": "skeleton"
}
```

- `main_mode`：`"skeleton"`（缺省，现行为）| `"smoke"`（自检冒烟）。
- `reference_ids`：可选，手动选参考文件 id 列表；缺省 = 现行为（零参考）。装配走 `resolve_topic_context(..., reference_ids=reference_ids, platform=platform)` 同款语义——锚定 ∪ 手动，平台过滤，幻觉 id / 重复 id 大声失败。
- 返回不变：`{"main_c": str, "intercepted": [str]}`。

### `generate_smoke_main`

```python
def generate_smoke_main(
    llm: LLM,
    problem_text: str,
    manifests: Sequence[ModuleManifest],
    platform: str,
    library_dir: Path,
    master_project_dir: Path | None = None,
) -> tuple[str, tuple[str, ...]]:
```

- 行为 = `generate_skeleton` 的冒烟变体：接口块同源（`build_skeleton_interfaces`）；LLM 出稿 → `sanitize_skeleton` 静态自检兜底。
- prompt 要求：OLED 为主（若选中 oled）串口为辅（若选中 debug_uart）；每个选中模块一段自检；只自检不写题逻辑。
- 输出通道校验在 webapp 层（400），不在 skeleton 纯函数层（保持纯函数可内存直测）。

### `generate_skeleton` 扩展

```python
def generate_skeleton(
    llm, problem_text, manifests, platform, library_dir,
    master_project_dir=None,
    reference_fulltexts: Mapping[str, str] | None = None,
) -> tuple[str, tuple[str, ...]]:
```

- `reference_fulltexts`：`{参考文件 id: 全文}`；`None`/空 = 现行为逐字节不变（prompt 不加参考段）。
- prompt 增加参考段（每条带 id 标注 + 截断预算），并加约束 3 的改写规则。

## 前端

- 步骤 8：`btn-skeleton` 旁加 `btn-smoke`「生成自检骨架」；共用 `main-c` 文本框与 `intercepted` 提示；按钮禁用逻辑与现「生成骨架」一致（题面/平台/模块齐备）。
- 步骤 4 已勾选的参考 id 随骨架请求发送（`reference_ids`）；自检请求不带参考（自检不写题逻辑）。
- 自检请求 400 文案直接显示在 `skeleton-msg`。

## 工单链（按序，串行）

| # | 工单 | 内容 |
|---|---|---|
| 01 | `.scratch/skeleton-smoke-refs/issues/01-smoke-self-test.md` | `generate_smoke_main` + `/api/skeleton` `main_mode` + 输出通道 400 + 前端按钮 |
| 02 | `.scratch/skeleton-smoke-refs/issues/02-reference-drafts-in-skeleton.md` | `generate_skeleton` `reference_fulltexts` + `/api/skeleton` `reference_ids` + prompt 扩展 + 前端透传 |

## 关键事实（grilling 调查，实施会话必读）

- `/api/skeleton`（webapp.py:645-669）当前只调 `generate_skeleton`，docstring 写明"骨架阶段不注入参考文件……等真实用例再评估"——本 spec 就是那个真实用例。
- `generate_skeleton`（skeleton.py:377-397）无参考参数；接口块 = `build_skeleton_interfaces(manifests, platform, library_dir, master_project_dir)`；自检 = `sanitize_skeleton`。
- `TopicContext`（generator.py:185-205）已含 `references` / `manual_references` / `manual_fulltexts` / `read_fulltext`；`resolve_topic_context(..., reference_ids, platform)` 已实现手动准入 + 锚定 + 平台过滤 + 手动全文直读——工单 02 复用它即可，不新造。
- `llm.generate_main_skeleton(problem_text, module_interfaces)` 是协议方法；`DeepSeekLLM.generate_main_skeleton`（llm.py:836-844）调 `_skeleton_user_prompt(problem_text, module_interfaces)`（llm.py:1946）——扩展 prompt 的落点在 `_skeleton_user_prompt` 或新增冒烟 prompt，双端（协议 + 实现 + FakeLLM）同步。
- `debug_uart` 模块两平台都有；`oled` 模块两平台都有（stm32 实现内嵌母版 ml_oled、mspm0 有 code/oled.c 未上板）——OLED 为主在两平台都成立。
- 前端步骤 4 参考勾选 state 在 `index.html`（参考资料卡片），骨架请求在 `btn-skeleton` 点击处理（index.html:2095-2118）——工单 01/02 都要动这里。
