import json, base64, zlib

sess = 'SLUS-00493_20260818T185128Z-p19644'
snaps = [('0014', 'DAA185DE57F49AF7'), ('0015', '8822B207D90B551A'), ('0016', '32D7032513EB8033')]

for seq, fnv in snaps:
    s = json.load(open('build-release/%s_%s_%s.json' % (sess, seq, fnv), encoding='utf-8'))
    print('=== snapshot %s: top=%s len=%d ===' % (seq, type(s).__name__, len(s) if hasattr(s, '__len__') else '?'))
    if isinstance(s, dict):
        for k, v in s.items():
            if isinstance(v, list):
                print('  %s: list[%d]' % (k, len(v)))
            else:
                print('  %s: %s' % (k, str(v)[:80]))
        continue
    for ov in s:
        if not isinstance(ov, dict):
            continue
        keys = list(ov.keys())
        la = ov.get('load_addr')
        sz = ov.get('size')
        n = len(ov.get('executed_pcs', []) or [])
        b = base64.b64decode(ov.get('bytes_b64', ''))
        crc = zlib.crc32(b) & 0xFFFFFFFF
        mx = max(ov.get('executed_pcs', []) or [0])
        print('  0x%s size=0x%s pcs=%d crc=%08X maxpc=0x%s' % (la, sz, n, crc, mx))