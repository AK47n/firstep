r"""反证探针：两支生成器的 `--check` **判不判得红**（工单 border-guard/01 + 02）。

`--check` 是"这张表当年是不是这么生成的、有没有人偷偷改过"的唯一抓手；它自己要是永远绿，
就只是给那几份副本盖了个假章。照本仓惯例（08 账第 3 条：新腿要自证）：
往守卫里真注入一处漂移 → `--check` 必须非零退出 → 复原 → 逐字节相同 → 复跑必须绿。

两支各证一遍（01 的样式块面 115 条、02 的渲染方面 10 条）——
02 单第一版**根本没带 `--check`**，是双轴评审按"01 的整改没延续到 02"点出来的。

逐字节读写（`tests/js/**` 实测是 LF；这条**按文件实际形态**走，不按记忆写死）。
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"
PY = sys.executable

# (生成器, [(名字, 锚点, 替换成什么)]) —— 每支两处漂移：改类别 + 改选择器/锚点
TARGETS = [
    (".scratch/border-guard/generate-01-register.py", [
        ("把一条登记项的类别改掉",
         b'["shell", ".card", "block"],',
         b'["shell", ".card", "control"],'),
        ("把一条登记项的选择器改名",
         b'["guide", ".guide-table td", "doc"],',
         b'["guide", ".guide-table th", "doc"],'),
    ]),
    (".scratch/border-guard/generate-02-js-register.py", [
        ("把渲染方一条登记项的类别改掉",
         b'["ui/codeeditor.js", \'border:1px solid #888\', "float"],',
         b'["ui/codeeditor.js", \'border:1px solid #888\', "modal"],'),
        ("把渲染方一条登记项的锚点改名",
         b'["ui/generate-pins.js", \'border:1px dashed var(--warn)"\', "nonbox"],',
         b'["ui/generate-pins.js", \'border:1px dashed var(--warn)x\', "nonbox"],'),
    ]),
]


def run_check(gen: str) -> tuple[int, str]:
    proc = subprocess.run([PY, str(ROOT / gen), "--check"], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    out = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
    return proc.returncode, (out[-1] if out else "")


def main() -> int:
    original = GUARD.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    failures = 0

    for gen, injections in TARGETS:
        print(f"\n=== {gen} ===")
        print("前置：干净树上 `--check` 必须绿")
        code, last = run_check(gen)
        print(f"  → 退出码 {code}  {last}")
        if code != 0:
            print("干净树上就不绿——先修生成器，别往下走")
            return 1
        for name, anchor, repl in injections:
            if original.count(anchor) != 1:
                print(f"[跳过] {name}：锚点命中 {original.count(anchor)} 次（应为 1）")
                failures += 1
                continue
            GUARD.write_bytes(original.replace(anchor, repl))
            code, last = run_check(gen)
            print(f"[{'红 ✅' if code != 0 else '**没红 ❌**'}] {name}（退出码 {code}）{last}")
            if code == 0:
                failures += 1
            GUARD.write_bytes(original)

    GUARD.write_bytes(original)
    after = hashlib.sha256(GUARD.read_bytes()).hexdigest()
    print(f"\n复原：sha256 {'逐字节相同 ✅' if before == after else '**不同 ❌**'}（{before[:12]}…）")
    for gen, _inj in TARGETS:
        code, last = run_check(gen)
        print(f"复原后复跑 {pathlib.Path(gen).name}：退出码 {code}" + ("（绿 ✅）" if code == 0 else "（**红 ❌**）"))
        if code != 0:
            failures += 1
    if before != after:
        failures += 1
    print(f"\n结论：{'全部按预期 ✅' if failures == 0 else f'有 {failures} 处不符预期 ❌'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
