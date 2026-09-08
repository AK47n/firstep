# -*- coding: utf-8 -*-
import json
for s in ['motor', 'servo', 'huidu', 'xunji']:
    m = json.load(open('library/modules/%s/manifest.json' % s, encoding='utf-8'))
    e = m['platforms']['mspm0']
    print('==', s)
    print('   kit=%r' % e.get('kit'))
    print('   source_url=%r' % e.get('source_url'))
    # 定位 kit 行在文件流中的外观
    txt = open('library/modules/%s/manifest.json' % s, encoding='utf-8').read()
    import re
    for mm in re.finditer(r'"[^"\n]*kit[^"\n]*"[ \t]*:[ \t]*"[^"\n]*"', txt):
        print('   行:', repr(mm.group(0)[:120]))
    for mm in re.finditer(r'"[^"\n]*source_url[^"\n]*"[ \t]*:[ \t]*"[^"\n]*"', txt):
        print('   行:', repr(mm.group(0)[:120]))
