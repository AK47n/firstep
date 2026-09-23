# 02 — 「我的器件」：定义形状 + 数据目录 + 端点 + 检测页表单

**要做什么：** 检测页多出「我的器件」：学生能新增一件库外器件（名称 / 总线 / 7 位地址 / 身份寄存器 / 期望值 / 备注），保存后下次还能选，可改可删。数据落在**工具数据目录**（不进产品库根）。这一张**不生成任何代码**——先把"事实"这条路打通。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] 定义落 `<配置目录>/hwcheck_devices/<id>/device.json`（目录即数据库），资料副本目录 `materials/` 预留；**不进 `library/`**、不进 git、不随发布包分发
- [x] 字段与校验（全部是事实，没有一项推导）：`id`（`mine_` 前缀 slug 形）、`name`、`bus`（词表 `i2c`/`spi`/`uart`/`onewire`/`analog`/`gpio`/`other`）、`address`（**7 位** 0x08–0x77，`bus=i2c` 必填）、`register`（8 位，可选）、`expect`（8 位，可选；填了 `expect` 就必须有 `register`）、`notes`（可选）、`created_at` / `updated_at`
- [x] `id` 与库内 slug 冲突 → 400 中文**当场点名要求改名**（不静默加后缀）
- [x] 页面**双向显示地址**：7 位值 + 派生的 8 位读 / 写形式（手册里 0x68 与 0xD0 两种写法都能对上——填错地址最常见的一处坑）
- [x] 端点：列出 / 新增（按 id 幂等更新）/ 删除；错误映射沿用既有 400 中文口径
- [x] 检测页有「+ 我的器件」卡片与表单：能建、能列、能选、能改、能删；件**与平台无关**（切平台不丢）
- [x] 前端 fx 纯件单测进前端门禁；真实浏览器验收能看见并操作这块卡片
- [x] 反证：把「id 撞库内 slug」的守卫拿掉后，对应用例必须变红

---

## 结论（2026-09-23，工单 02 已 resolved）

### 交付物

| 落点 | 是什么 |
|---|---|
| `src/contest_generator/my_devices.py` | 新域模块：「我的器件」的**定义形状 + 校验 + 数据目录 + 载荷投影**。`CustomDevice`（id/name/bus/address/register/expect/notes + 时间戳，`validated()` 全套判据）、`my_devices_dir()`、`save_device()`（原子落盘：临时目录 + 改名）、`load_device()` / `list_devices()` / `delete_device()`、`address_forms()`（7 位 → 7 位 + 8 位读写）、`read_device_payload()`。零 LLM、不碰 `library/` |
| `src/contest_generator/static/js/fx/my-devices.js` | 前端纯件：地址双向显示、表单校验（与服务端同规则）、载荷组装、列表行 / 表单 / 空态渲染。**不碰 DOM、不发请求** |
| `src/contest_generator/static/js/ui/hwcheck.js` | DOM 胶水：三件事的端点调用 + 列表 / 表单渲染 + 名称→id 建议（失焦时）+ 加选按钮 |
| `src/contest_generator/static/index.html` | 检测页「3. 要测的器件」区里的「我的器件」块（`#btn-my-device-new` / `#my-devices-list` / `#my-devices-form`）+ 样式（`.hwcheck-my-device*`，全走令牌） |
| `src/contest_generator/webapp.py` | 三个端点 `GET/POST /api/my-devices`、`DELETE /api/my-devices/{id}`；四个检测端点新增 `custom_device_ids=_my_device_ids()` |
| `src/contest_generator/hwcheck_board.py` | `hwcheck_view` / `hwcheck_board_view` / `_missing_devices` 新增 `custom_device_ids`：自建件**不进模块集**（它还不是模块），也**不算**"本平台没有条目" |
| `src/contest_generator/errors.py` | `MyDeviceError` 登记进既有 400 中文表（结构测试 `test_errors.py` 兜底） |
| `tests/test_my_devices.py` | 52 条域层判据（落点 / 校验 / 双向显示 / 撞名 / 原子落盘 / 只校验一遍） |
| `tests/test_my_devices_endpoint.py` | 26 条端点判据（列出 / 幂等新增 / 删除 / 撞名 400 / 路径穿越 / 与检测计划的接缝） |
| `tests/js/my-devices.test.mjs` | 28 条 fx 判据（含**跨语言对账**：总线词表 / id 前缀 / 地址区间读后端真源码比） |
| `tests/js/hwcheck.test.mjs` | +9 条接线判据（控件齐备 / 静态 import / 端点走 `api*` / 删除时摘掉选择 / 打字不重绘 / 选中集联动） |
| `tests/browser/hwcheck.spec.mjs` | +4 条真浏览器用例（能建能改能删能存住 / 能选 / 撞已有件当场拦 / 与平台无关 + 非 I2C 如实说） |

