# 10 — 词表顺延批落地：27 条规则可入的裸名（单 08 顺延，预算已复核够用）

**要做什么：** 把单 08 因**预算不足**顺延的 **27 条方案裸名**补进各自所属行的 `models`，
让「模型照抄提示词里的方案名 → 被闸拒收」的可达面再压掉一层。**纯数据改动**，
`SelectionError` 语义、判据、渲染形态全部不动。

**被谁阻塞：** 无（前置 = 单 08 已 resolved；预算前提已被单 05 改掉，本轮已复核）。

**状态：** resolved（2026-09-17 落地：27 条全收 + 结构守卫 + 真机复跑；见文末「实施记录」）

## 为什么现在能做（单 08 收口那句结论已过时）

单 08 收口写「账面已经没有可降空间，下批必须先瘦身 models 或重议 2KB 自建边界」——
**该结论的前提是「全文段 25600 且边界只剩 731B」**，而**单 05 把全文段改成 23400
（-2200B）**、段级记账也改成可执行。本轮按**权威口径**
（`tests/test_llm.py::test_recommend_real_library_budget` 的完整载荷构造）复核：

| 项 | 实测 |
|---|---|
| 现状最坏形态 mspm0 / stm32 | **125476B**（余 **3548B**）/ **124856B**（余 **4168B**） |
| 顺延 27 条逐条试加 | **可收 27 / 27**（判据：距断言边界留 ≥512B 活动余量） |
| 收下后 mspm0 | **128005B**（余 **1019B**），每条均摊 **94B**、全收 ≈2529B |
| 断言边界 | 129024 = `MAX_REQUEST_BYTES` 131072 − `REQUEST_RESERVE_BYTES` 2048 |

证据：`.scratch/recommend-domain-reject/measure-20-deferred-headroom.py`
+ `verify-20-deferred-headroom.txt`（只读，可复跑）。清单源：
`.scratch/recommend-domain-reject/deferred-18.txt`。

## 27 条的落点（机械反查得出，勿手抄）

判据：name 命中某行 `solutions[].name` 或它的**去括号裸名** → 落该行 `category`。
27 条全部反查得到落点（无一条需人工裁）：

| 行 | 条数 | 名字 |
|---|---|---|
| 感知传感器 | 16 | `SHT30 温湿度传感器`、`红外对射传感器`、`磁力计指南针`、`BMP180 气压/海拔传感器`、`MS5611 高精度气压传感器`、`GP2Y1014AU 粉尘传感器`、`S12SD 紫外线传感器`、`BH1750 光照度传感器`、`TTP224 4 路电容触摸按键`、`TCS34725 颜色识别传感器`、`MLX90614 非接触红外测温`、`MQ-2 烟雾/可燃气体传感器`、`MQ-135 空气质量传感器`、`DS18B20 单总线温度传感器`、`SHT20 温湿度传感器`、`JY61P 六轴姿态传感器` |
| 执行机构 | 3 | `L298N 大电流驱动板`、`1 路 5V 继电器模块`、`PCA9685 16 路舵机板` |
| 语音模块 | 2 | `JQ8900 语音播报模块`、`SYN6288 语音合成模块` |
| 显示模块 | 2 | `0.96 寸 OLED 单色屏`、`MAX7219 数码管/点阵` |
| 遥控接收 | 2 | `双轴摇杆按键`、`红外遥控接收头 VS1838B` |
| 声光提示器件 | 1 | `有源蜂鸣器模块` |
| 无线通信模块 | 1 | `RC522 射频 IC 卡读卡器` |

（单 08 那批按「感知传感器 + 执行机构」两行的经验不适用：本批跨 7 行。）

## 修复方向（实施会话照此做）

1. **补数据**：`src/contest_generator/wordlist.json` 按上表把 27 条裸名加入对应行
   `models`（**去重保序**；已在 models 的不重复加）。落盘前用**机械反查**再确认落点
   （判据见上，照单 08 的先例写一次性脚本，别手抄）。
2. **红证先行**：先跑权威口径量一遍现状（`measure-20-deferred-headroom.py`），
   并现算 27 条各自在 `build_module_selection` 下的判决（现状应全部拒收）。
3. **预算守卫**：补数据后复跑 `measure-20-deferred-headroom.py` + 全量
   `tests/test_llm.py::test_recommend_real_library_budget`（真实库预算绑定测试，
   余量必须仍 ≥ `REQUEST_RESERVE_BYTES`）。**注意词表段还有一道闸**：
   `WORDLIST_PROMPT_BYTES`（截断 = 模型看不到合法名 = 退化成本工单要治的病），
   落盘后确认词表段**未被截断**。
