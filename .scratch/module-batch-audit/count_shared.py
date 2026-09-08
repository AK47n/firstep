# -*- coding: utf-8 -*-
import json, os
mods = os.listdir('library/modules')
for plat in ['mspm0', 'stm32']:
    g = {}
    tot = 0
    for s in mods:
        p = 'library/modules/%s/manifest.json' % s
        if not os.path.isfile(p):
            continue
        m = json.load(open(p, encoding='utf-8'))
        e = m.get('platforms', {}).get(plat)
        if e is None:
            continue
        for pin in e.get('pins', []):
            g.setdefault(pin['default'], set()).add(s + '.' + pin['id'])
            tot += 1
    groups = {k: v for k, v in g.items() if len(v) > 1}
    n_roles = sum(len(v) for v in groups.values())
    print('%s: 角色总数=%d 默认脚去重=%d 共享脚组=%d 组内角色=%d' % (
        plat, tot, len(g), len(groups), n_roles))
