# -*- coding: utf-8 -*-
"""工单 hwcheck-hardening/02 的落地脚本：给缺自述的 17 格补一条「**未上板**」平台说明。

为什么用脚本而不是手改 17 处：同一条文案要**逐字同源**地插到 17 个格子的 note 末条，
手改一定会漂；脚本还能顺带断言"锚点唯一""JSON 仍合法""插完 57/57 命中"。

纪律：逐字节读写（LF 保持），不重新序列化整个 JSON（那会把 22 万字节的手工排版重排一遍）。
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECIPE = ROOT / "library" / "hwcheck_recipes.json"

# 变体 A：本件在板上**真能打出 OK / FAIL**（探头带期望值）→ 口径同扩张批那 38 格
TAIL_A = (
    "**未上板**：本格的结论只到「编译矩阵绿 + 驱动实现的返回码判据」，"
    "真机上板验证还没做（与库内 manifest 的口径一致）。实测差异优先于本页参考值。"
)
# 变体 B：本件**不在板上打判定**（纯输出件 / 输入件 / 探头只回显现象）→ 中间那句如实换成静态核对
TAIL_B = (
    "**未上板**：本格的结论只到「编译矩阵绿 + 页面清单与探头调用的静态核对」"
    "（本件不在板上打 OK / FAIL），真机上板验证还没做（与库内 manifest 的口径一致）。"
    "实测差异优先于本页参考值。"
)


def main() -> int:
    original = RECIPE.read_bytes()
    text = original.decode("utf-8")
    data = json.loads(text)

    targets: list[tuple[str, str, str, str]] = []
    for slug, entry in data.items():
        if not isinstance(entry, dict):
            continue
        for platform, cell in entry.items():
            if not isinstance(cell, dict):
                continue
            notes = [str(n) for n in ((cell.get("note") or {}).get("lines") or [])]
            if not notes or "**未上板**" in notes[-1]:
                continue
            # 判据 = **探头带期望值**（`probe.expect`）：只有那样的格才真的在板上打 OK / FAIL。
            # 光有 `probe.calls` 的（oled / debug_uart / beep / xunji）是"跑一遍探头、判定交给你眼睛"，
            # 归到 B——xunji 的平台说明自己就写着「板上不打 OK / FAIL」。
            judged = bool((cell.get("probe") or {}).get("expect"))
            targets.append((slug, platform, notes[-1], TAIL_A if judged else TAIL_B))

    # 按文件里的出现顺序落地（同一段文本在别处重复时当场停手，不猜）
    targets.sort(key=lambda row: text.index(json.dumps(row[2], ensure_ascii=False)))
    print(f"待补格数 = {len(targets)}")
    for slug, platform, last, tail in targets:
        quoted = json.dumps(last, ensure_ascii=False)
        count = text.count(quoted)
        if count != 1:
            print(f"✗ 锚点不唯一（{count} 次）：{slug} × {platform} → {last[:40]}…")
            return 2
        indent = ""
        for line in text.splitlines():
            if quoted in line:
                indent = line[: len(line) - len(line.lstrip())]
                break
        text = text.replace(quoted, quoted + ",\n" + indent + json.dumps(tail, ensure_ascii=False), 1)
        print(f"  ✓ {slug} × {platform}（{'板上有 OK/FAIL' if tail is TAIL_A else '板上不打判定'}）")

    RECIPE.write_bytes(text.encode("utf-8"))

    # 复核：JSON 合法 + 57/57 命中 + 换行形态不变
    check = json.loads(RECIPE.read_bytes().decode("utf-8"))
    hit = total = 0
    for slug, entry in check.items():
        if not isinstance(entry, dict):
            continue
        for platform, cell in entry.items():
            if not isinstance(cell, dict):
                continue
            total += 1
            notes = [str(n) for n in ((cell.get("note") or {}).get("lines") or [])]
            if notes and "**未上板**" in notes[-1]:
                hit += 1
    after = RECIPE.read_bytes()
    print(f"\n复核：JSON 合法；{hit}/{total} 格的末条带「**未上板**」")
    print(f"换行 = {'CRLF' if b'\\r\\n' in after else 'LF'}，字节 {len(original)} → {len(after)}")
    return 0 if hit == total and total >= 57 else 1


if __name__ == "__main__":
    raise SystemExit(main())
