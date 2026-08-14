# 03 — 板图 SVG 前端：引脚配置卡片 + 角色菜单 + 双视图（前端层）

**What to build:** 生成页插入"引脚配置"卡片：左板图 SVG（开发板本体、焊盘可点击）+ 右待接角色清单；点引脚弹角色菜单；配置随生成请求（bindings）发送。

**Blocked by:** pin-board-config/01、02（依赖 /api/boards 与 /api/generate bindings）

**Status:** resolved（2026-08-14 PR #72 squash merged 4f5a333，主会话程序化验收通过；剩余 3 项纯目验见 Comments 尾注）

## 需求

1. **新卡片**：`index.html` 的 `#tab-generate` 内插在"模块清单"（卡 6）与"main.c 骨架"（卡 7）之间——新卡成为卡 7，原 7/8/9/10 序号顺延（h2 序号与内部引用同步）。卡片内：左板图 + 右角色清单 + 图例。
2. **板图 SVG**：按 `GET /api/boards` 返回的板定义渲染（无静态路由——SVG 由 JSON 坐标内联生成；双排焊盘、丝印名、功能区、固定引脚灰色不可点、IO 引脚按绑定角色类型着色；图例列角色类型颜色）。视觉参照 `sources/contest/2026H/26H/pin_config.html` 深色 tag 风格；颜色全部用 `:root` 令牌或派生色。
3. **角色清单**：已选模块的 pins 声明展开——每条角色显示 标签 / 默认值 / 绑定状态（已绑=引脚名+颜色、未绑=红显、用默认=标注"默认"、**默认板外=标注"默认板外（排针未引出）"**——HUIDU R3/R4=PB4/PB5 先例，仍可绑定到板内空闲脚）；点条目 → 板图高亮可接引脚（能力过滤）。**数据源**：声明 = `/api/selection/expand` 返回的 `modules[].platforms.<p>.pins`（工单 01 的 to_dict 已含，零新接口）；板定义 = `/api/boards`。
4. **点击交互**：
   - 点空闲引脚 → 锚定浮层菜单（复用 `.ref-files-overlay` 模式）：只列该引脚能力支持的角色（**strict-all 判定**——见下节工单 02 发现，与门禁同语义，勿做 any-of），不兼容角色灰显 + 悬停原因；点角色即绑定。
   - 点已占用引脚 → 菜单显示占用者，可直接替换；被替换角色回"未绑定"红显。
   - 同引脚多角色共享 → 叠加标注（xunji/huidu 先例）。
5. **发送**：`/api/generate` 请求体加 `bindings: {"<slug>.<role_id>": "<PIN>"}`（跳过未改动的角色——缺省即默认，payload 只含用户动过的项；未配任何引脚时干脆不发 bindings 字段）。
6. **状态**：绑定存前端 state（会话内）；切平台时清空重取板定义；选模块变化时角色清单重算（新角色的默认值预填显示）。

## 工单 02 关键发现（前端设计必读）

1. **能力过滤 = strict-all**（与门禁同语义）：角色默认引脚能力 token 的**全部实例**都必须出现在目标引脚能力集。判例：motor.PWMAB_C0 默认 PA12 有 `pwm:TIMG0_C0 + pwm:TIMA0_C3` 双实例——any-of 会放行仅 TIMA0_C3 的 PA28（界面显示兼容但 SysConfig 路由必炸）；strict-all 下 PA28 灰显、双实例俱有的 PA23 可绑。JS 镜像实现此判定，浏览器验收用此反例。
2. **mspm0 排针满员**：32 IO 全占满，单角色换脚多数撞已占用引脚（实证 LED→PB8 撞 STEP_MOTOR，SysConfig "Resource conflict" exit=2——机制改写正确，冲突是接线语义）。v1 交互 = 替换两步完成换位（点已占用引脚 → 原角色变未绑红显 → 再绑目标脚）；"双角色一键换位"留后续候选。
3. **共享宏族提示**（stm32）：LED_PORT 三灯共口、DIP_GPIO 四拨码共口——绑其中一个角色会改到同族其它角色的共享宏。v1 不拦截（接线语义用户把关），UI 在绑定此类角色时给提示文案（列出同族角色）。

