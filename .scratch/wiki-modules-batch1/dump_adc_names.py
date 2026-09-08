# -*- coding: utf-8 -*-
import json
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

t = open(r"C:\ti\ccs2051\sysconfig_1.26.2\dist\deviceData\MSPM0G350x\MSPM0G350X.json", encoding="utf-8").read()
names = sorted(set(re.findall(r'"([A-Za-z0-9_.]*(?:ADC0|ADC12|A0_)[A-Za-z0-9_.]*)"', t)))
for n in names:
    print(n)
