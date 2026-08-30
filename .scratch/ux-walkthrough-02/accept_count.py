# 验收辅助：统计每个工单的验收框勾选状态（UTF-8 直读，避免控制台编码噪音）
import re, glob, os

for p in sorted(glob.glob(r".scratch/ux-walkthrough-02/issues/*.md")):
    t = open(p, encoding="utf-8").read()
    c = len(re.findall(r"(?m)^- \[x\]", t))
    u = len(re.findall(r"(?m)^- \[ \]", t))
    st = re.search(r"(?m)^\*\*状态[:：]\*\*\s*(\S+)", t)
    name = os.path.basename(p)
    print(f"{name}: checked={c} unchecked={u} status={st.group(1) if st else '?'}")
