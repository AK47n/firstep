# 12 — 自建件 id 带连字符时产物编不过（id 直接拼进 C 函数名）

**要做什么：** 学生给库外件起一个带连字符的 id（`mine_gyro-2` 这种很自然），生成的检测工程里会出现 `static void hwcheck_custom_mine_gyro-2(void)`——**不是合法 C 标识符**，整份工程编不过；而检测页与预览 / 生成两个端点都返回 200，学生会以为"生成成功了"，直到编译才撞上一串看不懂的语法错。

**被谁阻塞：** 无——可立即开始（发现于 `hwcheck-unknown-device/06` 的会话：`02` 定的 id 文法允许 `-`，`03` 又把 id 直接拼进 C 函数名——两处判据对不上）

**状态：** resolved

- [x] **判据单源**："这个 id 会被拼进 C 标识符"这件事只能有一处判据。两条出路取其一并在工单结论里说清取舍：① **id 文法收紧**到 C 标识符可用字符（建件时 400 中文点名并说清为什么——顺便处理盘上已有的坏 id：读不回来时怎么如实报）；② ~~渲染层拼名时消毒~~（未取，取舍见结论）
- [x] 判据面覆盖**三条**入口：建件端点、预览载荷里的 `console.commands`（工单 06 的字符分配对连字符是安全的，别在修的时候破坏它）、生成产物的 `main.c`
- [x] 已有合法 id（`mine_gyro` 一类）的产物**逐字节不变**
- [x] 真编译 0 error / 0 warning：矩阵里补一格带连字符 id 的形态（照 `probe-03-compile-matrix.py` 的口径，两平台）——**实施口径**：取出路①后连字符 id 无法经产品路径存在，这一格落地为**边界格** `hyphen-id-refused`（手工写旧条目 → 两平台都在装载期被拦下，读数记 `MyDeviceError`，不计入 0e/0w 验收线，照 `all-recipes` 先例）
- [x] 反证：停用新守卫后对应用例必须变红（读数写进工单）

---

## 现场与证据（工单 06 会话量到的，别再重复排查）

量具（走产品真路径：`TestClient` + 真库真母版，建件 → 预览 → 生成）：

```powershell
python .scratch/hwcheck-unknown-device/probe-12-hyphen-id.py
```

读数 `.scratch/hwcheck-unknown-device/probe-12-hyphen-id.txt`（2026-09-23 实测）：

```
[1] 建件端点：200（200 = id 文法收下了连字符）
[2] 预览端点：200
    产物里的那几行（**都不是合法 C**）：
      static void hwcheck_custom_mine_gyro-2(void)
      hwcheck_custom_mine_gyro-2();
      hwcheck_custom_mine_gyro-2();
[3] 生成端点：200（200 = 界面会说「生成成功」，坏工程已经落盘）
[4] 'hwcheck_custom_mine_gyro-2' 是合法 C 标识符吗：False
=== 结论：缺陷成立：id 直接拼进 C 函数名，产物编不过（页面与端点都不拦） ===
```

判据来源两处（这是根因）：

* `src/contest_generator/entry_store.py` 的 `SLUG_PATTERN = ^[A-Za-z0-9_][A-Za-z0-9_-]*$`
  —— 允许 `-`；`my_devices._require_device_id` 复用它（"id 文法与库内 slug 同一文法"）。
* `src/contest_generator/hwcheck_custom.py` 的 `CustomSection.func_name =
  f"hwcheck_custom_{self.device.id}"` —— id 原样进 C 标识符。

`tests/test_hwcheck_custom.py` 的 `test_section_uses_the_custom_device_id_in_its_function_name`
只证了 `mine_gyro` 这类"恰好合法"的 id（它自述"两件不会撞名"，而连字符 / 消毒撞名
这条它证不到），所以这条一直没被抓住。

**与工单 06 的关系**：06 把自建件接进命令台，`ConsoleEntry.call_target` 读的是同一个
`func_name`（命名规则不重推，这是对的）——所以这一单修好之后，命令台那一路自动跟着好；
06 的字符分配只从 id 里取字母数字（`isalnum()`），**不受这条影响**（实测 `mine_gyro-2`
分到的是字符 `2`）。

---

## 结论（2026-09-23，工单 12 已 resolved）

### 一句话

02 定的 id 文法（`entry_store.SLUG_PATTERN`，允许连字符）与 03 的 `func_name = f"hwcheck_custom_{id}"`
对不上：`mine_gyro-2` 建得出、预览与生成全 200，产物里却是非法 C 标识符，整份工程编
不过。这一单把 id 文法收紧到 **C 标识符可用字符**（`my_devices.DEVICE_ID_PATTERN`），
坏 id 从建件那一步就 400 说清为什么；盘上已存在的旧坏条目（收紧文法之前建的）读回时
**大声点名 + 指路**，绝不静默跳过。

