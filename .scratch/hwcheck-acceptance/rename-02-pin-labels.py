# -*- coding: utf-8 -*-
"""工单 02 的改名器：母版撞名引脚符号 → `<实例名>_<原符号>`（幂等、可 dry-run）。

**为什么是"全部 14 组"而不是只改 OLED 那两个符号名**（裁决依据见票面 Comments）：

* `probe-02-combos.py` 实测 12 格组合里 **10 格撞在墙上**——不止
  `OLED × 传感器`，还有 `aht10 × bh1750`（环境站标配）、`oled × lcd`、
  `led_beep × gp2y1014au`、`rc522 × nrf24l01`、`hx711 × rc522` ……
  只改 OLED 两个符号名，这 9 格照旧是死的；
* SysConfig 的判据是 `$name` **全局唯一**，所以"每组留一件裸名"救不了
  `SCL`/`SDA`（18 个实例里只能留 1 个裸名）——要真正放开只能让**每个**
  撞名实例的符号带自己的前缀；
* 全部改完，母版才满足"引脚符号全局唯一"这条**单一不变量**，守卫才写得成
  `name_count == 0`（spec 用户故事 7：「新加实例时撞名当场红」）。

改名会改掉生成的宏名（SysConfig 命名 `<实例>_<符号>_<后缀>`），所以同批改三处：

1. `library/masters/mspm0/mspm0.syscfg` 的 `associatedPins[n].$name` 值；
2. **mspm0 平台文件清单**（manifest `platforms.mspm0.files`，单源）里的宏引用；
3. mspm0 的 manifest `notes` 里提到的宏名（只动 mspm0 段，stm32 段一个字不碰）。

stm32 侧**零改动**（有断言：跑完复核 stm32 文件清单的 sha256 逐字节不变）。
测试侧的期望值不在这里改——由套件点名后逐个处理（判据是既有测试）。

用法：
    python .scratch/hwcheck-acceptance/rename-02-pin-labels.py            # dry-run
    python .scratch/hwcheck-acceptance/rename-02-pin-labels.py --write    # 落盘
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.manifest import ModuleManifest  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.syscfg_instances import INSTANCE_CONSUMERS  # noqa: E402
from contest_generator.syscfg_model import parse_syscfg  # noqa: E402

MASTER = REPO / "library" / "masters" / "mspm0" / "mspm0.syscfg"
MODULES = REPO / "library" / "modules"

# 宏引用：`<实例>_<符号>` 后面必须紧跟 mspm0 侧后缀（stm32 的 `_GPIO` 不吃）
SUFFIX = r"(?=_PORT\b|_PIN\b|_IOMUX\b)"


def rename_plan() -> dict[str, dict[str, str]]:
    """工作树母版的改名计划。"""
    return _plan_from_text(MASTER.read_text(encoding="utf-8"))


def _plan_from_text(text: str) -> dict[str, dict[str, str]]:
    """母版文本 → `实例 → {旧符号: 新符号}`，只收进重名组里的实例。"""
    model = parse_syscfg(text)
    by_name: dict[str, list[str]] = {}
    for instance, names in model.pin_names.items():
        for name in names:
            by_name.setdefault(name, []).append(instance)
    plan: dict[str, dict[str, str]] = {}
    for name, instances in by_name.items():
        if len(instances) < 2:
            continue
        for instance in instances:
            plan.setdefault(instance, {})[name] = f"{instance}_{name}"
    return plan


def token_pattern(instance: str, old: str) -> re.Pattern[str]:
    return re.compile(r"(?<![0-9A-Za-z_])" + re.escape(f"{instance}_{old}") + SUFFIX)


def read_source(path: Path) -> tuple[str, str]:
    """读源码：UTF-8 优先，退回 GBK（个别模块源码是 GBK——如实带回编码，
    写回时按同一编码落盘，不做转码）。"""
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("gbk"), "gbk"


def rewrite_text(text: str, plan: dict[str, dict[str, str]]) -> tuple[str, int]:
    hits = 0
    for instance, renames in plan.items():
        for old, new in renames.items():
            new_text, count = token_pattern(instance, old).subn(
                f"{instance}_{new}", text
            )
            text = new_text
            hits += count
    return text, hits


LABEL_LINE = re.compile(
    r'^(?P<head>\s*(?P<inst>[A-Za-z_]\w*)\.associatedPins\[\d+\]\.\$name\s*=\s*)"'
    r'(?P<name>[^"]+)"'
)


def rewrite_label_lines(text: str, plan: dict[str, dict[str, str]]) -> tuple[str, int]:
    """只改 `$name` 赋值行（母版那一行的逐字副本——测试里也照抄了它）。

    ⚠ 与 `rewrite_text`（宏引用 token 趟）**分开**：stm32 侧 `pin_config.h` 的
    `QMC5883L_SCL_PIN` 这类宏与 SysConfig 生成宏同名不同源，token 趟在测试文件里
    会把它们一起改掉（本轮踩过：117 条假红）。测试文件只吃这一趟。
    """
    out: list[str] = []
    changed = 0
    for line in text.splitlines(keepends=True):
        match = LABEL_LINE.match(line)
        if match is not None:
            inst, name = match.group("inst"), match.group("name")
            new = plan.get(inst, {}).get(name)
            if new is not None:
                line = f'{match.group("head")}"{new}"' + line[match.end():]
                changed += 1
        out.append(line)
    return "".join(out), changed


LABEL_EXPECT = re.compile(
    r'(?P<head>(?P<inst>[A-Za-z_]\w*)\.associatedPins\[\d+\]\.\$name\s*=\s*)"'
    r'(?P<name>[^"]+)"'
)


def rewrite_label_expectations(
    text: str, plan: dict[str, dict[str, str]]
) -> tuple[str, int]:
    """测试里的期望行：断言语句把母版那一行**整行抄进了字符串**，
    所以按"行内出现"匹配（`assert '...' in syscfg` 这种前缀挡不住）。"""

    def sub(match: re.Match[str]) -> str:
        new = plan.get(match.group("inst"), {}).get(match.group("name"))
        if new is None:
            return match.group(0)
        return f'{match.group("head")}"{new}"'

    return LABEL_EXPECT.subn(sub, text)


def rewrite_master(text: str, plan: dict[str, dict[str, str]]) -> tuple[str, int]:
    """母版：先改 `$name` 的值，再扫剩下的宏引用（注释里那种）。"""
    text, changed = rewrite_label_lines(text, plan)
    text, extra = rewrite_text(text, plan)
    return text, changed + extra


def mspm0_notes_span(raw: str) -> tuple[int, int] | None:
    """母版式 JSON 文本里 `"mspm0": {` 那一段的字符区间（花括号配对）。"""
    match = re.search(r'^\s*"mspm0"\s*:\s*\{', raw, re.MULTILINE)
    if match is None:
        return None
    start = raw.index("{", match.start())
    depth = 0
    for index in range(start, len(raw)):
        if raw[index] == "{":
            depth += 1
        elif raw[index] == "}":
            depth -= 1
            if depth == 0:
                return start, index + 1
    return None


def rename_plan_from_rev(rev: str) -> dict[str, dict[str, str]]:
    """从某个 git 版本里的母版算改名计划（工作树已经改过时仍可复算）。"""
    import subprocess

    text = subprocess.run(
        ["git", "show", f"{rev}:library/masters/mspm0/mspm0.syscfg"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    return _plan_from_text(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="真的落盘（缺省 dry-run）")
    parser.add_argument(
        "--tests-only",
        action="store_true",
        help="只改 tests/**/*.py 里那些**逐字抄自母版**的 `$name` 期望行"
        "（计划按 --base-rev 的母版复算——工作树已改过也能跑）",
    )
    parser.add_argument("--base-rev", default="HEAD", help="复算计划的基线版本")
    args = parser.parse_args()

    if args.tests_only:
        plan = rename_plan_from_rev(args.base_rev)
        total = 0
        for path in sorted((REPO / "tests").rglob("*.py")):
            text = path.read_text(encoding="utf-8", newline="")
            new_text, hits = rewrite_label_expectations(text, plan)
            if hits:
                total += hits
                print(f"  {path.relative_to(REPO).as_posix()}：{hits} 处")
                if args.write:
                    path.write_text(new_text, encoding="utf-8", newline="")
        print(f"合计 {total} 处" + ("" if args.write else "（dry-run）"))
        return 0

    plan = rename_plan()
    total_labels = sum(len(v) for v in plan.values())
    print(f"改名计划：{len(plan)} 个实例 / {total_labels} 个引脚符号")

    # stm32 侧指纹（跑完复核）
    stm32_files: list[Path] = []
    for slug_dir in sorted(MODULES.iterdir()):
        if not (slug_dir / "manifest.json").is_file():
            continue
        manifest = ModuleManifest.load(slug_dir)
        entry = manifest.platforms.get(PLATFORM_STM32)
        if entry is not None:
            stm32_files.extend(slug_dir / name for name in entry.files)

    def fingerprint(paths: list[Path]) -> dict[str, str]:
        return {
            p.relative_to(REPO).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths
            if p.is_file()
        }

    stm32_before = fingerprint(stm32_files)

    edits: list[tuple[Path, str, str]] = []
    non_utf8: list[str] = []

    master_text, master_hits = rewrite_master(
        MASTER.read_text(encoding="utf-8", newline=""), plan
    )
    edits.append((MASTER, master_text, "utf-8"))
    print(f"  {MASTER.relative_to(REPO).as_posix()}：{master_hits} 处")

    # mspm0 源文件 + manifest（notes 只动 mspm0 段）
    for slug, renames_instances in sorted(plan.items()):
        slugs = INSTANCE_CONSUMERS.get(slug, ())
        for module in slugs:
            module_dir = MODULES / module
            manifest_path = module_dir / "manifest.json"
            manifest = ModuleManifest.load(module_dir)
            entry = manifest.platforms.get(PLATFORM_MSPM0)
            files = [module_dir / name for name in entry.files] if entry else []
            for path in files:
                if not path.is_file():
                    continue
                text, encoding = read_source(path)
                if encoding != "utf-8":
                    non_utf8.append(f"{path.relative_to(REPO).as_posix()}（{encoding}）")
                text, hits = rewrite_text(text, plan)
                if hits:
                    edits.append((path, text, encoding))
                    print(f"  {path.relative_to(REPO).as_posix()}：{hits} 处")
            # manifest notes（mspm0 段）
            raw = manifest_path.read_text(encoding="utf-8", newline="")
            span = mspm0_notes_span(raw)
            if span is None:
                continue
            head, body, tail = raw[: span[0]], raw[span[0] : span[1]], raw[span[1] :]
            body2, hits = rewrite_text(body, plan)
            if hits:
                edits.append((manifest_path, head + body2 + tail, "utf-8"))
                print(f"  {manifest_path.relative_to(REPO).as_posix()}（mspm0 段）：{hits} 处")

    if non_utf8:
        print("\n非 UTF-8 源码（按原编码写回，不转码）：")
        for rel in non_utf8:
            print("  · " + rel)

    # 去重（同一文件可能被多个实例命中）
    merged: dict[Path, tuple[str, str]] = {}
    for path, text, encoding in edits:
        merged[path] = (text, encoding)
    print(f"合计待写文件：{len(merged)} 个")

    if not args.write:
        print("\n（dry-run：没有落盘。加 --write 才写。）")
        return 0

    for path, (text, encoding) in merged.items():
        path.write_bytes(text.encode(encoding))

    stm32_after = fingerprint(stm32_files)
    changed = [
        rel for rel in stm32_before if stm32_before[rel] != stm32_after.get(rel)
    ]
    print(f"\nstm32 侧复核：{len(stm32_before)} 个文件，变了 {len(changed)} 个")
    for rel in changed:
        print("  ✗ " + rel)
    return 0 if not changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
