"""真机验收注入脚本（工单 compile-experience-ui/01）：给输出目录 main.c 注入
一条必然报错的调用语句（未声明符号，Keil AC5 → error #20: identifier ...
is undefined，path(line) 形态可解析），供浏览器验收「编译失败横幅 → 结构化
错误列表 → 点击展开源码行 → AI 修复状态标签」。

用法（在会话输入框用 ! 前缀执行，输出会直接显示）：
  python .scratch/compile-experience-ui/inject_error.py <输出目录>           # 注入
  python .scratch/compile-experience-ui/inject_error.py <输出目录> --undo    # 还原

注入前把 main.c 原样备份为同目录 main.c.bak-ceui（--undo 恢复后删除）。
AI 修复会改写 main.c（fix-backups 另有回滚入口），--undo 恢复的是注入前
原版（本来就编译通过，恢复即干净）。
"""
import argparse
import re
import sys
from pathlib import Path

INJECT = "    zzz_undeclared_symbol_injected();  // compile-experience-ui 验收注入\n"
BACKUP_SUFFIX = ".bak-ceui"


def inject(main_c: Path) -> None:
    text = main_c.read_text(encoding="utf-8", errors="replace")
    if INJECT.strip() in text:
        sys.exit("main.c 已注入过（先 --undo 再重新注入）")
    backup = main_c.with_name(main_c.name + BACKUP_SUFFIX)
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    match = re.search(r"main\s*\([^)]*\)\s*\{", text)
    if match is None:
        sys.exit(f"main.c 里没找到 main() 函数体（{main_c}）——注入失败，请换完整工程")
    insert_at = match.end()
    line_no = text[:insert_at].count("\n") + 1
    main_c.write_text(text[:insert_at] + INJECT + text[insert_at:], encoding="utf-8")
    print(f"已注入错误行（main.c 第 {line_no} 行）：zzz_undeclared_symbol_injected();")
    print("回浏览器点「一键编译修复」→ 验收：红色失败横幅 / 错误列表（待修复）/ 点条目展开源码行 / AI 修复后状态标签")


def undo(main_c: Path) -> None:
    backup = main_c.with_name(main_c.name + BACKUP_SUFFIX)
    if not backup.exists():
        sys.exit("没有找到备份 main.c.bak-ceui（注入过吗？）")
    main_c.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
    backup.unlink()
    print("已还原 main.c（注入前内容，编译通过状态）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="编译体验验收：注入/还原错误行")
    parser.add_argument("output_dir")
    parser.add_argument("--undo", action="store_true", help="还原注入前 main.c")
    args = parser.parse_args()
    main_c = Path(args.output_dir) / "main.c"
    if not main_c.is_file():
        sys.exit(f"输出目录里没有 main.c：{main_c}")
    (undo if args.undo else inject)(main_c)
