"""Minimal MIPS-LE scanner for Final Bout SLUS_004.93 text.
Decodes enough of the ISA to find combat-relevant functions:
  - references to SIO0 pad (0x1F801040) -> input decode
  - references to SPU (0x1F801C00) etc.
  - LUI/LW/SW around likely fighter-struct globals
  - global data addresses loaded via LUI+ADDIU (0x800xxxxx) -> candidate globals
Prints candidate addresses + a compact disasm of each hit.
"""
import struct, sys, collections

DATA = open(r'C:\Users\javie\Desktop\PROYECTOS IA\DBFinalBoutRecomp\disc\SLUS_004.93', 'rb').read()
TEXT_OFF = 0x800          # file offset of virtual 0x80010000
BASE = 0x80010000

def word_at(va):
    off = TEXT_OFF + (va - BASE)
    if off + 4 > len(DATA): return None
    return struct.unpack('<I', DATA[off:off+4])[0]

def disasm(va):
    w = word_at(va)
    if w is None: return '??'
    op = w >> 26
    rs = (w >> 21) & 0x1F; rt = (w >> 16) & 0x1F; rd = (w >> 11) & 0x1F
    shamt = (w >> 6) & 0x1F; funct = w & 0x3F; imm = w & 0xFFFF
    simm = imm if imm < 0x8000 else imm - 0x10000
    regs = ['$zero','$at','$v0','$v1','$a0','$a1','$a2','$a3',
            '$t0','$t1','$t2','$t3','$t4','$t5','$t6','$t7',
            '$s0','$s1','$s2','$s3','$s4','$s5','$s6','$s7',
            '$t8','$t9','$k0','$k1','$gp','$sp','$fp','$ra']
    if op == 0:  # R-type
        if funct == 0x21: return 'addu %s,%s,%s' % (regs[rd],regs[rs],regs[rt])
        if funct == 0x23: return 'subu %s,%s,%s' % (regs[rd],regs[rs],regs[rt])
        if funct == 0x08: return 'jr %s' % regs[rs]
        if funct == 0x09: return 'jalr %s' % regs[rs]
        if funct == 0x00: return 'sll %s,%s,%d' % (regs[rd],regs[rt],shamt)
        if funct == 0x02: return 'srl %s,%s,%d' % (regs[rd],regs[rt],shamt)
        if funct == 0x18: return 'mult %s,%s' % (regs[rs],regs[rt])
        if funct == 0x19: return 'multu %s,%s' % (regs[rs],regs[rt])
        if funct == 0x1A: return 'div %s,%s' % (regs[rs],regs[rt])
        if funct == 0x20: return 'add %s,%s,%s' % (regs[rd],regs[rs],regs[rt])
        if funct == 0x22: return 'sub %s,%s,%s' % (regs[rd],regs[rs],regs[rt])
        if funct == 0x27: return 'nor %s,%s,%s' % (regs[rd],regs[rs],regs[rt])
        if funct == 0x24: return 'and %s,%s,%s' % (regs[rd],regs[rs],regs[rt])
        if funct == 0x25: return 'or %s,%s,%s' % (regs[rd],regs[rs],regs[rt])
        if funct == 0x2A: return 'slt %s,%s,%s' % (regs[rd],regs[rs],regs[rt])
        if funct == 0x2B: return 'sltu %s,%s,%s' % (regs[rd],regs[rs],regs[rt])
        return 'R op=%d funct=%d' % (op, funct)
    if op == 0x0F: return 'lui %s,0x%04X' % (regs[rt], imm)
    if op == 0x08: return 'addi %s,%s,%d' % (regs[rt],regs[rs],simm)
    if op == 0x09: return 'addiu %s,%s,%d' % (regs[rt],regs[rs],simm)
    if op == 0x0C: return 'andi %s,%s,0x%04X' % (regs[rt],regs[rs],imm)
    if op == 0x0D: return 'ori %s,%s,0x%04X' % (regs[rt],regs[rs],imm)
    if op == 0x23: return 'lw %s,%d(%s)' % (regs[rt],simm,regs[rs])
    if op == 0x2B: return 'sw %s,%d(%s)' % (regs[rt],simm,regs[rs])
    if op == 0x20: return 'lb %s,%d(%s)' % (regs[rt],simm,regs[rs])
    if op == 0x24: return 'lbu %s,%d(%s)' % (regs[rt],simm,regs[rs])
    if op == 0x25: return 'lhu %s,%d(%s)' % (regs[rt],simm,regs[rs])
    if op == 0x21: return 'lh %s,%d(%s)' % (regs[rt],simm,regs[rs])
    if op == 0x22: return 'lwl %s,%d(%s)' % (regs[rt],simm,regs[rs])
    if op == 0x26: return 'lwr %s,%d(%s)' % (regs[rt],simm,regs[rs])
    if op == 0x28: return 'sb %s,%d(%s)' % (regs[rt],simm,regs[rs])
    if op == 0x29: return 'sh %s,%d(%s)' % (regs[rt],simm,regs[rs])
    if op == 0x2C: return 'sllv %s,%s,%s' % (regs[rd],regs[rt],regs[rs])
    if op == 0x04: return 'beq %s,%s,->%d' % (regs[rs],regs[rt],simm)
    if op == 0x05: return 'bne %s,%s,->%d' % (regs[rs],regs[rt],simm)
    if op == 0x07: return 'bgtz %s,->%d' % (regs[rs],simm)
    if op == 0x06: return 'blez %s,->%d' % (regs[rs],simm)
    if op == 0x01: return 'b%02X %s,->%d' % (rt,regs[rs],simm)
    if op == 0x02: return 'j 0x%08X' % ((w & 0x3FFFFFF) << 2)
    if op == 0x03: return 'jal 0x%08X' % (((w & 0x3FFFFFF) << 2))
    if op == 0x0A: return 'slti %s,%s,%d' % (regs[rt],regs[rs],simm)
    if op == 0x0B: return 'sltiu %s,%s,%d' % (regs[rt],regs[rs],simm)
    if op == 0x3F: return 'sd? 0x%08X' % w
    return 'op%02X rt=%s rs=%s imm=%d' % (op, regs[rt], regs[rs], simm)

