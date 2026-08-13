# 01 — generate_check --reuse-recommend：推荐结果跨运行缓存

**What to build:** `generate_check.py` 每次真实推荐 done 后把 done 载荷全量落缓存 json；加 `--reuse-recommend` 时跳过 `/api/recommend` SSE 段（推荐流单题 ~10-15 min，占回归 90%），直进骨架/生成/编译。回归场景（验证修复循环、编译链路）推荐结果稳定，缓存完全够用；全流程抽查不带该 flag 即可。纯 CLI 侧改动，**不动 src**。

**Status:** claimed

**Blocked by:** gen-check-fix-loop/01 合 main（同文件 `.scratch/real-run/generate_check.py`，避免共享检出竞态 / 合并冲突——对方重跑收尾后再开工，开工前先拉 main）。

## 现状证据（2026-08-13 真机实测，并行会话 run1）

- 一次双题回归 ≈ 30-40 min，大头 = 推荐流每次运行都全量重付真实 LLM 调用（单题 ~10-15 min），没有缓存。
- `generate_check.py` 已有 `recommend_stream`（SSE 消费）→ done 载荷（modules / requirements / references / topic_id）→ 骨架 → 生成 → 编译的全链路；缓存只需包住推荐段。
- 真机教训：推荐 SSE 流分钟级，日志提前打 200 勿误判挂起急杀（与缓存无关但开工前须知）。

## 决策记录（代决，用户可 grilling）

1. **缓存内容** = 推荐 done 载荷全量（modules+reasons / requirements / references / topic_id），另存题面指纹与 topic key。骨架**不缓存**——修复循环需要真实 main_c（1-2 min 保留）。
2. **缓存键**：topic_id 优先；无 topic_id 用题面 sha256。
3. **缓存位置**：`.scratch/real-run/cache/recommend_<key>.json`，**补 .gitignore**（.scratch 在 git 内，缓存必须忽略——`git status` 干净是既有验收项）。
4. **`--reuse-recommend` 语义**：缓存命中 → 跳过推荐段直进骨架；缓存缺失 → **报错退出**（不静默回退真实调用——回归确定性优先，防止"以为复用了其实又烧了 15 min"）。
5. **默认行为不变**：不带 flag = 真实推荐 + 写缓存（写失败不阻断主流程，打印警告即可）。
6. **范围外**：骨架缓存、src 改动、缓存失效策略（题面变 → 指纹变自然失效；显式删除缓存文件即可重推）。

## 实施

1. **`.scratch/real-run/generate_check.py`**：
   - `recommend_cache_path(...)`：键 → 缓存文件路径（目录可由环境变量 / 参数覆盖，测试注临时目录）。
   - `cache_recommend(...)` / `load_recommend(...)`：纯函数读写（json 落盘 / 读回 + 形状校验）。
   - `--reuse-recommend` 参数：`check_topic` 推荐段分流——命中读缓存进下游，缺失打印"缓存不存在：<path>（先跑一次不带 --reuse-recommend 生成缓存）"并退出非零。
2. **`tests/test_generate_check_contract.py`**：缓存纯函数测试（tmp_path 注入：写→读回形状全等；坏 json / 缺字段拒绝）+ flag 行为契约（命中跳过推荐段 / 缺失报错）。沿用既有契约测试机制（词表断言 / payload 字段集双强制先例）。
3. **`.gitignore`**：补 `.scratch/real-run/cache/`。

### 实施注

- 缓存 json 结构 = done 载荷逐字（下游 selectedSlugs / expand / generate 零改动语义——CLI 内 consumption 变量对齐 `recommend_stream` 返回的 done 即可，别发明新形状）。
- 真机验证时注意：generate_check 不清理旧 out 目录需先删（既有教训）。

## 验收标准

- [ ] pytest 全绿（含契约测试新增）+ `mypy src` 干净（CLI 脚本不在 mypy src 范围）
- [ ] 真机：真实 2026C 全流程跑一次（写缓存）→ `--reuse-recommend` 重跑：推荐段秒过、UV4 0 错、两次用时对比写进 Comments
- [ ] 真机：缓存缺失时 `--reuse-recommend` 报错退出（非零码 + 可操作文案）
- [ ] `git status` 只出现预期文件（generate_check.py + 契约测试 + .gitignore + 本工单文件），缓存目录不出现

## Comments
