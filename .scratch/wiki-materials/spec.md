# 立创 wiki 地猛星移植手册接入工具（素材浏览入口 + 模块提炼）

## 问题陈述

立创地猛星 wiki 的 70 篇模块移植手册已抓取为 Markdown（`sources/materials/lckfb-地猛星移植手册/`，含 70 篇手册 + 模块索引 + 网盘索引，共 17MB，gitignore 不入库），但**用户在工具里看不到它们**：现有「PDF 资料库」tab 只列 `.pdf`，这批 `.md` 无法浏览、无法搜索、无法预览。同时手册里含大量电赛常用器件（彩屏/称重/温湿度/超声波/幻彩灯等）的地猛星（MSPM0G3507）完整驱动源码（`bsp_*.c/h` 全文），但模块库里没有对应条目——用户做题选模块时 AI 不知道库里有这些驱动，只能当作"需自备"。

## 方案

分两步：

**步骤① 素材浏览入口**：在「PDF 资料库」旁新增「Markdown 资料」tab——素材根（`sources/materials`）下全量 `.md` 的直通入口（照 pdf_library + tab-pdf 先例：批次 = 第一级目录、名字串过滤、排序、统计、批次 chips、页内渲染预览）。`lckfb-地猛星移植手册/` 天然是一个批次，70 篇手册 + 2 篇索引全部可见。

**步骤② 模块提炼（首批 4 个，仅 mspm0）**：从手册里挑 wiki 页面**自带完整驱动源码**、模块库目前**没有**、电赛常用度高的 4 件，按模块库规范（manifest + ADR 0009 纯驱动切片 + 简介判据①②③④ + 平台条目 + 编译验证）提炼入库：

| slug | 手册（文件名） | 器件/总线形态 | 引脚角色 |
|---|---|---|---|
| `ws2812` | control--ws2812-color-rgb-led.md | WS2812 幻彩灯，单 GPIO 位操作时序 | 1 × gpio_out |
| `hx711` | sensor--hx711-weighing-sensor.md | HX711 称重（增益 128），双 GPIO 时序 | 1 × gpio_out(SCK) + 1 × gpio_in(DT) |
| `aht10` | sensor--aht10-temp-humi-sensor.md | AHT10 温湿度，软 I2C 位操作 | 2 × gpio（SCL/SDA） |
| `sr04` | sensor--sr04-ultrasonic-ranging-sensor.md | HC-SR04 超声波测距，TRIG + ECHO + 1ms 定时器 | 1 × gpio_out + 1 × gpio_in + 1 × TIMER 实例 |

**已排除（本批）**：彩屏 ST7735/ST7789 系列——wiki 页面只有移植改动片段（typedef/引脚宏/空 init），完整 `lcd.c/lcd_init.c/pic.h` 在百度网盘厂家例程里，**不下载网盘无法提炼**（用户裁决：跳过彩屏先炼完整源，网盘下载策略后续再议）。MPU6050、灰度/循迹——模块库已有 `ml_mpu6050`、`huidu`/`pid`/`xunji` 条目，不重复提炼。

## 用户故事

1. 作为做题用户，我在「Markdown 资料」tab 里能看到素材根全部 70 篇手册 + 索引，按批次/文件名过滤、排序，点开在弹窗内渲染预览（代码块带高亮），不用离开工具。
2. 作为做题用户，我选中 `ws2812`/`hx711`/`aht10`/`sr04` 后，工具自动分配引脚（默认脚，可选绑）、生成工程里直接可编译、可调用（init + 服务函数）。
3. 作为做题用户，我调用 `ws2812` 设置颜色、`hx711` 读重量、`aht10` 读温湿度、`sr04` 测距离时，不需要再读传感器资料——驱动已按手册时序封装。
4. 作为维护者，我在模块库浏览每个新条目时能看到平台条目（verified/硬件身份 kit+source_url/备注含手册来源与改动说明），能追溯到手册原文、原页链接与网盘链接。
5. 作为维护者，新模块随 manifest 补入 wordlist 词表方案（lib_modules 挂接 + 硬件词表），推荐链路与买件指引能认出它们。

## 实现决策

### 步骤① Markdown 资料入口

- **后端**：新域模块 `md_library.py`（照 `pdf_library.py` 同构，独立模块不并入 pdf_library——职责清晰，PDF 专属逻辑不污染）：
  - `list_markdowns(root, name="")` → `[{rel_path, name, batch, size_bytes, mtime}]`，递归收集 `.md`（扩展名大小写不敏感），批次 = 第一级目录，按 (batch, rel_path) 排序；素材根缺失 = 空清单。
  - `resolve_markdown(root, rel_path)` → 路径安全校验（`is_unsafe_path`）+ 存在性 + `.md` 后缀，失败抛 `ReferenceError`（webapp 映射 400，与 pdf_library 同通道）。