4. **结构守卫**：照单 08 的先例，在 `tests/test_wordlist.py` 把「顺延批 27 条不得再被
   拒收」写成断言（`DEFAULT_WORDLIST` + `build_module_selection` 直测，
   与既有「现场被拒名不得再被拒」同型），并保留 `TI MSPM0 主控板` 仍拒收的对照。
5. **不做的事**：不动 `selection._solution_group`、不动 `OutOfLibrarySuggestion` /
   `degraded` 语义、不动 `format_wordlist_prompt` 渲染形态；**11 条按可达性让位的**
   （`AT24C02 EEPROM` / `OpenMV Cam H7` / `GPS/北斗` / `UWB 定位` / `蓝牙信标定位` /
   `WS2812 幻彩灯带` / `IPS 彩屏` / `HC05 蓝牙串口` / `ESP8266 WiFi 模块` /
   `Zigbee 模块` / `LoRa 数传` / `NRF24L01 2.4G 点对点`）**本批不碰**——它们多数已被
   既有 models 短名覆盖，只在单 08 的裁定里让位。

## 文件边界

- `src/contest_generator/wordlist.json`（唯一产品改动，纯数据）
- `tests/test_wordlist.py`（结构守卫）
- 只读工具：`.scratch/recommend-domain-reject/measure-20-deferred-headroom.py`
  （已就位，权威口径）；落点反查脚本新增在 `.scratch/recommend-domain-reject/`
- **预算不必再改常量**：本批实测只需 ≈2529B，现状余量 3548B 够用；
  若实施中发现必须动 `budget.py` / `llm.py` 的段预算，**先停下来记决策点**，
  别顺手改（单 05 刚立的口径：尺寸断言走 wire 记账、改常量要红证校准）。

## 验收标准

- [x] 红证：27 条现状在 `build_module_selection` 下**全部拒收**（现算留档）
- [x] 补数据后 27 条**全部不再抛 `SelectionError`**，`name` 原样保留（不擅自改名）
- [x] 对照：`TI MSPM0 主控板` 仍拒收（闸没被放宽成万金油）
- [x] 权威口径复核：`test_recommend_real_library_budget` 绿（余量 ≥
      `REQUEST_RESERVE_BYTES`），`measure-20-deferred-headroom.py` 显示 mspm0 仍有余量
- [x] 词表段未截断（`WORDLIST_PROMPT_BYTES` 内，全量送达）
- [x] 全量 `pytest` + `node --test tests/js/*.test.mjs` 绿
- [x] 真机复跑：`python .scratch/recommend-domain-reject/probe-16-recommend-live.py
      --topic 2022C --platform stm32 --attempts 2 --out-prefix done-21` 与
      `--topic 2026H --platform mspm0`（跑前带 `$env:PYTHONIOENCODING='utf-8'`，
      探针在 GBK 控制台会因 `⚠` 崩溃）——期望域拒绝 0 条「硬件名不在硬件词表中」

## 已知坑（照抄，别重踩）

- **预算结论只认权威口径那一套载荷构造**：漏一个段（如 15 条关联参考候选）就会
  少算约 27KB（简化探针实测 97959B vs 权威 125476B）。`measure-18-wordlist-coverage.py`
  的 ② 节已被证伪，docstring 有弃用警示。
- **排序/入选依据是可达性，不是字节成本**（单 08 第一版按成本收，真机当场打到让位名）。
- **提交信息别用 PowerShell 的 `Out-File -Encoding utf8` 生成 `-F` 消息文件**——带 BOM
  会打穿 CHANGELOG 跳过清单（盘点「新发现」第 6 条）；用 `git commit -m` 或 write 工具。

## 实施记录（2026-09-17 落地）

**改动面**：`src/contest_generator/wordlist.json`（+27 条 models，跨 7 行）+
`tests/test_wordlist.py`（+2 条结构守卫）。**零产品代码改动**——`_solution_group` 判据、
`OutOfLibrarySuggestion`/`degraded` 语义、`format_wordlist_prompt` 渲染形态、`budget.py` /
`llm.py` 段预算常量**全部未动**（工单三条硬边界与「不顺手改常量」都守住了）。

**落点机械反查**（`.scratch/recommend-domain-reject/probe-21-deferred-placement.py`，
判据 = name 命中某行 `solutions[].name` **或它的去括号裸名**）：27 条**全部**反查得到
**恰好一行**（0 歧义、0 需人工裁），跨 7 行——与本工单「27 条的落点」表**逐行一致**
（16 / 3 / 2 / 2 / 2 / 1 / 1）。落盘脚本 `patch-21-deferred-wordlist.py` 用同一反查
（不手抄表），幂等（从 `wordlist-before-21.json` = git HEAD 副本重生）。

