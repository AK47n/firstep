# 02 — 参考实现进骨架（锚定 + 手动全文注入 prompt）

**What to build:** `generate_skeleton` 加可选 `reference_fulltexts: Mapping[str, str] | None`——非空时在骨架 prompt 里加参考段（每条 id 标注 + 截断），并明确约束"参考里有的功能 → 改写为适配当前模块接口的草稿实现；参考里没有的 → 保持 TODO"；`/api/skeleton` 加 `reference_ids` 透传（复用 `resolve_topic_context` 装配，锚定 ∪ 手动 + 平台过滤 + 幻觉 id 400）；前端步骤 4 勾选的参考随骨架请求发送。

**Blocked by:** 01（都碰 `/api/skeleton` 与步骤 8 按钮区）

**Status:** pending

## 需求

1. **`skeleton.generate_skeleton(..., reference_fulltexts=None)`**：签名扩展；`None`/空 = 现行为逐字节不变（不追加参考段）。非空时组装参考段喂给 LLM（每条 `### 参考资料 <id>` + 全文截断；截断复用 `library.truncate_content` 或同源预算，避免撑爆 128KB 网关）。
2. **`llm` 协议与实现扩展**：`generate_main_skeleton(problem_text, module_interfaces, reference_fulltexts=None)`（或同源变体）——协议、`DeepSeekLLM`、`FakeLLM` 三端同步；`_skeleton_user_prompt` 加参考段与改写约束。
3. **`webapp /api/skeleton` 扩展**：请求体加可选 `reference_ids: [str]`；装配走 `resolve_topic_context(..., reference_ids=reference_ids, platform=platform)`——拿到 `topic.references`（锚定）与 `topic.manual_fulltexts`（手动直读），再按锚定 id 回读全文（`topic.read_fulltext`），合并为 `reference_fulltexts` 传 `generate_skeleton`。幻觉 id / 重复 id / 查无此条照旧大声失败；`skeleton` 与 `smoke` 两个模式都接受该参数，但 smoke 模式下 prompt 不使用（或 smoke 分支不传）。
4. **前端步骤 4 → 步骤 8 透传**：生成骨架请求体带步骤 4 已勾选参考的 `reference_ids`（自检骨架请求可带可不带——v1 不带，自检不写题逻辑）。
5. **测试（红证先行）**：
   - `tests/test_skeleton.py`：FakeLLM 收到 reference_fulltexts → prompt 含参考 id 与改写约束；空/None → prompt 与现行为逐字节一致（零回归）。
   - `tests/test_llm.py`：三端签名同步 + prompt 参考段结构钉。
   - `tests/test_webapp.py`：`reference_ids` 透传 → 生成 main.c 的 LLM 收到全文；幻觉 id 400；重复 id 400；缺省零参考回归。
6. **真机**：2024H 巡线题（有锚定参考）生成骨架 → 出稿含参考里的路口检测草稿且 UV4 0 错 0 警；不传 reference_ids 回归 == 01 后现状。

## 文件边界

- `src/contest_generator/skeleton.py`、`src/contest_generator/llm.py`、`src/contest_generator/webapp.py`
- `src/contest_generator/static/index.html`（步骤 4 勾选透传）
- `tests/test_skeleton.py`、`tests/test_llm.py`、`tests/test_webapp.py`、`tests/fakes.py`

## 验收

- [ ] pytest 全绿 + mypy src 干净
- [ ] 红证已验（无参考零回归 / 幻觉 id 400 / 重复 id 400）+ 绿证（prompt 含参考段 + 改写约束 + FakeLLM 收到全文）
- [ ] 真机：2024H 锚定参考进骨架 UV4 0 错 0 警 + 缺省回归
- [ ] 提交（post-commit 钩子自动补 CHANGELOG）

## Comments
