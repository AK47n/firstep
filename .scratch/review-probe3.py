import urllib.request, re, sys

url = sys.argv[1]
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) firstep-review'})
raw = urllib.request.urlopen(req, timeout=25).read()
s = raw.decode('utf-8', 'replace')
m = re.search(r'<main[^>]*>([\s\S]*?)</main>', s)
main = m.group(1) if m else ''

pres = []
for mm in re.finditer(r'<pre[^>]*>([\s\S]*?)</pre>', main):
    pres.append(len(re.findall(r'<span class="line">', mm.group(1))))
print('span.line per pre:', pres)

wraps = []
for mm in re.finditer(r'<div class="line-numbers-wrapper"[^>]*>([\s\S]*?)</div>', main):
    wraps.append(mm.group(1).count('span class="line-number"'))
print('line-number per wrapper:', wraps)
