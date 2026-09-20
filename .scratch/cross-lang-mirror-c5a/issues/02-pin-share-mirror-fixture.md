# 02 — pinShareClass 修掉已漂的 adc 分支 + 补生成对拍 fixture

**要做什么：** 同脚多角色的「合法共享 / 物理冲突」分类，前端与后端给出**同一结论**，并且这件事从此
由闸门内的对拍守住。同时修掉今天就存在的漂移：同一 ADC 实例上共读一路模拟量的模块（`adc` / `us016` /
`mq2` 等十几件按设计同读 `ADC12_0` 的 MEM0=PA24）前端判「冲突」、后端判「共享」——用户在角色行被
提示「请改线」，而那根脚改了就是另一条通路。端到端行为：选这些件不再出现「请改线」黄字；往后任意
一侧改了分类判据，pytest 或前端门禁里当场变红并点名场景。

**被谁阻塞：** 无——与 01 互不阻塞（两条判据彼此独立）。

**状态：** resolved

- [x] 前端资源键判据补 `adc` 分支（与 `gpio_out` / `gpio_in` 同路走实例映射，来源与后端同源）；
      `adc` 类型不再落进「无键」分支。
- [x] `pinShareClass` 补「引脚不在板内 → 不标注（`none`）」门控，与后端对板外脚直接跳过的口径一致；
      记录不可达论证（今天 i2c/uart 角色默认脚全在板内）与它以场景表用例形式被钉住。
- [x] 对拍机制落地（照功能组「未选」判据先例的形制）：
      - 场景表**单一出处**在 Python（`tests/test_pin_share_mirror.py`），fixture 生成脚本由它导出；
      - 场景用**真实库内 slug + 平台 + 真实板（pin 名 / 能力 token / 板内与否）+ 实例映射**，
        期望值由后端判据现算，**不手抄**；
      - 两侧规范化成同一形状（`pin`、角色 key 集、`kind`）后逐场景比对，只对账 `kind`
        （原因文案前端自有，不进对拍）；
      - 场景至少覆盖：`adc` 共读同槽（**本轮漂移证据**）、uart 家族同实例共享、i2c 总线多挂共享、
        gpio 同器件实例共享、混合同脚冲突、板外脚不标注、单角色不标注、pwm 等无键类型同脚冲突、
        多角色交集为空判冲突；
      - fixture 生成后 pytest 断言「盘上 fixture == 现算结果」；**测试不自动重写**，漂移即红并提示
        跑生成脚本。
- [x] `tests/js/pin-share-mirror.test.mjs` 读同一份 fixture 复算对拍；红时输出**场景名 + 两侧结论**。
- [x] `tests/js/pin-share.test.mjs` 补两例（函数自身行为）：`adc` 同实例同脚 = 共享；板外脚 = 不标注。
- [x] **红证**（对拍机制真的会红）：临时停用前端 `adc` 分支 → 对拍测试必须变红且点名那个场景；
      恢复后变绿。证据（改动 + 红/绿两次输出）留 `## Comments`。
- [x] `CONTEXT.md` 引脚绑定行补一句：分类判据单源在 `pin_bindings`，前端镜像由对拍 fixture 守卫。
- [x] `python -m pytest` 全绿 + `node --test "tests/js/*.test.mjs"` 全绿；提交信息中文。
- [x] 无行为回归证据：单角色 / 无重叠 / i2c 共享 / uart 同实例 / 既有 6 条 `pin-share.test.mjs` 用例
      全绿（`adc` 分支与板内门控都不得改变既有结论）。

## Comments

### 实现记录（claim → tdd → 对拍）

**对拍机制**（形制照 `tests/test_group_choice_mirror.py`）：

- 场景表单一出处 = `tests/test_pin_share_mirror.py` 的 `CASES`（14 条，真实库内 slug +
  真实板定义 + 真实实例映射；`category` 声明这条钉哪一类结论，供覆盖断言现推）。
- 期望值由后端 `_shared_groups` 现算 → `tools/gen_pin_share_mirror.py` 写
  `tests/js/pin-share-mirror.fixture.json`；pytest 断言「盘上 == 现算」，**不自动重写**。
