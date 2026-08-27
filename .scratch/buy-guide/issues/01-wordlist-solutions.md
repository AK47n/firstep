# 工单 01：词表 solutions 扩展 + 后端装配（wordlist / selection / llm）

> 来源：.scratch/buy-guide/spec.md §2.1-2.2
> 状态：resolved（双轴评审通过，整改项已修：命中判定单源收敛、词表段预算重标 4200 + 标注进预算、词表内容对齐工单原文、REFERENCE_FULLTEXT_BYTES 64000）

**要做什么：**
- `wordlist.py`：新增 `SolutionOption` dataclass（name / interface / price / note / suitable / recommended=False，全 str）；`HardwareWordGroup` 加 `solutions: tuple[SolutionOption, ...] = ()`；`load_wordlist` 解析 + 形状校验（solutions 非数组 / 条目非对象 / 缺 name → WordlistError；`recommended` 非 bool → WordlistError；旧词表无 solutions 键 = 空，向后兼容）。
- `selection.py`：
  - `OutOfLibrarySuggestion` 加 `solutions: tuple[SolutionOption, ...] = ()` + `selected: str = ""`（selected = LLM 从词表 solutions.name 中选的 AI 建议方案，未选 = 空串）。
  - `_parse_suggestions`：解析后按词表 category 或 models 命中填充 solutions（降级类别名也可命中）；解析 LLM 可选输出的 `selected`（值必须 ∈ 该类 solutions.name，否则置空不报错——编造不高亮不阻断）；`to_dict()` 带出 solutions（每项 dict）+ selected。
  - 注意依赖方向：selection 已 import wordlist？（检查：_parse_suggestions 应能拿到词表组——hw_words 参数已存在，用它查 solutions，不要重新加载词表）。
- `llm.py`：选模块提示词科普段尾部加一行：库外建议「请从词表 solutions 的 name 中选一个作为 selected（并给出选择理由），不得自创方案名；无合适方案则不选」（单源常量，快照测试断言）。
- `wordlist.json`：首批内容——遥控接收 3 方案（红外 VS1838B / NRF24L01+手柄 / 蓝牙 HM-10）、感知传感器 3 类（超声波 3 方案 HC-SR04 / JSN-SR04T 串口 / VL53L0X 激光；红外 2 方案 循迹数组/避障；磁力计 3 方案 QMC5883L / HMC5883L / IST8310）、无线通信 4 方案（NRF24L01 / 蓝牙 / ESP8266 WiFi / LoRa）、定位 3 方案（NEO-6M GPS / UWB / 蓝牙信标）、视觉 3 方案（K230 / OpenMV / 串口摄像头）、执行机构 3 方案（TB6612 双路 / L298N / 自带驱动板）。价格一律文字区间（如「￥2-5/套」）。

**被谁阻塞：** 无。

**验收标准：**
- [x] wordlist 解析：合法 / 缺省空 / 缺 name 报错 / recommended 非 bool 报错
- [x] selection sugerencias 填 solutions（category 命中 / models 命中 / 降级类别名 / 词表无解决方案 = 空）
- [x] selected 词表内保留、词表外置空
- [x] to_dict 带 solutions + selected
- [x] llm 提示词新行单源 + 快照断言（test_wordlist_segment_covers_default_wordlist_and_budget：默认词表全类别/方案名全量送达 + 截断标注进预算）
- [x] wordlist.json 首批方案每类 ≥3 条、recommended 每类 ≤2（感知传感器 8 方案 = 超声波 3 + 红外 2 + 磁力计 3，遥控制 3，无线通信 4，定位 3，视觉 3，执行机构 3）
- [x] 全量 pytest 绿（2564 passed）；中文 commit
