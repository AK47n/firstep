# -*- coding: utf-8 -*-
import io
import re

files = ['sensor--mq-7-sensor.md', 'sensor--mq-8-sensor.md']
base = r'sources/materials/lckfb-地猛星移植手册'
for f in files:
    t = io.open(base + '/' + f, encoding='utf-8').read()
    print('=' * 16, f)
    for line in t.splitlines():
        if line.startswith('# '):
            print('TITLE:', line)
    for m in re.finditer(r'printf\("(.*?)"', t):
        print('  printf:', m.group(1))
    for line in t.splitlines()[:9]:
        print('  |', line[:110])
