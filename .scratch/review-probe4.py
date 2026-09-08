import urllib.request, re, sys

url = sys.argv[1]
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) firstep-review'})
raw = urllib.request.urlopen(req, timeout=25).read()
s = raw.decode('utf-8', 'replace')
m = re.search(r'<main[^>]*>([\s\S]*?)</main>', s)
main = m.group(1) if m else ''

i = main.find('WARNING')
print('--- around WARNING ---')
print(main[i - 300:i + 1200].replace('\n', ' ')[:1500])