- **webapp 路由**（注册在 pdf 路由区旁）：
  - `GET /api/materials-md`（清单，`name` 过滤）；
  - `GET /api/materials-md/{rel_path:path}`（全文 JSON `{rel_path, name, size_bytes, content}`——前端拿文本用 `fx/markdown.js` 页内渲染；**上限 `MD_FILE_MAX_BYTES = 1MB`**（照 codeview 先例，超限 400 中文；单篇手册均 <300KB，不会误伤）。路径安全与大小校验全在库内，路由只转调。
- **前端**：新 tab「Markdown 资料」（nav 按钮 + section，位置紧挨「PDF 资料库」）：
  - `fx/md.js` 纯函数组（对偶 `fx/pdf.js`）：`mdFilterEntries`（文件名/批次/目录/路径四合一子串过滤）/ `mdSortEntries` / `mdStats` + `mdStatsText` / `mdChipRowHTML` / `mdRowHTML`（文件名行 + 批次 chip + 目录 + 大小 + 修改时间 +「预览」「复制路径」钮）/ `mdEncodedPath`（逐段编码）。
  - `ui/md.js` DOM 胶水（对偶 `ui/pdf.js`，无页数/重复/回收——PDF 专属语义不移植）。
  - 预览弹窗：复用 `ref-files-overlay` 遮罩 + `fx/markdown.js` 的 `parseMarkdownBlocks` + `markdownPreviewHTML`（与 code-viewer 的 md 预览同一条渲染管线，代码块自带高亮）；懒取 memo（按 rel_path），400 缓存可重试、网络/500 不缓存。正文内相对路径图片不适用（wiki 抓取正文图 0），`opts.imageUrl` 置空。
- 索引文件（模块索引.md / 网盘索引.md）作为普通条目一并列出。

### 步骤② 模块条目（4 个，仅 mspm0 平台条目）

- **代码提炼**：从手册「代码块」章节抽取完整 `bsp_xxx.c/h`（正文内嵌段落不可直接复制——抓取脚本把正文包裹代码按行拆散了，**代码块章节才是完整源码**），按模块库规范改造：
  - API 标准化为纯驱动切片：`xxx_init()` + 服务函数（读/写/换算），丢弃手册里的 main.c 演示与 printf 调试，不留状态机/调度（ADR 0009）；SR04 的 1ms 定时器中断计数保留（驱动测距必需，照 ntb_time 的 `NTB_INST_IRQHandler` 先例）。
  - 时序延时全部走库内 `delay` 模块（`dependencies: ["delay"]`——4 个模块的位操作全靠 `delay_us`，库内 mspm0 已有）。
  - 引脚宏改写为参数化角色（manifest pins + 母版 syscfg 实例名）；不写死立创宏名（`GPIO_PORT`/`GPIO_SCL_PIN`/`GPIO_SDA_IOMUX` 等）。
- **母版 syscfg 与登记**（照 ir_beam 先例）：
  - `mspm0.syscfg` 新增实例：WS2812 → 1 个 GPIO 输出实例（1 associatedPin）；HX711 → 1 个 GPIO 实例（2 associatedPins：SCK 输出 + DT 输入）；AHT10 → 1 个 GPIO 实例（2 associatedPins：SCL/SDA）；SR04 → 1 个 GPIO 输出实例（TRIG）+ 1 个 GPIO 输入实例（ECHO）+ 1 个 TIMER 实例（Basic_Periodic 1ms 中断，闲置 TIMGx）。
  - `syscfg_instances.py` 的 `INSTANCE_CONSUMERS` 登记（每实例 → 对应 slug）。
  - 默认引脚：从地猛星 2×20 排针空闲脚选择，**不与母版现有默认布局重叠**（对齐「母版默认布局 = 模块库默认引脚方案」注释约束；实施时用板定义 + 现有默认值清单核对，冲突则换脚）。