- JS 侧 `tests/js/pin-share-mirror.test.mjs` 用同一份板 + 实例映射构造角色对象，
  复算 `pinShareClass` 后逐场景比对；只对账 `kind`（原因文案不进对拍），归一化键 = 角色键。
- 一致性代价受控：**不让测试起 node 子进程**（那是 pytest 面不该有的新依赖），场景表与
  期望值都在 Python 面，JS 面只读现成 fixture。

**红证 1（验收项：停用前端 `adc` 分支 → 对拍必须红且点名场景）**：

```
✖ 镜像：adc 共读同槽：adc + us016 默认同落 PA24（同一 ADC 实例）→ 共享
✖ 镜像：adc 共读同槽三件（adc + us016 + mq2）→ 共享
ℹ pass 12   ℹ fail 2
（断言输出：+ 'conflict'  - 'share'）
```

恢复后 16 passed。

**红证 2（板内门控也有真覆盖，评审整改后才成立）**：

```
✖ 镜像：两件 I2C 器件的 SCL/SDA 同落板外脚 PD0 → 两侧都不标注（不是「合法共享」）
ℹ pass 15   ℹ fail 1
```

### code-review 整改（双轴评审后）

| 发现 | 处理 |
|---|---|
| **板外脚场景空转**（两轴都报，最重）：`pins: []` 让 `expected_groups` 与 `roles_by_pin` 双双过滤成空 → `[] == []` 恒绿，前端门控实际零覆盖 | 删掉手写的 `pins`，改为 `_case_pins` **从生效落点现推**（手写漏一处就是一次空转）；并补 `test_off_board_scenario_is_not_vacuous` 钉住「有角色、全在板外、后端不报组」。**关键**：光这样仍不够——两件 i2c 器件落板外时，资源键那条路本来就有各自的门控，只有 `pinShareClass` 的「全 i2c → 直接判 share」**快路**才暴露差异，故新增专钉快路的场景（`instance_override` 置空免撞板内同组），红证 2 即由它产出 |
| `test_backend_predicate_on_every_scenario` 手写 12 条 kind 期望 = 把 fixture 的活重做一遍（Violates spec「期望值由后端现算」） | 换成 `test_scenario_categories_cover_the_ticket_floor`：由 `CASES` 的 `category` 现推覆盖，断言三类结论齐全且与后端结论相符 |
| Python 与 JS 各有一条 adc 漂移断言（重复），且 JS 那条只读 fixture、对前端行为零信息量 | 删掉 Python 那条，只留 JS 侧（它读的是真实 fixture，前端停用 adc 分支即红） |
| 「pwm 等无键类型同脚冲突」表内缺失 | 补场景「config 的 DIP 输入与 pid 灰度输入共 PB12」——两者都是 gpio 但实例集交集为空，覆盖无键/空交集两支 |
| 「多角色交集为空」表内只有跨类型版本 | 补「同型实例交集为空」场景；**实测库内 adc 家族全挂 `ADC12_0`**（唯一有第二实例的是 `gp2y1014au`），该分支要靠 `instance_override` 造可达形态，并在场景注释与 `actual_groups` 里说明两侧输入必须同样生效（否则是假对拍） |
| fixture 冗余：`roles_by_pin[].default` 前端不读；板定义按场景重复（PA24 出现 6 次 / 48 条 vs 去重后 25 条） | 删掉 `default` 字段；板定义**按平台去重**放顶层 `boards`（JS 侧按 `c.platform` 取），板外脚天然不在任何板子集里 |
| `dump_fixture` 死代码（生成器自己重写了写盘逻辑） | 删掉 `dump_fixture`，test 模块只导出 `mirror_payload` / `CASES` 等数据 |
| `pin-share.test.mjs` 对 `reason` 文案打正则（spec 明确文案不进对拍） | 删掉该断言，只留 kind |
| `CONTEXT.md` 那句带流程细节（超出「只做词表与架构要点」） | 压成领域事实一句（判据单源在哪 + 谁守 + adc/板外两条口径） |
| 新 JS 文件注释里的运行命令与 workflow 的既定命令不一致 | 改为 `node --test "tests/js/*.test.mjs"` |

**测试结果（整改后）**：`python -m pytest -n auto` **全绿**；
`node --test "tests/js/*.test.mjs"` **1712 passed**（新增 16 条镜像用例 + 5 条函数级用例）。
