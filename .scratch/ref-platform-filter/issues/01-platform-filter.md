# 01 — 参考条目平台属性（topic / kit 锚定统一按 platform 过滤）

**What to build:** 参考文件库锚定只有 topic / kit 两维，**没有平台维**——topic 锚定的条目（如 car xunji 巡线模板）在 2024H + stm32 场景也会注入 mspm0 内容误导 LLM；kit 锚定同样不分平台（`associated_references` 的 manifests 是全量模块，generator.py:220，ALX 是 STM32F1 例程，mspm0 工程也会命中注入）。本工单给参考条目加平台属性（`platform: stm32 / mspm0 / any`，缺省 any 向后兼容），装配点按生成平台过滤。

**Blocked by:** 无

**Status:** resolved

## 现状事实（实施前必读）

- 装配链：`webapp._assemble_topic_context`（webapp.py:227，无 platform 参数）→ `generator.resolve_topic_context`（generator.py:144-195，签名无 platform）→ `associated_references`（selection.py:186-198，锚定判据 = topic_key ∪ `collect_kits(manifests)`；**manifests = 全量模块** generator.py:220，非平台过滤后的候选）。recommend 请求体有 `platform`（前端平台卡片单选，index.html:188-192），装配点可得，加参透传即可。
- 参考条目 schema：`library/references/<id>/reference.json`（id/title/type/description/anchor_kind/anchor_value/files），`add_reference`（webapp.py:893-911 直调，锚定词表校验 kit 走 `module_kit_vocabulary`）；录入表单在 index.html 参考库 tab（锚定二选一：赛题编号 / 套件型号）。`GET /api/references` 返回 `entry.to_dict()` 全量。
- 归档：`archive.write_archive_entries` 创建参考条目（锚定该题，报告平台已知——但归档残渣多为平台无关参考文件，本工单缺省 any 不传）。
- 手动选（工单 gen-reference-select 已合 main）：手动勾选 = 用户显式意图，**不过平台过滤**（UI 标注平台让用户自判）。
- 库数据顺带操作：car xunji 录入（`sources/car/car xunji/`：xunji_template.c/h + xunji_logic_spec.md + control/Delay/JY61P，3.5M，Debug/ 排除，c 文件 GBK→UTF-8）+ k230资料 补锚定 `topic=2021F` + 既有四批补平台标注（2026_04 地猛星=mspm0、ALX=stm32；k230/视觉/真题/MOTOR=any）。

## 需求

1. **schema**：`reference.json` 加 `platform` 字段，词表 = `stm32` / `mspm0` / `any`（缺省 any，旧条目缺字段 = any，向后兼容；词表复用 platforms.py 或 reference_library 内声明，随现有锚定词表校验模式）。
2. **录入**：`add_reference` 校验 platform 词表（非法 → 400 大声失败）；录入表单加平台三选（index.html 参考库 tab）；`GET /api/references` 响应带 platform。
3. **过滤**：`associated_references` 加 `platform: str = ""` 参数——topic 命中与 kit 命中**统一**按 platform 过滤（不匹配跳过；`any` 全进；platform 空串 = 不过滤，向后兼容）。`resolve_topic_context` / `_assemble_topic_context` 加 platform 透传（recommend 路由传请求体 platform；skeleton / generate 不注入参考文件，传缺省即可）。
4. **手动选不受影响**：手动准入不过平台过滤（用户显式意图）；结果清单 UI 对条目显示平台标注（如"mspm0 平台"chip）。
5. **库数据操作（入库随本工单提交）**：
   - car xunji 录入：title=car 1.1 巡线模板（mspm0）、type=参考例程、锚定 `topic=2024H`、`platform=mspm0`、files=xunji_template.c/h + xunji_logic_spec.md + control.c/h + Delay.c/h + USART_JY61P/（排除 Debug/、README.html、png、empty.*、targetConfigs/；c/h GBK→UTF-8）
   - k230资料 补锚定：`anchor_kind=none` → `topic`，`anchor_value=2021F`，platform 缺省 any
   - 既有批次补平台标注：2026_04 地猛星配套 → `mspm0`（地猛星题锁平台）；ALX-AOA-FIT 串口例程 → `stm32`（例程是 STM32F1 的）；其余批次保持缺省 any
