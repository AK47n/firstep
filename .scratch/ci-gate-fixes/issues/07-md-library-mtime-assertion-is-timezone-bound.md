# 07 — 前端门禁里有一条**时区**断言：`md-library.test.mjs` 把东八写死进期望值

**要做什么：** 让 `tests/js/md-library.test.mjs` 里那条 `formatMtime` 断言对**时区**不敏感——
CI（UTC）与本机（东八）两个方向都必须绿，且判据仍然钉得住"本地时区渲染"这件真事，
不是把它削弱成只判长度或直接删掉。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 断言改成对时区不敏感，**照本仓既有口径**：`tests/js/pdf-library.test.mjs:30-42` 是同一件
      对偶函数的用例（两个 `formatMtime` 在源码注释里互相声明"实现一致"），它早就是
      「期望值由本地 `Date` 现算」（`fmtLocal`），不写死时刻。`md` 这份跟它对齐即可。
- [x] **反向验证（先红后绿）**：修前 `TZ=UTC` 下这条必红（贴读数），修后 `TZ=UTC` 与东八
      **两个方向都绿**。只跑一遍绿不算数——这条缺陷的本性就是"本机绿"。
- [x] 审计同族断言：JS 与 py 两侧都扫一遍"拿本地时刻当字面量"的写法，确认没有第二条漏网
      （**更正**：第一版在这里写了"py 侧零命中"、"`recent-jobs` 只判形态"，两句都不准——
      评审抓出，实测与更正见下面「评审整改」段）
- [x] 中文提交

## Comments

### 现场（2026-09-26，CI run `36213107191`）

`全套 pytest（windows-latest）` 的**前端门禁** step：整支 1796 条只红 1 条——

```
not ok 1039 - formatMtime：缺失/非法 → —；合法 → YYYY-MM-DD HH:mm
  location: D:\a\firstep\firstep\tests\js\md-library.test.mjs:105:1
  Expected values to be strictly equal:
  + actual - expected
  + '1970-01-01 00:00'
  - '1970-01-01 08:00'
```

出在断言 `assert.equal(formatMtime(0), "1970-01-01 08:00"); // 本地时区（东八）`：
CI runner 是 **UTC**，本机是**东八**，所以本机永远绿。

### 为什么 `03` 没顺带修掉它（这条的教训）

`03` 修的是「拿 `\n` 当锚点」，复现口径是**在同一台机器上做干净 clone** —— 换掉的是**换行**，
而**时区不是 git 属性**，clone 一万次也换不掉。所以那套复现口径对"环境替 CI 兜底"这一类缺陷
只覆盖了**一半**：凡期望值里含有"本机环境"（时区 / 盘符 / 用户名 / 工具链 / 桌面目录）的断言，
都得另想办法在本机把 CI 的那个前提**造出来**（`08` 的夹具能力就是为此而立）。

### 收口读数（2026-09-26，本机）

**反馈回路**（一条命令就能在本机造出 CI 那个前提——`TZ` 在本机 Node 上真的生效，已实测：
`TZ=UTC` 时 `new Date(0).getHours()` = 0、`getTimezoneOffset()` = 0）：

```powershell
$env:TZ='UTC'; node --test tests/js/md-library.test.mjs
```

| 状态 | 读数 |
|---|---|
| **修前** `TZ=UTC` | `tests 23 / pass 22 / fail 1`，`actual: '1970-01-01 00:00'` vs `expected: '1970-01-01 08:00'`——与 CI 日志**逐字相同** |
| **修后** `TZ=UTC` | `tests 23 / pass 23 / fail 0` |
| **修后** 东八（缺省） | `tests 23 / pass 23 / fail 0`——两个方向都绿 |

**判据强度**（`.scratch/ci-gate-fixes/probe-07-guard-strength.py`，读数在同目录
`probe-07-guard-strength.txt`）：把产品侧 `formatMtime` 临时换成"拿 UTC 取值"
（`getUTCFullYear/getUTCHours/…`，正是本单要防的那类错）——东八下 **exit=1 / fail 1**（判据红），
UTC 下同一注入 **exit=0**（那里 local 就等于 UTC，实现没错）。读写逐字节保真、跑完 sha256
复核 `OK`（`c2374e5b…` 注入前后一致）。