def scan():
    print("== references to SIO0 pad 0x1F801040 ==")
    # find LUI rt,0x1F80 + ADDIU rt,rt,0x1040 nearby
    hits = []
    for va in range(BASE, BASE + len(DATA)-TEXT_OFF, 4):
        w = word_at(va)
        if w is None: continue
        if w >> 16 == 0x1F80 and (w & 0xFFFF) in (0x1040,0x1042,0x1044,0x1046):
            hits.append(va)
    print("SIO0 LUI hits:", len(hits))
    for va in hits[:40]:
        print("  0x%08X: %s" % (va, disasm(va)))

    print("== references to SPU 0x1F801C00 ==")
    hits2 = []
    for va in range(BASE, BASE + len(DATA)-TEXT_OFF, 4):
        w = word_at(va)
        if w is None: continue
        if w >> 16 == 0x1F80 and (w & 0xFF00) == 0xC00:
            hits2.append(va)
    print("SPU hits:", len(hits2))
    for va in hits2[:15]:
        print("  0x%08X: %s" % (va, disasm(va)))

    print("== all global 0x800xxxxx / 0x801xxxxx LUI targets (candidate data) ==")
    cnt = collections.Counter()
    for va in range(BASE, BASE + len(DATA)-TEXT_OFF, 4):
        w = word_at(va)
        if w is None: continue
        if (w >> 26) == 0x0F:  # lui
            tgt = (w & 0xFFFF) << 16
            if 0x80000000 <= tgt <= 0x80200000:
                cnt[tgt] += 1
    print("top global-page LUI targets:")
    for tgt, c in cnt.most_common(30):
        print("  0x%08X : %d refs" % (tgt, c))

scan()
