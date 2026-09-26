# 优化方向评审：硬件检测（hwcheck）是否达到要求

> 评审日期：2026-09-26（工作区 `d4cf62e5`，工作树干净）
> 性质：**改进机会盘点存档，非 spec、非工单**。选定方向后按 `docs/agents/workflow.md` 立项（clarify → spec → 工单）。
> 被评对象：「硬件检测」栏目（v1.3.0 已发布）——`module-hwcheck` / `hwcheck-acceptance` /
> `hwcheck-specialize` / `hwcheck-unknown-device` / `hwcheck-pin-conflict-exit` 五份 spec 的产出。
> 要求的三个来源：① 五份 spec 的验收判据；② 原始目标「拿到硬件能不能用 / 不会用能不能上手」；
> ③ v1.3.0 发布说明里已经说给用户听的话（`VERSIONS.md:13-21`）。
> 证据：本机现跑的只读核对（`json` 统计、`grep`/`read` 定位）+ 四支子审计（服务端 / 前端 / 验收证据 / 配方数据），
> 每条结论都指到文件与行号。**未跑** pytest / 浏览器门禁（读数沿用仓库既有记账）。

## 〇、结论先行

**工程做得比大多数"自检功能"扎实：35 张工单 34 张 resolved，600 条自动化用例（pytest 423 / 前端 156 / 浏览器 21）、
反证探针、跨语言镜像守卫、编译矩阵一应俱全。但它离"达到要求"还差两层，而且第二层是硬的：**

1. **验收层从未做过**——没有任何一块真板跑过检测程序。原始目标① 的字面要求是"看看能不能正常用"，
   而这一层至今只有编译证据。`hwcheck-acceptance/05` 仍 `ready-for-agent`
   （`docs/agents/local-environment.md:159-163`、`.scratch/module-hwcheck/issues/09` 均自记"未上板"）。
2. **覆盖层只有三分之一**——专精 30 件 / 57 格，库内 96 件 / 176 格 ⇒ **模块 31.3% / 格 32.4%**；
   57 格里真正能给板端 OK/FAIL 的只有 **35 格（61%）**，另 22 格（39%）打不出判定。

**而这两层已经发出去了**：v1.3.0（2026-09-25）把「30 件器件的专精检测」写进了用户可见的发布说明
（`VERSIONS.md:16`），而那句承诺没有附带"验证到哪一步"的限定。

| 要求层 | 判定 | 依据 |
|---|---|---|
| 规格承诺（五份 spec 的判据） | **基本达成** | 35 张工单 34 resolved；唯一未开工 = 真机上板（`acceptance/05`） |
| 代码质量与判据强度 | **达成** | 编译/渲染/守卫/反证均有硬证据；专精 30 件 57 格与自述数字一致 |
| 用户可用的实际达成度 | **部分达成** | 常见 1~8 件组合可用；勾满必 400；OLED-only 形态的承诺不成立 |
| 目标① 验收（硬件真能用） | **未达成** | 上板 0 次；41/57 格页面写"未上板"，16 格（含 `ml_mpu6050`）没写 |
| 目标② 辅助使用 | **达成** | 接线表 / 应看到什么 / 复测命令台 / 资料→草稿 / 一键带进生成页 全链在 |

## 一、红色缺陷（会让学生得出错误结论，或让页面承诺不成立）

### R1. OLED 通道的承诺不成立：恒写第 0 行 + 53% 读数行超屏宽

- **证据（代码）**：唯一的 OLED 出口是 `oled_show_text(0, 0, s)`
  （`src/contest_generator/hwcheck.py:1176`）——**每一次整行刷新都写第 0 行**，屏上只留最后一行；
  驱动侧 `oled_show_text(line, column, …)` → `OLED_ShowString(column*8, line*16, …, 16)`
  （`library/modules/oled/code/oled.c:481-483`），16 号字 = **16 列 × 4 行**，框架只用了第 0 行。
- **证据（文案与 spec 冲突）**：`hwcheck.py:274` 写着「结果**分屏显示**在屏幕上，不接串口也能看」，
  `hwcheck.py:270-271` 写着「OLED 上也能看到**同样的分段内容**」；spec 用户故事 6/11 同样要求"分段打出来"。
