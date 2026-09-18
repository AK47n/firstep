# -*- coding: utf-8 -*-
"""把 B2 主跑留档的两条**判据口径更正**追加进证据（原始输出一个字不改）。

为什么要一支单独的更正脚本（而不是重跑一遍）：主跑里那三条红里，两条是**量具自己的**问题
（一条并发人工编辑造成的假红、一条「半成品」被读成 0 字节其实量出来是整卷），
重跑一遍既费 6 分钟又会把「第一次看到的原始输出」覆盖掉。更正就该是**追加**的、
带时间与理由的，而不是让原始证据消失。

用法：`python .scratch/verify-gate-drills/amend-02-corrections.py`
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TXT = HERE / "verify-02-degraded.txt"
JSON = HERE / "verify-02-degraded.json"
RUN_DIR = Path(r"C:\Users\luoji\AppData\Local\Temp\fe02-20260918-231212")
ARCHIVE = RUN_DIR / "drill-updates-archive"

AMENDMENT = """
## 修订与更正（{stamp}，B5 收口时追加；上面的原始输出一个字未改）

### 1. 隔离判据「真身工作树未变 = False」的成因 = **本会话自己在改账本**

那三条红里有一条是这一格：`changed=['docs/agents/local-environment.md']`。
成因：演练跑着的时候，同一个会话正在写 B5 的账本（就是那份文件），tree_stamp 于是把它记成「变了」。
**这不是产品往真身写了东西**，证据三条：

- `git status --short` 此刻（原样贴出）只有本轮的 `.scratch/` 新文件与该文档；
- B2 另外三条隔离判据（真身数据目录 mtime / 真身 `updates/` 条目 / 8000 监听）**全部成立**；
- B1 / B3 / B4 各自的 tree_stamp 判据**都成立**（那几轮跑的时候没人在改仓库）。

→ **判定：撤回这条判红**（假红，量具与并发编辑的相互作用，与产品行为无关）。

```
{git_status}
```

### 2. 场景三（校验失败·不可重试）那两条红的更正 —— 量准之后是**一条真缺陷**

原始输出说「半成品被清」「边车被清」都不成立。收口时把归档目录量准：

```
{leftovers}
```

- 留下的**不是 0 字节**：是**整卷 3,961,701 字节**（就是服务器发的那份完整载荷）
  外加边车 73 B（`{{"url": ".../p?mode=stable", "expected_size": 1048576}}`）；
- 按 spec `.scratch/resumable-download/spec.md` 第 147 行「成功 / 校验失败时**一并删除边车与
  半成品**，不留孤儿」，这两件都该被清掉 —— **真缺陷（低severity、可自愈）**：
  线上完整包场景里，用户看到 `failed` 之后磁盘上白占 ~765 MB（下次重试会因 416 就地清掉）。
  已开单 `.scratch/update-verify-failure-leftovers/01`；
- 其余 10 条判据成立（终态 `failed`、中文且指明「发布信息不一致」、`error_kind=verify`、
  不再重试、`updating.lock` 与 `pending` 未留下、旧版本可用且未被换掉、工具根逐字节未变）。

### 3. 结构澄清：下载态落在**演练目录**，不是沙箱数据目录

harness 用的是一次性配置（`<work>/profile/.contest_generator/config.json`）——
产品的 `updates/` 是 `context.config_path.parent / "updates"`，所以下载态全落在演练目录里。
沙箱自己的 `~\\.contest_generator_sim\\updates` 本格**零触碰**（开头结尾各列了一次条目，逐字相同）。
唯一写进沙箱的是**更新器落位的那两个演练标记文件**（工具根 `sources/materials/.b2-drill-*`）——
那是产品自己的替换链干的，也正是这一格想要的证据。

### 4. 更正后的总判

| 场景 | 判据 | 更正后 |
|---|---|---|
| 一 · 弱网中途取消 | 10 条（取消态 4 + 续传 6） | **全成立** |
| 二 · 断线重试 | 12 条（重试观测 6 + 台账 2 + 终态 4） | **全成立** |
| 三 · 校验失败（不可重试） | 13 条 | **11 成立 / 2 不成立**（失败后残留整卷 + 边车，真缺陷，已开单） |
| 四 · 持久内容不符 | 观察格（不判产品红：与 spec 第 122 行一致） | 记录：150.1s / 7 次重试 / 台账起始偏移全 0 / 无终态 → 决策单 |
| 隔离 | 4 条 | **全成立**（第 1 节那条撤回） |
| **合计** | **35 条** | **33 成立 / 2 不成立** |

（条数口径：`slow-cancel` 的 10 条存在 `.json` 的 `cancel_checks` + `retry_checks` 两个键里——
按 `checks` 单键数会漏掉它，第一版就是那么把总数写成 33/34 的。）
"""


def main() -> int:
    stamp = time.strftime("%Y-%m-%d %H:%M")
    git = subprocess.run(["git", "status", "--short"], cwd=str(HERE.parents[1]),
                         capture_output=True, text=True, encoding="utf-8")
    git_status = (git.stdout or "").strip() or "（空）"
    if not ARCHIVE.is_dir():
        leftovers = f"（归档目录不在：{ARCHIVE}——用原始输出里的记录）"
    else:
        rows = []
        for path in sorted(ARCHIVE.rglob("*")):
            if path.is_file():
                rows.append(f"{path.relative_to(ARCHIVE)}  {path.stat().st_size} 字节")
        leftovers = "\n".join(rows)

    text = AMENDMENT.format(stamp=stamp, git_status=git_status, leftovers=leftovers)
    existing = TXT.read_text(encoding="utf-8") if TXT.is_file() else ""
    if "## 修订与更正" in existing:
        # 幂等：这一节只该有一份（第二次跑只刷 JSON，不再往证据里堆重复段落）
        print("更正节已存在——跳过文本追加（只刷 JSON 的 corrections）")
    else:
        with open(TXT, "a", encoding="utf-8") as handle:
            handle.write(text)

    data = json.loads(JSON.read_text(encoding="utf-8"))
    data["corrections"] = {
        "amended_at": stamp,
        "false_reds_withdrawn": ["隔离判据 real_tree_untouched（并发人工编辑账本造成）"],
        "corrected_findings": [
            "场景三：不可重试的 verify 失败残留整卷 3961701 字节 + 边车 73 字节"
            "（spec 第 147 行要求一并删除）→ 开单 update-verify-failure-leftovers/01",
        ],
        "verdict_after_correction": {
            "slow-cancel": "全部成立（10 条）",
            "cut-retry": "全部成立（12 条）",
            "verify-size": "11 成立 / 2 不成立（残留整卷 + 边车，真缺陷）——13 条判据",
            "content-mismatch": "与 spec 一致（无终态），决策单；不计入判据数",
            "isolation": "全部成立（4 条）",
            "judgment_counts": {
                "total": 35, "pass": 33, "fail": 2,
                "note": "slow-cancel 的 10 条存在 cancel_checks + retry_checks 两个键里"
                        "（按 checks 单键数会漏掉它）",
            },
        },
    }
    JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已追加更正：{TXT.name} / {JSON.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
