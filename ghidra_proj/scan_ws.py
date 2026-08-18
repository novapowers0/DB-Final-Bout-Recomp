"""Find widescreen render-funnel signatures + screen-extent culls in Final Bout.
The recompiler's auto_screen_x looks for a function with a width sltiu 0x140/0x141
(320) AND a height sltiu 0xE0/0xF1 (240). Those are the screen-extent rejects that
widen to reveal the wider FOV. Also list functions doing LUI 0x8003 + offset loads
(candidate player-struct) and the GTE render loop.
"""
import struct, collections

DATA = open(r'C:\Users\javie\Desktop\PROYECTOS IA\DBFinalBoutRecomp\disc\SLUS_004.93', 'rb').read()
TEXT_OFF = 0x800
BASE = 0x80010000
TEXT_SIZE = len(DATA) - TEXT_OFF

def word_at(va):
    off = TEXT_OFF + (va - BASE)
    if off + 4 > len(DATA): return None
    return struct.unpack('<I', DATA[off:off+4])[0]

# Slice into functions using the recompiler's known function boundaries.
# We don't have them in this file, so use a heuristic: a jr $ra + nop (0x03E00008
# followed by 0x00000000) ends a function. We already know funcs start at known
# addresses from full.ranges — load them.
func_starts = []
try:
    with open(r'C:\Users\javie\Desktop\PROYECTOS IA\DBFinalBoutRecomp\generated\SLUS_004.93_full.ranges') as f:
        for line in f:
            line = line.strip()
            if line.startswith('F '):
                func_starts.append(int(line.split()[1], 16))
except Exception as e:
    print('no ranges:', e)
print("funciones conocidas:", len(func_starts))

# Build address->func index
import bisect
def func_for(va):
    i = bisect.bisect_right(func_starts, va) - 1
    return func_starts[i] if i >= 0 else None

# Scan for sltiu/sltiu width & height immediates per function
# sltiu opcode = 0x0B, slti = 0x0A. Format: op(6) rs(5) rt(5) imm(16)
w_imms = {0x140, 0x141, 0x141}
h_imms = {0xE0, 0xF1}
def scan_funnel():
    print("\n==== functions with width+height screen-extent culls (render funnel) ====")
    func_hits = collections.defaultdict(set)  # func -> set of ('W',imm) or ('H',imm)
    for va in range(BASE, BASE + TEXT_SIZE, 4):
        w = word_at(va)
        if w is None: continue
        op = w >> 26
        if op == 0x0B:  # sltiu
            imm = w & 0xFFFF
            if imm in w_imms or imm in h_imms:
                f = func_for(va)
                if f is not None:
                    func_hits[f].add(('W' if imm in w_imms else 'H', imm))
    # only functions with BOTH width and height
    for f, kinds in sorted(func_hits.items()):
        hasW = any(k=='W' for k,_ in kinds)
        hasH = any(k=='H' for k,_ in kinds)
        if hasW and hasH:
            print("0x%08X  %s" % (f, sorted(kinds)))
    print("total funcs with any screen cull:", len(func_hits))

# Scan for player-struct: LUI 0x8003 followed by load with offset in a small range
# across multiple sites (indicates a dense struct). Just list LUI 0x80030000 refs.
def scan_globals():
    print("\n==== LUI 0x8003xxxx sites (global page) grouped by page ====")
    pages = collections.Counter()
    for va in range(BASE, BASE + TEXT_SIZE, 4):
        w = word_at(va)
        if w is None: continue
        if (w >> 26) == 0x0F:
            tgt = (w & 0xFFFF) << 16
            if 0x80030000 <= tgt < 0x80040000:
                pages[tgt] += 1
    for tgt, c in pages.most_common(25):
        print("0x%08X : %d" % (tgt, c))

scan_funnel()
scan_globals()
