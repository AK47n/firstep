# -*- coding: utf-8 -*-
"""hwcheck-unknown-device/01 **反证探针**：拿掉「I2C_0 消费者登记」那一行，
mspm0 选中 i2c_probe 时 I2C_0 是不是真的被裁掉。

工单验收项 9 要求这条反证有实测读数。判据链（本探针一次走完）：

1. **前置干净性检查**：`syscfg_instances.py` 里那行登记**在且只在一处**——
   不满足就拒绝动手（防在别人已经改过的文件上注入，读数会凭空变绿/变红）。
2. 注入：把那行换成没有 `i2c_probe` 的形态（逐字节备份原文）。
3. 子进程重新 import（父进程的模块缓存不算数）→ 跑 `prune_syscfg(母版, ["i2c_probe"])`
   → 报 `I2C_0` 的三行（`$name` / `sdaPin` / `sclPin`）还在不在。
4. **无论成败都逐字节复原**并复核 sha256（探针被强杀时 finally 跑不到，
   所以还留了「前置干净性检查」这条兜底）。

读数落 `probe-01-c1-reverse.txt`（UTF-8，先落盘再打印——本机控制台是 GBK，
先 print 再写盘会在 UnicodeEncodeError 上把证据一起丢掉）。

用法：python .scratch/hwcheck-unknown-device/probe-01-c1-reverse.py
"""
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "src" / "contest_generator" / "syscfg_instances.py"
MASTER = REPO / "library" / "masters" / "mspm0" / "mspm0.syscfg"
OUT = Path(__file__).resolve().parent / "probe-01-c1-reverse.txt"

REGISTERED = '"I2C_0": ("ml_mpu6050", "i2c_probe"),'
UNREGISTERED = '"I2C_0": ("ml_mpu6050",),'

# 子进程里跑的那段：重新 import 模块（不吃父进程缓存）→ 裁剪 → 逐行报告
CHILD = r'''
import sys
from pathlib import Path
sys.path.insert(0, r"{src}")
from contest_generator.syscfg_prune import prune_syscfg

master = Path(r"{master}").read_text(encoding="utf-8", newline="")
pruned = prune_syscfg(master, ["i2c_probe"])
for needle in (
    'I2C_0.$name',
    'I2C_0.peripheral.sdaPin.$assign = "PA0";',
    'I2C_0.peripheral.sclPin.$assign = "PA1";',
):
    print("SURVIVES" if needle in pruned else "PRUNED", needle)
'''

lines: list[str] = []
ok = True


def log(text: str) -> None:
    lines.append(text)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_child() -> list[str]:
    proc = subprocess.run(
        [sys.executable, "-c", CHILD.format(src=REPO / "src", master=MASTER)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        return [f"CHILD-FAILED rc={proc.returncode}", proc.stderr.strip()[-400:]]
    results = [line for line in proc.stdout.splitlines() if line.strip()]
    # 子进程活着但没吐满三行 = 读数不完整，同样按「不可信」处理
    if sum(1 for line in results if line.startswith(("SURVIVES", "PRUNED"))) != 3:
        return ["CHILD-FAILED 读数不完整（不足三条）", *results]
    return results


def child_says_pruned(lines: list[str]) -> bool:
    """子进程读数是否**可信地**报告「三条全被裁」。

    评审整改：原来只看「没有 SURVIVES 行」——子进程崩掉时也满足，会把崩溃
    误读成「反证成立」。判据改成「三条读数齐全且全是 PRUNED」。
    """
    results = [line for line in lines if line.startswith(("SURVIVES", "PRUNED"))]
    return len(results) == 3 and all(line.startswith("PRUNED") for line in results)


def child_says_survives(lines: list[str]) -> bool:
    """子进程读数是否**可信地**报告「三条全在」（正断言的同款完整性判据）。"""
    results = [line for line in lines if line.startswith(("SURVIVES", "PRUNED"))]
    return len(results) == 3 and all(line.startswith("SURVIVES") for line in results)


original = TARGET.read_bytes()
original_sha = sha256(original)
text = original.decode("utf-8")

log("== 反证：拿掉 I2C_0 消费者登记，看 I2C_0 是否真被裁 ==")
log(f"目标文件：{TARGET.relative_to(REPO)}")
log(f"原文 sha256：{original_sha}")
log(f"母版 syscfg：{MASTER.relative_to(REPO)}")

# ---- ① 前置干净性检查 ---------------------------------------------------
count = text.count(REGISTERED)
log("")
log(f"[1] 前置检查：登记行出现 {count} 次（应为 1）")
if count != 1 or text.count(UNREGISTERED) != 0:
    log("    前置不干净——拒绝注入（先看这个文件是不是停在某个探针的注入态）")
    ok = False
else:
    log("    干净：登记行在且只在一处，未登记形态不存在")

if ok:
    # ---- ② 注入前：正断言（登记在 = I2C_0 存活）------------------------
    log("")
    log("[2] 注入前（登记在）：prune(master, [\"i2c_probe\"])")
    before = run_child()
    for line in before:
        log(f"    {line}")
    if not child_says_survives(before):
        log("    ✗ 注入前 I2C_0 没全活着（或子进程读数不可信）——前提不成立")
        ok = False

    try:
        # ---- ③ 注入 ---------------------------------------------------
        TARGET.write_bytes(
            text.replace(REGISTERED, UNREGISTERED, 1).encode("utf-8")
        )
        log("")
        log(f"[3] 已注入（逐字节备份原文 {len(original)} B）")
        log("[4] 注入后（登记没了）：prune(master, [\"i2c_probe\"])")
        child = run_child()
        for line in child:
            log(f"    {line}")
        if not child_says_pruned(child):
            log("    ✗ 反证不成立：拿掉登记 I2C_0 仍在（或子进程读数不可信）"
                "——登记行不是判据？")
            ok = False
        else:
            log("    ✓ 反证成立：I2C_0 的 $name 与两条 $assign 全被裁掉"
                "——不登记就没有 I2C_0_INST，i2c_probe.c 编不过")
    finally:
        # ---- ④ 逐字节复原 + 复核 ---------------------------------------
        TARGET.write_bytes(original)

restored = TARGET.read_bytes()
log("")
log(f"[5] 复原复核：sha256 {sha256(restored)}")
if sha256(restored) != original_sha:
    log("    ✗ 复原失败（文件与原文不一致）")
    ok = False
else:
    log("    ✓ 逐字节复原（与原文 sha256 相等）")

# ---- ⑤ 复原后再跑一次正断言 --------------------------------------------
if sha256(restored) == original_sha:
    log("")
    log("[6] 复原后复跑正断言（应与 [2] 同形）")
    after = run_child()
    for line in after:
        log(f"    {line}")
    if not child_says_survives(after):
        log("    ✗ 复原后 I2C_0 没全活回来——复原不完整或判据不成立")
        ok = False

log("")
log("== 结论 ==")
log("PASS：登记行是 I2C_0 存活的唯一判据（拿掉即裁、放回即活）"
    if ok else "FAIL：见上面 ✗")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
print("\n".join(lines))
print(f"\n读数已落盘：{OUT}")
raise SystemExit(0 if ok else 1)
