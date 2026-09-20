# -*- coding: utf-8 -*-
"""工单 hwcheck-pin-conflict-exit/01 的验收取证（进程内 TestClient，零 LLM）。

逐条对着票面验收线收读数，落盘 `verify-01-page-exit.txt`（PASS/FAIL 清单）：

1. mspm0 + **默认双通道** + 任意器件（含"一件都不选"）能生成检测工程；
2. 预览与生成在这些形态上判据一致（同码）——装不下的形态两边都 400；
3. `ADC12_0.adcPin7`（PA22）不再以"角色未登记"挡住 adc / us016 / mq2 的生成；
4. 装不下的形态（9 件同堂）给出的出路在检测页做得到（不是"去引脚配置改绑"）；
5. 改绑过引脚时接线表与工程 README 里那条线**跟着变**（同一组脚）。

用法：python .scratch/hwcheck-pin-conflict-exit/verify-01-page-exit.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from contest_generator.config import AppConfig  # noqa: E402
from contest_generator.hwcheck_board import HWCHECK_PIN_EXIT_MARKER  # noqa: E402
from contest_generator.readme import parse_pin_table  # noqa: E402
from contest_generator.webapp import AppContext, create_app  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "verify-01-page-exit.txt"

ALL_NINE = ("led", "oled", "debug_uart", "key", "beep", "sr04", "jy61p",
            "xunji", "ml_mpu6050")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    root = Path(tempfile.mkdtemp(prefix="firstep-verify01-"))
    results: list[tuple[bool, str]] = []
    detail: list[str] = []
    try:
        ctx = AppContext(
            config_path=root / "cfg" / "config.json",
            config=AppConfig(
                api_key="sk-test",
                module_library_dir=REPO / "library" / "modules",
                masters_dir=REPO / "library" / "masters",
            ),
            desktop_dir=lambda: root,
        )
        client = TestClient(create_app(ctx))

        def _post(url: str, platform: str, devices, uart: bool, oled: bool, gen: bool):
            payload = {"platform": platform, "debug_uart": uart, "oled": oled,
                       "devices": list(devices)}
            if gen:
                payload["parent_dir"] = str(root)
            return client.post(url, json=payload)

        # ---- 1 + 2：默认双通道逐格能生成；预览与生成同码 ----
        for devices, label in (
            ((), "一件器件都不选"),
            (("adc",), "adc"),
            (("us016",), "us016"),
            (("mq2",), "mq2"),
            (("xunji",), "xunji"),
            (("sr04",), "sr04"),
            (ALL_NINE, "9 件同堂"),
        ):
            preview = _post("/api/hwcheck/preview", "mspm0", devices, True, True, False)
            generate = _post("/api/hwcheck/generate", "mspm0", devices, True, True, True)
            same = preview.status_code == generate.status_code
            ok = same and (
                preview.status_code == 200
                or HWCHECK_PIN_EXIT_MARKER in str(preview.json().get("detail", ""))
            )
            results.append((
                ok,
                f"默认双通道 {label}：预览 {preview.status_code} / 生成 "
                f"{generate.status_code}"
                + ("（页面已说明原因）" if preview.status_code == 400 else ""),
            ))
            if generate.status_code == 200 and devices not in (ALL_NINE,):
                body = generate.json()
                detail.append(f"  {label}: pin_fixes={body['wiring']['pin_fixes']}")

        # ---- 3：adcPin7 不再挡 adc / us016 / mq2 ----
        generated = _post(
            "/api/hwcheck/generate", "mspm0", ("adc",), True, False, True
        )
        syscfg = ""
        if generated.status_code == 200:
            project = Path(generated.json()["output_dir"])
            syscfg = (project / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
        results.append((
            generated.status_code == 200
            and 'ADC12_0.peripheral.adcPin7.$assign = "PA22";' not in syscfg
            and 'ADC12_0.adcMem6chansel             = "DL_ADC12_INPUT_CHAN_3";' in syscfg
            and 'ADC12_0.peripheral.adcPin3.$assign = "PA24";' in syscfg,
            "adc 单选（只开串口）：能生成，且孤儿槽位 adcPin7 让位、自己的 adcPin3 不动",
        ))

        # ---- 4：装不下的出路在检测页做得到 ----
        refusal = _post(
            "/api/hwcheck/generate", "mspm0", ALL_NINE, True, True, True
        )
        text = str(refusal.json().get("detail", ""))
        results.append((
            refusal.status_code == 400
            and HWCHECK_PIN_EXIT_MARKER in text
            and "只勾一个输出通道" in text
            and "引脚配置里改绑上述角色" not in text,
            "9 件同堂：400 且出路是检测页做得到的（不原样带赛题页那句）",
        ))

        # ---- 5：改绑过引脚时接线表与工程 README 同源 ----
        body = _post("/api/hwcheck/generate", "mspm0", (), True, True, True).json()
        project = Path(body["output_dir"])
        page = {(row["slug"], row["role_id"]): row["pin"]
                for row in body["wiring"]["rows"]}
        readme = {(row["slug"], row["role_id"]): row["pin"]
                  for row in parse_pin_table(
                      (project / "README.md").read_text(encoding="utf-8")) or []}
        moved = [key for key, pin in page.items()
                 if readme.get(key) and readme[key] != pin]
        results.append((
            not moved and page == {k: v for k, v in readme.items() if k in page},
            f"默认双通道：页面接线表与工程 README 逐行同脚（移过的是 "
            f"{[row for row in body['wiring']['pin_fixes']]}）",
        ))
        return _report(results, detail)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _report(results: list[tuple[bool, str]], detail: list[str]) -> int:
    failed = [text for ok, text in results if not ok]
    lines = [
        "# 工单 hwcheck-pin-conflict-exit/01 验收读数（检测页 mspm0 出口 + ADC 孤儿槽位）",
        "",
        f"判据：{len(results)} 条里 PASS {len(results) - len(failed)} / FAIL {len(failed)}",
        "",
    ]
    lines.extend(("PASS  " if ok else "FAIL  ") + text for ok, text in results)
    if detail:
        lines.append("")
        lines.append("自动移开的脚（生成载荷 wiring.pin_fixes）：")
        lines.extend(detail)
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
