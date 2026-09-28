# ui-density —— 界面「呼吸感」改造（样板：硬件检测页）

> 立项 2026-09-27。用户原话：「这个 ui 画面好挤啊……一点也不够明朗……小家子气」。
> 流程：`docs/agents/workflow.md` 的 clarify → spec → 工单 → 逐张实现。
> **范围**：先拿检测页做样板，用户认可方向后再推全站（全站推广是本目录之外的下一轮）。

## 文件索引

| 文件 | 是什么 |
|---|---|
| `spec.md` | 需求 spec（问题陈述 / 方案 / 决策 / 测试决策 / 范围外） |
| `issues/01-type-and-space-scale.md` | 工单 01：字台阶梯 + 间距阶梯（检测页落地） |
| `issues/02-unbox-and-emphasis.md` | 工单 02：拆「框套框」+ 让重点会跳 |
| `issues/03-guard-and-evidence.md` | 工单 03：防回退守卫 + 前后对照证据 |
| `issues/04-find-device-entry.md` | 工单 04：「挑器件 / 登记我的器件」入口藏太深（用户报的"点不动"结案在这张） |
| `probe-01-type-census.py` | 排版碎片化读数（字号分布 / 间距令牌引用），改前改后同一把尺子 |
| `probe-01-before.txt` / `probe-01-after.txt` | 上面那支探针的两次读数 |
| `probe-03-contract.py` | 契约机械对账（id 集合 / 既有元素顺序 / 中文文案零删除） |
| `probe-03-contract.txt` / `probe-03-contract-02.txt` | 对账读数（01 / 02 两轮） |
| `probe-04-input-clickable.mjs` | 「输入框点不动」的判据：12 页签滚到底，每个控件三点取样 + 真打字 |
| `probe-04-input-clickable-*.txt` | 上面那支探针的读数（结论：**点击面没坏**，是入口藏太深 → 工单 04） |
| `probe-05-covered-detail.mjs` | 把唯一那个"被盖住"的控件挖开看（一次性诊断件） |
| `probe-02-shot.mjs` | 真浏览器整页截图（真后端夹具，端口内核分配、跑完自收） |
| `shots/` | `before-*` / `02b-after-*` / `04-after-*` × 暗/亮 × 空态/选了器件 × 首屏/整页 |

## 怎么复跑

```powershell
# 读数（改前 / 改后同一把尺子）
$env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density\probe-01-type-census.py --out 读数.txt

# 契约对账（基线取 git 对象，不依赖工作树干净）
$env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density\probe-03-contract.py --out contract.txt

# 截图（先 npm install && npx playwright install chromium）
node .scratch\ui-density\probe-02-shot.mjs after
# 改前那一份：git stash push -- src/contest_generator/static/index.html → 跑 before → git stash pop
```

## 判据边界（别误读）

- **门禁只证明"没改坏"**（前端 1830 / 浏览器 60 / 全量 pytest 读数见工单 01）；
  "好不好看"只有**用户看样板**作数。
- 截图里的"选了器件"那一态是**探针造出来的**（点了 mspm0 平台 + `ml_mpu6050`），
  不是用户数据；空态那一张才是首屏原样。
- 读数探针**故意不含 `module-card`**（器件网格用的共享组件，改它属全站轮），
  混进来会把"这一页改干净没"看糊。