- **证据（宽度）**：读数行是「`  <表达式> = <值> <单位>`」，横幅在数值之前（`hwcheck_recipe.py:1378-1384`）——
  165 条读数里 **88 条（53%）光"`  <表达式> = `"就超过 16 列**，最长的
  `gpio_get(DEBUG_UART_RX_GPIO, DEBUG_UART_RX_Pin)` 达 52 列 ⇒ **屏上看到的是算式开头，数值被切掉**。
- **谁会撞上**：地猛星（mspm0）默认勾着「调试串口 + OLED」两路，此时串口能看全；
  但**只用 OLED 的学生**（没有 USB-TTL 转串口线是最常见的情况）看到的结果是"一行一行闪过去、最后什么都不剩"。
- **候选修法**（先量后定，别直接改）：① 框架侧分页/滚动（4 行窗口 + 按键翻页或定时轮播）；
  ② 逐件结果落在固定行（每件一行、只刷新自己那行）；③ 如实降级——页面明说"OLED 只显示最近一行，
  要看完整结果请勾调试串口"。③ 最省，但要让 spec 的用户故事 6/11 改口径。

### R2. 预览失败被说成「接线表取不到」，并且留着上一次的 main.c

- **证据**：预览请求失败时写进的是 `wiringError`（`static/js/ui/hwcheck.js:778`），
  渲染走 `hwcheckWiringErrorHTML`（`:577`），文案是「**接线表与冲突暂时取不到**：…」
  （`static/js/fx/hwcheck.js:534`）；而专门为预览失败写的那句「检测程序预览失败：…」
  （`fx/hwcheck.js:104`）**在产品里没有消费者**（只在 `:1306` 的 window 桥与测试里出现）。
- **并且**：失败分支只清板侧视图，**不清 main.c**（`ui/hwcheck.js:773-777`），
  注释给的理由是「检测程序只依赖平台与通道」（`ui/hwcheck.js:739-740`）——
  这个前提**不成立**：主程序是按所选器件渲染的（`webapp.py:2816`
  `render_main_c(config, view.sections, view.generic, view.custom)`）。
  于是学生看到的是**上一组器件的 main.c**，配一句指向接线表的错误。
- **影响**：复制/编译到的是过期产物，而错误提示把他引去查接线。**这类"静默给旧产物"是硬件检测最不该有的失败形态。**

### R3. 配方文案还在教学生去改 main.c（与 v1.3.0 的承诺相反）

- **证据**：`library/hwcheck_recipes.json:474`（`key × mspm0` 的平台说明）原文：
  「⚠ **上板前先把 main.c 里 SYSCFG_DL_init() 那一行的注释去掉**（它现在是注释状态——本平台生成链的已知限制…）」。
  而 `hwcheck-acceptance/01` 之后那一行**已经是活代码**，v1.3.0 发布说明也写着"三平台都不需要你改 main.c"。
- **守卫漏口**：现有断言 `tests/test_hwcheck.py:904` 只查 `render_checklist` 的输出，
  **不吃配方文件**；`.scratch/hwcheck-acceptance/报告-复测.md:64-73` 已点名这一处（N1）并建议扩守卫，
  至今未做——`取消注释` 字样在配方里没了，但换了个写法的 `注释去掉` 还在。
- **影响**：学生照做会找不到那一行，且与页面清单自相矛盾（清单里那条已删）。

### R4. 「0 error / 0 warning」这条验收线在链接器诊断上是漏的，而且已经有一格 FAIL

- **证据（判据漏）**：`parse_compile_errors` 只认带 `file(line)` 引用的行
  （`src/contest_generator/fix_errors.py:303-310`），`summarize_compile_output` 在无汇总行时
  退化成"按 message 里的 `warning` 计数"（`:436-443`）——**链接器形态的 `warning #10210-D:` 没有文件引用，
  两条路都看不见** ⇒ 编译面板会对它报"0 warning"。
- **证据（已红的格）**：`.scratch/hwcheck-acceptance/recheck-compile-matrix.txt` 的 F 格
  `[FAIL] F-hwcheck-oled+mpu6050-mspm0：exit=0、error 0、warning 1`，文件末行写着
  「**结论：有 FAIL**」；而同一份复测报告的结论句（`报告-复测.md:10`）写的是"代码侧该修的都修了、也都验过了"。
  根因在 `library/modules/ml_mpu6050/ml_libs/inv_mpu.c:60-61`（`log_i`/`log_e` 定义成 `printf` → stdio 要堆）。
