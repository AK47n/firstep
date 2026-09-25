# -*- coding: utf-8 -*-
"""专精面扩张的**每批量具**：指定 slug 一列 → 两平台真编译 + 配方生效核对。

为什么要它（而不是复用 `hwcheck-acceptance/recheck-compile-matrix.py`）：那一支验的是
**检测工程的形态**（骨架 / 赛题 / 检测默认通道 / 那两格组合），本支验的是**配方本身**：
每一格既要真编译（0 error / 0 warning），又要证明"这条配方真的生效了"——页面载荷里
这一件挂着 `[专精]` 小节、命令字符来自这张表，而不是悄悄退回通用降级。

两处口径按复测的发现加严：
  ① **链接器形态的告警也算数**：`parse_compile_errors` 认不出 `warning #10210-D:`，
     所以本支直接在**原始日志行**上同时数 `warning:` 与 `warning #`，把两者都写进读数；
  ② **被拦下的格如实分类**（装不下 / 引脚冲突），不算编不过、也不算通过。

用法：
    py -3 .scratch/hwcheck-specialize/probe-compile-matrix.py --slugs led,oled,sr04
    py -3 .scratch/hwcheck-specialize/probe-compile-matrix.py            # 默认首批 20 件
读数先落盘 `probe-compile-matrix.txt` 再打印；编译产物落系统临时目录，跑完即清。
"""
import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.compile_runner import (  # noqa: E402
    collect_build_log, find_ccs_tools, find_make, find_uv4,
)
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"
REPORT = REPO / ".scratch" / "hwcheck-specialize" / "probe-compile-matrix.txt"

FIRST_BATCH = [
    "aht10", "sht20", "sht30", "bh1750", "bmp180", "ms5611",
    "hmc5883l", "qmc5883l", "tcs34725", "mlx90614", "sgp30", "at24c02",
    "ads1115", "pca9685", "dht11", "ds18b20", "hx711",
    "joystick", "servo", "relay",
]

# 编译器形态（`error:` / `warning:`）与链接器形态（`warning #10210-D:`）分开数：
# 后者的存在本身就是一条要写进读数的口径事实。
_COMPILER_DIAG = re.compile(r"\b(error|warning)\b\s*:", re.IGNORECASE)
_LINKER_DIAG = re.compile(r"\b(error|warning)\b\s*#", re.IGNORECASE)
_SUMMARY_RE = re.compile(r"^\d+\s+Error\(s\)")


