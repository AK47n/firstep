# spec — 生成期引脚冲突：拦下 + 一键消解（mspm0 syscfg）

## 问题陈述

用户按 AI 推荐选好模块、点「生成」，工程顺利产出，然后在 CCS 里编译 → SysConfig 报
7 条 `Resource conflict`，exit=2。用户此时看到的是一堆「PA7/31 is currently in use by
L298N」——问题在**生成时才暴露**，而它其实在生成前就完全确定：

- 母版 `mspm0.syscfg` 是「全量实例 + 同选概率最低者重叠」的默认布局，生成时按选中模块
  `prune`，**选中的两个模块若默认脚相同**（如 `motor` 的 BIN2 与 `servo` 的 C0 都默认
  PA7），落盘的 syscfg 就是两只实例抢一脚 —— SysConfig 必然拒绝。真机现场：2026H 的
  13 模块组合，prune 后同脚多实例**恰好 7 条**，与真机日志的 7 条逐脚对上
  （PA7 / PA13 / PA22 / PA27 / PA28 / PA31 / PB18）。
- 生成侧现在**没有任何门禁**看这件事（`GENERATION_GATES` 里没有 syscfg 引脚判据）；
  引脚卡虽然对这些脚标了 ⚠「物理冲突」，但那是提示语义、不拦生成。
- 用户点「自动配置」想一键解决也**没用**：`auto_assign_bindings` 只修**显式绑定**的角色
  （`resolve_bindings` 只校验传入的绑定），而这类冲突双方都是**未绑的默认脚** →
  实测增量与 fixed 都是空（`.scratch/pin-conflict-gate/verify-01-red.txt` ③ 段）。

这直接违背产品最核心的承诺：「打开的工程就能编译」。

## 方案

两件事，按顺序落地：

1. **生成前拦下**（拦在写盘前，产出 400 中文）：判据 = 把「写侧将要落盘的 syscfg」在
   内存里算出来（母版 → 按选中模块 prune → 按用户绑定 rewrite，与写侧同一条 pipeline），
   按 `$assign` 引脚分组，**同脚多实例 = 冲突**（与 SysConfig 自身判据同构）。错误信息
   逐脚列出「引脚 + 双方实例/消费模块/角色」，并指明两条出路：在引脚配置里改绑这些角色
   （或点「自动配置」）／去掉冲突模块中的一个。
2. **让「一键自动配置」真能解这类冲突**：`auto_assign_bindings` 增加一相「默认脚冲突
   消解」——对同脚冲突组确定性地让**一个**角色让位（选中清单里靠后的模块先让位），
   移到能力匹配且不制造新冲突的空闲脚；合法共享（同一 syscfg 器件实例等）一律不动。
   端点与载荷形状不变（仍是 `{ok, bindings, fixed, shared}`），前端零改动。

## 用户故事

1. 作为做题的学生，我希望选完模块点「生成」时就被明确告知「这几个脚撞了、撞在哪两个
   模块之间」，以便我不用打开 CCS 才发现工程编不过。
2. 作为做题的学生，我希望在引脚配置卡点一次「自动配置」就真的把这几个撞脚的冲突解开
   （而不是按钮按下去什么也没变），以便我不用逐个人工挑脚。
3. 作为做题的学生，我希望系统只动「撞了的那几个脚」，我手填过的绑定与合法的共享
   （灰度 8 路共一个器件实例之类）不要被改。
4. 作为做题的学生，我希望改完绑脚后重新生成能通过（同一个判据告诉我「现在没问题了」），
   以便我知道可以进下一步（骨架/编译）。
5. 作为 agent（真机验收），我希望这个判据在生成路径与「产物复核路径」是同一条实现，
   以便我用 `generate_check.py` 复核产物时看到的就是生成时的判断，不会两边各有一套。
6. 作为维护者，我希望判据只来自 syscfg 文件模型（`$assign` 引脚的唯一解析方）与
   `pin_bindings` 的共享/冲突判定，不再新写正则或第二套同脚判据。

## 实现决策

- **判据单源**：`syscfg_model.parse_syscfg` 的一次解析产物（`lines` / `instances` /
  `assigns`）→ `prune(选中集)` → `rewrite(resolved)` —— 与 `pinwriter.apply_pin_bindings`
  的写侧 pipeline **同一条**。同脚多实例 = 冲突；同一实例内的多个落点不算。
- **语料补一个字段**：`ModuleCorpus.master_syscfg`（生成路径 = 母版 `mspm0.syscfg` 原文；
  产物复核路径 = 产物树现值，已 prune/rewrite 过；该平台无此文件 = `None`）。门禁保持
  「吃语料、不各自读盘」的不变量。
- **产物复核路径的语义**：`run_generation_gates(corpus, [], platform)`（`generate_check.py`
  现状）——`manifests` 为空 = 无选中集知识 → 不 prune、不 rewrite，直接判语料里的现值
  （那正是生成时落盘的结果）。空 `manifests` 下若仍 prune 会把实例全裁掉、判据静默失明，
  这条要写进谓词并有测试钉住。
- **新门禁**：`GENERATION_GATES` 表加一条 `syscfg_pin_conflicts`，排在 `pin_bindings`
  之后（依赖绑定先通过校验，`resolve_bindings` 才不会抛）；谓词签名与存量一致（4 参）。
- **新错误类**：`SyscfgPinConflictError(GeneratorError)`，在 `errors.py` 登记为 400 中文
  （结构测试反射兜底会强制登记）。
