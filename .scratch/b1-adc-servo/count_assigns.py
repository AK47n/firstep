import re
from collections import Counter

t = open("library/masters/mspm0/mspm0.syscfg", encoding="utf-8").read()
vals = [m.group(1) for m in re.finditer(r'^\s*.+?\.\$assign\s*=\s*"([A-Za-z0-9]+)"', t, re.M)]
print({k: c for k, c in Counter(vals).items() if c != 1})
