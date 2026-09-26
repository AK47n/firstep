# 09 — 自建件被删掉之后仍留在选择集里 → 预览 400「库中不存在模块：mine_xxx」

**要做什么：** 让"选中的自建件已经不在用户器件库里"这个状态**自愈或有话直说**，而不是把整页
预览打成一个 400，还把它说成"库里不存在模块"（那是**库内 slug** 的错话）。

**被谁阻塞：** 无——可立即开始。但**修法有取舍**（下面「两条出路」），要人拍板。

**状态：** resolved（**自愈 + 明说**：后端摘掉 + 如实下发 `dropped_devices`，页面说一句）

- [ ] 定性已完成（见 Comments，CI 上有逐字证据）：**不必再复现**，直接进修法选择
- [ ] 按拍板的修法实现；判据落在**既有缝**上：`tests/test_my_devices_endpoint.py` 的自建件族
      （端点面）与 `tests/js/hwcheck.test.mjs`（前端载荷/提示，若选前端侧修法）
- [ ] 反向用例：选中的自建件**已被删除**时，预览不再 400、页面给出那句说明；
      且**库内 slug 写错**仍照旧 400（别把这道守卫一起放松了）
- [ ] 中文提交

## Comments

### 现场（2026-09-26，CI run `36216009452` 的浏览器门禁 job —— 本单是诊断抓出来的）

那两条红（`:818` 自建件的串口复测、`:914` 装不下时的出路）本机复现不出来，于是本轮给它们加了
诊断（工单 08）。CI 上诊断一次就答出来了，逐字：

```
[诊断] 接线区 #hwcheck-wiring → 接线表与冲突暂时取不到：请求失败（HTTP 400）：库中不存在模块：mine_probe692113
[诊断] 末几次 /api/hwcheck/preview 响应 →
  {"status":400,"body":"{\"detail\":\"库中不存在模块：mine_probe692113\"}"}   ×3
```

`mine_probe692113` 是**上一条用例（`自建件的检测计划`）的自建件**：那条用例先 `生成检测工程`
（`HWCHECK_LAST_DIR_KEY` 因此指向它，且工程上下文里记着 `devices: [mine_probe692113]`），
**收尾时把这件自建件删掉了**（`myDeviceCleanup`）。下一条用例 `openTab()` 打开栏目时，
栏目按 `HWCHECK_LAST_DIR_KEY` **回读上一次的检测工程**（`restoreHwcheckProject`），
于是那个**已经被删掉的自建件**又进了选择集 → 下一次预览带着它 → 后端按"库外 slug"守卫拒掉。

**为什么这是产品缺陷、不只是测试卫生**：真实用户走得到同一条路——选上自己的器件 →
在「我的器件」里把它删了 → 预览/生成答 400「库中不存在模块：mine_xxx」。
那句话**指错了地方**（`mine_*` 从来不是库内模块，用户也没法去"库里"找它），
页面就此卡住，唯一的出路是手动把那个 chip 去掉。

### 两条出路（请拍板）

1. **自愈 + 明说**（推荐）：后端把"选择集里已经从器件库消失的 `mine_*`"**摘掉**并在载荷里如实
   报出（如 `dropped_devices`），预览照常出；页面补一句中文：「『X』已经不在你的器件里了，
   这次检测已把它摘掉」。判据两条：不再 400 + 那句说明在场；**库内 slug 写错仍 400**（守卫不放松）。
2. **只说清楚**（最小改动）：保留 400，但把消息改成能指路的中文（「自建件 mine_x 已不存在
   ——可能已被删除，请把它从器件清单里去掉」）。代价：页面仍卡住，用户得自己动手；
   `:818`/`:914` 两条用例也仍会红（除非它们自己把脏 chip 摘掉）。

> 本条**不并进 08**：08 是"CI 上没有工具链"那条线（编译按钮置灰 → 显式 skip），
> 与本条同源不同因（这条与工具链无关，是**选择集里带了一个已消失的自建件**）。

### 根因（读代码读出来的两处，不是猜）

`hwcheck_view` 里那段"把选中的自建件从模块集里摘掉"的注释写着**"全体"**，
代码取的却是**交集**：

```python
custom = {device.id for device in custom_devices} & set(selected)   # 旧写法
module_slugs = [s for s in hwcheck_modules(config) if s not in custom]
```

——只摘掉"器件库里还在"的那些，**已删的那件**因此一路往下走。而它踩到的是**两处**闸门：

1. `resolve_dependencies(module_slugs, by_slug)` → `UnknownModuleError`「库中不存在模块：mine_xxx」
   （`selection.py:268`）；
2. `hwcheck_board_view(..., devices=selected, custom_device_ids=custom)` 里的
   `_missing_devices` → `check_platform_warnings` → **同一个** `UnknownModuleError`
   （第二处是修完第一处之后当场暴露的——两处都得让路）。

### 修法（已实现）

- `hwcheck_board.py`：新增 `dropped_custom`（选中的 id 里 `mine_` 前缀、既不在库内
  `by_slug`、也不在器件库里的那些）；`excluded = custom | set(dropped_custom)` 用于
  `module_slugs` 过滤，并且**同一个集合**作为 `custom_device_ids` 传给板侧视图
  （"这些是自建件、不是缺条目的库内模块"——已删的那件同样是"还不是模块"）。
  守卫**不放松**：非 `mine_` 前缀的库外 slug 照旧 400。
- `HwCheckView.dropped_devices` + 预览/生成两个端点下发 `dropped_devices`。
- 前端：`fx/hwcheck.js` 的 `hwcheckDroppedNoteHTML`（一条件一句话，中性提示、转义）；
  `ui/hwcheck.js` 的 `applyDroppedDevices`（**对齐本地选择集**——摘掉的件不再算已选，
  否则界面与服务端不一致）＋ `renderHwcheckDropped`；`index.html` 新容器
  `#hwcheck-dropped`（在 device-chips 之下）+ 一条 CSS。

### 收口读数

| 判据 | 读数 |
|---|---|
| 新用例 `test_a_deleted_custom_device_is_dropped_and_reported_not_400` | **修前红 / 修后绿**（`git stash` 掉产品改动跑：2 failed → 恢复后 2 passed） |
| 新用例 `test_a_deleted_custom_device_no_longer_blocks_generate` | 同上（生成这条路也不再 400，工程照常落盘） |
| 既有守卫（库内 slug 写错仍 400） | 未动：`test_passing_a_custom_device_id_as_a_device_does_not_400` 等 4 条同族用例全绿 |
| 前端纯函数 | `tests/js/hwcheck.test.mjs` 156 passed / 0 fail（含新增的说明条 4 组判据） |
