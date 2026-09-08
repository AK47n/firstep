# 01 — 器件/内部件判据归位单源 + 三处引用改造

**要做什么：** 库内出现**唯一一处**「哪些 slug 是用户会单独采购的器件、哪些是内部件 /
协议切片」的判据，并且词表守卫、参考关联豁免、身份字段三处的名单都从它派生。落地后
维护者改判据只改一处；三处名单互相矛盾时测试红。本工单只做判据与名单，不动任何
manifest 数据、不加身份字段守卫（守卫在 02）。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] `library.py` 落 `ModuleKind`（DEVICE / INTERNAL / PROTOCOL）+ `MODULE_KIND`
      （只登记非器件类：10 个内部件 + 3 个协议切片）+ `MODULE_KIND_REASONS`
      （逐条中文理由）+ `module_kind` / `requires_identity` / `device_slugs` /
      `internal_slugs` / `protocol_slugs`，模块 docstring 写明判据与单源约定
- [x] `tests/test_wordlist.py` 删手写 `_DEVICE_SLUGS` / `_INTERNAL_SLUGS`，两条既有
      守卫改引用单源派生名单，失败信息点名 slug 与判据
- [x] `reference_library.py` 的 `MODULE_REFERENCE_EXEMPT` 补注释说明与 `MODULE_KIND`
      的关系（判据来源），`zigbee_link` 的豁免理由从「协议切片」更正为「器件但参考库
      暂无条目」（切片是 zigbee_uart / zigbee_uart_key），其余条目理由不动
- [x] `tests/test_library_invariants.py` 新增不变量：单源 slug 都在库内且都有理由；
      内部件/协议切片不得**既豁免又有参考映射**（参考关联是另一个判据——多一层
      「参考库有无条目」，故 `adc`/`uart`/各 uart 等有同名例程映射而合法不豁免，
      见 spec 修订）；词表挂接名单只许含器件（`test_wordlist_hooks_are_devices_only`）
- [x] `tests/test_skeleton_mapping_coverage.py` 补一条断言：
      `INTERNAL`/`PROTOCOL` 若在豁免表内，豁免理由的类别前缀须与单源一致
      （`test_reference_exempt_reason_kind_matches_module_kind`）
- [x] 全量 pytest 绿（基线 3881 passed），无 manifest 数据改动（`git diff --stat` 只
      有库源码 + 测试）

## Comments

- 判据单源落点结论（spec「实现决策·单源方案」）：抽得动，落 `library.py`——该文件已有
  「判据④机械词表」`BANNED_TOPIC_WORDS` / `CAPABILITY_WORDS` 的单源先例（结构测试与
  补录流程共用）。不放 `manifest.py`（数据模型层，判据会变成数据形状问题）、不放
  `reference_library.py`（参考库域，依赖方向反了——身份字段与词表不依赖参考库）。
- 默认值取「未登记 = 器件」：库里 93 个模块绝大多数是器件，新增器件自动进守卫；
  内部件/协议切片是少数且必须逐条写明理由（防「顺手豁免」）。
- 三处矛盾的三条修正见 spec 判定表下方（`zigbee_link` 判 DEVICE、`huidu` 判 INTERNAL、
  `ir_beam` 判 DEVICE 但参考关联仍豁免——不同域的两种豁免允许并存）。
- **实施中发现第四处漂移并修正**：词表把 `coord_detect`（K230 帧解析切片）挂进了
  `K230（CanMV）` 方案——按判据不该挂（用户不采购解析切片，实物是 K230 板）。已改为
  只挂 `k230`，方案 note 写明「主控侧串口解析随依赖 coord_detect 自动带入」；
  词表守卫（内部件/协议切片不得挂接）随即绿。**判据不放宽来迁就数据**。
- **参考关联不是同一判据的第三处表述**（修正 spec 初稿）：参考豁免的判据是「参考库
  有没有可关联的条目」，比器件判据多一层——`adc`/`debug_uart`/`digit_uart`/
  `imu_uart`/`uart`/`zigbee_uart`/`zigbee_uart_key` 是内部件/协议切片但**有**同名
  例程映射（合法不豁免）。故单源只派生「器件判据」，参考关联按自己的判据走，测试断言
  两者不矛盾（不得既豁免又映射；凡豁免的理由类别前缀须与单源一致）。
- 全量 pytest：3884 passed（`tests/test_autocommit.py` 的公开函数分类注册表要求新增
  5 个读函数登记，已补；本工单自身其余用例全绿）。