- **manifest**：
  - 平台条目：仅 `mspm0`（缺 stm32 条目 = 该平台无版本，生成时 missing 警告——imu_uart 先例）；`files = code/*.c, code/*.h`；`verified` 初始 false，编译矩阵跑完转 true；`hardware_bound: false`（通用驱动不绑定具体件）。
  - `kit` / `source_url`（简介判据②）：套件型号按手册「模块来源」采购链接文本定（如 "WS2812 幻彩灯带"），source_url 取手册原页链接（URL 格式合法，视为资料溯源；商家购买链接可后续由人补填）。
  - 简介判据③④（能力方向 + 无题绑定）：声明多值能力方向（如 ws2812 → "RGB 幻彩指示/氛围灯效"；hx711 → "电子称重/拉力检测"；aht10 → "环境温湿度采集"；sr04 → "超声波测距/避障"），全文过库内 BANNED_TOPIC_WORDS 机械拦截（无题号/年份/题名）。
  - 备注（notes）：写明「手册来源：`sources/materials/lckfb-地猛星移植手册/<文件名>` + 原页链接 + 网盘链接（如需完整工程）」、改造要点（删 printf/改引脚宏/接 delay）、编译矩阵记录。
- **wordlist 补录**（照 ir-beam-module/02 先例）：`wordlist.json` 感知传感器/显示组加 4 条方案（名称 + `lib_modules` 挂接）；硬件词表加可选词条。
- **编译验证**：复用 module-polish 编译矩阵配方（`.scratch/module-polish/compile_matrix.py`：生成单选工程 → gmake（`C:/ti/ccs2050` 自带）→ 0 error 为硬门槛、模块自身 warning=0、syscfg 基线 warning 记录）——每模块一张矩阵，结果写回 manifest verified/notes。

## 测试决策

- **步骤① 后端**（照 `test_pdf_library.py` 先例，最高既有接缝）：`tests/test_md_library.py`——清单字段/批次推导/过滤/排序、路径安全拒绝面（绝对路径/.. /盘符/反斜杠/空段）、非 .md 拒绝、超 1MB 拒绝、素材根缺失空清单；webapp 端点两态（清单 + 单文件内容、非法路径 400 中文）。
- **步骤② 每个模块**（照 `test_module_ir_beam.py` + `test_pins.py` 先例）：
  - manifest 结构测试自动覆盖（全库扫描已有）；`test_pins.py::MSPM0_DEFAULT_MAP` 增默认脚映射；`test_syscfg_prune.py` 增新实例保留/裁剪断言；`test_makefiles.py`（若涉及 makefile 产物）与生成级测试（单选生成 → syscfg 含对应实例 + 模块文件落盘 + main.c 调 init/服务函数过静态门禁）新增 `test_module_ws2812.py` / `test_module_hx711.py` / `test_module_aht10.py` / `test_module_sr04.py`。
  - 编译级验收：4 模块逐一 gmake 真编译（± 工具链在 `C:/ti/ccs2050`，已验证存在）。
- **前端纯函数**：`fx/md.js` 无单测先例（历史同侪 fx/pdf.js 亦无），以人工验收 + 对偶审查保证；不新增 JS 测试基建。

## 范围外

- 彩屏（ST7735/ST7789/GC9A01 等 12 篇 screen 手册）——wiki 页无完整驱动源码，待网盘下载策略定案后另立项；0.96 彩屏已有 oled 模块（SSD1306）不在此列。

  说明：用户裁决「跳过彩屏，先炼完整源」；网盘下载（126 链接）本身不在本 spec，如需完整工程/DEMO 再议。
- 「PDF 资料库」现有 PDF 逻辑（页数/重复/回收/trash）不为 Markdown 复制；不做 .md 回收删除。
- stm32 平台条目（逐飞 ml_libs 无对应驱动，属后续双平台移植项）。
- MPU6050 / 灰度循迹（库内已有条目，不重复）。
- 参考文件库入库（手册作 AI 学习素材注入生成链）——与参考库「赛题/套件锚定」定位不完全吻合，且 17MB 全量注入成本高，另议。
- 手册正文中的既有 bug/历史代码缺陷修复不在本批（按手册源码提炼，编译过即可；运行期偏差留真机验证）。

## 补充说明

- 素材目录 gitignore 不入库：md_library 纯读盘，不依赖 git 状态（与 pdf_library 同）。
- 手册抓取脚本（`.scratch/materials-wiki/fetch_wiki.py`）重抓时文件名/结构不变，md_library 无兼容负担。
- module-polish/04 编译矩阵结论（2026-08-15）表明 gmake 全链路可行；本批每模块独立矩阵，不合并批次。
- 工单编号：`issues/01-markdown-library-backend.md`（后端）→ `02-markdown-library-frontend.md`（前端，阻塞 01）→ `03-module-ws2812.md` / `04-module-hx711.md` / `05-module-aht10.md` / `06-module-sr04.md`（四模块互相独立，均不依赖 01/02——其 manifest notes 引用手册路径为文本引用，无需入口先行；01/02 与 03-06 并行推进）。
