# -*- coding: utf-8 -*-
"""量具：v1.2.2 小发版清单 vs v1.2.1 小发版清单 + v1.2.1 完整包清单（只读）。

要回答三个问题（工单 release-v1.2.2/04）：

1. **少了什么**：v1.2.1 小发版发过、v1.2.2 不发的路径，按顶层目录归类——
   应该是「本机库备份 + egg-info」这类**故意不发**的东西，不能有产品文件；
2. **多了什么**：v1.2.2 新发的路径（真实新增文件 / 新登记进 git 的）；
3. **egg-info 与 revise-backups 在不在删除清单里**（累计口径要能清掉用户盘上那批）。

用量具而不是眼估：1481 这个数字对不上就要当场看见。
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PACK = Path.home() / "Desktop" / "firstep-pack"


def read_list(name: str) -> list[str]:
    path = PACK / name
    text = path.read_bytes().decode("utf-8-sig")
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def by_top(paths: list[str]) -> Counter:
    return Counter(
        p.split("/")[0] + "/" + (p.split("/")[1] if p.count("/") >= 1 else "")
        for p in paths
    )


def main() -> int:
    new_files = set(read_list("firstep-update-v1.2.2.files.txt"))
    new_removed = set(read_list("firstep-update-v1.2.2.removed.txt"))
    old_update = set(read_list("firstep-update-v1.2.1.files.txt"))
    old_full = json.loads((PACK / "firstep-full-v1.2.1.manifest.json")
                          .read_bytes().decode("utf-8-sig"))
    old_full_files = {str(item["path"]) for item in old_full.get("files") or []}

    print("## 数量")
    print(f"  v1.2.2 小发版产品文件：{len(new_files)}")
    print(f"  v1.2.1 小发版产品文件：{len(old_update)}")
    print(f"  v1.2.1 完整包产品文件：{len(old_full_files)}")
    print(f"  v1.2.2 删除清单：{len(new_removed)}")
    print(f"  差（本版 − 上版小发版）：{len(new_files) - len(old_update)}")

    dropped = sorted(old_update - new_files)
    added = sorted(new_files - old_update)
    print(f"\n## 不再发的（v1.2.1 小发版有、本版没有）：{len(dropped)}")
    for top, count in by_top(dropped).most_common(10):
        print(f"  {count:6d}  {top}")
    print("  样例（前 5）：")
    for path in dropped[:5]:
        print(f"    - {path}")

    print(f"\n## 新增发的（本版有、v1.2.1 小发版没有）：{len(added)}")
    for top, count in by_top(added).most_common(10):
        print(f"  {count:6d}  {top}")
    print("  样例（前 5）：")
    for path in added[:5]:
        print(f"    - {path}")

    print("\n## 关键路径在删除清单里吗（累计口径要清得掉用户盘上那批）")
    egg = sorted(p for p in new_removed if "egg-info" in p)
    rb = sorted(p for p in new_removed if p.startswith("library/revise-backups/"))
    print(f"  egg-info：{len(egg)} 条")
    for path in egg:
        print(f"    - {path}")
    print(f"  library/revise-backups/：{len(rb)} 条（样例前 3）")
    for path in rb[:3]:
        print(f"    - {path}")

    print("\n## 判据")
    ok = True
    # ① 不再发的必须全是「**本来就该排除**」的类别（判据用产品文件判据单源本身，
    #    不手写类别名单）：库备份目录 / 安装包通配（*.exe 这类）/ egg-info。
    #    写窄了会误报——v1.2.1 的 spec 更正③就记过：`sources/contest/**` 下那个
    #    `UartAssist.exe` 是**安装包通配正确排除**的，不是「漏发」。
    from contest_generator import full_pack as fp  # noqa: PLC0415 —— 量具要吃产品判据

    offenders = [p for p in dropped if fp.is_product_file(p)]
    print(f"  ① 不再发的里面混进**产品文件**（判据 = full_pack.is_product_file）："
          f"{len(offenders)}{'  ✓' if not offenders else '  ✗'}")
    for path in offenders[:20]:
        print(f"      ✗ {path}")
    if not offenders:
        reasons = Counter(fp.product_file_reason(p) for p in dropped)
        for reason, count in reasons.most_common():
            print(f"      排除原因 {reason}：{count} 条")
    ok = ok and not offenders
    # ② 这两个类别必须在删除清单里（否则用户盘上清不掉）
    print(f"  ② egg-info 全在删除清单里：{'✓' if len(egg) == 6 else f'✗（{len(egg)} 条，期望 6）'}")
    print(f"  ③ 库备份在删除清单里：{'✓' if rb else '✗'}")
    ok = ok and len(egg) == 6 and bool(rb)
    # ④ 新增发的必须真在旧完整包里（不是凭空冒出来的路径）
    ghost = [p for p in added if p not in old_full_files]
    print(f"  ④ 新增发的都在 v1.2.1 完整包里：{'✓' if not ghost else f'✗（{len(ghost)} 条不在）'}")
    for path in ghost[:20]:
        print(f"      ✗ {path}")
    ok = ok and not ghost
    print(f"\n  总判：{'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