### 取舍：取出路①（文法收紧），不取出路②（渲染层消毒）

1. **为什么能单源**：`entry_store.SLUG_PATTERN` 是**库内键文法**（模块 slug 与母版
   平台名共用，`0-96-iic` 这类带连字符的库内 slug 靠它）——它一个字不能动。自建件
   id 的判据因此改成 `my_devices.DEVICE_ID_PATTERN` 自己一条（`^[A-Za-z0-9_]+$`，
   配 `mine_` 前缀检查），注释明写"两条文法管两件事，判据各自单源"。02 当时"不自造
   第二套"的决定被本单推翻，理由落在常量注释与 docstring 里，spec「补充说明」也照
   既有先例补了更正痕迹。
2. **为什么不消毒**：出路②要把 `mine_gyro-2` 映射成某个合法 C 名，而两个 id 消毒后
   撞名（`mine_gyro-2` 与 `mine_gyro_2`）必须再配一套"撞名大声失败"的判据——等于在
   渲染层再造半个 id 体系，而 id 同时是**目录名**（消毒后的名字与目录名对不上，
   排障时两头找）。本特性未进任何发布包、没有存量用户数据，收紧文法没有迁移成本。
3. **渲染侧零改动**：`CustomSection.func_name` 的拼法一个字没动——文法保证输入合法
   （前缀以字母开头，拼出的 `hwcheck_custom_*` 恒为合法 C 标识符），docstring 反向
   指向判据单源。这同时守住了"已有合法 id 的产物逐字节不变"。

### 盘上旧坏条目怎么如实报（出路①的另一半）

- **读侧**（`list_devices` / `load_device`）：坏条目 **400 点名**——报错含条目名
  （`这件器件的定义不合法（mine_gyro-2）：…不能用连字符…`）+ 两条出路（手工修
  `hwcheck_devices/<条目>/device.json`，或删掉重填）。照 `list_devices` 的既定约定
  "坏条目大声失败，静默跳过会让器件从页面上消失"。
- **评审记录的已知限制**：**删除入口也过同一条文法**（`delete_device → _entry_dir →
  _require_device_id`——那同时是路径穿越防线），所以旧坏条目**在产品里删不掉**，
  要到数据目录手工删 `hwcheck_devices/<id>/`。报错文案已写明"删掉这个条目重填"并
  点名条目；给 delete 放行旧 id 需要把"路径安全"与"C 标识符文法"拆成两条判据，
  另立小票再议（见「范围外」）。
- **长度上限**（评审补的长度维）：小节函数是 `static`（内部链接），C99 对内部标识符
  只保证前 63 个字符有效，`hwcheck_custom_` 占 15 → `DEVICE_ID_MAX_CHARS = 48`。
  字符集收紧关不掉"两个长 id 截断后同名"的角，上限才能；前端 `myDeviceSlugFromName`
  的派生（slice 32）天然在上限内。

### 交付物

| 落点 | 是什么 |
|---|---|
| `src/contest_generator/my_devices.py` | `DEVICE_ID_PATTERN`（C 标识符文法，单源注释讲清推翻 02 的理由）+ `DEVICE_ID_MAX_CHARS = 48`；`_require_device_id` 换判据 + 分长度/文法两条 400 文案（连字符那条明说"id 会拼进 C 函数名"）；读侧包装补手工指路（点名 `hwcheck_devices/<条目>/device.json`）；`import re`，`SLUG_PATTERN` import 撤除 |
| `src/contest_generator/hwcheck_custom.py` | `func_name` docstring 指回 `my_devices.DEVICE_ID_PATTERN`（拼法零改动） |
| `src/contest_generator/static/js/fx/my-devices.js` | `MY_DEVICE_ID_RE` 收紧 + `MY_DEVICE_ID_MAX_CHARS = 48`（导出）；表单校验两条文案与后端同口径；`myDeviceSlugFromName` 连字符改下划线（"帮你填好"的 id 不许被服务端拒收） |
| `CONTEXT.md` | 「我的器件」词条：id 文法描述更新（C 标识符文法、两套文法各管各的、旧条目大声点名指路） |
| `tests/test_my_devices.py` | 文法参数化（+2 连字符形态）、合法 id 形态、**判据本体**（真渲染路径验每个收下的 id 都出合法 C 函数名）、字符集逐字钉、长度上限、盘上旧坏条目点名 + 指路 |
| `tests/test_my_devices_endpoint.py` | 建件端点拒连字符并说清为什么；**盘上旧条目三入口**（列表 / 预览 / 生成）全 400 且生成不落盘 |
| `tests/js/my-devices.test.mjs` | 连字符被拒 + 说清为什么；id 太长被拒；**跨语言正则逐字对账**（读两份真源码比对字面量 + 长度常量）；slugFromName 连字符断言 |
| `.scratch/hwcheck-unknown-device/probe-12-guard-strength.py` / `.mjs` | 反证探针（3 条后端注入 + 1 条前端注入，逐字节复原 + sha256 复核） |
| `.scratch/hwcheck-unknown-device/probe-03-compile-matrix.py` | `hyphen-id-refused` 边界格（手工写旧条目 → 预期装载期拦下，`BOUNDARY_KINDS` 照 `all-recipes` 先例；起手先清上一格坏条目，与格顺序无关；`save_device` 整调用重试抗 Windows 瞬时文件锁） |