## 文件边界

- `src/contest_generator/static/index.html`：唯一前端文件（CSS + SVG 渲染 + 交互 + 卡片）
- 零后端改动（/api/boards 与 bindings 载荷由工单 01/02 提供）
- `tests/`：无新测试（node --check 语法过 + 浏览器人工验收；如需契约测试只做 payload 形状断言）

## 验收

- [x] `node --check` 语法过（实施会话 + 主会话合并后复跑 OK）
- [x] 交互逻辑验收（卡片位置/双板渲染/固定引脚不可点/能力过滤/灰显/替换红显/清单高亮/宏族提示/payload 两态——jsdom 37/37 + 主会话读码逐项核对；**视觉外观与 devtools 网络核对留用户目验**）
- [x] strict-all 反例（jsdom 用例 PA28 灰显缺 TIMG0_C0、PA23 可绑 + 读码 pinCanHost 与门禁 `insts.every` 同语义）
- [x] 真机全流程（实施会话 web 路径：改绑定 MOTOR_B_ENC→PB4 → EXTI_PB4 UV4 0 错 0 警 + 不配回归 EXTI_PA4 默认 UV4 0 错 0 警；**浏览器点击全流程留用户**）
- [x] pytest 零扰动（主检出合并后复跑 1456 绿 34.2s）
- [x] 独立 worktree + 提交 + 推送

## 实施提示词（复制到新会话）

```
实施板级引脚配置前端工单 .scratch/pin-board-config/issues/03-board-ui.md：
1. 读工单（含「工单 02 关键发现」节——strict-all / 排针满员 / 共享宏族，必读）+ spec + 工单 01/02 产物
   （板定义 = /api/boards；pins 声明 = /api/selection/expand 的 modules[].platforms.<p>.pins；bindings 载荷形状）
2. index.html 插新卡片（模块清单与骨架之间，序号顺延）：左板图 SVG + 右角色清单 + 图例
3. SVG 由 boards JSON 坐标内联渲染（无静态路由）；固定引脚灰色、IO 引脚按角色类型着色；
   视觉参照 sources/contest/2026H/26H/pin_config.html，颜色用 :root 令牌
4. 交互：点引脚 → 锚定浮层菜单（.ref-files-overlay 模式；能力过滤 = strict-all 与门禁同语义，
   不兼容灰显）；点已占用引脚 → 可替换、被替换角色红显未绑；点清单条目 → 板图高亮可接引脚；
   LED_PORT/DIP_GPIO 等共享宏族角色绑定给出提示
5. 生成请求带 bindings（只含用户动过的角色；没配就不发字段）
6. 验收：node --check 过；浏览器人工验收清单逐项过（含 strict-all 反例 PA28 灰显/PA23 可绑）；
   真机 2026C 改绑定 UV4 0 错 + 不配回归
7. 提交 + 推送
注意：独立 worktree；单文件改动（index.html）；零后端改动
```

## Comments

