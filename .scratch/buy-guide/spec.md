# 库外建议买件指引（buy-guide）

> spec 状态：draft（用户已拍板：必给多方案、思想打开、方便用户选择）
> 关联：工单 10 库外建议（wordlist.py / selection.py，已 resolved）· wordlist.json 8 类

---

## 一、问题陈述

库外建议（无库内实现的功能的外设推荐）现在只有 `name + examples`（常识举例，仅展示）。
用户实际场景（原话）：「告诉用户需要什么模块，如果是库外的，然后用户去买后商量该怎么去选择方案购买模块」——缺的是**选型层面**：
- 不知道这个缺件有几条技术路线可走（如遥控接收：红外 / 2.4G / 蓝牙 / WiFi，接口、价格、难度完全不同）；
- 只能看到推荐名，没有方案对比，无从「商量怎么选」；
- 买了之后任务推进虽然能写驱动（补充框通道已通），但买之前无指引。

## 二、方案

### 2.1 词表扩展（确定性知识，LLM 不编造）

`wordlist.json` 每个条目组新增 `solutions`：该类别（或具体型号）的**方案列表**，3-5 条为佳（多方案、多技术路线、多价位档），每条：

```json
{
  "category": "遥控接收",
  "models": ["红外遥控接收头", "NRF24L01"],
  "solutions": [
    {
      "name": "红外遥控接收头 VS1838B",
      "interface": "GPIO 中断 + NEC 解码（需自写解码）",
      "price": "￥2-5/套",
      "note": "一个接收头+一个遥控器；视距 8m；占 1 个定时器",
      "suitable": "现场遥控启动/停车；室内无遮挡",
      "recommended": true
    },
    {
      "name": "NRF24L01 2.4G 遥控（含手柄）",
      "interface": "SPI（模块库已有 uart，SPI 需自写或走 STM32 裸寄存器）",
      "price": "￥15-30/对",
      "note": "双向、可多机；需 SPI 驱动与配对逻辑",
      "suitable": "双车协同/远距遥控（>8m）"
    },
    {
      "name": "蓝牙遥控（HM-10 / HC-05）",
      "interface": "UART 透明传输",
      "price": "￥10-20/个",
      "note": "手机 App 直接控；无需自写协议，代价是现场手机干扰",
      "suitable": "室内调试 / 手机方案"
    }
  ]
}
```

字段：`name`（方案名，可含型号）/ `interface`（接口与实现难度一句话）/ `price`（参考价档，文字区间）/ `note`（关键注意点）/ `suitable`（适用场景）/ `recommended`（词表级推荐，可多个 true 但每类至多 2 个，false 或不写 = 非推荐）。

### 2.2 后端装配

- `HardwareWordGroup` 加 `solutions: tuple[SolutionOption, ...]`（新增 `SolutionOption` dataclass，字段如上，`recommended: bool = False`）；`load_wordlist` 解析（缺省 `solutions` = 空，旧词表向后兼容；`solutions` 非数组/条目非对象/缺 name = WordlistError 大声失败，宁缺毋编）。
- `OutOfLibrarySuggestion` 加 `solutions: tuple[SolutionOption, ...] = ()` 与 `selected: str = ""`（LLM 从词表 solutions.name 里选的「AI 推荐方案」，未选 = 空串；**展示层仍展示全部方案**，selected 只是默认高亮）。
- `_parse_suggestions`（selection.py）：解析后**按词表 category 填充 solutions**（匹配 = category 或 models 命中的那条的 solutions；词表外降级类别名同样能填）；LLM 可选输出 `selected`（词表 solutions 名字内校验，词表外置空不报错——编造不阻断导览，只不高亮）。
- `suggestion.to_dict()` 带出 `solutions`（每项 dict）+ `selected`。
- 提示词（llm.py 选模块 prompt）：科普段尾部加一行「库外建议的解决方案请从词表 solutions 的 name 里选一个作 selected（并给理由），不要自创方案名」。

### 2.3 前端（推荐确认页）

- `suggestionChip(s)` 升级：名称后加「⤵ N 方案」徽标（N = solutions 长度；0 = 现行为）。chip 变为可展开（点击 toggle）：下方展开「选型参考」面板：
  - 每方案一行：`名称` + `[接口]` + `[价格]` + `推荐↑`/`AI 建议` 徽标（recommended / selected） + `备注` + `适用：...`；
  - 展开状态动画/样式复用现有 chip 风格；再次点击收起。
- 无 solutions 的建议芯片保持旧样（仅 name + 「需自备」）。
- 不新增对话框/弹窗，全部卡片内展开（0 构建原生 ESM 约束不变）。

## 三、用户故事

1. 作为学生，推荐看到「需自备：遥控接收」时，点开看到 3 个方案（红外/2.4G/蓝牙），有接口、价格、适用场景对比，选了红外（便宜、简单）。
2. 作为学生，AI 已从题面判断「场地 8m 内、室内」推荐红外，我在前端看到「AI 建议：红外遥控（视距 8m，适合室内）」徽标，但也能看其他方案。
3. 作为学生，看到某建议没有方案（词表未覆盖）——chip 保持旧样式，不误导。
4. 作为学生，我在清单里看到多个缺件都是多方案，可以逐个「商量」哪条路线。
5. 作为学生，词表方案写的是「￥2-5/套」这种档位而非精确价——不被价格锚定，实际以淘宝为准。

## 四、实现决策

1. **知识确定性**：方案全部来自 `wordlist.json`（可手补，同现词表机制）；LLM 只选 `selected`，不生成方案文本。价格一律文字区间（`￥2-5/套`），不写精确数字——避免模型编造。
2. **推荐标记双轨**：`recommended`（词表知识定，静态）与 `selected`（LLM 按题面定，动态）并存；前端徽标区分「推荐」与「AI 建议」，互不覆盖。
3. **降级兼容**：`solutions` 缺省空 + 旧词表无该键 = 完全现行为；`selected` 词表外直接置空。
4. **范围**：只改推荐展示层与词表，不建新端点、不动任务推进 / 生成 / 骨架、不做用户「已购清单」持久化（购买后走题面/补充框通道——已有）。
5. **词表首批内容**：遥控接收（3 方案）、感知传感器（超声波 3 方案 / 红外 2-3 / 磁力计指南针 3）、无线通信（NRF/蓝牙/WiFi/zigbee 4）、定位（GPS 北斗 / UWB / 蓝牙 3）、视觉模块（K230 / OpenMV / 摄像头直读 3）、执行机构（电机驱动板多方案 3）。每类 3-5 条，思想打开。

## 五、测试决策

- `tests/test_wordlist.py` 扩展：solutions 解析（合法/缺省空/差 name 报错/非数组报错）；SolutionOption 字段默认。
- `tests/test_selection.py` 扩展：suggestions 填充 solutions（匹配 category / 匹配 models / 降级类别名也填 / 词表无 solutions = 空）；selected 词表内保留、词表外置空。
- `tests/test_llm.py`：提示词科普段含新行（快照级断言）。
- 前端 `tests/js/recommend.test.mjs`：chip 徽标数 / 展开渲染方案行 / recommended+selected 徽标 / solutions 空退回旧样。
- 全量 pytest + JS 绿。

## 六、范围外（明确不做）

1. 词表外缺失方案的自动生成（LLM 编造方案 = 禁止，宁缺）。
2. 用户「已购清单」持久化与选中方案的跨会话记忆（后续如需另立 feature）。
3. 任务推进/骨架生成注入方案信息（本轮仅推荐展示）。
4. 精确价格/链接/购买渠道表单（价格档位 + 建议搜索关键词即可——note 里写）。
