import urllib.request, re, sys

url = sys.argv[1]
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) firstep-review'})
raw = urllib.request.urlopen(req, timeout=25).read()
s = raw.decode('utf-8', 'replace')
m = re.search(r'<main[^>]*>([\s\S]*?)</main>', s)
main = m.group(1) if m else ''

lns = [mm.start() for mm in re.finditer(r'class="line-number"', main)]
print('line-number span count:', len(lns))
# 找这些 span 的容器
for off in lns[:3]:
    seg = main[max(0, off - 400):off]
    opens = re.findall(r'<div class="([^"]*)"', seg)
    print('  preceding divs:', opens[-3:])
# 数字列内容
snip = main[lns[0] - 200:lns[0] + 600] if lns else ''
print('snip:', repr(snip[:400]))
