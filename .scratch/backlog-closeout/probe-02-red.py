"""反证探针（工单 backlog-closeout/02）：逐段撤掉修 → 对应判据必须**点名红**。

三段（每段一类机制，逐条声明必须红 + 与实得 FAILED 对账 + 复原 sha256 逐字节）：

- **A 撤 mq2 的「正向映射」**：那条 note 改回原样（只少这一句）
- **B 撤 mq135 的「正向映射」**：同上
- **C 撤 mq5 的预热口径**：把「预热 3-5 分钟」改回「预热（几分钟级）」（只这一件）

A/B 打 `test_default_wordlist_mq_family_notes_state_mapping_direction`；
C 打 `test_default_wordlist_mq_family_notes_share_the_preheat_wording`。

形状照 `.scratch/record-write-hardening/probe-01-red.py`：逐条声明 + 与实得 FAILED 对账 +
每段复原 sha256 逐字节相同（**字节往返**，不用文本模式）——多出来的红如实打印，
**并且照实判该段不成立**（不是"打印了但不算"）。用法：
`python .scratch/backlog-closeout/probe-02-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORDLIST = ROOT / "src" / "contest_generator" / "wordlist.json"
CASES = "tests/test_wordlist.py"
DIRECTION = "tests/test_wordlist.py::test_default_wordlist_mq_family_notes_state_mapping_direction"
PREHEAT = (
    "tests/test_wordlist.py::test_default_wordlist_mq_family_notes_share_the_preheat_wording"
)

MAP_PHRASE = "——**正向映射**（浓度越高 ADC 值越高）"
PREHEAT_PHRASE = "模块上电必须预热（手册只说「加热一段时间」，一般几分钟）否则输出不准"
# mq5 那条的预热句：锚点带上下半句（预热句九件都有，得用独有的尾巴定位）
MQ5_PREHEAT = PREHEAT_PHRASE + "；DO 阈值由模块可调电阻控制（库内未声明 DO 角色，需要时经 GPIO 输入自读）；对丁烷/丙烷/甲烷/天然气（液化气）灵敏"
MQ5_PREHEAT_OLD = (
    "模块上电必须预热（几分钟级）否则输出不准；DO 阈值由模块可调电阻控制"
    "（库内未声明 DO 角色，需要时经 GPIO 输入自读）；对丁烷/丙烷/甲烷/天然气（液化气）灵敏"
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tests() -> tuple[set[str], str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", CASES, "-q", "--tb=no", "-rf"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    failed = set(re.findall(r"^FAILED (\S+)", out, flags=re.MULTILINE))
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    return failed, tail


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raw = WORDLIST.read_bytes()
    source = raw.decode("utf-8")
    print(f"# 被撤的源码：{WORDLIST.relative_to(ROOT).as_posix()} sha256={sha256(WORDLIST)}")
    print(f"# 判据文件：{CASES} sha256={sha256(ROOT / CASES)}")
    print()

    def seg(name: str, old: str, declared: str) -> tuple[str, str, set[str]]:
        return name, old, {declared}

    segments = [
        seg(
            "A 撤 mq2 的「正向映射」",
            "mq2_read_percent 出 0-100% 相对浓度" + MAP_PHRASE,
            DIRECTION,
        ),
        seg(
            "B 撤 mq135 的「正向映射」",
            "mq135_read_percent 出 0-100% 相对浓度" + MAP_PHRASE,
            DIRECTION,
        ),
        seg("C 撤 mq5 的预热口径", MQ5_PREHEAT, PREHEAT),
    ]

    verdicts: list[bool] = []
    for name, old, declared in segments:
        print(f"== {name} ==")
        if source.count(old) != 1:
            print(f"   [!] 锚点命中 {source.count(old)} 次（应恰好 1 次）——探针该修了\n")
            verdicts.append(False)
            continue
        if name.startswith("C"):
            new = MQ5_PREHEAT_OLD
        else:
            # 只把这句连着的「，」去掉：还原成"没有那一句方向说明"的形态
            new = old.split(MAP_PHRASE)[0] + "，"
        try:
            WORDLIST.write_bytes(source.replace(old, new, 1).encode("utf-8"))
            failed, tail = run_tests()
        finally:
            WORDLIST.write_bytes(raw)

        restored = sha256(WORDLIST) == hashlib.sha256(raw).hexdigest()
        missing = declared - failed
        extra = failed - declared
        print(f"   声明必须红：{sorted(declared)}")
        print(f"   实得 FAILED：{sorted(failed) if failed else '（无）'}")
        print(f"   pytest 尾行：{tail}")
        print(f"   复原 sha256 逐字节相同：{restored}")
        if missing:
            print(f"   [x] 声明必须红的没红：{sorted(missing)}")
        if extra:
            print(f"   [x] 多出来的红（如实打印，不据此判 PASS）：{sorted(extra)}")
        verdicts.append(not missing and not extra and restored)
        print()

    print("== 复原后必须回绿 ==")
    green_failed, green_tail = run_tests()
    print(f"   实得 FAILED：{sorted(green_failed) if green_failed else '（无）'}")
    print(f"   pytest 尾行：{green_tail}")
    print()
    ok = all(verdicts) and not green_failed
    print("结论：" + ("PASS（三段反证全成立）" if ok else "不成立，见上"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
