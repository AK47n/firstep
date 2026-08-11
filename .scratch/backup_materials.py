# -*- coding: utf-8 -*-
"""全量备份 Desktop 素材到 sources/（大文件 >50M 列入 gitignore，工作区仍全量保真）。
用法: python .scratch/backup_materials.py
"""
import os
import shutil

REPO = r"C:\Users\luoji\Desktop\firstep"
SRCS = [
    (r"C:\Users\luoji\Desktop\2026H", r"sources\contest\2026H"),
    (r"C:\Users\luoji\Desktop\key", r"sources\contest\key"),
    (r"C:\Users\luoji\Desktop\key_dmx", r"sources\contest\key_dmx"),
    (r"C:\Users\luoji\Desktop\2026_04_地猛星电赛控制题配套资料", r"sources\materials\2026_04_地猛星电赛控制题配套资料"),
    (r"C:\Users\luoji\Desktop\2026_06_电赛视觉资料", r"sources\materials\2026_06_电赛视觉资料"),
    (r"C:\Users\luoji\Desktop\2026_07_电赛带练真题资料", r"sources\materials\2026_07_电赛带练真题资料"),
    (r"C:\Users\luoji\Desktop\k230资料", r"sources\materials\k230资料"),
    (r"C:\Users\luoji\Desktop\MSPM0_MOTOR(参考例程)", r"sources\materials\MSPM0_MOTOR参考例程"),
]
BIG_MB = 50

big_files = []  # (rel_to_sources, size_mb)
total_copied = 0
total_bytes = 0
skipped_existing = 0

for src, dest in SRCS:
    if not os.path.isdir(src):
        print(f"!! 源不存在: {src}")
        continue
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target_root = os.path.join(REPO, dest, rel) if rel != "." else os.path.join(REPO, dest)
        os.makedirs(target_root, exist_ok=True)
        for f in files:
            sp = os.path.join(root, f)
            tp = os.path.join(target_root, f)
            sz = os.path.getsize(sp)
            if os.path.exists(tp) and os.path.getsize(tp) == sz:
                skipped_existing += 1
                continue
            if sz > BIG_MB * 1024 * 1024:
                rel_sources = os.path.join(dest, rel, f).replace("\\", "/")
                big_files.append((rel_sources, round(sz / 1024 / 1024, 1)))
                print(f"  [BIG {round(sz/1024/1024)}MB] {rel_sources}")
            shutil.copy2(sp, tp)
            total_copied += 1
            total_bytes += sz

print(f"\n复制 {total_copied} 文件, {round(total_bytes/1024/1024)}MB, 跳过已存在 {skipped_existing}")

gitignore_path = os.path.join(REPO, "sources", ".gitignore")
existing = ""
if os.path.exists(gitignore_path):
    existing = open(gitignore_path, encoding="utf-8").read()
new_lines = []
for rel, mb in sorted(big_files):
    line = f"/{rel}"
    if line not in existing and line not in new_lines:
        new_lines.append(line)
with open(gitignore_path, "w", encoding="utf-8") as fh:
    fh.write(existing)
    if new_lines:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write("# 大文件（>50MB：安装包/固件/镜像，工作区全量保真、不进 git）\n")
        fh.write("\n".join(new_lines) + "\n")
print(f"\n.gitignore 追加 {len(new_lines)} 条大文件路径:")
for line in new_lines:
    print("  ", line)