- **影响**：`module-hwcheck/spec.md:110` 与 `hwcheck-acceptance/spec.md:123-124` 都把"0 error / 0 warning"
  写成验收判据；这条判据今天**既漏（看不见链接器告警）又假（面板显示 0 warning）**。

### R5. 上板 0 次，而页面只有一部分格如实说了

- **证据**：`hwcheck-acceptance/05` 状态 `ready-for-agent`；`.scratch/` 下没有任何上板读数；
  `library/modules/*/manifest.json` 里 **170 处"未上板"**（库内所有"模块 × 平台"条目）。
- **已经做得好的部分**：配方 note 里 **41/57 格**带一句「**未上板**：本格的结论只到『编译矩阵绿 + 驱动返回码判据』」
  （例：`library/hwcheck_recipes.json` 的 `aht10` 格），这句会**原样印到检测页的平台说明里**（学生看得到）。
- **缺口**：剩下 **16 格没有这句**，恰好是 v1 pilot 那批——`led / oled / debug_uart / key / beep / sr04 / jy61p / adc / ml_mpu6050`
  （两平台）。它们里有旗舰件 `ml_mpu6050`（DMP 姿态），note 甚至写着
  「板上判 FAIL 就是通信真的没通」这种**从未在真板上验证过的断言**。
  另外**全站没有一处"整块能力未上板"的总提示**（README / VERSIONS / 页面标题区都是零）。
- **影响**：学生把"配方 bug"读成"我线接错了"，而工具的设计前提恰恰是"检测没过 = 正常结果，先自查接线"。

## 二、黄色缺陷（不挡路，但会让学生困惑或白折腾）

### Y1. 复测字符池：勾满必 400，而报错文案把池子说大了 6 个

- **证据**：`COMMAND_POOL` = 字母数字 36 − 保留字 5 = **31**（`hwcheck_console.py:142-149`）；
  但把 57 格配方全量统计，**真正被声明过的字符只有 25 个**（`4 5 6 7 8 9` 六个池位没有任何
  `console.command/candidates` 用过）⇒ 学生勾满时 **stm32 第 23 件、mspm0 第 26 件**就撞（400）。
  而 `_pool_description()`（`:152-159`）印的是「可用字符一共 **31** 个」——**承诺比实际多 6 个**，
  正好把人往"还能再勾几件"引。`.scratch/backlog.md` §22 同一段里"26 件 > 25 个可用字符"与"池子 31 个"
  两个数字自相矛盾，实测 25 才对。
- **小规模是安全的**：`|S| ≤ 4` 全子集穷举（stm32 17550 / mspm0 27405 组）与 `|S| = 5~8` 各 4000 组抽样**零撞车**。
- **候选修法**：① 页面**事前**预警（勾到接近上限就说"再勾就排不上号了"，现在的 400 是唯一提示）；
  ② 报错文案与 `_pool_description` 改成"实际可分配的字符数"或在池里补上 `4~9` 的候选；③ 长期再谈短串命令。

### Y2. 5 条读数行超板上 128 字节行缓冲（全是 pilot 格，守卫只覆盖扩张格）

- **证据**：板上报告缓冲 `static char hwcheck_line[128]`（`hwcheck.py:1155`），超长**静默截断**
  （`hwcheck.py:1144-1145` 明说"宁可截断"）。按"算式 + 单位"逐条量 165 条读数行，
  **5 条已超 128 字节**：`debug_uart×stm32` 239B、`adc×mspm0` 152B、`beep×stm32` 146B、
  `adc×stm32` 139B、`adc×mspm0` 139B（单位里带长中文说明，一字 3 字节，**截在字中间就是半个乱码**）。
- `.scratch/backlog.md` §21 只记了 `debug_uart×stm32` 一条；实测是**5 条**，且新增的守卫
  `test_expansion_read_lines_fit_the_device_line_buffer` **刻意不吃 pilot 格**（§21 自述），所以这 5 条无人看管。
- **候选修法**：把这 5 条的单位说明挪进 `note`（note 是页面文本、不进板上缓冲），守卫射程从
  `EXPANSION` 扩到全量配方。

### Y3. 多实例只验首路

