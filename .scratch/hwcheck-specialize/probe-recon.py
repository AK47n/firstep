# -*- coding: utf-8 -*-
"""专精面扩张（首批 20 件）侦察探针：**先量后定**。

回答三个问题，供 spec 定射程与分批：
  1. 每一件在两个平台上到底有没有「可调用的 init / 可读的函数」——没有 read 路径的件
     只能做到「身份探头」档，配不了读数；
  2. 有没有**身份寄存器**（WHO_AM_I / ID 常量 / 器件地址宏）——有才谈得上"板上 OK/FAIL"；
  3. 读数走**整数**还是**浮点**——配方 read 段只收整数表达式（`RecipeRead` 的判据），
     浮点件要拆整数/小数两次回显（ml_mpu6050 mspm0 那格就是先例）。

只读，不改任何库内文件。读数落 `probe-recon.txt`（本机控制台 GBK，先落盘再打印）。
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODULES = REPO / "library" / "modules"

SLUGS = [
    # I2C 环境 / 姿态 / 光色传感一族
    "aht10", "sht20", "sht30", "bh1750", "bmp180", "ms5611",
    "hmc5883l", "qmc5883l", "mlx90614", "sgp30", "tcs34725",
    # I2C 通用外设
    "at24c02", "ads1115", "pca9685",
    # 单总线 / 模拟 / 执行件
    "dht11", "ds18b20", "hx711", "joystick", "servo", "relay",
]

# 头文件里的函数声明（`ret name(args);`）：够判"有没有 read 路径"
_PROTO_RE = re.compile(
    r"^\s*(?:static\s+inline\s+)?([A-Za-z_][\w \t\*]*?)\s+([A-Za-z_]\w*)\s*\(([^;{)]*)\)\s*;",
    re.M,
)
# 身份类常量：器件地址 / WHO_AM_I / 寄存器号
_IDENT_RE = re.compile(
    r"#define\s+(\w*(?:ADDR|ADDRESS|WHO_AM_I|_ID|CHIP_ID|DEVICE_ID|I2C_ADDR)\w*)\s+([^\s/]+)"
)
_FLOAT_HINT = re.compile(r"\b(float|double)\b")
_READISH = re.compile(r"_(read|get|measure|fetch|query|scan|value|data)\w*$", re.I)
_INITISH = re.compile(r"_init\w*$", re.I)


def header_text(module_dir: Path) -> str:
    out = []
    for path in sorted(module_dir.rglob("*.h")):
        out.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(out)


def source_text(module_dir: Path) -> str:
    out = []
    for path in sorted(module_dir.rglob("*.c")):
        out.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(out)


def main() -> int:
    lines: list[str] = [
        "=== 专精面扩张（首批 20 件）侦察：先量后定 ===",
        "",
        "判据三列：平台 / 可调用函数（init 与 read 各列一条）／身份常量（有则板上可判 OK/FAIL）",
        "",
    ]
    for slug in SLUGS:
        mdir = MODULES / slug
        manifest = json.loads((mdir / "manifest.json").read_text(encoding="utf-8"))
        platforms = list((manifest.get("platforms") or {}).keys())
        head = header_text(mdir)
        body = source_text(mdir)
        protos = [
            (ret.strip(), name, args.strip())
            for ret, name, args in _PROTO_RE.findall(head)
        ]
        inits = [n for _, n, _ in protos if _INITISH.search(n)]
        reads = [(r, n) for r, n, _ in protos if _READISH.search(n)]
        idents = _IDENT_RE.findall(head)
        float_reads = [f"{n} -> {r}" for r, n in reads if _FLOAT_HINT.search(r)]
        i2c = bool(re.search(r"\bi2c\b", head + body, re.I))

        lines.append(f"## {slug}  [{', '.join(platforms)}]" + ("  （I2C 类）" if i2c else ""))
        lines.append(f"   init : {', '.join(inits) or '（头文件里没有 *_init* 声明）'}")
        lines.append(
            "   read : "
            + (", ".join(f"{n}() -> {r}" for r, n in reads) or "（头文件里没有 read/get 类声明）")
        )
        if float_reads:
            lines.append(f"   ⚠ 浮点读数：{', '.join(float_reads)}（配方 read 只收整数，要拆两行）")
        lines.append(
            "   身份 : "
            + (", ".join(f"{k}={v}" for k, v in idents) or "（头文件里没有身份 / 地址常量）")
        )
        lines.append("")

    text = "\n".join(lines) + "\n"
    (REPO / ".scratch" / "hwcheck-specialize" / "probe-recon.txt").write_text(
        text, encoding="utf-8"
    )
    print(text)
    return 0


if __name__ == "__main__":
    Path(REPO / ".scratch" / "hwcheck-specialize").mkdir(parents=True, exist_ok=True)
    raise SystemExit(main())
