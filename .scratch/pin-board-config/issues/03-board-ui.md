# 03 — 板图 SVG 前端：引脚配置卡片 + 角色菜单 + 双视图（前端层）

**What to build:** 生成页插入"引脚配置"卡片：左板图 SVG（开发板本体、焊盘可点击）+ 右待接角色清单；点引脚弹角色菜单；配置随生成请求（bindings）发送。

**Blocked by:** pin-board-config/01、02（依赖 /api/boards 与 /api/generate bindings）

**Status:** 待实施

## 需求

1. **新卡片**：`index.html` 的 `#tab-generate` 内插在"模块清单"（卡 6）与"main.c 骨架"（卡 7）之间——新卡成为卡 7，原 7/8/9/10 序号顺延（h2 序号与内部引用同步）。卡片内：左板图 + 右角色清单 + 图例。
2. **板图 SVG**：按 `GET /api/boards` 返回的板定义渲染（无静态路由——SVG 由 JSON 坐标内联生成；双排焊盘、丝印名、功能区、固定引脚灰色不可点、IO 引脚按绑定角色类型着色；图例列角色类型颜色）。视觉参照 `sources/contest/2026H/26H/pin_config.html` 深色 tag 风格；颜色全部用 `:root` 令牌或派生色。
3. **角色清单**：已选模块的 pins 声明展开——每条角色显示 标签 / 默认值 / 绑定状态（已绑=引脚名+颜色、未绑=红显、用默认=标注"默认"、**默认板外=标注"默认板外（排针未引出）"**——HUIDU R3/R4=PB4/PB5 先例，仍可绑定到板内空闲脚）；点条目 → 板图高亮可接引脚（能力过滤）。
4. **点击交互**：
   - 点空闲引脚 → 锚定浮层菜单（复用 `.ref-files-overlay` 模式）：只列该引脚能力支持的角色（能力 token 匹配），不兼容角色灰显 + 悬停原因；点角色即绑定。
   - 点已占用引脚 → 菜单显示占用者，可直接替换；被替换角色回"未绑定"红显。
   - 同引脚多角色共享 → 叠加标注（xunji/huidu 先例）。
5. **发送**：`/api/generate` 请求体加 `bindings: {"<slug>.<role_id>": "<PIN>"}`（跳过未改动的角色——缺省即默认，payload 只含用户动过的项；未配任何引脚时干脆不发 bindings 字段）。
6. **状态**：绑定存前端 state（会话内）；切平台时清空重取板定义；选模块变化时角色清单重算（新角色的默认值预填显示）。

## 文件边界

- `src/contest_generator/static/index.html`：唯一前端文件（CSS + SVG 渲染 + 交互 + 卡片）
- 零后端改动（/api/boards 与 bindings 载荷由工单 01/02 提供）
- `tests/`：无新测试（node --check 语法过 + 浏览器人工验收；如需契约测试只做 payload 形状断言）

## 验收

- [ ] `node --check` 语法过（脚本段提取）
- [ ] 浏览器人工验收：卡片出现在卡 6 与骨架之间；stm32/mspm0 两板切换渲染正常；点引脚弹菜单且能力过滤正确（UART 脚不出现 PWM 角色）；不兼容角色灰显；重绑替换后原角色红显未绑；payload 带 bindings 字段（devtools 网络面板核对）
- [ ] 真机全流程：2026C 配一个改绑定（如电机 PWM 换线）→ 生成 → UV4 0 错；不配引脚照旧全绿（回归）
- [ ] pytest 零扰动
- [ ] 独立 worktree + 提交 + 推送

## 实施提示词（复制到新会话）

```
实施板级引脚配置前端工单 .scratch/pin-board-config/issues/03-board-ui.md：
1. 读工单 + .scratch/pin-board-config/spec.md + 工单 01/02 产物（/api/boards 形状、bindings 载荷）
2. index.html 插新卡片（模块清单与骨架之间，序号顺延）：左板图 SVG + 右角色清单 + 图例
3. SVG 由 boards JSON 坐标内联渲染（无静态路由）；固定引脚灰色、IO 引脚按角色类型着色；
   视觉参照 sources/contest/2026H/26H/pin_config.html，颜色用 :root 令牌
4. 交互：点引脚 → 锚定浮层菜单（.ref-files-overlay 模式，能力过滤 + 不兼容灰显）；
   点已占用引脚 → 可替换、被替换角色红显未绑；点清单条目 → 板图高亮可接引脚
5. 生成请求带 bindings（只含用户动过的角色；没配就不发字段）
6. 验收：node --check 过；浏览器人工验收清单逐项过；真机 2026C 改绑定 UV4 0 错 + 不配回归
7. 提交 + 推送
注意：独立 worktree；单文件改动（index.html）；零后端改动
```

## Comments

- 2026-08-14 立项（板级引脚配置 grilling 定稿）。
