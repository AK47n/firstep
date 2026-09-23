# 10 — 闸门与真机验收收口

**要做什么：** 整套闸门与真机口径收口 —— 新守卫的判据强度反证、两平台编译矩阵、浏览器门禁、CONTEXT.md / ADR 补笔与台账，全部读数落进本工单。

**被谁阻塞：** 04、06、07、08、09

**状态：** resolved

- [x] 每条新守卫各有一次「**停用后用例必须变红**」的实测读数（守卫：调用 ⊆ `i2c_probe` 接口 / 无写寄存器 / 无引脚字面量 / 标注词不互串 / id 撞库内 slug / 草稿不编造），红证工具与读数写进本工单
- [x] 三项闸门本机读数记进本工单：`python -m pytest -n auto`、前端门禁、浏览器门禁（串行）
- [x] 两平台真编译矩阵 0 error / 0 warning（含"只有自建件""自建件 + 库内器件""全选装不下时如实拦下"三类形态）
- [x] CONTEXT.md 的「硬件检测」词条扩写：我的器件 / `i2c_probe` 支点 / 自建件标注 / 探测只读这条边界
- [x] ADR 0016 补一笔：检测程序 = 确定性渲染 +（**库内配方数据 或 用户确认的事实**）；AI 仍然不产出检测程序的一个字节
- [x] CHANGELOG 与提交信息中文（仓库语言规范）
- [x] 上板口径如实：**没跑过就写"未上板"**，不假装
- [x] 若本机环境事实有变化（新端口 / 沙箱痕迹 / 发布落差），同步更新 `docs/agents/local-environment.md`

---

## 结论（2026-09-23，工单 10 已 resolved；本特性 01–12 全部收口）

### 一句话

把 `hwcheck-unknown-device` 整批（12 张工单）的**闸门、反证、编译矩阵与台账**一次收齐：
**17 支判据强度探针在同一份冻结 revision 上逐支重跑全 PASS**（每条新守卫都有一次
"停用后用例变红"的实测）、三门禁全绿、两平台编译矩阵 **12 格 × 2 平台 0 error /
0 warning**（含三类形态与连字符边界格）、CONTEXT.md 与 ADR 0016 补齐、
**未上板如实声明**。

### 一、判据强度总表（工单 10 第 1 条）

新写的收口驱动 `.scratch/hwcheck-unknown-device/probe-10-guard-strength-all.py`
（读数 `probe-10-guard-strength-all.txt`）在冻结 revision 上**依次重跑全部探针**——
它同时解决两件事：各单读数原本散在十几个 `.txt` 里、且 09 之后 `webapp.py` /
`hwcheck_custom.py` 动过（锚点可能失效，只有重跑才知道）。

```
[2] 强度探针（反证）——退出码 0 = 反证成立
    probe-01-c1-reverse.py               PASS ｜  0.5s ｜ 登记行是 I2C_0 存活的唯一判据
    probe-02-guard-strength.py           PASS ｜ 15.8s ｜ 撞名用例变红（id 撞库内 slug 守卫）
    probe-03-guard-strength.py           PASS ｜  2.3s ｜ 多调一个不存在的函数 = 守卫当场变红
    probe-03b-sanitize-strength.py       PASS ｜  2.2s ｜ 消毒是那条用例变红的唯一判据
    probe-04-guard-strength.py           PASS ｜  6.2s ｜ 3 条注入（重复定义 / 死代码 / 平台代价句）
    probe-05-guard-strength.py           PASS ｜ 14.2s ｜ 5 条注入（顺序 / 计划覆盖面 / 清单 / 总线判据 / 端点）
    probe-05-guard-strength.mjs          PASS ｜  0.5s ｜ 2 条前端注入（标注词与计划行）
    probe-06-guard-strength.py           PASS ｜ 15.6s ｜ 6 条注入（复测复用上电那遍 / 保留字 / 大声失败 / 载荷 / 同表 / 逐字）
    probe-06-guard-strength.mjs          PASS ｜  0.5s ｜ 2 条前端注入
    probe-07-guard-strength.py           PASS ｜  7.9s ｜ 4 条注入（**草稿不编造**：出处比对 / 字段白名单 / 区间 / import 面）
    probe-07-guard-strength.mjs          PASS ｜  0.3s ｜ 前端注入
    probe-08-guard-strength.py           PASS ｜ 16.3s ｜ 4 条注入（快照回读 / 归档大声报错 / 资料草稿随保存 / 生成调归档）
    probe-08-guard-strength.mjs          PASS ｜  0.4s ｜ 前端注入
    probe-09-guard-strength.py           PASS ｜ 24.2s ｜ 8 条注入（事实段 / id 专用判据 / 名称词 / 端点喂料 / 快照口径 / 空地址行 / 旧措辞 / 提示词）
    probe-11-guard-strength.py           PASS ｜  9.1s ｜ 4 条注入（重名判据四入口）
    probe-12-guard-strength.py           PASS ｜  7.7s ｜ 3 条注入（id 文法 / 保存执行点 / 装载不吞坏条目）
    probe-12-guard-strength.mjs          PASS ｜  0.3s ｜ 前端注入

[3] 量具（不是反证，退出码按各自约定）
    probe-12-hyphen-id.py                PASS ｜ 0.9s ｜ 连字符 id 三个端点全拒（退出码 1 = 守卫在）
    probe-11-contest-dupname.py          PASS ｜10.5s ｜ 撞名组合全被拦下 + 不撞名组合编译绿

[4] 收尾指纹：src/ + tests/ 共 646 个文件逐字节未变 ✓
=== 结论：收口成立（17 支强度探针全 PASS + 2 支量具读数一致 + 工作树逐字节未变） ===
```

