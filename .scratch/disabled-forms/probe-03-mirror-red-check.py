"""临时反证（跑完删）：把 probe_lib 的类名词法规则改坏，看镜像守卫会不会红。"""
import pathlib
import subprocess
import sys

P = pathlib.Path(".scratch/light-contrast/probe_lib.py")
GOOD = 'hits = [w for w in words if any(n == w or n.endswith("-" + w) for n in names)]'
BAD = 'hits = [w for w in words if any(n == w for n in names)]'

orig = P.read_text(encoding="utf-8")
assert GOOD in orig, "锚点没命中——这条反证会静默空转"
P.write_text(orig.replace(GOOD, BAD, 1), encoding="utf-8")
try:
    proc = subprocess.run([sys.executable, "-m", "pytest", "tests/test_contrast_mirror.py", "-q"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
finally:
    P.write_text(orig, encoding="utf-8")
after = P.read_text(encoding="utf-8")
print("坏规则时 pytest 退出码 =", proc.returncode, "（要 ≠ 0）")
for ln in (proc.stdout or "").splitlines():
    if "类名词法规则两侧给出不同答案" in ln or "passed" in ln or "failed" in ln:
        print("  ", ln.strip()[:200])
print("复原后与原文逐字节相同：", after == orig)
