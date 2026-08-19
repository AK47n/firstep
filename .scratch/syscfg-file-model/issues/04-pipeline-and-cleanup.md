# 04 — 单一 pipeline + 收尾 + CONTEXT.md（cleanup）

**What to build:** generator 由 prune-then-apply 两步改为调用文件模型单一 pipeline（prune→rewrite 顺序由构造保证）；prune 不再为文件名反向 import pinwriter；删除 syscfg_instances 的旧导入路径 shim 与兼容期冗余；CONTEXT.md 增「syscfg 文件模型」词条。

**Blocked by:** 03

**Status:** resolved

- [x] 一次真实 mspm0 生成的 syscfg 产物与迁移前逐字节一致（产物 diff 或真机验收脚本）
- [x] 全测试套件绿（至少 mspm0 相关 + test_generator）
- [x] syscfg_prune 不再 import pinwriter（文件名常量只从新模块取）
- [x] CONTEXT.md 增「syscfg 文件模型」词条并指向新模块

**Resolution notes:**
- **单一 pipeline**：`pinwriter.apply_pin_bindings` 增 `selected_slugs` 参数（keyword-only、必传——不设默认值，缺省会静默全裁）；mspm0 分支改为一读一解析一写：`parse_syscfg(original).prune(selected_slugs).rewrite(resolved).to_text()`，先后由构造保证，不再靠调用顺序/注释。`generator.generate` 删 `prune_mspm0_syscfg_file` 两步，改单次 `apply_pin_bindings(...)`（条件 `platform == PLATFORM_MSPM0 or resolved_bindings` 保留旧 prune-always/apply-conditional 语义）。stm32 侧零改动。
- **删反向 import 旧环**：`syscfg_prune` 删 `from .pinwriter import MSPM0_SYSCFG_FILENAME`、`INSTANCE_CONSUMERS` re-export（+ `__all__`）与文件挂钩 `prune_mspm0_syscfg_file`（并入 apply_pin_bindings）；只留 `prune_syscfg` 薄委托。`pinwriter` 删 `MSPM0_SYSCFG_FILENAME` 定义、改从 `syscfg_model` import；`instance_render` 同步改指 `syscfg_model`。
- **文件名常量单源**：`MSPM0_SYSCFG_FILENAME` 只定义在 `syscfg_model`（pinwriter 旧定义已删）。
- **CONTEXT.md**：增「syscfg 文件模型」词条（独占文法 + 一次解析 + 槽位身份原语，prune/rewrite 两操作一 serialize）；顺带把「mspm0 实例迁移分级」实现列 `pinwriter.py syscfg 改写器` 改指 `syscfg_model.py`（改写器已迁）。
- **`_LED_BEEP_ASSIGN_RE` 顺带核（03 留痕，属工单边界外——留痕不展开）**：`instance_render._LED_BEEP_ASSIGN_RE` 是多实例 LED 渲染（module-multi-instance/03）专用的 $assign 副本（LED_BEEP 通道 0 落点），不是引脚绑定改写。它配套 `rewrite_syscfg_for_led_instances` 还**追加**新 GPIO 实例块（LED_<实例号>）——文件模型没有「追加实例」操作，收敛它得给模型长 append 原语，属多实例渲染的独立特性，非本工单（单一 pipeline + 清理）边界。留痕：不改、不展开，留待多实例渲染侧自行决定。
- 测试：`test_syscfg_prune` 改从 `syscfg_instances` 直取 `INSTANCE_CONSUMERS`；`test_syscfg_model` / `test_pin_bindings` / `test_pin_unlock_mspm0_same/cross` 的 `MSPM0_SYSCFG_FILENAME` 改从 `syscfg_model` 取；新增结构测试 `test_syscfg_prune_does_not_import_pinwriter`（AST 扫 ImportFrom）与 `test_mspm0_syscfg_filename_single_source_in_model`（pinwriter 源码无定义）。
- 验证：全量 pytest **1715 passed**（较 03 的 1714 +1 = 新增结构测试）+ mypy src 45 文件干净；真机验收脚本对 3 组真实 mspm0 生成（[led]+LED 换脚 / [led,key] 无绑定 / [motor,led]+PWM 换脚）断言产物与旧 `rewrite_syscfg(prune_syscfg(...))` 两步逐字节一致。