### 验收读数（2026-09-23 冻结版）

**三门禁**：

```
python -m pytest -n auto -q                   5285 passed + 1 skipped / 141.5s（06 轮 5272 + 本单 13）
node --test "tests/js/*.test.mjs"             1755 passed / 0 fail（06 轮 1752 + 本单 3）
node --test --test-concurrency=1 "tests/browser/*.spec.mjs"
                                              37 passed / 0 fail（复跑；首跑 2 红为
                                              launcher-reload 已知并行偶发，单跑 3/3 全绿复证）
```

**量具**（`probe-12-hyphen-id.py`，修复前返回 0 = 缺陷复现）：修复后 **返回 1**——
建件 / 预览 / 生成三端点全 **400**（读数 `probe-12-hyphen-id.txt`：缺陷不成立）。

**反证**——后端 3 条注入（读数 `probe-12-guard-strength.txt`）：

```
注入 A: DEVICE_ID_PATTERN 放宽回允许连字符的旧文法        → RED ｜ 复原 sha256 相等 ✓
注入 B: 保存路径不再查字符集（判据在、执行点被绕过）       → RED ｜ 复原 sha256 相等 ✓
注入 C: 列表装载吞掉坏条目（静默跳过）                    → RED ｜ 复原 sha256 相等 ✓
复原后复跑：三条全 PASS（回绿）；收尾指纹逐字节未变 ✓
```

前端 1 条注入（读数 `probe-12-guard-strength-front.txt`）：`MY_DEVICE_ID_RE` 放宽 →
门禁红 5 条，宣称的两条守卫（连字符拒绝 + 跨语言逐字对账）**都在红名单**，逐字节复原 ✓。

**两平台真编译矩阵**（`probe-12-compile-matrix.txt`）：**12 格 × 2 平台全 PASS**——
11 个既有格 0 error / 0 warning（合法 id 产物不变的产物级证据：各格 `Program Size`
与警告数与 06 轮逐份一致）；`hyphen-id-refused` 边界格**两平台都在装载期被
`MyDeviceError` 拦下**（报错点名 `mine_gyro-2` + 指路），不计入验收线。

### code-review 两轴结论与整改

**Standards 轴**（0 红 4 黄 → 4 条全修）：

1. JS 测试文件头注释仍写"slug 文法" → **已改**为 C 标识符文法。
2. spec「补充说明」没留 02 决定被推翻的痕迹 → **已补**更正段（照既有"与既有决策相反
   的事实"先例）。
3. 矩阵边界格的位置是隐式依赖（坏条目不清理会毒化后面的格）→ **已修**成"每格起手
   先清"，与格顺序无关。
4. id 无长度上限（截断撞名角）→ **已修**：`DEVICE_ID_MAX_CHARS = 48`（63 −
   `hwcheck_custom_` 15）+ 前端镜像 + 两侧用例钉住。
   判断题不改的：报错文案单句带指路（对非连字符拒绝原因是轻噪音，单源文案优先）；
   `myDeviceSlugFromName` 函数名不改（导出面 churn，注释已写明新口径）。

**Spec 轴**（无破票面 / 无蔓延；1 收口待办 + 1 轻）：

1. 工单结论与勾框未落 → **本结论即收口**。
2. 旧坏条目的"删掉重填"在产品内走不通（delete 也过同一条文法）→ **判为不阻塞、
   如实记录**：读侧报错已点名条目 + 给出手工路径；拆"路径安全 / C 标识符文法"为
   两条判据属设计变更，另立小票再议（范围外）。

### 范围外 / 留给后面的工单

- **给 delete 放行旧 id**（拆两条判据的小票）——候选，见上。
- **产品侧 `save_device` 的瞬时锁重试**：矩阵探针连发落盘实测撞到 3 次
  `PermissionError [WinError 5]`（Windows 实时扫描占住暂存目录句柄一拍）。探针侧已加
  整调用重试；产品要不要对单次保存也加同样的重试，另议（端点单次保存未观测到）。
- **未上板**：本单是定义校验与渲染输入，没有真机动作；照 spec 口径写"未上板"，不假装。