def count_diagnostics(text: str) -> tuple[int, int, int, int, list[str]]:
    """→ (编译器 error, 编译器 warning, 链接器 error, 链接器 warning, 诊断原文行)。"""
    ce = cw = le = lw = 0
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if _SUMMARY_RE.match(stripped) or stripped.startswith("Build Time"):
            continue
        linker = _LINKER_DIAG.search(stripped)
        if linker:
            if linker.group(1).lower() == "error":
                le += 1
            else:
                lw += 1
            lines.append(stripped[:170])
            continue
        compiler = _COMPILER_DIAG.search(stripped)
        if compiler:
            if compiler.group(1).lower() == "error":
                ce += 1
            else:
                cw += 1
            lines.append(stripped[:170])
    return ce, cw, le, lw, lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slugs", default="", help="逗号分隔；缺省 = 首批 20 件")
    parser.add_argument("--out", default="")
    parser.add_argument("--oled", default="1", help="1 = 带 OLED 通道（学生默认形态）")
    args = parser.parse_args()

    slugs = [s.strip() for s in args.slugs.split(",") if s.strip()] or FIRST_BATCH
    oled = args.oled != "0"
    out_path = Path(args.out) if args.out else REPORT

    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.hwcheck import HwCheckConfig  # noqa: F401  (载荷同源)
    from contest_generator.webapp import AppContext, create_app

    make = find_make(GMAKE)
    uv4 = find_uv4()
    work = Path(tempfile.mkdtemp(prefix="firstep-specialize-"))
    ctx = AppContext(
        config_path=work / "cfg" / "config.json",
        config=AppConfig(api_key="sk-test", module_library_dir=MODULES,
                         masters_dir=MASTERS),
        desktop_dir=lambda: work,
    )
    client = TestClient(create_app(ctx))

    rows: list[str] = []
    fails: list[str] = []
    blocked: list[str] = []
    absent: list[str] = []
    try:
        # 本平台没有这一格的件（如 sr04 / jy61p / xunji 只有 mspm0 条目）要先摘掉：
        # 否则它们会被"所选模块文件不齐全"式的 400 记成"被拦下"，把读数读歪。
        import json as _json
        from contest_generator.library import list_modules
        platforms_of = {m.slug: set(m.platforms) for m in list_modules(MODULES)}
        for platform in (PLATFORM_MSPM0, PLATFORM_STM32):
            rows.append(f"## {platform}")
            for slug in slugs:
                if platform not in platforms_of.get(slug, set()):
                    absent.append(f"{platform}/{slug}")
                    rows.append(f"[——] {platform}/{slug}  本平台没有这一格（库内条目只有 "
                                f"{'/'.join(sorted(platforms_of.get(slug, set()))) or '无'}）")
                    continue
                payload = {"platform": platform, "debug_uart": True, "oled": oled,
                           "devices": [slug], "parent_dir": str(work)}
                view = client.post("/api/hwcheck/preview", json=payload)
                specialized = "（预览失败）"
                if view.status_code == 200:
                    body = view.json()
                    tags = [s.get("slug") for s in (body.get("sections") or [])
                            if s.get("slug") == slug]
                    unspec = [u.get("slug") for u in (body.get("unspecialized") or [])]
                    specialized = ("[专精]" if tags else
                                   ("未专精" if slug in unspec else "（载荷里没有这一件）"))
                response = client.post("/api/hwcheck/generate", json=payload)
                if response.status_code != 200:
                    blocked.append(f"{platform}/{slug}")
                    rows.append(f"[拦下 {response.status_code}] {platform}/{slug}"
                                f"  页面标记={specialized or '—'}")
                    detail = response.json().get("detail") if \
                        response.headers.get("content-type", "").startswith("application/json") \
                        else response.text
                    rows.append("        " + str(detail).splitlines()[0][:150])
                    continue
                project = Path(response.json()["output_dir"])
                log = collect_build_log(
                    platform, project,
                    make=make if platform == PLATFORM_MSPM0 else None,
                    uv4=uv4 if platform == PLATFORM_STM32 else None,
                    timeout=900,
                )
                text = log.run.output or ""
                ce, cw, le, lw, diag = count_diagnostics(text)
                ok = log.run.exit_code == 0 and ce == 0 and cw == 0
                mark = "PASS" if ok and not (le or lw) else ("PASS*" if ok else "FAIL")
                if not ok:
                    fails.append(f"{platform}/{slug}")
                rows.append(
                    f"[{mark}] {platform}/{slug}  页面标记={specialized or '—'}"
                    f"  exit={log.run.exit_code}  编译器 error {ce} / warning {cw}"
                    f"  链接器 error {le} / warning {lw}"
                )
                for line in diag:
                    rows.append("        " + line)
            rows.append("")

        head = [
            "=== 专精面扩张：两平台真编译矩阵 + 配方生效核对 ===",
            f"gmake：{make}",
            f"UV4：{uv4}",
            f"CCS 三件套：{find_ccs_tools()}",
            f"格数：{len(slugs)} 件 × 2 平台（OLED 通道 {'开' if oled else '关'}）",
            "",
            "判据：exit=0 且 编译器 0 error / 0 warning；`PASS*` = 编过了但带链接器形态告警"
            "（如实记账，见复测发现的口径漏洞）；`[拦下]` = 生成前拦下（如引脚装不下）；"
            "`[——]` = 库内这一件本平台没有条目（不是失败，也不算通过）。"
            "页面标记 = 预览载荷里这一件挂的是 `[专精]` 还是 `未专精`（配方真的生效没有）。",
            "",
        ]
        tail = [
            "=== 结论："
            + ("全绿（编译器 0 error / 0 warning，无链接器告警）" if not fails and not any(
                r.startswith("[PASS*]") for r in rows) else
               (f"编不过 {len(fails)} 格：{'、'.join(fails)}" if fails else "编过了，但有链接器形态告警"))
            + f"；被拦下 {len(blocked)} 格" + ("：" + "、".join(blocked) if blocked else "")
            + f"；本平台没有这一格 {len(absent)} 格" + ("：" + "、".join(absent) if absent else "")
            + " ===",
        ]
        report = "\n".join(head + rows + tail) + "\n"
        out_path.write_text(report, encoding="utf-8")
        print(report)
        return 1 if fails else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
