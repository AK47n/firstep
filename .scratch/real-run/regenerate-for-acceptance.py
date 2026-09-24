# -*- coding: utf-8 -*-
"""第十八轮真机验收 A4/A5/A7：按 HEAD 确定性重生成三份工程，再用产品编译器各跑一遍。

**为什么要重生成（不是多此一举）**：A4/A5/A7 要证的是「**当前代码**生成的工程能被
Keil5 / CCS 打开并编过」，而盘上三份产物是 2026-09-10/11 的旧树。此后 main 上
`library/masters/stm32/pin_config.h` 被 `hwcheck-unknown-device/01`（2026-09-22）
加了 10 行 `I2C_PROBE_*` 定义——母版会进生成工程，而旧树里零命中。也就是说：
**自那次母版改动以来，还没有人在 Keil 里编过一份 2026C 赛题工程**。拿旧树去点，
验的是三周前的代码。

**怎么重放**：读每份产物里的 `.contest_context.json`（产品自己的读侧
`context_manifest.read_context_fields`，不自己解析 JSON），把那组输入原样喂回
`generator.generate_project`。main.c 骨架是清单里的快照，直接复用——**不走 HTTP
端点 / 不调 LLM / 不依赖推荐缓存**，零额度、确定可重演。

**与产品路径的偏离（如实记账）**：
- 绕过 `/api/generate` 路由，故不经过「功能组必须显式选择」门禁、输出目录裁决、
  覆盖确认与备份——这些都是 HTTP 层关切，不改变产物内容。
- 原清单 `problem_text` 为空 → 产品路径本身也不会调设计报告草稿那一次 LLM。
- `tool_version` 写当前 `__version__`（旧清单里是生成当天的值，故清单文件必然记
  为「已变」，属预期）。
- 产物内容由同一个 `generate_project` 用同一组输入产出，故与产品路径一致。

**产物落新目录** `out_18_<tag>`（**不覆盖旧树**，旧树留作对照）；同时逐文件 sha256
对比旧树，把「到底变了什么」摊开。编译走产品自己的 `collect_build_log`
（stm32 = UV4 `-j0 -r -b`；mspm0 = gmake `-C Debug -f makefile -B`）。

用法：python .scratch/real-run/regenerate-for-acceptance.py [--no-compile] [--force]
（--force = 新树已存在时删掉重建；新树可确定性重建，删了不丢证据）
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator import __version__  # noqa: E402
from contest_generator.compile_runner import (  # noqa: E402
    collect_build_log,
    find_ccs_tools,
    find_make,
    find_uv4,
)
from contest_generator.context_manifest import read_context_fields  # noqa: E402
from contest_generator.fix_errors import (  # noqa: E402
    parse_compile_errors,
    summarize_compile_output,
)
from contest_generator.generator import generate_project  # noqa: E402

RUN = REPO / ".scratch" / "real-run"
EVIDENCE = RUN / "verify-18-A4A5A7-regenerate.txt"

# (新目录 tag, 旧树目录名, 服务哪张验收单)
TARGETS = (
    ("A4_stm32_2026C", "out_2026C_stm32", "A4（Keil5 里编译一次）"),
    ("A5_mspm0_2026H", "out_2026H_mspm0", "A5（CCS 里编译一次）"),
    ("A7_mspm0_min", "out_16_mspm0_min", "A7（CCS Theia GUI 编译复验）"),
)

# 预期必然变化的文件（不与「代码改动导致的差异」混在一起报）
EXPECTED_DIFF = {".contest_context.json"}

# 编译产物前缀：旧树编译过、新树生成时还没编译，逐文件列会淹没真差异——单列计数
BUILD_ARTIFACT_PREFIXES = ("user/Objects/", "user/Listings/", "Debug/")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root: Path) -> dict[str, str]:
    """目录 → {相对路径: sha256}（逐字节指纹）。"""
    return {
        p.relative_to(root).as_posix(): sha256(p)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def replay(tag: str, src_name: str, *, force: bool = False) -> tuple[str, Path]:
    """把旧树的记录输入重放一遍，生成本轮新树；返回 (platform, 新目录)。

    force=True 时删掉已存在的新树再生成（新树可确定性重建，删了不丢证据）；
    缺省 False = 已存在就停，不静默覆盖。
    """
    src = RUN / src_name
    out = RUN / f"out_18_{tag}"
    fields = read_context_fields(src)
    if fields is None:
        raise SystemExit(f"[{tag}] 旧树没有 .contest_context.json：{src}")
    if fields["instances"]:
        raise SystemExit(
            f"[{tag}] 清单带多实例，本脚本未实现该路（如实停，不猜）：{fields['instances']}"
        )
    if out.exists():
        if not force:
            raise SystemExit(f"[{tag}] 目标目录已存在，加 --force 重建（不静默覆盖）：{out}")
        shutil.rmtree(out)
        print(f"[{tag}] --force：已删旧新树 {out.name}（可确定性重建）")

    platform = fields["platform"]
    print(f"[{tag}] 重放 {src_name} → {out.name}")
    print(f"        platform={platform} / slugs={fields['slugs']}")
    print(f"        bindings={fields['bindings'] or '（无）'}  topic_id={fields['topic_id'] or '（无）'}")

    generate_project(
        platform=platform,
        slugs=fields["slugs"],
        main_c_content=fields["main_c"],
        output_dir=out,
        module_library_dir=REPO / "library" / "modules",
        masters_dir=REPO / "library" / "masters",
        ccs_tools=find_ccs_tools() if platform == "mspm0" else None,
        bindings=fields["bindings"] or None,
        instances=None,
        python_templates=fields["python_templates"] or None,
        problem_text=fields["problem_text"],
        topic_id=fields["topic_id"],
        qa_text=fields["qa_text"],
        requirements=fields["requirements"] or None,
        references=fields["references"],
        tool_version=__version__,
    )
    print(f"        已生成 {len(snapshot(out))} 个文件")
    return platform, out


def diff_trees(old: Path, new: Path) -> list[str]:
    """逐字节对比旧树 / 新树，返回可读的差异行。

    编译产物（旧树编译过、新树生成时还没）只报计数；真差异（源文件内容变了）
    逐条列出——那才是「重生成到底改变了什么」的答案。
    """
    a, b = snapshot(old), snapshot(new)

    def is_artifact(key: str) -> bool:
        return key.startswith(BUILD_ARTIFACT_PREFIXES)

    only_old = sorted(set(a) - set(b))
    only_new = sorted(set(b) - set(a))
    art_old = [k for k in only_old if is_artifact(k)]
    src_old = [k for k in only_old if not is_artifact(k)]
    art_new = [k for k in only_new if is_artifact(k)]
    src_new = [k for k in only_new if not is_artifact(k)]
    changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    expected = [k for k in changed if k in EXPECTED_DIFF]
    unexpected = [k for k in changed if k not in EXPECTED_DIFF]

    lines = [
        f"  文件数：旧 {len(a)} / 新 {len(b)}",
        f"  仅在旧树的编译产物 {len(art_old)} 个"
        f"（新树编译后会自己长出来，非差异）",
        f"  仅在旧树的源文件 {len(src_old)} 个：{src_old or '（无）'}",
        f"  仅在新树的源文件 {len(src_new)} 个：{src_new or '（无）'}",
        f"  仅在新树的编译产物 {len(art_new)} 个：{art_new or '（无）'}",
        f"  源文件内容已变 {len(unexpected)} 个：",
    ]
    for key in unexpected:
        lines.append(f"    - {key}")
    if not unexpected:
        lines.append("    （无——除清单外逐字节相同）")
    if expected:
        lines.append(f"  预期变化（清单时间戳/工具版本）{len(expected)} 个：{expected}")
    return lines


def compile_tree(tag: str, platform: str, out: Path) -> list[str]:
    """走产品自己的编译入口编译一遍，返回可读读数。"""
    build = collect_build_log(platform, out, uv4=find_uv4(), make=find_make())
    parsed = parse_compile_errors(build.run.output)
    summary = summarize_compile_output(build.run.output, parsed)
    ok = build.run.exit_code == 0 and summary["errors"] == 0 and summary["warnings"] == 0
    lines = [
        f"  编译入口：{build.project_file}",
        f"  命令：{' '.join(build.command)}",
        f"  exit={build.run.exit_code} 超时={build.run.timed_out} "
        f"错误={summary['errors']} 警告={summary['warnings']} "
        f"耗时={build.run.duration:.1f}s → {'PASS' if ok else 'FAIL'}",
    ]
    if not ok:
        tail = build.run.output.strip().splitlines()[-15:]
        lines.append("  编译输出尾部：")
        lines.extend(f"    {line}" for line in tail)
    print(f"[{tag}] " + lines[0].strip())
    print(f"[{tag}] " + lines[2].strip())
    return lines


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    do_compile = "--no-compile" not in sys.argv
    force = "--force" in sys.argv

    report: list[str] = [
        "# 第十八轮真机验收 A4/A5/A7：按 HEAD 重生成（确定性重放）+ 产品编译器预跑",
        "",
        f"生成器版本：{__version__}",
        "旧树 = 2026-09-10/11 的产物；新树 = 本次按 HEAD 重放。",
        "",
    ]
    failed = False
    for tag, src_name, purpose in TARGETS:
        old, new = RUN / src_name, RUN / f"out_18_{tag}"
        report.append(f"## {tag} — {purpose}")
        report.append(f"来源旧树：{src_name}")
        try:
            platform, out = replay(tag, src_name, force=force)
        except SystemExit as exc:
            print(f"[{tag}] 停：{exc}")
            failed = True
            report.append(f"  重放失败：{exc}")
            report.append("")
            continue
        report.append("逐一对比旧树：")
        report.extend(diff_trees(old, new))
        if do_compile:
            report.append("产品编译器预跑：")
            lines = compile_tree(tag, platform, out)
            report.extend(lines)
            if "FAIL" in lines[2]:
                failed = True
        report.append("")

    EVIDENCE.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\n证据已落盘：{EVIDENCE.relative_to(REPO)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