- **不做 role 级第二判据**（A 单）：`pin_bindings._shared_groups` 的 `kind=conflict` 与
  syscfg 级同脚多实例在这批真机数据上**同集**，但生成期以**文件模型**为准——它与编译
  结果同源；role 级判据在 B 单作为**求解判据**使用（消解后要能通过 A 的拦检）。
- **B 单消解规则**（确定性，无模糊判断；★ = 真机探针跑出来的修正，规格初稿没写对）：
  - 输入 = 选中 manifests + 现有 bindings；冲突组来自 `_shared_groups`（`kind=conflict`）。
  - **缺省关，端点显式开**（★）：全库默认布局本身就是「全量实例 + 同选概率最低者重叠」
    （mspm0 27 组 / stm32 26 组刻意重叠）——库级 / 纯校验调用方把它们当「要解的冲突」
    是无意义的；只有生成页引脚卡（`/api/bindings/auto`）拿到的是**本次选中集**。
    故 `auto_assign_bindings(..., resolve_default_conflicts=True)`，端点传 True。
  - 让位方 = 该组成员所属模块在选中清单里**靠后**的那个角色（同模块内按 role_key 序），
    且**未被用户显式绑定**（用户明确选择只标注不搬；组内全是显式绑定 → 整组不动）；
    **按偏好序逐个试**（★：UART TX/RX 这类成对角色单搬一个过不了成对校验，得让另一侧
    让位——只钉第一个候选会在真机留下解不掉的两组）。
  - 候选脚 = 板定义引脚序里「**空闲**（本次选中集内没有别的角色落脚，含合法共享的同伴
    ★——同一实例的三条落点挤一个脚是接线错）+ `resolve_bindings` 试绑合法 + 搬完该角色
    不再出现在任何冲突组 + 不把冲突搬到别处」的首个脚。
  - 无候选脚 = 该组保留在 `shared` 标注里（前端已渲染 ⚠ + 理由），不吞成成功。
    **结构性不可实现要如实说**（★）：真机那个 12 模块选中集里 4 个空闲脚被一次配置
    全部用掉后仍剩 3 组——母版默认布局的上限使「全模块同选」物理不可实现；这不是算法
    没解，正是 01 的门禁与「去掉冲突模块」这条出路的现实依据。
  - 契约不变：`AutoAssignResult(bindings=增量, fixed=说明行, shared=标注)`；
    `/api/bindings/auto` 载荷形状与前端应用增量的路径零改动。

## 测试决策

- 新增门禁测试（内存直构语料 + 真母版文本做一条真数据回归）：
  - **红证**：真机 13 模块集 + 真母版 `mspm0.syscfg` → 门禁抛错，且错误里出现的引脚集合
    恰为 {PA7, PA13, PA22, PA27, PA28, PA31, PB18}（与真机日志 7 条逐脚对上）。
  - **对照**：只选 `motor + servo` → 只报 PA7；只选 `motor` → 不报；`huidu + pid`
    （同一 syscfg 器件实例，合法共享）→ 不报；stm32 → 跳过。
  - **绑定参与判据**：把 `motor.BIN2` 显式绑到别的脚 → 该冲突消失（证明 rewrite 在判据里）。
  - **产物复核形态**：`manifests=[]` → 不 prune、判现值（不做假红/失明）。
  - `errors.py` 表驱动契约：新错误类 → 400 且 message 原文保留（沿用既有端到端先例）。
- B 单测试（`tests/test_pin_bindings.py` 先例，纯函数直构）：真机 13 模块集上
  `auto_assign_bindings(..., {})` → 增量非空、每个 conflict 组只剩一个角色；
  解完后用**门禁判据**复算 = 无冲突（两单互相钉住）；合法共享（huidu/pid 的 6 个脚）
  逐条不动；让位方选择对清单顺序确定（换序 → 让位方随之改变）；无解时不假绿。
- 真机（本机工具链在盘）：`generate_check.py --platform mspm0 --reuse-recommend 2026H`
  —— 现状产出 exit=2 的工程；A 落地后**生成前即拦**（不再产出编不过的工程）；B 落地后
  用 `--bindings`（`auto_assign_bindings` 的产出）再生成 → SysConfig + gmake 0 error。

## 范围外

- **stm32 默认脚冲突**：ADR 0010 的「同引脚多角色允许、默认×默认不查、前端提示」不动；
  本期只治 mspm0（SysConfig 会硬拒绝、真机已验证失败的那条线）。
- **多实例渲染新增实例的引脚**：`render_instances` 在门禁**之后**跑（led 多实例新增
  `LED_<n>` 实例），其引脚冲突本期不覆盖——留后续候选（需把实例计划纳入语料）。
- 不改库内默认脚分配（默认布局是 manifest 事实）；不做模糊/AI 消解（全部确定性求解）。
- 前端不改（400 文案走既有通道；自动配置按钮已消费同一载荷形状）。

## 补充说明

- 现场证据：`.scratch/pin-conflict-gate/verify-01-red.txt`（只读探针 `probe-01-red.py`，
  零额度）——① 真机 13 模块集 prune 后 7 条同脚多实例，逐脚对上真机日志；② `motor+servo`
  对照只剩 PA7；③ `auto_assign_bindings(空 bindings)` 增量/ fixed 皆空（按钮无效的实测）。
- 真机日志原文：`.scratch/real-run/verify-16-A8-mspm0-2026H-buildlog.txt`；产物树：
  `.scratch/real-run/out_2026H_mspm0/`（含 `.contest_context.json` 的 slug 集）。