- 2026-08-14 立项（板级引脚配置 grilling 定稿）。
- 2026-08-14 实施完成（分支 pin-board-config-03，独立 worktree，单文件 index.html +535/-10，零后端改动，pytest 1456 零扰动）：
  **卡片 7「引脚配置（板图点选）」**插在模块清单与骨架之间（h2 序号 7→11 顺延 + JS 分节注释同步）——左板图 SVG（boards JSON 坐标内联渲染，无静态路由：PCB 本体 + 芯片丝印 + 双排焊盘 + 丝印名，固定/电源引脚灰色不可点，IO 按绑定角色类型着色，同脚多角色叠加小色点，title 悬停含能力与板载注记，固定资源功能区虚线 chips）+ 右角色清单（类型 tag / 默认值 / 已绑 / 红显未绑 / 默认板外（PB4/PB5 先例）/ 默认被占用警示 / 共享宏族行）+ 图例（角色类型色 + 空闲 IO + 固定电源）。
  **交互**：点引脚 → 锚定浮层菜单（.ref-files-overlay 模式：全屏遮罩 + Esc + 越界翻面）——第一层类型过滤（UART 脚不列 PWM 角色）+ strict-all 实例判定（与门禁同语义勿 any-of，不兼容灰显 + 缺实例原因）；点已占用引脚 → 占用者可替换/解除（被替换角色红显未绑——排针满员两步换位交互）；点清单条目 → 板图高亮可接引脚（pin-cand 高亮 / pin-dim 不兼容变暗 / 默认脚虚线环，再点取消）；共享宏族（LED_PORT/DIP_GPIO）绑定时卡片顶部黄色提示列出同族角色（v1 不拦截）。
  **payload**：/api/generate 带 bindings（只含用户动过且模块仍在选择集内的角色；未配任何引脚不发字段——缺省即默认，旧行为不变）；切平台清空重取板定义；展开/清单变化时角色清单重算 + 残留绑定清理。
  **验证**：node --check 过（脚本段提取）；jsdom DOM 冒烟 37/37 全绿（卡片序号顺延 / stm32+mspm0 双板渲染 / 固定引脚不可点 / strict-all 反例 PA28 灰显缺 TIMG0_C0、PA23 可绑 / 替换后原角色红显未绑 / 共享宏族提示 / 默认板外 PB4 PB5 / 默认被占用警示 / 高亮与取消 / payload 带 bindings 与不带两态 / 还原默认）；纯函数逻辑用真 boards JSON 复核（stm32 enc 实例锁线号仅 PA2 可绑、UART 脚类型层不列 pwm）；真机 web 路径（worktree 服务 8000 + generate_check --reuse-recommend）：2026C --add motor --bindings `{"motor.MOTOR_B_ENC":"PB4"}` → pin_config.h MOTOR_B_ENC_EXTI=EXTI_PB4（默认 EXTI_PA4，产物恰一处宏行变化）UV4 exit=0 0 错 0 警；不配 bindings 回归 EXTI_PA4 默认值 UV4 0 错 0 警；顺带实证后端门禁：绑未选模块的角色（motor 未在 2026C 推荐集）→ 400 中文。DeepSeek 骨架段瞬态 502 两次（Remote end closed / WinError 10054）重跑即过（known transient，deepseek-retry-hardening/01 口径）。
  **浏览器人工验收清单（待用户执行）**：① 卡片位置与序号 7→11 顺延；② stm32/mspm0 两板切换渲染正常（蓝药丸 / 地猛星），固定引脚灰色不可点；③ mspm0 点 PA28 菜单 PWMAB_C0 灰显 + 原因"缺 TIMG0_C0"，PA23 可绑（strict-all 反例）；④ UART 脚菜单不出现 PWM 角色；⑤ 点已占用引脚 → 替换后原角色红显未绑（两步换位）；⑥ 点清单条目 → 板图高亮可接引脚；⑦ stm32 绑 LED_RED → 共享宏族提示；⑧ devtools 网络面板核对 /api/generate 请求体带 bindings（还原默认后再生成 → 无该字段）；⑨ 真机 2026C 浏览器全流程配一个改绑定 → UV4 0 错。
- 2026-08-14 主会话程序化验收 + 合并（PR #72 squash merged 4f5a333，远端分支已删）：pytest 1456 绿复跑 + node --check 复跑 OK（脚本段提取）；/api/boards 双板返回 + /api/selection/expand pins 载荷实测（motor 10 角色/huidu 8）；读码逐项核对 9 项清单——pinCanHost 与门禁 strict-all 同语义（`insts.every`）、类型层过滤、pin-cand/pin-dim 高亮、共享宏族提示、payload 只发仍在选择集内的用户绑定且空则不发字段；sse-parser 回归通过。**剩余纯目验 3 项（用户浏览器，合并后重启 8000 看）**：① 视觉外观（板图/颜色/叠加小色点观感）；② devtools 网络面板 bindings 两态核对；③ 浏览器点击全流程配一个改绑定 → UV4 0 错。另注：并行会话丢失的 index.html UI 改造与本工单无关（index-html-ui-redo-pending 待办在案），本分支基于 clean main，两者若都改 index.html 合并时需人工核对。