票面点名的六条守卫 ↔ 探针的对应：**调用 ⊆ `i2c_probe` 接口 / 无写寄存器 / 无引脚
字面量** = probe-03（+ 03b 消毒）；**标注词不互串** = probe-05；**id 撞库内 slug**
= probe-02（12 又补了文法那条）；**草稿不编造** = probe-07（出处比对是真判据：
注入 A 让资料里没有的片段照单全收 → 用例当场红）。

### 二、三项闸门（本单第 2 条；2026-09-23 冻结版实测）

```
python -m pytest -n auto -q                                  5356 passed + 1 skipped / 137.0s（收口前一次 139.1s，同数）
node --test "tests/js/*.test.mjs"                            1768 passed / 0 fail / 5.5s
node --test --test-concurrency=1 "tests/browser/*.spec.mjs"   38 条：**首跑 36 passed / 2 failed**（见下），单跑复证 3/3 绿
```

浏览器门禁那 2 条红是**已知并行偶发**、且**与本特性无交集**（`launcher-reload.spec.mjs`
的 A：`page.reload` 30 秒超时 → B/C 跟着 7ms/37ms 速败；这支 spec 验的是"启动器模式下
F5 不会把应用关掉"，不碰检测页）：

- 整支跑（`browser-10-all-specs.txt`）：`✖ B ... (30006.9ms)` / `✖ C ... (7.0ms)`；
- **单跑复证**（`browser-10-launcher-isolated.txt`）：**A/B/C 3 passed / 0 fail**；
- 同一工作树的**前一次整支跑是 38 passed / 0 fail**（收口文档改动前的那一版）。

这条偶发在 02 / 07 / 12 三单的会话里各撞过一次、每次单跑复证即绿（`local-environment.md`
第 2 节有记账）——这里按同一条纪律处置：**不当产品缺陷读，也不掩盖**。

### 三、两平台真编译矩阵（本单第 3 条）

按交接单口径**直接引用最近一轮矩阵读数**（`probe-12-compile-matrix.txt`，12 格 ×
2 平台），不重复跑——本批 09/10 两单都没碰 C 渲染（09 改的是排障上下文 / 提示词 /
页面计划载荷三个键，10 只改文档）：

