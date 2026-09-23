# 12 — 自建件 id 带连字符时产物编不过（id 直接拼进 C 函数名）

**要做什么：** 学生给库外件起一个带连字符的 id（`mine_gyro-2` 这种很自然），生成的检测工程里会出现 `static void hwcheck_custom_mine_gyro-2(void)`——**不是合法 C 标识符**，整份工程编不过；而检测页与预览 / 生成两个端点都返回 200，学生会以为"生成成功了"，直到编译才撞上一串看不懂的语法错。

**被谁阻塞：** 无——可立即开始（发现于 `hwcheck-unknown-device/06` 的会话：`02` 定的 id 文法允许 `-`，`03` 又把 id 直接拼进 C 函数名——两处判据对不上）

**状态：** ready-for-agent

- [ ] **判据单源**："这个 id 会被拼进 C 标识符"这件事只能有一处判据。两条出路取其一并在工单结论里说清取舍：① **id 文法收紧**到 C 标识符可用字符（建件时 400 中文点名并说清为什么——顺便处理盘上已有的坏 id：读不回来时怎么如实报）；② **渲染层拼名时消毒**（注意两个 id 消毒后撞名 = 两个同名 C 函数，那是另一个编译错，必须大声失败而不是静默取一个）
- [ ] 判据面覆盖**三条**入口：建件端点、预览载荷里的 `console.commands`（工单 06 的字符分配对连字符是安全的，别在修的时候破坏它）、生成产物的 `main.c`
- [ ] 已有合法 id（`mine_gyro` 一类）的产物**逐字节不变**
- [ ] 真编译 0 error / 0 warning：矩阵里补一格带连字符 id 的形态（照 `probe-03-compile-matrix.py` 的口径，两平台）
- [ ] 反证：停用新守卫后对应用例必须变红（读数写进工单）

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
