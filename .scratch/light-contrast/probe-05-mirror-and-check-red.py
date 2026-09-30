"""浅色调色板轮 · 反证探针（05）：**镜像守卫**与**生成器 `--check`** 判不判得红？

**为什么要有它**（01 单双轴评审点名）：`tests/test_contrast_mirror.py` 与
`generate-01-contrast-register.py --check` 都是"防漂移"的闸——可**闸自己有没有牙**没人证过。
描边那轮的先例是 `probe-05-mirror-red.py` / `probe-06-generator-check-red.py`（两支探针、六处注入）。

**做法**：每处注入都是"真改盘上的文件 → 跑判据 → 断言它红了 → `finally` 复原"，
复原后校验 **sha256 与注入前逐字节相同**（描边那轮的纪律：注入探针必须能证明自己复原了）。
跑法（仓库根）：
    python .scratch/light-contrast/probe-05-mirror-and-check-red.py
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_lib as L  # noqa: E402

MIRROR_TEST = L.ROOT / "tests" / "test_contrast_mirror.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: list[str]) -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}   # 子进程输出别按 GBK 解（读数里会乱码）
    p = subprocess.run(cmd, cwd=L.ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def inject_and_check(name: str, path: Path, old: str, new: str, cmd: list[str]) -> bool:
    """注入 → 跑判据（期望红）→ `finally` 复原 → 校验逐字节相同。返回"判红了没有"。"""
    before_hash = sha256(path)
    raw = path.read_bytes()
    nl = b"\r\n" if b"\r\n" in raw else b"\n"
    needle = old.encode("utf-8").replace(b"\n", nl)
    replacement = new.encode("utf-8").replace(b"\n", nl)
    if needle not in raw:
        print(f"  ✗ {name}：锚点没命中（按 {nl!r} 换算后仍找不到）——这条反证无效，先修锚点")
        return False
    try:
        path.write_bytes(raw.replace(needle, replacement, 1))
        code, out = run(cmd)
        red = code != 0
        detail = ""
        if red:
            for line in out.splitlines():
                if line.startswith("FAILED") or "AssertionError" in line:
                    detail = line.strip()[:110]
                    break
        print(f"  {'✓' if red else '✗'} {name}：{'判红' if red else '**没判红（闸门没牙）**'}"
              + (f"  ← {detail}" if detail else ""))
        return red
    finally:
        path.write_bytes(raw)
        after = sha256(path)
        if after != before_hash:
            raise SystemExit(f"复原失败：{path} 的 sha256 变了（{before_hash[:12]} → {after[:12]}）")


def main() -> None:
    print("=" * 78)
    print("浅色调色板轮 · 反证读数（probe-05：镜像守卫 + 生成器 --check 判不判得红）")
    print("=" * 78)

    guard = L.GUARD
    gen = HERE / "generate-01-contrast-register.py"
    mirror_cmd = ["python", "-m", "pytest", "tests/test_contrast_mirror.py", "-q"]
    check_cmd = ["python", str(gen.relative_to(L.ROOT)), "--check"]

    # 先钉基线：不注入时两条都得绿（否则"判红"什么也证明不了）
    code1, _ = run(mirror_cmd)
    code2, _ = run(check_cmd)
    print(f"\n## 基线（不注入）\n\n  镜像守卫 {'绿' if code1 == 0 else '**红**'}；"
          f"生成器 --check {'绿' if code2 == 0 else '**红**'}")
    if code1 != 0 or code2 != 0:
        raise SystemExit("基线就不是绿的——先修，再谈'判不判得红'")

    print("\n## 镜像守卫：五处口径漂移各注入一次（期望每次判红）\n")
    ok = []
    ok.append(inject_and_check(
        "① 合成基色令牌（--panel → --bg）", guard,
        'const CONTRAST_BASE_TOKEN = "--panel";', 'const CONTRAST_BASE_TOKEN = "--bg";',
        mirror_cmd))
    ok.append(inject_and_check(
        "② 切规则正则（[^{}]* → [^{}]*? 懒匹配）", guard,
        r"const CONTRAST_RULE_RE = /([^{}]+)\{([^{}]*)\}/g;",
        r"const CONTRAST_RULE_RE = /([^{}]+)\{([^{}]*?)\}/g;",
        mirror_cmd))
    ok.append(inject_and_check(
        "③ 亮度系数（w_r 0.2126 → 0.2127）", guard,
        "w_r: 0.2126, w_g: 0.7152, w_b: 0.0722,", "w_r: 0.2127, w_g: 0.7152, w_b: 0.0722,",
        mirror_cmd))
    ok.append(inject_and_check(
        "④ 阈值档位词表（CONTRAST_FAMILY_KINDS 去掉 nontext）", guard,
        'const CONTRAST_FAMILY_KINDS = ["text", "nontext"];',
        'const CONTRAST_FAMILY_KINDS = ["text"];',
        mirror_cmd))
    ok.append(inject_and_check(
        "⑤ 第三面令牌表（var(--muted) 的档位 text → skip）", guard,
        '["var(--muted)", ["--bg", "--panel", "--panel-2"], "text", "次要说明色"],',
        '["var(--muted)", ["--bg", "--panel", "--panel-2"], "skip", "次要说明色"],',
        mirror_cmd))
    ok.append(inject_and_check(
        "⑥ 族表底列表（焦点环那族去掉 --panel-2）", guard,
        '["--accent 焦点环 / 语义左条", "=--accent", ["--bg", "--panel", "--panel-2"], "nontext",',
        '["--accent 焦点环 / 语义左条", "=--accent", ["--bg", "--panel"], "nontext",',
        mirror_cmd))

    # ⑧ 的锚点**从当前表里现算**（写死某一行会在它被修好后失效——02 单就修掉了 `.badge.ok`）
    cur_table = L.load_exceptions_raw()
    row_re = re.compile(r'^(\s*\["(?:dark|light)", .*?, "(?:debt|skip)", .*?, )([0-9.]+)\],\s*$', re.M)
    row = row_re.search(cur_table)
    if not row:
        raise SystemExit("例外表里找不到可改的 debt 行——(8) 这条反证失去对象")
    old_frozen = f"{row.group(1)}{row.group(2)}],"
    new_frozen = f"{row.group(1)}{float(row.group(2)) + 3.0}],"

    print("\n## 生成器 --check：两处数据漂移各注入一次（期望每次判红）\n")
    ok.append(inject_and_check(
        "⑦ 例外表多出一条假登记", guard,
        '  ["light", "#main-c::selection", "skip",',
        '  ["light", ".never-on-disk", "debt", "凭空多出来的一条", 1.0],\n'
        '  ["light", "#main-c::selection", "skip",',
        check_cmd))
    ok.append(inject_and_check(
        f"⑧ 例外表的冻结值被改坏（{row.group(2)} → +3.0）", guard,
        old_frozen, new_frozen, check_cmd))

    print("\n## 复原校验\n")
    code1, _ = run(mirror_cmd)
    code2, _ = run(check_cmd)
    print(f"  镜像守卫 {'绿 ✅' if code1 == 0 else '红 ❌'}；生成器 --check {'绿 ✅' if code2 == 0 else '红 ❌'}")
    print(f"\n  八处注入里判红 **{sum(ok)}/8**"
          + ("——**每一处都判得红，两条闸都有牙**" if sum(ok) == 8 else "——有没判红的，见上面逐条"))
    print("  （复原走 `finally` + sha256 校验：文件与注入前逐字节相同）")


if __name__ == "__main__":
    main()
