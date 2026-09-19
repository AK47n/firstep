# -*- coding: utf-8 -*-
"""工单 module-hwcheck/03 真机口径证据：**走产品端点**看接线表 / 冲突 / 顺序。

用法：python .scratch/module-hwcheck/verify-03-real-machine.py

为什么走端点而不是直接调域函数：本单的验收判据是"页面上看到的那张表与生成工程
README 里那张表是同一份推导"。这条只有在**产品路径**上才证得了——预览端点给页面
的行，必须逐格等于真生成出来的 `README.md` 里解析回来的行（tests/test_hwcheck.py
里那条用例是同一个判据，这里把它跑成可复跑的证据文件）。

它做四件事（全程真库 + 真母版，输出到 %TEMP%，跑完自删）：

1. `POST /api/hwcheck/preview`（mspm0 + MPU6050）→ 打印接线行 / 冲突组 / 缺条目；
2. `POST /api/hwcheck/preview`（stm32 + 只有 mspm0 条目的 sr04）→ 缺条目点名；
3. `POST /api/hwcheck/generate`（mspm0 + MPU6050）→ 落盘工程 README 的引脚接线表
   **与预览载荷逐格对比**（单源判据）；同时复核上下文清单里的 devices；
4. 把结论写成 PASS/FAIL 清单落 `verify-03-real-machine.txt`。
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
from contest_generator.context_manifest import read_context_fields  # noqa: E402
from contest_generator.readme import parse_pin_table  # noqa: E402
from contest_generator.webapp import AppContext, create_app  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "verify-03-real-machine.txt"
CORE = ("slug", "role", "role_id", "role_label", "pin", "remark")


def main() -> int:
    lines: list[str] = ["# 工单 module-hwcheck/03 真机口径证据（产品端点 + 真库真母版）", ""]
    verdicts: list[tuple[str, bool, str]] = []
    root = Path(tempfile.mkdtemp(prefix="firstep-verify03-"))
    desktop = root / "desktop"
    desktop.mkdir()
    try:
        ctx = AppContext(
            config_path=root / "cfg" / "config.json",
            config=AppConfig(
                api_key="sk-test",
                module_library_dir=REPO / "library" / "modules",
                masters_dir=REPO / "library" / "masters",
            ),
            desktop_dir=lambda: desktop,
        )
        client = TestClient(create_app(ctx))

        # ① mspm0 + MPU6050：接线行 / 冲突组 / 顺序
        preview = client.post(
            "/api/hwcheck/preview",
            json={"platform": "mspm0", "debug_uart": True, "oled": False,
                  "devices": ["ml_mpu6050"]},
        )
        lines.append(f"## ① POST /api/hwcheck/preview（mspm0 + ml_mpu6050）→ {preview.status_code}")
        body = preview.json()
        wiring = body["wiring"]
        lines.append("接线行：")
        for row in wiring["rows"]:
            note = f"  ［板上注记：{row['pin_note']}］" if row["pin_note"] else ""
            lines.append(f"  - {row['slug']} | {row['role']} | {row['pin']} | {row['remark']}{note}")
        lines.append("同脚组（模块之间）：")
        lines.append("  " + (str(wiring["groups"]) if wiring["groups"] else "（无）"))
        lines.append("板上自带的共享（板定义注记）：")
        for item in wiring["board_shares"]:
            lines.append(f"  - {item['pin']}：{item['note']}  ［{', '.join(item['roles'])}］")
        lines.append("建议顺序：")
        for i, item in enumerate(wiring["order"], 1):
            tag = "（先做·板子活着）" if item["bring_up"] else ""
            lines.append(f"  {i}. {item['slug']}{tag} — {item['description']}")
        lines.append(f"引导语：{wiring['guide']}")
        lines.append(f"理由：{wiring['reason']}")
        lines.append(f"尾注：{wiring['footnote']}")
        lines.append("")

        rows = wiring["rows"]
        pa = {row["pin"]: row for row in rows}
        verdicts.append((
            "①a 地猛星 MPU6050 的 I2C0 默认脚 PA0/PA1 出现在接线表里",
            "PA0" in pa and "PA1" in pa,
            f"pins={sorted(pa)}",
        ))
        verdicts.append((
            "①b PA0/PA1 带出板上共享注记（板载 LED 共用——这条暗雷如实呈现）",
            all("板载 LED 共用" in pa[p]["pin_note"] for p in ("PA0", "PA1") if p in pa),
            pa.get("PA1", {}).get("pin_note", ""),
        ))
        verdicts.append((
            "①c 顺序里 MPU6050 排在 bring-up 模块之后（先确认板子活着）",
            [i["slug"] for i in wiring["order"]][-1] == "ml_mpu6050"
            and any(i["bring_up"] for i in wiring["order"]),
            " → ".join(i["slug"] for i in wiring["order"]),
        ))
        shares = {item["pin"]: item for item in wiring["board_shares"]}
        verdicts.append((
            "①d PA0/PA1 同时进「板上共享」一列（评审整改：同脚组只看模块角色，"
            "看不见板载 LED，冲突区不能只说「没有共用同一个引脚」）",
            set(shares) >= {"PA0", "PA1"}
            and all("板载 LED 共用" in shares[p]["note"] for p in ("PA0", "PA1"))
            and shares["PA1"]["roles"] == ["ml_mpu6050.I2C_0_SCL"],
            "；".join(f"{p}：{shares[p]['note']}" for p in sorted(shares)),
        ))

        # ② 本平台没有条目的器件：点名而不是静默省略
        missing = client.post(
            "/api/hwcheck/preview",
            json={"platform": "stm32", "debug_uart": False, "oled": False,
                  "devices": ["sr04"]},
        ).json()["wiring"]["missing"]
        lines.append(f"## ② POST /api/hwcheck/preview（stm32 + 只有 mspm0 条目的 sr04）")
        lines.append(f"  missing = {missing}")
        lines.append("")
        verdicts.append((
            "② sr04 在 stm32 上被点名「无本平台版本，无法检测」",
            [m["slug"] for m in missing] == ["sr04"]
            and "无本平台版本" in missing[0]["message"]
            and "无法检测" in missing[0]["message"],
            missing[0]["message"] if missing else "（空）",
        ))

        # ③ 生成：README 引脚接线表 vs 预览载荷（同一推导）
        parent = root / "out"
        parent.mkdir()
        generated = client.post(
            "/api/hwcheck/generate",
            json={"platform": "mspm0", "debug_uart": True, "oled": False,
                  "devices": ["ml_mpu6050"], "parent_dir": str(parent)},
        )
        lines.append(f"## ③ POST /api/hwcheck/generate（同形态）→ {generated.status_code}")
        gen = generated.json()
        project = Path(gen["output_dir"])
        lines.append(f"落盘工程：{project.name}")
        readme = (project / "README.md").read_text(encoding="utf-8")
        table = parse_pin_table(readme) or []
        lines.append(f"README 引脚接线表 {len(table)} 行 / 载荷 {len(gen['wiring']['rows'])} 行")
        same = [tuple(r[k] for k in CORE) for r in table] == [
            tuple(r[k] for k in CORE) for r in gen["wiring"]["rows"]
        ]
        lines.append("")
        verdicts.append((
            "③a 页面接线行 = 生成工程 README 的引脚接线表（逐格）",
            same and bool(table),
            f"README {len(table)} 行 vs 载荷 {len(gen['wiring']['rows'])} 行",
        ))
        fields = read_context_fields(project) or {}
        verdicts.append((
            "③b 上下文清单记下器件选择（回读的服务端真源）",
            fields.get("devices") == ["ml_mpu6050"] and "ml_mpu6050" in fields.get("slugs", []),
            f"devices={fields.get('devices')} slugs={fields.get('slugs')}",
        ))
        back = client.get(
            "/api/hwcheck/project", params={"output_dir": str(project)}
        ).json()
        verdicts.append((
            "③c 回读拿回同一套器件与接线行（刷新回显）",
            back["devices"] == ["ml_mpu6050"]
            and back["wiring"]["rows"] == gen["wiring"]["rows"],
            f"devices={back['devices']} rows={len(back['wiring']['rows'])}",
        ))

        # ③d 默认双通道（mspm0）的撞脚：页面预警与生成门禁报的是同一个脚
        conflict = client.post(
            "/api/hwcheck/preview",
            json={"platform": "mspm0", "debug_uart": True, "oled": True},
        ).json()["wiring"]["groups"]
        pins = [g["pin"] for g in conflict if g["kind"] == "conflict"]
        refused = client.post(
            "/api/hwcheck/generate",
            json={"platform": "mspm0", "debug_uart": True, "oled": True,
                  "parent_dir": str(parent)},
        )
        lines.append("## ④ mspm0 默认双通道：页面预警 vs 生成门禁")
        lines.append(f"  页面冲突组：{[g for g in conflict if g['kind'] == 'conflict']}")
        lines.append(f"  生成返回：{refused.status_code} {refused.json().get('detail', '')[:120]}")
        lines.append("")
        verdicts.append((
            "④ 页面预警的冲突脚（PA22）与生成门禁报的是同一个脚",
            pins == ["PA22"] and refused.status_code == 400
            and "PA22" in str(refused.json().get("detail", "")),
            f"预警={pins} 生成={refused.status_code}",
        ))

        lines.append("## 结论")
        failed = 0
        for name, ok, detail in verdicts:
            lines.append(f"- [{'PASS' if ok else 'FAIL'}] {name} —— {detail}")
            if not ok:
                failed += 1
        lines.append("")
        lines.append(
            f"合计 {len(verdicts)} 条，判红 {failed} 条。"
            + ("全部成立。" if not failed else "**有判据不成立**。")
        )
        print("\n".join(lines))
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n[已写入] {OUT}")
        return 1 if failed else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
