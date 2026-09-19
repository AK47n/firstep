# -*- coding: utf-8 -*-
"""工单 module-hwcheck/04 真机口径证据：**走产品端点**看配方机制 + led / oled 专精。

用法：python .scratch/module-hwcheck/verify-04-real-machine.py

为什么走端点而不是直接调域函数：本单的验收判据是"生成的检测程序里，专精件真的
被测了、未专精件被如实点名，而配方引用的接口一个都不能是编的"。前两条只有
**产品路径**证得了；第三条要用真生成内核的门禁语料独立复核一遍（配方里写了
`led_init(0)`，而语料里 stm32 的 led 是 `files: []` 的空条目——它的实现在母版
`ml_led.h` 里）。所以这里既走端点，也把生成语料拉出来自己跑一次
`_check_main_calls`，两条路都得绿。

它做六件事（全程真库 + 真母版，输出到 %TEMP%，跑完自删）：

1. 预览（stm32 / mspm0 + led + oled）→ 小节清单 / 顺序 / 顺序理由；
2. **真生成**（stm32 + led，双通道）→ 落盘 main.c 逐字节等于载荷、逐件小节真在、
   盘上文件含 [专精] 标记与逐件调用；
3. 把生成语料重建出来跑一次 `_check_main_calls`（门禁独立复核配方引用）；
4. 未专精件点名（stm32 + sr04 + led：sr04 没配方 → 点名，led 有配方 → 出小节）；
5. 平台差异（mspm0 的 led 只测通道 0；地猛星无浮点显示接口写进 oled 的 note）；
6. **红证**：把配方里的函数名临时改坏 → 产品端点必须 400 并点名那个名字
   （探针逐字节复原配方文件）。

结论写成 PASS/FAIL 清单落 `verify-04-real-machine.txt`。
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from contest_generator.config import AppConfig  # noqa: E402
from contest_generator.compile_runner import find_uv4, run_compile  # noqa: E402
from contest_generator.generator import (  # noqa: E402
    ModuleCorpus,
    _check_main_calls,
    build_module_corpus,
)
from contest_generator.hwcheck import HwCheckConfig, hwcheck_modules, render_main_c  # noqa: E402
from contest_generator.hwcheck_recipe import (  # noqa: E402
    RECIPE_FILENAME,
    load_recipes,
    recipe_library_path,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.master_store import master_project_dir  # noqa: E402
from contest_generator.selection import resolve_dependencies  # noqa: E402
from contest_generator.sse import SseEmitter  # noqa: E402
from contest_generator.treewalk import iter_project_files  # noqa: E402
from contest_generator.webapp import AppContext, create_app  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "verify-04-real-machine.txt"
LIBRARY = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"


def main() -> int:
    lines: list[str] = ["# 工单 module-hwcheck/04 真机口径证据（产品端点 + 真库真母版）", ""]
    verdicts: list[tuple[str, bool, str]] = []
    root = Path(tempfile.mkdtemp(prefix="firstep-verify04-"))
    desktop = root / "desktop"
    desktop.mkdir()
    try:
        ctx = AppContext(
            config_path=root / "cfg" / "config.json",
            config=AppConfig(
                api_key="sk-test",
                module_library_dir=LIBRARY,
                masters_dir=MASTERS,
            ),
            desktop_dir=lambda: desktop,
        )
        client = TestClient(create_app(ctx))

        # ① 预览：小节清单 + 顺序（两平台各来一次）
        for platform, channels in (("stm32", {"debug_uart": True, "oled": True}),
                                   ("mspm0", {"debug_uart": False, "oled": True})):
            body = client.post(
                "/api/hwcheck/preview",
                json={"platform": platform, **channels, "devices": ["oled", "led"]},
            ).json()
            lines.append(f"## ① POST /api/hwcheck/preview（{platform} + oled + led）")
            lines.append(f"  sections = {[s['slug'] for s in body['sections']]}")
            lines.append(f"  unspecialized = {body['unspecialized']}")
            for section in body["sections"]:
                lines.append(
                    f"  - {section['tag']} {section['slug']}：init={section['init']} "
                    f"init_expect={section['init_expect']!r} "
                    f"probe={section['probe']} has_probe={section['has_probe']} "
                    f"read={section['read']}"
                )
                for note in section["note"]:
                    lines.append(f"      · {note}")
            lines.append("")
            if platform == "stm32":
                verdicts.append((
                    "①a stm32 上 led / oled 都出 [专精] 小节，且顺序把 led 排在前"
                    "（bring-up 分区，与 README 验证顺序同一函数）",
                    [s["slug"] for s in body["sections"]] == ["led", "oled"]
                    and all(s["tag"] == "[专精]" for s in body["sections"]),
                    f"sections={[s['slug'] for s in body['sections']]}",
                ))
                verdicts.append((
                    "①b led 的配方**不判返回值**（led_init 是 void）+ 无探头"
                    "（如实「只看现象」）——真机判例：硬编 `r = led_init(...)` 编译不过",
                    body["sections"][0]["init"] == ["led_init(LED_RED)"]
                    and body["sections"][0]["init_expect"] == ""
                    and body["sections"][0]["has_probe"] is False,
                    f"init={body['sections'][0]['init']} "
                    f"expect={body['sections'][0]['init_expect']!r} "
                    f"probe={body['sections'][0]['probe']}",
                ))
                verdicts.append((
                    "①c oled 的配方把「本平台没有浮点显示接口」写进 note"
                    "（平台不对称如实呈现，不假装有角度）",
                    any("浮点显示接口" in n for n in body["sections"][1]["note"]),
                    "；".join(body["sections"][1]["note"])[:160],
                ))
            else:
                mspm0_led = next(s for s in body["sections"] if s["slug"] == "led")
                # 判据分开看两件事（本次踩到的坑：note **就该提到**不要写的通道名，
                # 所以不能对整份小节做子串否定——那会把正确的说明判成违规）：
                #   ① 调用面（init / prereq / read）不许出现 YELLOW / GREEN；
                #   ② note 里要把"越界通道被钳回 0"这条平台事实说清楚。
                calls = " ".join(
                    [*mspm0_led["init"], *mspm0_led["prereq"],
                     *(r["expression"] for r in mspm0_led["read"])]
                )
                notes = " ".join(mspm0_led["note"])
                verdicts.append((
                    "①d mspm0 的 led 只测通道 0（越界通道被钳回 0，配方不照搬三色宏）",
                    "LED_YELLOW" not in calls and "LED_GREEN" not in calls
                    and "LED_RED" in calls
                    and ("钳" in notes or "通道 0" in notes),
                    f"init={mspm0_led['init']}",
                ))
                verdicts.append((
                    "①e mspm0 的 oled note 写明要配 I2C1 实例 + 无浮点显示接口",
                    all(any(k in n for n in body["sections"][1]["note"])
                        for k in ("I2C1", "浮点显示接口")),
                    "；".join(body["sections"][1]["note"])[:200],
                ))

        # ② 真生成：落盘 main.c 与载荷逐字节一致 + 逐件小节真在盘上
        parent = root / "out"
        parent.mkdir()
        generated = client.post(
            "/api/hwcheck/generate",
            json={"platform": "stm32", "debug_uart": True, "oled": False,
                  "devices": ["led"], "parent_dir": str(parent)},
        )
        lines.append(f"## ② POST /api/hwcheck/generate（stm32 + led）→ {generated.status_code}")
        gen = generated.json()
        project = Path(gen["output_dir"])
        on_disk = (project / "main.c").read_text(encoding="utf-8")
        lines.append(f"落盘工程：{project.name}（main.c {len(on_disk)} 字节）")
        lines.append("")
        verdicts.append((
            "②a 落盘 main.c 逐字节等于端点回的 main_c",
            on_disk == gen["main_c"],
            f"{len(on_disk)} vs {len(gen['main_c'])} 字节",
        ))
        verdicts.append((
            "②b main.c 里 [专精] 小节的函数本体与调用都在（渲染了也真被跑）",
            "static void hwcheck_check_led(void)" in on_disk
            and "hwcheck_check_led();" in on_disk
            and "[专精] led" in on_disk,
            "函数本体 + main() 调用 + 标题标记",
        ))
        verdicts.append((
            "②c 未选中的器件不出小节（oled 没选 → 盘上查无此节）",
            "hwcheck_check_oled" not in on_disk,
            "hwcheck_check_oled 无命中",
        ))
        verdicts.append((
            "②d 分账运行时在（led 没有可判项 → 只渲「通过 / 未判定」两档；"
            "「失败」档与 hwcheck_verdict 按需渲染，不留死代码）",
            "hwcheck_summary_probe_none++;" in on_disk
            and "hwcheck_summary_ok++;" not in on_disk   # 通过档在汇总里，无判定则不加
            and "hwcheck_summary_fail" not in on_disk
            and "hwcheck_verdict(" not in on_disk
            and "hwcheck_verdict_probe_none(" in on_disk,
            "未判定计数 + 无判定函数（真机编译矩阵实测的 #177-D 死代码）",
        ))

        # ③ 门禁独立复核：把生成语料重建出来跑 _check_main_calls
        by_slug = {m.slug: m for m in list_modules(LIBRARY)}
        config = HwCheckConfig(
            platform="stm32", debug_uart=True, oled=False, devices=("led",)
        )
        manifests = resolve_dependencies(list(hwcheck_modules(config)), by_slug)
        from contest_generator.hwcheck_recipe import resolve_sections

        recipes = load_recipes(
            LIBRARY, list(by_slug.values()),
            _interfaces_for("stm32", list(by_slug.values())),
        )
        sections = resolve_sections("stm32", ("led",), recipes, manifests)
        main_c = render_main_c(config, sections)
        corpus = build_module_corpus(
            manifests, "stm32", LIBRARY, master_project_dir(MASTERS, "stm32"), main_c
        )
        try:
            _check_main_calls(corpus)
            gate_ok, gate_note = True, "门禁通过（led_init / LED_RED 都在语料里）"
        except Exception as exc:  # noqa: BLE001 —— 证据脚本要的是结论，不是栈
            gate_ok, gate_note = False, f"{type(exc).__name__}: {exc}"
        lines.append("## ③ 生成门禁独立复核（_check_main_calls 吃真语料）")
        lines.append(f"  {gate_note}")
        lines.append("")
        verdicts.append((
            "③ 配方引用的接口全在生成语料的接口清单里（门禁独立复核，不是自家判据）",
            gate_ok,
            gate_note[:160],
        ))

        # ④ 两种"测不了"分道：sr04 在 stm32 没条目（wiring.missing 点名）/
        #    mspm0 上没有配方的件（unspecialized 点名）——两条都不许静默消失
        body = client.post(
            "/api/hwcheck/preview",
            json={"platform": "stm32", "debug_uart": False, "oled": False,
                  "devices": ["led", "sr04"]},
        ).json()
        lines.append("## ④ 未专精件点名（stm32 + led + sr04）")
        lines.append(f"  sections = {[s['slug'] for s in body['sections']]}")
        lines.append(f"  unspecialized = {body['unspecialized']}")
        lines.append(f"  wiring.missing = {body['wiring']['missing']}")
        lines.append("")
        verdicts.append((
            "④a 本平台没有条目的 sr04 走 wiring.missing 点名「无本平台版本」",
            [m["slug"] for m in body["wiring"]["missing"]] == ["sr04"]
            and "无本平台版本" in body["wiring"]["missing"][0]["message"]
            and "无法检测" in body["wiring"]["missing"][0]["message"],
            body["wiring"]["missing"][0]["message"] if body["wiring"]["missing"] else "（空）",
        ))

        # mspm0 + ml_mpu6050：有平台条目、但本版还没有配方 → unspecialized 点名
        unspec = client.post(
            "/api/hwcheck/preview",
            json={"platform": "mspm0", "debug_uart": True, "oled": False,
                  "devices": ["led", "ml_mpu6050"]},
        ).json()
        lines.append("## ④b 未专精件点名（mspm0 + led + ml_mpu6050）")
        lines.append(f"  sections = {[s['slug'] for s in unspec['sections']]}")
        lines.append(f"  unspecialized = {unspec['unspecialized']}")
        lines.append("")
        verdicts.append((
            "④b 有平台条目但没配方的 ml_mpu6050 走 unspecialized 点名"
            "「不会给它出检测小节」（不静默消失）",
            [s["slug"] for s in unspec["sections"]] == ["led"]
            and [u["slug"] for u in unspec["unspecialized"]] == ["ml_mpu6050"]
            and "不会给它出检测小节" in unspec["unspecialized"][0]["message"],
            unspec["unspecialized"][0]["message"] if unspec["unspecialized"] else "（空）",
        ))

        # ⑤ 回读：sections 一起回来（刷新后检测计划不丢）
        back = client.get(
            "/api/hwcheck/project", params={"output_dir": str(project)}
        ).json()
        lines.append("## ⑤ GET /api/hwcheck/project（回读）")
        lines.append(f"  sections = {[s['slug'] for s in back['sections']]}")
        lines.append("")
        verdicts.append((
            "⑤ 回读拿回同一份逐件小节（刷新后页面上的检测计划不丢）",
            back["sections"] == gen["sections"] and bool(back["sections"]),
            f"{len(back['sections'])} 节",
        ))

        # ⑥ 红证：把配方里的函数名改坏 → 产品端点必须 400 并点名
        recipe_path = recipe_library_path(LIBRARY)
        original = recipe_path.read_bytes()
        lines.append("## ⑥ 红证：故意把 led 配方的函数名写错")
        try:
            mutated = original.decode("utf-8").replace(
                "led_init(LED_RED)", "led_initX(LED_RED)", 1
            )
            recipe_path.write_text(mutated, encoding="utf-8")
            broken = client.post(
                "/api/hwcheck/preview",
                json={"platform": "stm32", "debug_uart": True, "oled": False,
                      "devices": ["led"]},
            )
            detail = str(broken.json().get("detail", ""))
            lines.append(f"  注入后返回：{broken.status_code} {detail[:200]}")
            verdicts.append((
                "⑥ 配方写错函数名 → 构建期 400 + 点名（不学骨架兜底改成注释）",
                broken.status_code == 400
                and "led_initX" in detail
                and "led" in detail,
                f"{broken.status_code} / {detail[:120]}",
            ))
        finally:
            recipe_path.write_bytes(original)
            restored = recipe_path.read_bytes() == original
            lines.append(f"  配方文件已复原：{restored}")
            verdicts.append((
                "⑥b 探针逐字节复原配方文件",
                restored,
                f"{len(original)} 字节",
            ))
        lines.append("")

        # ⑦ 没配母版库时的降级：检测页照常可用（配方校验判不了就不判）
        masters = MASTERS
        hidden = masters.with_name("masters-verify04-hidden")
        lines.append("## ⑦ 母版库缺失时的降级（配方校验判不了就不判）")
        try:
            masters.rename(hidden)
            degraded = client.post(
                "/api/hwcheck/preview",
                json={"platform": "stm32", "debug_uart": True, "oled": False,
                      "devices": ["led"]},
            )
            deg_body = degraded.json()
            lines.append(f"  母版库不存在 → {degraded.status_code} "
                         f"sections={[s['slug'] for s in deg_body.get('sections', [])]}")
            verdicts.append((
                "⑦ 母版库目录不存在时预览仍可用（不 500，配方校验宽免空接口清单）",
                degraded.status_code == 200
                and [s["slug"] for s in deg_body["sections"]] == ["led"],
                f"{degraded.status_code} / sections="
                f"{[s['slug'] for s in deg_body.get('sections', [])]}",
            ))
        finally:
            if masters.exists():
                masters.rmdir()
            hidden.rename(masters)
            verdicts.append((
                "⑦b 母版库目录已复原",
                masters.is_dir() and not hidden.exists(),
                f"{masters.name} 复位",
            ))
        lines.append("")

        # ⑧ **真编译**：专精产物的 stm32 侧（spec「stm32 UV4 编译绿」的硬判据）。
        # 工单 03 的证据链只编过"未选器件"的形态，本单新增的逐件小节必须自己编
        # 一次——评审就是在这一步抓到"中文字面量让 ARMCC 报 22 个 error"的。
        uv4 = find_uv4()
        lines.append("## ⑧ UV4 真编译（专精产物，中文字面量转义之后）")
        lines.append(f"  UV4 = {uv4}")
        if uv4 is None:
            lines.append("  未探测到 UV4：本机没有 Keil——如实标红，不假装编过")
            verdicts.append((
                "⑧ stm32 专精产物编译绿（UV4）",
                False,
                "本机没有 UV4：这条判据本机跑不了（如实标红）",
            ))
        else:
            for compile_devices in (("led",), ("oled",), ("led", "oled")):
                compiled = client.post(
                    "/api/hwcheck/generate",
                    json={"platform": "stm32", "debug_uart": True, "oled": False,
                          "devices": list(compile_devices),
                          "parent_dir": str(parent)},
                ).json()
                collector = _CompileCollector()
                run_compile("stm32", Path(compiled["output_dir"]), uv4=uv4,
                            make=None, emit=collector)
                done = collector.done_payload or {}
                summary = done.get("summary") or {}
                lines.append(
                    f"  {compile_devices} → passed={done.get('passed')} "
                    f"error={summary.get('errors')} warning={summary.get('warnings')}"
                )
                verdicts.append((
                    f"⑧ stm32 专精产物编译绿（UV4，devices={list(compile_devices)}）",
                    bool(done.get("passed")) and not summary.get("errors"),
                    f"passed={done.get('passed')} error={summary.get('errors')} "
                    f"warning={summary.get('warnings')}",
                ))
        lines.append("")

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


def _interfaces_for(platform: str, manifests):
    """该平台的接口清单（模块头 ∪ 母版头）——与 webapp 装配点同一个函数。"""
    from contest_generator.hwcheck_recipe import interface_names

    master_dir = master_project_dir(MASTERS, platform)
    headers = [
        (path.relative_to(master_dir).as_posix(),
         path.read_text(encoding="utf-8", errors="replace"))
        for path in iter_project_files(master_dir, pattern="*.h")
    ]
    return interface_names(manifests, LIBRARY, platform, headers)


class _CompileCollector(SseEmitter):
    """编译执行体的 emit 缝：只收 done 载荷（passed / summary / parsed_errors）。

    ⚠ 载荷存 `self.done_payload` 而**不是** `self.done`：`done` 是 SseEmitter 的
    方法名，同名实例属性会把它遮掉 → `emit.done(...)` 报
    `TypeError: 'NoneType' object is not callable`（本探针自己踩过）。
    """

    def __init__(self) -> None:
        self.done_payload: dict | None = None

    def progress(self, event) -> None:  # noqa: D102 - 收集器不关心进度
        return None

    def done(self, data: dict) -> None:  # type: ignore[override]
        self.done_payload = data

    def error(self, data: dict) -> None:  # noqa: D102
        self.done_payload = data

    def question(self, data: dict) -> None:  # noqa: D102
        return None


if __name__ == "__main__":
    raise SystemExit(main())