6. **CONTEXT.md**：参考文件库词条补平台属性过滤一句。

## 文件边界

- `src/contest_generator/reference_library.py`：schema（读缺省 + 校验）、`add_reference` platform 参数与词表校验
- `src/contest_generator/selection.py`：`associated_references` 加 platform 参数过滤（topic / kit 统一）
- `src/contest_generator/generator.py`：`resolve_topic_context` 加 platform 透传
- `src/contest_generator/webapp.py`：`_assemble_topic_context` 加 platform（recommend 传请求体值）
- `src/contest_generator/static/index.html`：录入表单平台三选 + 结果清单平台 chip
- `library/references/`：库数据（car xunji 新增条目 + k230 补锚定 + 两批补平台标注，库 CRUD 自动 git 提交）
- `tests/`：schema 缺省/校验、过滤（topic 命中按平台、kit 命中按平台、any 全进、空串不过滤）、录入表单契约、装配透传、旧条目兼容
- `CONTEXT.md`：词条补句
- 注意：主检出有在途未提交改动（webapp.py / index.html / tests/test_webapp.py 的 API key 掩码草稿），实施独立 worktree、独立 commit，不混批

## 验收

- [x] 全量测试绿 + mypy 干净
- [x] 2024H 巡线题 + platform=stm32：car xunji 条目（topic=2024H, platform=mspm0）不进清单；platform=mspm0 时进
- [x] mspm0 工程 + ALX 批次（platform=stm32）：kit 命中也不注入（双保险过滤生效）
- [x] 旧条目（无 platform 字段）：照旧注入（缺省 any）
- [x] 手动勾选 car xunji + 生成 stm32 工程：仍注入（手动选不过滤），UI 显示 mspm0 平台标注
- [x] 录入表单：平台三选可选、非法值 400；`GET /api/references` 带 platform
- [x] 库数据：car xunji 条目可查（files 正确、无 Debug/）、k230 锚定变 2021F、两批 platform 标注正确，自动提交消息正确
- [x] 独立 worktree + 独立 commit，工作区在途改动不混入

## Comments

- 2026-08-09 立项（用户提出"巡线题但 stm32 怎么办"——锚定平台盲区确认）：现状 topic 锚定不分平台，kit 锚定因 manifests 全量模块同样不分平台（修正认知：kit 并非间接平台感知）。方案 = 条目平台属性 + 装配统一过滤；手动选尊重显式意图不过滤（用户已确认）。2026H 地猛星题命题锁平台所以无感，2024H 开放题必须处理。

- 2026-08-09 实施（worktree-ref-platform-filter，3 commit）：reference_library.py ReferenceEntry.platform（缺省 any 向后兼容，from_dict 词表外大声失败）+ add_reference platform 词表校验；selection.associated_references platform 参数（topic/kit 命中统一过滤：不匹配跳过、any 全进、空串不过滤，_platform_matches）；generator.resolve_topic_context / webapp._assemble_topic_context platform 透传（recommend 传请求体值，skeleton/generate 缺省）；done 事件参考清单带 platform；前端录入表单平台三选（缺省 any）+ 参考库表 / 勾选清单 / 结果清单平台 chip（any 不标注）。库数据：car xunji 经真实 add_reference 录入（自动提交 "lib: add reference car-1-1-巡线模板-mspm0"，9 文件无 Debug/，c/h 已 UTF-8 无需转换）；k230 锚定 topic=2021F（platform 缺省 any）；2026_04=mspm0、ALX=stm32 补标注（提交 9eece93）。956 绿 + mypy 干净；真实库数据端到端验证 2024H+stm32 过滤 / kit 双保险 / 旧条目兼容全过。注意：主检出 library/references/ 下 k230资料 与 2026_04_地猛星电赛控制题配套资料 是未跟踪目录，合入本 PR 前需先删除/移走（pull 会因未跟踪同名文件拒绝）。
