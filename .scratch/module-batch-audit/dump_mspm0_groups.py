# -*- coding: utf-8 -*-
"""dump mspm0 默认脚共享组快照（供 test_mspm0_default_layout.py 白名单常量）。"""
import json
import os

mods = os.listdir('library/modules')
roles = []  # (slug, id, type, default)
for s in mods:
    p = 'library/modules/%s/manifest.json' % s
    if not os.path.isfile(p):
        continue
    m = json.load(open(p, encoding='utf-8'))
    e = m.get('platforms', {}).get('mspm0')
    if e is None:
        continue
    for pin in e.get('pins', []):
        roles.append((s, pin['id'], pin.get('type', ''), pin['default']))

groups = {}
for s, rid, t, d in roles:
    groups.setdefault(d, set()).add('%s.%s' % (s, rid))
print('角色总数:', len(roles))
for pin in sorted(groups):
    grp = sorted(groups[pin])
    if len(grp) < 2:
        continue
    types = sorted({t for s, rid, t, d in roles if d == pin})
    print('--- %s  types=%s' % (pin, types))
    for r in grp:
        print('   %s' % r)
