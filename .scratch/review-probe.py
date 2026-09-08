import urllib.request, re, sys

url = sys.argv[1]
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) firstep-review'})
raw = urllib.request.urlopen(req, timeout=25).read()
s = raw.decode('utf-8', 'replace')
m = re.search(r'<main[^>]*>([\s\S]*?)</main>', s)
main = m.group(1) if m else ''
print('page len', len(s), 'main len', len(main))
pres = re.findall(r'<pre[^>]*>([\s\S]*?)</pre>', main)
print('pre blocks in main:', len(pres))
for i, p in enumerate(pres):
    nlines = len(re.findall(r'<span class="line">', p))
    print('  pre%d: span.line=%d' % (i, nlines))
wrappers = re.findall(r'<div class="line-numbers-wrapper">([\s\S]*?)</div>', main)
print('line-numbers-wrappers:', len(wrappers), [w.count('line-number') for w in wrappers])
print('warning custom-block count:', main.count('custom-block'))
cbs = re.findall(r'<div class="([^"]*custom-block[^"]*)"[^>]*>([\s\S]*?)</div>', main)
for cls, body in cbs:
    t = re.search(r'<p class="custom-block-title[^"]*">([\s\S]*?)</p>', body)
    print('  custom-block cls=%r title=%r body_len=%d' % (cls, t.group(1) if t else '', len(body)))
# ol 分布
ols = re.findall(r'<ol start="(\d+)">', main)
print('ol starts:', ols)
