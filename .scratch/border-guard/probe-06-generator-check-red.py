r"""反证探针：`generate-01-register.py --check` **判不判得红**（工单 border-guard/01）。

`--check` 是"这张 115 条的表当年是不是这么生成的、有没有人偷偷改过"的唯一抓手；
它自己要是永远绿，就只是给两份副本盖了个假章。照本仓惯例（08 账第 3 条：新腿要自证）：
往守卫里真注入一处漂移 → `--check` 必须非零退出 → 复原 → 逐字节相同 → 复跑必须绿。

逐字节读写（`tests/js/**` 实测是 LF；这条**按文件实际形态**走，不按记忆写死）。
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"
GEN = ROOT / ".scratch" / "border-guard" / "generate-01-register.py"
PY = sys.executable

# (名字, 锚点, 替换成什么) —— 两处漂移：一处改类别、一处改选择器
INJECTIONS = [
    ("把一条登记项的类别改掉",
     b'["shell", ".card", "block"],',
     b'["shell", ".card", "control"],'),
    ("把一条登记项的选择器改名",
     b'["guide", ".guide-table td", "doc"],',
     b'["guide", ".guide-table th", "doc"],'),
]


def run_check() -> tuple[int, str]:
    proc = subprocess.run([PY, str(GEN), "--check"], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main() -> int:
    original = GUARD.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    print("前置：干净树上 `--check` 必须绿")
    code, out = run_check()
    print(f"  → 退出码 {code}  {out}")
    if code != 0:
        print("干净树上就不绿——先修生成器，别往下走")
        return 1

    failures = 0
    for name, anchor, repl in INJECTIONS:
        if original.count(anchor) != 1:
            print(f"[跳过] {name}：锚点命中 {original.count(anchor)} 次（应为 1）")
            failures += 1
            continue
        GUARD.write_bytes(original.replace(anchor, repl))
        code, out = run_check()
        first = next((ln.strip() for ln in out.splitlines() if ln.strip().startswith("首个不同")), "")
        print(f"[{'红 ✅' if code != 0 else '**没红 ❌**'}] {name}（退出码 {code}）{first}")
        if code == 0:
            failures += 1

    GUARD.write_bytes(original)
    after = hashlib.sha256(GUARD.read_bytes()).hexdigest()
    print(f"\n复原：sha256 {'逐字节相同 ✅' if before == after else '**不同 ❌**'}（{before[:12]}…）")
    code, out = run_check()
    print(f"复原后复跑：退出码 {code}" + ("（绿 ✅）" if code == 0 else "（**红 ❌**）"))
    if before != after or code != 0:
        failures += 1
    print(f"\n结论：{'全部按预期 ✅' if failures == 0 else f'有 {failures} 处不符预期 ❌'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
