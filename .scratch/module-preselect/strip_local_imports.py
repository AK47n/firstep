import io

p = r'tests\test_selection.py'
src = io.open(p, encoding='utf-8').read()
lines = src.splitlines(keepends=True)
out = []
removed = 0
for line in lines:
    s = line.strip()
    if s.startswith('from contest_generator.selection import preselect_module_summaries') \
       or s.startswith('from contest_generator.budget import MIN_PRESELECT') \
       or s.startswith('from contest_generator.wordlist import load_wordlist'):
        removed += 1
        continue
    out.append(line)
io.open(p, 'w', encoding='utf-8', newline='').writelines(out)
print('removed', removed, 'local import lines')
