# 04 — 前端实例配置 UI（列表 / 命名 / 颜色 / 引脚）

**What to build:** index.html 上支持多实例的模块（led）显示「添加实例 / 删除实例 /
编辑显示名 / 选颜色 / 绑引脚」；用户手动增删改后装配进生成请求的 `instances` 载荷。
旧单选 UI 与旧请求行为不变。

**Blocked by:** 01

**Status:** resolved

- [x] 多实例模块卡片渲染实例列表，每实例可改显示名（自由中文）、选颜色、绑引脚（复用现有板图绑定）
- [x] 添加/删除实例，数量上限 8，超限禁用并提示
- [x] 装配：前端把实例清单编进 `/api/generate`（及 `/api/skeleton`）请求的 `instances` 字段
- [x] 旧单选模块 / 旧请求无 `instances` = 现行为，UI 与产物不破
- [x] 手动绑定的引脚冲突沿用现有前端提示语义（不新增后端 400 之外的行为）
- [x] 与主链并行时用独立 worktree（[[parallel-tickets-shared-checkout-race]]），只提交本票前端文件

**Notes:** 请求层 instances 解析落 selection.parse_instances（照 build_module_selection
先例：webapp 只取参转调，SelectionError → 400 中文）；/api/skeleton 与 /api/generate 都
收 `instances`，缺省 / 空 = 现行为逐字节（旧请求零改动）。前端新卡「多实例配置」（不占
步骤号，插在步骤 6/7 之间）——multi_instance 非空的模块（当前 led）显示实例列表：显示名
自由中文 / 颜色下拉（红/黄/绿可重复 + 无颜色 = LED_1..n 通用编号，补 spec User Story 4
的可达性）/ 绑引脚（复用板图：gpio_out 能力脚候选高亮，点即绑，Esc/再点取消，可「改回
自动」空 = 自动分配）；上限 = multi_instance.max（led=8）超限禁用加「已达上限」提示；
instances 装配进 skeleton / generate（空清单不发 = 旧行为）。generate 侧「只发其一」
（03 判据⑦）：已配实例的模块不再发其角色绑定（实例脚为权威）。选脚目标有失效守卫
（移除模块 / 实例号越界清掉，防陈旧高亮）。

1684 passed + mypy 44 文件干净 + node --check / node --test 9 通过。code-review 双轴：
Standards——无硬违规，3 条 judgement-call smell（颜色词表 Python/JS 跨语言重复、{slug,index}
数据团、instList 缩写）留；`t` 复用命名已修。Spec——非内置色 UI 可达性已补（无颜色选项）；
空数组语义（parse_instances({"led":[]}) → {"led":()}）与「手动绑脚冲突提示」留痕为可接受
（spec D3 把冲突留给 generate-time 门禁，前端不新增）。

**与旧 UI 重做的关系**：index.html 的「未提交 UI 重做」（memory index-html-ui-redo-pending）
已查明实为丢失后另立工单 index-html-ui-redo 部分合入（#84 等），本票改动时工作树 index.html
为 clean、无未提交冲突；本票未碰 firstep 标题/层级/设置三分卡/第四步搜索/第六步多行。