**同族审计**（JS + py + 浏览器 spec 三面都扫）：
- 硬编码 `"YYYY-MM-DD HH:mm"` 字面量的断言：**只此一条**，已修（其余命中都是本次新写的注释文字）；
- 测试里自己算本地时刻的位置：**只有两处**，就是 `md` 与 `pdf` 这一对 `fmtLocal`——两处都是正确
  写法（且互为对偶，源码注释本来就说"实现一致"）；
- py 侧与浏览器 spec 侧：**另外有四处命中**（`time.strftime("%Y-%m-%d")`，两侧同源现算）与一处
  JS 本地分量往返（`recent-jobs`）——都安全，理由见下面「评审整改」第 1、2 条
  （**注意**：本段第一版把这里写成"零命中 / 只判形态"，是错的，已更正）。

**改动面**：`tests/js/md-library.test.mjs`（一条用例的期望值改成按本机时区现算 + 文件头注释说明
为什么不能写死）。产品代码零改动——`formatMtime` 的"本地时区"语义本来就是对的，错的是断言。

### 评审整改（2026-09-26，code-review 两轴之后）

评审抓到三处**我自己写错的证据/过度声称**，逐条更正：

1. **审计那句"py 侧零命中"是错的**。当时的 grep 模式写窄了（只匹配 `strftime("%Y-%m-%d %H`），
   漏掉了实际写法。重扫（`strftime|fromtimestamp|localtime|astimezone|utcnow`）真实命中四处：
   `tests/test_pdf_library.py:144,165`、`tests/test_webapp.py:8049,8058` —— 全都是
   `time.strftime("%Y-%m-%d")` **与实现同源现算**（两侧都用"此刻的本地日期"），
   `tests/test_generation_output.py:100` 是把 `time.strftime` 打桩成固定串。**结论仍成立**
   （没有第二条时区绑定缺陷），但成立的理由是"两侧同源"，**不是"没有命中"**。
2. **"`recent-jobs` 只判形态"也不准**：`tests/js/recent-jobs.test.mjs:23-24` 硬编码了
   `"01-05 08:09"`。它安全的原因是 `new Date(2025, 0, 5, 8, 9)` 用**本地分量构造**、再本地
   渲染回去（往返自洽），与时区无关——理由换了，结论不变。
3. **注释过度声称"时区算错…这条都照样红"**：探针自己的读数就否掉了它——注入"拿 UTC 取值"后
   **东八 exit=1、UTC exit=0**。也就是说在当年翻车的那个环境（CI = UTC）里，本地与 UTC 取值
   **行为完全相同**，任何断言都区分不了。注释已改成按环境限定（牙齿长在非 UTC 一侧，UTC 一侧
   的保护来自"根本不写死时区"），并**补了一条更硬的往返判据**：把渲染出的本地时刻按本地时区
   解析回去必须还是同一个瞬间（`1725000000` 秒位为 0，截到分钟是精确的）——它不依赖"测试里
   那份副本必须是对的"，比"等于本机自算的一份副本"多一层。

**取证纪律补强**（同一条评审意见）：探针 `.scratch/ci-gate-fixes/probe-07-guard-strength.py`
补了**前置干净性检查**（源文件停在上一轮注入态时**拒绝跑**并给出恢复命令，exit=3；自检读数：
模拟停在注入态 → 拒绝、逐字节复原 sha256 一致）与 `--out` 指定落点（照 `.scratch` 先例）。

**复核读数**（整改后重跑，**本工作树为 LF 检出**——照 `local-environment` 的纪律写明形态）：

| 状态 | 读数 |
|---|---|
| 东八 · 缺省 | `tests 23 / pass 23 / fail 0` |
| `TZ=UTC` | `tests 23 / pass 23 / fail 0` |
| 探针（注入 UTC 取值） | 东八 `fail 1` → 判据红；UTC `fail 0`（对照成立）；逐字节复原 OK |

**审议后未采纳的一条**（评审建议，判断项）：把测试里这份 `fmtLocal` 抽成共享 helper，
或改成 `mdFormatMtime(x) === pdfFormatMtime(x)` 的交叉断言。**不采纳**：两件产品实现的
"独立复刻"是本仓既有决策（`fx/md.js` 注释明写刻意不跨域 import），测试侧各留一份现算正是
照那个先例；抽 helper 会把两处判据绑成一处（改一处影响两条门），交叉断言则把"两个域"重新
耦合起来。留档在此，日后再谈。


