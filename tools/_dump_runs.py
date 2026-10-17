import json

c = json.load(open('build-release/overlay_captures.json', encoding='utf-8'))
cap = [o for o in c if int(o['load_addr'], 16) == 0x80053000][0]
p = sorted(int(x, 16) if isinstance(x, str) else x for x in cap['executed_pcs'])
runs = []
start = prev = p[0]
for x in p[1:]:
    if x == prev + 4:
        prev = x
    else:
        runs.append((start, prev))
        start = prev = x
runs.append((start, prev))
print('runs contiguos finales en overlay 0x80053000:')
for a, b in runs[-12:]:
    print('  0x%08X - 0x%08X (%d insns)' % (a, b, (b - a) // 4 + 1))