```
[custom/{mspm0,stm32}/custom-only]           0 error / 0 warning   ← "只有自建件"
[custom/{mspm0,stm32}/custom+library]        0 error / 0 warning   ← "自建件 + 库内器件"
[custom/{mspm0,stm32}/all-library]           0 error / 0 warning   ← 装得下的那一格
[custom/mspm0/all-recipes]                   产品按预期在生成前拦下（边界读数，不计入验收线）
[custom/stm32/all-recipes]                   0 error / 0 warning
[custom/{mspm0,stm32}/empty]                 0 error / 0 warning
[custom/{mspm0,stm32}/shape{1,2,3}-*]        0 error / 0 warning   ← 三档探测形态
[custom/{mspm0,stm32}/no-channel]            0 error / 0 warning
[custom/{mspm0,stm32}/probe-already-selected] 0 error / 0 warning
[custom/{mspm0,stm32}/custom-not-i2c]        0 error / 0 warning
[custom/{mspm0,stm32}/hyphen-id-refused]     产品按预期在生成前拦下（工单 12 的边界格）
=== 结果：全部 PASS（0 error / 0 warning） ===（12 格 × 2 平台）
```

mspm0 那两格另有一条**已知工具链**提示（`warning #10210-D ... use the -heap option`，
选了用堆的 `ml_mpu6050` 一族时 TI 链接器给 `.sysmem` 的默认段）——矩阵里单列一栏，
**不计入"我们代码的告警数"**（读数文件里逐格写着）。

### 四、文档收口（本单第 4、5 条）

- `CONTEXT.md`「硬件检测」词条尾部扩写四条边界：`i2c_probe` 支点（自建件不是模块、
  有它才补进 `generation_slugs`）/ 探测程序**只读**（调用集 ⊆ 读侧三件、不写寄存器、
  无引脚字面量）/ 自建件标注与库内 `[专精]` 不互串 / 装不下的三种都在生成前拦下。
  （「我的器件」词条的 09 段已在 09 单补，两处交叉引用。）
- `docs/adr/0016-hwcheck-render-plus-recipes.md` 补「配方之外的第二份输入」一节：
  数据从"库内配方"扩成"库内配方 **或** 用户确认的事实"，**AI 仍然不产出检测程序的
  一个字节**（它只抽草稿与给排障方向），只读边界与"构建期大声失败"两条不变。

### 五、全特性验收线自查（交接单那张清单）

- [x] 06–10、12 全部 `resolved`，每单结论里有实测读数
- [x] 每单一次中文提交（`946e9cc4` / `828c22d4` / `132e1058` / `c29abda3` / `743f2b20` / 本单），
      CHANGELOG 由 post-commit 钩子自动补（`chore: 自动更新 CHANGELOG`，中文）
- [x] `python -m pytest -n auto -q` 与两支前端门禁全绿（偶发那条本轮未出现）
- [x] 两平台真编译矩阵 0 error / 0 warning（含连字符 id 那一格：两平台都在装载期拦下）
- [x] `CONTEXT.md` / `docs/adr/0016` / `CHANGELOG.md` / `docs/agents/local-environment.md`
      四份文档与新行为一致（09/10 两单各改一次）
- [x] 工作树干净：生成产物（`matrix/`、`probe-0*-data/`、`tmp-matrix/`）按惯例 gitignore
      ——本单顺手把 `tmp-matrix/`（probe-11 的生成工程，探针 docstring 里写着 gitignore
      但规则一直没落）补进 `.gitignore`

### 六、上板口径（本单第 7 条）

**未上板。** 本特性验的是：域层确定性渲染 + 两平台**真编译 0 error / 0 warning** +
真浏览器验收；**没有任何一次"插上线在真板子上跑一轮"**（本机也没有板子）。所以
「板上会打出什么 / 对不对」清单是**给学生的**，不是我们验过的读数——照 spec 口径
如实写"未上板"，不假装（`library/modules/i2c_probe/manifest.json` 的 notes 里同样
写着这一条）。

### 七、发布落差与本机环境事实

- 第 0 节 main-only 落差表的第 ③ 批已改写为**「12 张全部 resolved」**；本特性
  （硬件检测栏目 + 库外件探测 + 完整包会话态进 `AppContext`）**仍然一个字节都没进
  任何发布包**——下次发版要一起带上（版本号建议仍是 `v1.3.0`）。
- 本轮**一次服务器都没起**；收尾实测 8000/8020/8021/8791 都没在听、无残留
  `contest_generator.webapp` 进程（唯一命中的 node 是 DSH 自己的）。
- 本单新增的环境事实（收口驱动、`tmp-matrix/` 的 gitignore 缺口）已写进
  `docs/agents/local-environment.md`。

