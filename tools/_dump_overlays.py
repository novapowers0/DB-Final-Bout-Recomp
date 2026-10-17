import json
c = json.load(open('build-release/overlay_captures.json', encoding='utf-8'))
crash = 0x8003ED74
for cap in c:
    la = cap['load_addr']
    sz = cap['size']
    if isinstance(la, str): la = int(la, 16)
    if isinstance(sz, str): sz = int(sz, 16)
    n = len(cap['executed_pcs'])
    hit = ' <== CRASH 0x8003ED74' if (la <= crash < la + sz) else ''
    print('0x%08X size=0x%X pcs=%d%s' % (la, sz, n, hit))