### 验收读数

```
python -m pytest -n auto -q                    5183 passed + 1 skipped   （本单新增 85 条 pytest）
node --test "tests/js/*.test.mjs"              1739 passed / 0 fail      （本单新增 37 条；改前 1702）
node --test --test-concurrency=1 "tests/browser/*.spec.mjs"
                                               34 passed / 0 fail        （本单新增 4 条；改前 30）
```

> 浏览器门禁的一条**环境观察**（不是本单引入的）：34 条连跑时 `launcher-reload.spec.mjs`
> 偶发红（A 在 `page.reload` 上 30 秒超时 → B/C 跟着 9ms/37ms 速败）；**单跑这一支
> 3/3 全绿**（读数 `.scratch/hwcheck-unknown-device/browser-02-launcher-isolated.txt`），
> 且与本次改动无交集（那支 spec 不碰检测页）。记为连跑时的资源争用偶发，与本单无关。

**反证读数**（`python .scratch/hwcheck-unknown-device/probe-02-guard-strength.py`，
证据 `.scratch/hwcheck-unknown-device/probe-02-guard-strength.txt`）——把
`CustomDevice.validated` 里的撞名判据换成 `pass`、逐字节复原后复核 sha256 相等：

```
[1] 前置检查：源文件 sha256=02f5154c208bcb6b…，注入目标唯一 ✓
[2] 注入前（守卫在）：  PASS（全绿）  ｜ 4 passed
[3] 注入后（守卫没了）：RED（撞名用例变红）｜ 2 failed, 2 passed
[4] 复原复核：sha256 相等 ✓（02f5154c208bcb6b…）
[5] 复原后复跑：        PASS（回绿）  ｜ 4 passed
```

→ **验收项 8 成立**：变红的两条正是撞名用例（`test_id_clashing_with_a_library_slug_is_named_out_loud`
+ `..._is_400_and_names_the_id`），另两条（不撞名 / 读当下库）注入前后都该绿。

**两处刻意的判据分工**（评审问过，这里记明）：

1. **"撞库内 slug"的判据在 pytest 里造真撞名**（`clash_client` fixture 造一个真叫
   `mine_gyro` 的库内模块），浏览器验收改验"撞**已有自建件**时页面当场拦住"。
   为什么：真库 96 个 slug **一个都不以 `mine_` 开头**（id 文法强制这个前缀），
   真浏览器里撞不成；要在浏览器里撞成，就得给这个 spec 换一个含 `mine_*` 模块的
   假库——那会连带把检测页的框架件（led / delay / 通道）一起换掉，验收跑的就
   不是真库了。所以浏览器那条另配一条**事实判据**（库里没有 `mine_` 开头的 slug）。
2. **路由层把自建件 id 从模块集里摘掉**（`custom_device_ids`）：这一版自建件还不是
   模块（没有 manifest，库外 slug 会在生成链上游被 `UnknownModuleError` 拒），但页面
   已经能勾它——摘掉之后这次预览 / 生成不 400，同时**不放松**既有守卫（对照组
   `test_an_unknown_slug_is_still_a_loud_failure` 断言库外 slug 照旧 400）。合
   spec「自建件本身不是模块、不进 slugs」。

### code-review 两轴结论与整改