**红证**：补数据前 27 条逐条真跑 `build_module_selection` → **全部拒收**、理由逐字为
「库外建议的硬件名不在硬件词表中：…」；`TI MSPM0 主控板` 同样拒收（留档
`verify-21-deferred-placement-before.txt`）。补数据后 27 条全部**命中**（非降级），
`name` 原样保留。

**预算与截断（实测，权威口径）**：

| 项 | 补数据前 | 补数据后 |
|---|---|---|
| 词表段全量 / 实发 wire | 9619B / 9619B（未截断） | **10994B / 10994B**（未截断） |
| mspm0 最坏形态 | 125476B（余 3548B） | **126851B（余 2173B）** |
| stm32 最坏形态 | 124856B（余 4168B） | **126231B（余 2793B）** |
| `test_recommend_real_library_budget` | 绿 | **绿**（余量 2173 ≥ `REQUEST_RESERVE_BYTES` 2048） |

词表段实发 10994 < `WORDLIST_PROMPT_BYTES` 12150 ⇒ **全量送达、未被截断**
（余 1156B）。**段预算常量一个没动**。

⚠️ **两处口径更正（都是量法问题，不是产品问题）**：

1. **本批真实成本是 +1375B，不是工单预估的 ≈2529B**（每条均摊 51B，不是 94B）。
   工单那个数是 `measure-20-deferred-headroom.py` 的**截断记账假数**：该脚本的
   `with_names` 把 27 条**重复加到「感知传感器 + 执行机构」两行**（本批真实落点跨
   7 行），该形态下词表段超过 12150 **被 fit 截断到 12150**，于是「再加一条」的边际
   字节被截断吃掉——摊出来 94B/条是截断的产物。真实 7 行形态不截断，实测 +1375B。
   **结论不变且更宽松**：余量 2173B 充足。复算留档
   `probe-21-reconcile-deltas.py` + `probe-21-authoritative-after.py`。
2. **`measure-20-deferred-headroom.py` 的「现状最坏形态」读数在补数据后不可直接信**：
   它 import 时读盘固化 `DEFAULT_WORDLIST`，脚本内又用「现状 + 逐条试加」的算术，
   两截口径不同（实测它报「现状 125476 / 收下后 128007」，而真实的「已落盘词表 +
   这 27 条」是 126851）。**判余量只看 `probe-21-authoritative-after.py` 或
   `test_recommend_real_library_budget` 这一套**（同一份落盘词表、同一条载荷构造）。

**结构守卫**（`tests/test_wordlist.py`，照单 08 先例同型）：新增
`test_default_wordlist_deferred_batch_names_are_legal_now`（27 条现算必须「合法」）
与 `test_default_wordlist_deferred_batch_landed_in_home_rows`（**落点行守卫**——
落错行不会让前者红，闸只要任何一行认它就放行，所以单独守一层：`_solution_group`
命中的行必须就是「该名字作为方案名/裸名出现的那一行」）；`TI MSPM0 主控板 仍拒收`
对照照旧保留。

**真机复跑**（`--out-prefix done-21`，带 `PYTHONIOENCODING=utf-8`）：
**2022C / stm32 终态 done（2 轮）**、**2026H / mspm0 终态 done（4 轮）**，
两跑**「硬件名不在硬件词表中」拒收 0 条**——验收线达成。证据
`verify-21-recommend-{2022C-stm32,2026H-mspm0}.txt` + `done-21-*.json` +
`verify-21-live-verdicts.py`（机械核：日志域拒绝分类 + done 载荷里每条库外建议名
过 `_solution_group`，两跑未命中 = 0）。

- ⚠️ 两跑的**澄清门**要答才到 done（与单 08 同）：2022C 首跑停在补问
  「车-车间通信是否限定无线模块」，加 `clarify-answers-21-2022C.json` 后 done。
- ⚠️ **多实例域拒绝是另一条线的病**（**非本单范围**，如实记）：2026H 出现 3 条
  「模块 k230 不支持多实例，不能带 instances」、2022C 首跑出现 1 条
  「模块 pid 不支持多实例」——都是模型给非多实例模块塞 `instances`，由
  `DOMAIN_RETRY_LIMIT=1` 自愈（两跑最终都 done）。**与词表闸无关**，要不要治另议。

**回归面**：`python -m pytest -q` → **3973 passed, 1 warning**（基线 3971 → 净增 2 =
两条新守卫）；`node --test tests/js/*.test.mjs` → **1444 pass / 0 fail**（无 JS 改动）。
