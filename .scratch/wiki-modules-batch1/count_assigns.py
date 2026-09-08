import re
from collections import Counter

p = r"library/masters/mspm0/mspm0.syscfg"
text = open(p, encoding="utf-8").read()
vals = re.findall(r'^\s*.+\.\$assign\s*=\s*"([A-Za-z0-9]+)"', text, re.M)
print(dict(sorted(Counter(vals).items(), key=lambda kv: (-kv[1], kv[0]))))