- `led` / `key` 声明 `multi_instance.max = 8`，配方只调 `led_init(LED_RED)` / `get_key_state(KEY_START)`
  ——**8 路只验第一路**，页面上另行回显通道数。学生装了 4 个 LED 只看见 1 个被验。
- 配方 schema 里没有"实例"这一维（`hwcheck.py` 内也无实例展开），所以这不是配方写漏，是**能力缺口**。

### Y4. 前端可达性与焦点

- **清单/器件勾选后丢焦点**：勾选回调整块 `innerHTML` 重绘（`ui/hwcheck.js:1246` → `:216-218`），
  刚按下的复选框被替换、焦点回 body；`#my-devices-list` 重绘（`:267`）同理。ui 层全文零 `.focus()`
  （其它 15 个 ui 模块有先例）。
- **器件卡鼠标专用**：器件卡是 `div`、chip 是 `span`（`fx/module.js:333/395`，无 `tabindex`/`role`/键盘），
  而**平台卡**补了 `role`/`tabindex`/keydown（`fx/hwcheck.js:90`、`ui/hwcheck.js:1032`）——同一页两套标准。
- **3 个输入没进无障碍表**：`#hwcheck-device-search`、`#hwcheck-parent`、`#hwcheck-symptom`
  只靠 placeholder（`index.html:4091/4103/4162`），`INPUT_A11Y_LABELS`（`js/boot.js:497`）零 hwcheck 条目。
- **长任务无进度/无 aria**：选器件 / 换平台期间的板侧刷新无 loading、无禁用；编译/烧录状态行
  （`fx/hwcheck.js:352-355`）无 `role=status`/`aria-live`。

### Y5. 检测记录读-改-写无锁、`.tmp` 名固定

- `webapp.py:3255-3266`（清单）与 `:3225-3244`（排障）+ `hwcheck_triage.py:779-784`（固定
  `hwcheck_record.json.tmp`）⇒ 两个页面同时勾选/回填会**丢更新或互相覆盖 tmp**。
  同仓已有 `_generation_guard`（`webapp.py:775/1608`）先例，这里没用。

### Y6. 前端 HTML 串里残留 markdown 粗体（学生看到字面星号）

- `static/js/fx/hwcheck.js:319`（缺工具链的"大声降级"）、`:334`（默认撞脚说明）、
  `:548`（`hwcheckPinFixHTML`，**mspm0 默认双通道会自动移脚，这条几乎必现**）——
  三条都是 `**…**` 直接进 `innerHTML`，全站没有任何 markdown 后处理。
- 现有测试用 `includes("未经验证")` 断言（`tests/js/hwcheck.test.mjs:343-346`），
  子串命中即过，**抓不到星号**。

### Y7. 母版 syscfg 读失败静默降级，容量判据整段消失

- `hwcheck_board.py:153-156` 读不到母版 syscfg 就返回 `None`，`hwcheck_pin_plan` 直接跳过容量判定
  （`:216`）——与 `hwcheck_board.py:193-195` 自述的"预览过了、生成再 400 这种情况不可能出现"**直接矛盾**。

### Y8. 读记录失败被当成"坏 JSON"，引导删真记录

- `hwcheck_triage.py:764-770`：`except (OSError, json.JSONDecodeError)` 走同一句提示
  "…可以把它删掉重填"。文件被占用/没权限时，学生照做会**删掉自己的检测记录**。

### Y9. 板级事实硬编码 + 判据反向依赖文案

- `hwcheck.py:486-487` 写死「stm32 板载三色 LED 在 PC13/PC14/PC15、地猛星用户 LED 是 PA15」
  （真源是 `selection.py:2343-2345` 与 `library/boards/*.json`）；
  `hwcheck_triage.py:362-366` 又把"清单里会出现 PC13"当作引脚白名单的**来源**——改板定义不会改这句话。

### Y10. 数据面小瑕（不影响常用组合，但该记）

- `tcs34725`：同一段"读 ID + 拷 RGB"在 stm32 塞进 **init**、在 mspm0 放 **prereq**，
  且 `tcs34725_init()` 被 init 与 probe **各调一次**（会记两笔判定）。
- 跨平台不对称：`hx711/servo/relay` 的 init 只在 stm32、prereq 只在 mspm0（servo/relay 的 mspm0 格连 probe 都没有）。
- `bh1750/servo/relay` 的 mspm0 格 `prereq` 调 `delay_ms` 但 `include` 段没有 delay 头（靠框架恒 include 兜住，属隐式依赖）。
- 名称层已全量机器核对：57 格引用的函数/宏**零悬空**（`validate_recipes` 那一层是可信的）。

