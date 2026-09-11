# 01 — 生成期 syscfg 引脚冲突门禁：撞脚的工程不再产出（mspm0）

**要做什么：** mspm0 生成前把「写侧将要落盘的 `mspm0.syscfg`」在内存里算出来
（母版 → 按选中模块 prune → 按用户绑定 rewrite，与写侧同一条 pipeline），按 `$assign`
引脚分组：**同脚多实例 = 冲突** → 写盘前 400 中文，逐脚列出「引脚 + 双方实例/消费模块/
角色」+ 两条出路（改绑这些角色或点「自动配置」／去掉冲突模块中的一个）。

真机现场（`.scratch/real-run/verify-16-A8-mspm0-2026H-buildlog.txt`）：2026H / mspm0 的
13 模块组合生成成功、CCS 编译 exit=2、SysConfig 报 7 条 `Resource conflict`。只读探针
（`.scratch/pin-conflict-gate/probe-01-red.py`，零额度）复算 prune 后同脚多实例 =
**恰好那 7 条**：PA7 / PA13 / PA22 / PA27 / PA28 / PA31 / PB18。

**被谁阻塞：** 无（可立即开始）。

**状态：** resolved

## 落地记录（本轮）

- **判据**：`generator._check_syscfg_pin_conflicts` + `_syscfg_role_labels`（`generator.py`）；
  语料新增 `ModuleCorpus.master_syscfg`（`_read_syscfg_text`：生成路径读母版、产物复核读
  产物树、非 mspm0 = None）；门禁表加 `syscfg_pin_conflicts`（排 `pin_bindings` 之后）；
  新错误类 `SyscfgPinConflictError` 登记 `errors.py` → 400。
- **角色标签取「裁剪后、改写前」的那份模型**：GPIO 组角色路径只带实例名（`DC_MOTOR.associatedPins[3].pin`），
  一个实例下多条落点要用「现脚 == 声明默认脚」消歧——改写会改掉现脚，所以消歧必须在改写前做；
  路径本身不随改写变（adc 除外，adc 换通道会换槽位名，此时如实报路径不猜角色）。
- **红证**：`probe-01-red.py`（只读探针）复算真机组合 = 7 条同脚多实例，逐脚对上真机日志
  （`verify-01-red.txt`）；改前 `GENERATION_GATES` 无任何 syscfg 引脚判据（生成成功、编译才炸）。
- **落地后真机**：
  - 进程内（不经 webapp）：`probe-02-real-machine.py` 复用真实推荐缓存
    （`cache/recommend_2026H.json` 12 模块）跑 `generator.generate` → 生成前抛
    `SyscfgPinConflictError`，7 个脚 + 逐个角色名，**输出目录未产生**
    （`verify-02-real-machine.txt`）；
  - HTTP 路径（工单原验收命令）：`generate_check.py --platform mspm0 --reuse-recommend 2026H`
    → `/api/generate` **HTTP 400** 带同一份 7 条清单（`verify-01-real-machine-generate-check.txt`）。
    注：脚本既定行为会先「清场」删旧产物树 `out_2026H_mspm0`——现场形态证据仍在
    `verify-16-A8-mspm0-2026H-buildlog.txt` + 推荐缓存 + `verify-17-A8-mspm0-2026H-verdict.txt`。
- **测试**：`tests/test_generator.py` 新增 6 条（红证 / 单对不假阳性 / 合法共享与单选不误伤 /
  平台与缺 syscfg 跳过 / 绑定两向 / 产物复核现值）+ 门禁表钉死 13→14 键；
  `tests/test_errors.py` 新错误类契约条。全量 `pytest` **3987 passed**、
  `node --test tests/js/*.test.mjs` **1444 pass**、`mypy` 两文件零问题。

## 修复方向（实施会话定措辞，红证先行）

1. **判据不新写**：`syscfg_model.parse_syscfg(text)` → `.prune(选中集)` →
   `.rewrite(resolved)`，然后按 `assigns[].pin` 分组，`len({实例}) > 1` 即冲突。
   实例名 = `assign.path` 的第一段（`DC_MOTOR.associatedPins[3].pin` → `DC_MOTOR`）。
