# 01 — 上传暂存域落域（stage.py：三层知识单源）

**What to build:** 未提交的 /api/masters/stage 端点在路由里内联一个迷你暂存域——路径穿越检查（webapp.py:713，与 entry_store.is_unsafe_path 规则集分歧：漏空段拒绝）、.git 跳过（treewalk 忽略集真子集）、目录名清洗、512MB 上限、staged 位置推导全在路由内；规则三处分歧且 HTTP 外不可测。本工单把暂存语义收进新叶子模块 stage.py，webapp 只收参数转调，校验吃既有单源。

**Blocked by:** 无

**Status:** resolved（2026-08-09 已合 main PR #29）

## 需求

1. **新建 `src/contest_generator/stage.py`（上传暂存域，叶子模块：依赖 entry_store + treewalk，零业务库）**：
   - `staged_root(masters_dir: Path) -> Path`：纯推导 = `masters_dir.parent / "staged"`
   - `stage_project_files(masters_dir: Path, files: Iterable[tuple[str, bytes]]) -> Path`：返回暂存目录路径（`staged/<原名>`），逐条保留现状行为与文案：
     - **穿越拒绝**：rel 先 `replace("\\", "/")` 归一，再走 `entry_store.is_unsafe_path` 单源（行为变化：空段 `a//b` 从放行变拒绝——浏览器畸形路径大声失败）
     - **目录名清洗**：parts[0] 逐字符白名单（isalnum + `-_. `），空回退 `"upload"`（现状逐字）
     - **噪音跳过**：任意深度 `".git" in parts`（版本库不进母版素材，现状保留）+ `treewalk.skip_project_noise("/".join(parts[1:]))`（Debug/Release/Listings/Objects 顶层——与扫描侧 iter_project_files 同规则；**注意 skip_project_noise 契约 = 项目根相对路径，上传路径首段是文件夹名，必须剥除后传**）
     - **上限**：`STAGE_MAX_TOTAL_BYTES = 512 * 1024 * 1024` 常量，超限报错文案不变（"文件夹过大（超过 512MB），请只选择工程源码目录"）
     - **空文件清单**：报错文案不变（"没有收到任何文件（选择文件夹后浏览器会逐文件上传）"）
   - 错误类型 `StageError(ValueError)`，文案逐字 = 现端点 HTTPException 文案
2. **webapp.py `masters_stage` 瘦身**：读 UploadFile → `[(f.filename, await f.read()) ...]` → 调 `stage_project_files` → 返回形状不变 `{"staged": [{"path": str(dir), "name": dir.name}]}`；@_map_errors 保持不变
3. **errors.py**：`StageError` 登记 `_ERROR_TABLE`（400, str）——结构反射测试（tests/test_errors.py）自动兜住，白名单不含
4. **CONTEXT.md** 词表补「上传暂存」词条（与 master.py 蒸馏预览暂存 mkdtemp 区分命名，实现列 = stage.py）

## 文件边界

- 新增 `src/contest_generator/stage.py`
- `src/contest_generator/webapp.py`：masters_stage 路由瘦身 + import stage（路由 docstring 同步噪音跳过说明）
- `src/contest_generator/errors.py`：登记 StageError
- 新增 `tests/test_stage.py`：穿越六态（`..` / `../x` / `/abs` / `C:/x` / `a//b` 空段 / 前导 `/`）+ 名称清洗（非法字符 / 空回退）+ 噪音跳过（顶层 .git/Debug/Release/Listings/Objects、任意深度 .git、保留目录仍落盘）+ 上限 + 空清单 + 落盘实况 + staged_root 推导
- `tests/test_webapp.py`：stage 路由一条（multipart 合法上传 → 200 形状；穿越 → 400 中文）
- `CONTEXT.md`：上传暂存词条
- 注意：stage 端点在途未提交（与参考库体量字段 entry_stats 同批在途），本工单在其上叠加或先独立提交，不混批

## 验收

- [ ] 全量测试绿 + mypy 干净
- [ ] 结构自证：grep webapp 无穿越检查 / ".git" 跳过 / 上限内联（三层知识只剩 entry_store.is_unsafe_path + treewalk.skip_project_noise 两个单源）
- [ ] 路由行为逐字不变（文案 + 返回形状 {"staged": [...]}）
- [ ] 单测覆盖六态穿越 + 噪音 + 上限 + 空清单
- [ ] tests/test_errors.py 反射测试含 StageError（400，非白名单）
- [ ] CONTEXT.md 上传暂存词条
- [ ] 独立 worktree + 独立 commit，工作区其他未提交修改不混入

## Comments

- 2026-08-09 立项（架构评审 2026-08-09 候选 2，grilling 决策树，用户授权代决）：① 落点 = 新叶子模块 stage.py（非 master_store——暂存不是母版库 CRUD；删除测试：删 stage.py 语义弹回 HTTP 层，集中 = 值得）；② 穿越校验归 entry_store.is_unsafe_path（唯一行为变化：空段从放行变拒绝）；③ 噪音跳过 = 任意深度 .git（现状保留）+ skip_project_noise 剥首段复用（新扩展：构建产物顶层上传即跳过——5.7GB 工程不再撞 512MB 上限，与「残留不进母版」哲学一致）；④ 上限 / 文案 / 返回形状全保留；⑤ StageError 登记 errors.py 400（反射测试兜底）