- **Standards 轴**：1 条**硬违规**——`ui/hwcheck.js` 里留了调试行
  `window.__myDebug = …`（排查表单重绘时加的，取证完没删；它还是"每次失焦往全局
  数组塞一条含用户输入的串"）。**已删**。判断项里挑了 3 条当场收掉：
  ① `save_device` 与路由各校验一遍 → 收成**只在 `save_device` 一处**（`library_slugs`
  改成它的关键字参数），并补一条行为判据钉住"只跑一遍"
  （`test_validated_is_applied_exactly_once_across_the_save_path`）；
  ② `custom_device_ids` 收成**与本次选中集取交集**（收藏里躺着的件不再影响模块集）；
  ③ `_missing_devices` 里那句 `slug and` 死防御删掉（`dedup_slugs` 已丢空串）。
  余下的判断项（`custom_device_ids` 四层直通、`NAME_MAX_CHARS` 两侧字面量）**判断为
  暂不改**：前者会随工单 03 把自建件接进渲染时自然收敛，后者由跨语言对账用例的
  同款先例在 03 一并补（此刻两侧都只有一处消费者，改名字面量没有收益）。
- **Spec 轴**：1 条**真缺陷** + 1 条**真缺口**，两条都已整改：
  ① **DELETE 不校验 id 文法**（评审实测）：`delete_device` 直接把 id 拼进路径 →
     `DELETE /api/my-devices/%2e%2e` 解码成 `..` → `Path(root)/".."` = **配置目录**
     （装着 config.json）→ `rmtree` 整棵删掉。修复 = 新增 `_entry_dir()` 作为
     **唯一的 id→路径拼接点**（文法校验与拼接绑在一起），`load_device` / `delete_device`
     都经它；域层用例逐字证过修复前真的会删掉配置目录，端点用例用**原始 ASGI 路径**
     打（`TestClient` 会把 `..` 先归一成 `/api/`，那样写用例会假绿——这条坑记在
     用例 docstring 里）。
  ② **"能选"没做**（工单验收第 6 条）：列表行原本只有编辑 / 删除。已补：行上
     `data-my-device-pick` 按钮两态（「加进这次检测」↔「✓ 已在这次检测里」），
     走**库内器件同一条路**（`addHwcheckDevice` → 既有 chip / 检测计划 / 生成都认它）；
     `renderHwcheckDevices` 一并重绘那一块（两个容器显示同一份选择集，只重绘一个
     就是界面自相矛盾）。浏览器验收 +1 条端到端（加选 → 预览出真 main.c 且不 400
     → chip 点掉 → 行按钮变回「加进」）。
  另有 2 条判断为**不改**：非 I2C 件填地址即 400（地址是 I2C 总线的事实，允许它
  等于教用户填一个用不上的字段）、新建表单撞已有 id 时要求改名而不是静默覆盖
  （要覆盖就点「编辑」——静默覆盖用户自己建的第二件更坏）。

### 两处实现口径（实施时定的）

1. **落点由 `AppContext.config_path.parent` 推**（与 `updates/` / `cache/` 同一个
   数据目录），**不是**由模块库推：模块库是可配置的产品库（仓库布局下 =
   `<仓库>/library`，跟着 git 走），数据目录是"这台机器上这份工具的数据"。
   两者混一起就会把用户自建的东西提交进产品库（本单有一条用例反证：保存一件后
   `library/` 下一个字节都不多）。
2. **地址只存 7 位那一个数**，8 位读 / 写形式永远是派生的（落盘两份就是两个真相
   来源）；`address_forms()` 是那条派生的单源，页面与载荷都读它。

### 范围外 / 留给后面的工单

- 本单**不生成任何代码**：探测小节渲染（03/04）、检测计划里的自建件条目与顺序
  （05）、串口复测命令（06）、资料上传与 AI 抽草稿（07）、工程内快照与回读（08）、
  AI 排障带自建件事实（09）——一行都没做。
- 因此**自建件目前不产生任何电路行为**：它进 `devices`、页面画 chip、服务端回显，
  但既不在 `main_c` 里也不在接线表里（`tests/test_my_devices_endpoint.py` 明写断言
  `"mine_gyro" not in main_c`）。"选中"在这一版是"记下这一趟要用它"，不是"测它"。
- 真机口径：本单是**数据与页面**，没有上板动作；真机验证属于 03 起（探测程序真编译
  + 上板）。