## 三、工程卫生（不进缺陷清单，但影响下一轮的速度）

- **体量**：9 个 hwcheck Python 模块 ≈ 6.8k 行（`hwcheck_recipe.py` 1427 / `hwcheck.py` 1314 最重）；
  前端 `fx/hwcheck.js` 1337 行 / **76 个导出**、`ui/hwcheck.js` 1276 行（仅 2 个导出 + 50 个私有函数，
  `initHwcheck` 一人 272 行绑 15 处委托）；`tests/test_hwcheck.py` 3087 行 / 117 用例。
  按行数切是错的，按职责切才对（fx：状态归一 / 装机渲染 / 计划渲染 / 衔接；ui：core / my-devices / actions）。
- **ui 层没有行为测试**：`tests/js` 里 156 条对 ui 的覆盖全是 `readFileSync` + `includes` 源码串匹配——
  断言"源码里有这行"而不是"点了会怎样"。R2/Y4 这类问题正是这一层的盲区。
- **死导出被守卫保护着**：`export-surface-guard` 把 `tests/js` 也算消费者，
  于是 `hwcheckErrorHTML`（R2）、`project.mainC`、`adviceDegraded` 这类**产品侧零消费者的键**永远抓不出来。
- **账本与自述的漂移**：`module-hwcheck/09` 正文写"16 形态"，其读数文件已重跑为"18 形态"；
  `.scratch/hwcheck-acceptance/报告.md` 与 `报告-复测.md` 已过期（仍写"未发版 / tag 最新 v1.2.2 / 配方 10 件 17 格"）；
  `hwcheck.py:100-107` 相邻两条 docstring 逐字相同；`hwcheck_board.py:278` 把内部工单号"见工单 11"印进了用户可见的 400 文案。
- 浏览器 `hwcheck.spec.mjs` 跑完有两个 `[afterEach] 器件集未清干净：waitForFunction Timeout` 告警（用例本身全绿）。

## 四、改进建议（按投入产出比排序）

### P0 —— 把"达到要求"这件事本身的缺口补上

1. **上板（`hwcheck-acceptance/05`，唯一未开工工单）**：地猛星一件专精件 + 一件未专精件 + 「OLED + I2C 器件」
   那一格 + stm32 一件专精件，现象逐条回填。**在拿到板子之前**，顺手做两件不需要板子的事：
   ① 把 41 格已有的那句「未上板」补到缺的 16 格（pilot 批）——这是**数据加一句**，不是改机制；
   ② 页头/README 加一句总口径（"本栏目的配方尚未在真板上验证"），或明确写进发布说明。
   判据：`grep 未上板 library/hwcheck_recipes.json` 命中 57 格；页面渲染出这一句。
2. **R1 OLED 出口**：三选一（分页 / 逐件固定行 / 如实降级），**先量后定**并同时改 spec 用户故事 6/11 的口径。
   判据：OLED-only 形态能在屏上读到**数值**（≥1 件器件的完整读数），或页面明确说"看不到完整结果"。
3. **R2 预览失败**：`ui` 改用 `hwcheckErrorHTML`（专用文案），失败时**把 main.c 清掉或标记为过期**
   （并在注释里删掉"main.c 只依赖平台与通道"这个不成立的前提）。
   判据：浏览器用例——制造一次预览 400，页面出现"检测程序预览失败"且**不显示上一次的 main.c**。

### P1 —— 已记账却仍会咬到学生的四条

4. **R3 配方文案**：删掉 `hwcheck_recipes.json:474` 那句，并把守卫从 `render_checklist` 输出扩到
   **整个配方文件**（`取消注释` / `注释去掉` 一律红）。判据：反证（把句子塞回去，用例必须红）。
5. **R4 链接器诊断**：`parse_compile_errors` 补"无文件引用的 `#NNNN-D: warning/error`"形态
   （归到伪路径，照 `SYSCFG_CONFLICT_PATH` 先例），`summarize` 不再漏计；
   同时把 `ml_mpu6050` 那格的 `.sysmem` 告警**如实记账**（修驱动或改判据口径，二选一，别让它继续红着不算红）。
