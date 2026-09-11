# 10 — 词表顺延批落地：27 条规则可入的裸名（单 08 顺延，预算已复核够用）

**要做什么：** 把单 08 因**预算不足**顺延的 **27 条方案裸名**补进各自所属行的 `models`，
让「模型照抄提示词里的方案名 → 被闸拒收」的可达面再压掉一层。**纯数据改动**，
`SelectionError` 语义、判据、渲染形态全部不动。

**被谁阻塞：** 无（前置 = 单 08 已 resolved；预算前提已被单 05 改掉，本轮已复核）。

**状态：** ready-for-agent

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

- [ ] 红证：27 条现状在 `build_module_selection` 下**全部拒收**（现算留档）
- [ ] 补数据后 27 条**全部不再抛 `SelectionError`**，`name` 原样保留（不擅自改名）
- [ ] 对照：`TI MSPM0 主控板` 仍拒收（闸没被放宽成万金油）
- [ ] 权威口径复核：`test_recommend_real_library_budget` 绿（余量 ≥
      `REQUEST_RESERVE_BYTES`），`measure-20-deferred-headroom.py` 显示 mspm0 仍有余量
- [ ] 词表段未截断（`WORDLIST_PROMPT_BYTES` 内，全量送达）
- [ ] 全量 `pytest` + `node --test tests/js/*.test.mjs` 绿
- [ ] 真机复跑：`python .scratch/recommend-domain-reject/probe-16-recommend-live.py
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