2. **语料补字段**：`ModuleCorpus.master_syscfg: str | None`——
   - 生成路径（`build_module_corpus`）：读 `master_project_dir / MSPM0_SYSCFG_FILENAME`；
     非 mspm0 / 文件不存在 = `None`；
   - 产物复核路径（`build_output_tree_corpus`）：读产物树同名文件（已 prune/rewrite 过）。
   门禁继续「吃语料、不各自读盘」。
3. **谓词语义**：`platform != mspm0` 或 `master_syscfg is None` → 直接返回；
   `manifests` 为空（`generate_check.py` 现状 `run_generation_gates(corpus, [], platform)`）
   → **不 prune、不 rewrite**，直接判语料现值（空 manifests 下 prune 会把实例全裁掉 →
   判据静默失明，这条要有测试钉住）。
4. **表位置**：`GENERATION_GATES` 加 `GenerationGate("syscfg_pin_conflicts", ...)`，排在
   `pin_bindings` 之后（绑定先通过校验，`resolve_bindings` 才不会抛）；谓词签名 4 参，
   绑定取 `GateContext`（与 `_check_pin_bindings` 同款 `resolve_bindings` 调用）。
5. **新错误类**：`SyscfgPinConflictError(GeneratorError)`（中文 message），`errors.py`
   登记 400——结构测试反射枚举会强制登记。
6. **文案**：逐脚一行，例如
   `PA7：motor（DC_MOTOR.associatedPins[3].pin，角色 motor.BIN2）与 servo（SERVO_PWM.peripheral.ccp0Pin，角色 servo.SERVO_PWM_C0）`；
   末尾指路「在引脚配置里改绑这些角色（或用「自动配置」一键解开），或去掉其中一个模块」。

## 文件边界

- `src/contest_generator/generator.py`（`ModuleCorpus` 字段 + 新谓词 + `GENERATION_GATES`
  表一条；`build_module_corpus` / `build_output_tree_corpus` 各读一次 syscfg）
- `src/contest_generator/errors.py`（登记新错误类 → 400）
- 判据实现放 `syscfg_model.py` **仅当**需要新纯函数（如「同脚多实例分组」）——查重逻辑
  若能在谓词内三行写完就不加函数（防平行实现）
- `tests/test_generator.py`（门禁段：红证 / 对照 / 空 manifests / stm32 跳过 / 绑定参与）
  + 必要的 `tests/test_errors.py` 契约行
- 前端**不改**（400 文案走既有错误通道）

## 验收标准

- [x] 红证：真机 13 模块集（`out_2026H_mspm0/.contest_context.json` 的 slugs）+ 真母版
      `mspm0.syscfg` → 门禁抛 `SyscfgPinConflictError`，错误里出现的引脚集合**恰为**
      {PA7, PA13, PA22, PA27, PA28, PA31, PB18}（与真机日志 7 条逐脚对上）
- [x] 对照不假阳性：只选 `motor + servo` → 只报 PA7；只选 `motor` → 不报；
      `huidu + pid`（同一 syscfg 器件实例 = 合法共享）→ 不报；stm32 → 跳过
- [x] 绑定参与判据：把 `motor.BIN2` 显式绑到别的空闲脚 → 该脚冲突消失（证明 rewrite 在判据里）
- [x] 产物复核形态：`manifests=[]` → 不 prune/不 rewrite，判语料现值（不假红也不失明）
- [x] `errors.py` 契约：新错误类 → HTTP 400 + message 原文到用户眼前
- [x] 真机：`python .scratch/real-run/generate_check.py --topics-dir library\topics
      --modules-dir library\modules --platform mspm0 --reuse-recommend 2026H`
      ——**生成前即拦**（不再产出编译 exit=2 的工程），错误信息逐脚可读
- [x] 全量 `pytest`（3987 passed）+ `node --test tests/js/*.test.mjs`（1444 pass）绿

## 不做什么（范围外）

- 不动 stm32 的默认×默认口径（ADR 0010「同引脚多角色允许、提示不拦」）。
- 不管多实例渲染新增实例（`render_instances` 在门禁之后跑，`LED_<n>` 之类本期不覆盖）。
- 不自动改用户请求（本单只拦；一键消解是 02）。
- 不改库内默认脚、不引入 AI 判断。
