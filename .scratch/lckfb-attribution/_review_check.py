from pathlib import Path
import json

LIB = Path("library/modules")
extra = []
for p in sorted(LIB.glob("*/manifest.json")):
    m = json.loads(p.read_text(encoding="utf-8"))
    listed = set()
    wiki = False
    for v in m.get("platforms", {}).values():
        if (v.get("source_url", "") or "").startswith("https://wiki.lckfb.com/"):
            wiki = True
        listed.update(v.get("files", []))
    if not wiki:
        continue
    ondisk = set()
    for f in (p.parent / "code").rglob("*"):
        if f.is_file() and f.suffix in (".c", ".h"):
            ondisk.add(str(f.relative_to(p.parent)).replace("\\", "/"))
    for x in sorted(ondisk - listed):
        extra.append(f"{m['slug']}: {x}")
print("wiki module .c/.h on disk but not in any platform entry files:", len(extra))
for e in extra:
    print(e)

# md count at HEAD and parent
import subprocess

for ref in ["HEAD", "91c1df86ef4bcc88ba80a49cf7ca1ba430ea3786"]:
    out = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, "--", "sources/materials/"],
        capture_output=True, text=True, encoding="utf-8",
    )
    names = [n for n in out.stdout.splitlines() if n.endswith(".md")]
    print(ref, "md files under sources/materials:", len(names))