6. **Y1 字符池**：报错文案与 `_pool_description` 改成实际可分配数（25），页面在接近上限时**事前**提示。
7. **Y2 行缓冲**：5 条 pilot 读数行的单位说明挪进 `note`；守卫射程扩到全量配方（别只守 `EXPANSION`）。

### P2 —— 体验与工程卫生（可与上面并行，或攒成一批）

8. **Y4 焦点与可达性**：勾选后恢复焦点（记 id，重绘后 `.focus()`）；器件卡补 `role`/`tabindex`/键盘；
   三个输入进 `INPUT_A11Y_LABELS`；编译/烧录/刷新加 `aria-live` 与禁用态。
9. **Y5 记录写**：纳入 `_generation_guard` 或改唯一 tmp 名 + 原子替换。
10. **Y6 星号**：修 3 处，并加一条"`fx` 产出的 HTML 串不许出现 markdown 粗体标记"的守卫。
11. **Y7/Y8/Y9**：syscfg 读失败改成中文 400 明说；记录读失败与"坏 JSON"分开话术；板级事实改从
    `boards/*.json` 与 `selection.py` 取，triage 的引脚白名单不要再以文案为源。
12. **拆分与测试**：按职责拆 `fx/hwcheck.js` / `ui/hwcheck.js`；给 `tests/js` 补一个极小 DOM 桩跑 ui 行为面；
    把 `export-surface-guard` 的消费者集合排除 `tests/js`（让死导出露出来）。
13. **Y3 多实例**：至少让页面/配方说明"多实例只验首路"，或按实例展开（后者要动配方 schema，属新 spec）。
14. **账本收口**：`module-hwcheck/09` 的"16 形态"改 18；两份核查报告加"已过期，见 `local-environment.md` §0"的头；
    删掉 400 文案里的工单号与 `hwcheck.py:100-107` 的重复 docstring。

## 五、一句话

**这套东西的工程完成度足够支撑"手上一两件核心器件的身份 + 读数体检"，也已经能如实标注"未专精"；
但要它真正兑现"看看拿到的硬件能不能正常用"，缺的不是更多配方，而是①一次真机上板、②OLED 出口这条
今天不成立的承诺、③把"未上板"如实说到每一个格上。**

## 附：本次评审的复现方式（全部只读）

```powershell
# 配方与库的覆盖读数（30 slug / 57 格 / 176 格 / 覆盖率）
py -3 -X utf8 -c "import json,pathlib; d=json.loads(pathlib.Path('library/hwcheck_recipes.json').read_text(encoding='utf-8')); print(len([k for k,v in d.items() if isinstance(v,dict)]))"

# 字符池与候选（25 vs 31）
Select-String -Path src\contest_generator\hwcheck_console.py -Pattern 'COMMAND_POOL|CUSTOM_COMMAND_FALLBACK'

# 上板状态与判据漏口
Select-String -Path .scratch\hwcheck-acceptance\issues\05-onboard-acceptance.md -Pattern '状态'
Get-Content .scratch\hwcheck-acceptance\recheck-compile-matrix.txt -Encoding UTF8 | Select-Object -Last 3
Select-String -Path library\hwcheck_recipes.json -Pattern '注释去掉'
```

**证据边界（哪些是本次现跑、哪些是子审计带来的）**：

- **本次现跑核对**：工单计数（35/34/1）、配方 30 slug / 57 格 / 库 176 格、`probe.expect` 35 格、
  未上板自述 41/16、OLED 宽度 88/165、行缓冲 5 条、字符池 31 与已声明 25、`library/hwcheck_recipes.json:474`、
  `recheck-compile-matrix.txt` 的 F 格 FAIL、`oled_show_text(0,0)`→`OLED_ShowString` 的落行语义、
  用例计数（423 / 156 / 21）、模块体量。
- **子审计带来（给了 `文件:行号`，未逐条二次复核）**：字符池天花板的具体件数（stm32 第 23 / mspm0 第 26）、
  `tcs34725`/`hx711`/`servo`/`relay` 的数据细节、前端焦点与 aria 那几条、
  `hwcheck_triage.py:764-770` 与 `hwcheck_board.py:153-156/216` 的行为读数。
- **未做**：本次没有跑 pytest / 前端门禁 / 浏览器门禁，也没有真板。
  **R5 与 P0-1 卡在同一件事上：本机没有板子。**
