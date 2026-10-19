"""Read-only disassembler for the private main executable (SLUS_004.93).

The R4 camera chain leaves STEP40 at 0x80044824 -> 0x80024850, which lives in
the always-resident main EXE, not the overlay. This helper adds COP2/GTE
decoding on top of combat_map.decode. No writes, no launch, no extraction.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from combat_map import decode, ROOT

EXE_SHA256 = "507f132cdcbb635bbbf7a75e15c62a9d0d51e22ce4432828da784ec03b67cbcc"
GTE_DATA = ("VXY0 VZ0 VXY1 VZ1 VXY2 VZ2 RGBC OTZ IR0 IR1 IR2 IR3 SXY0 SXY1 "
            "SXY2 SXYP SZ0 SZ1 SZ2 SZ3 RGB0 RGB1 RGB2 RES1 MAC0 MAC1 MAC2 MAC3 "
            "IRGB ORGB LZCS LZCR").split()
GTE_CTRL = ("RT11RT12 RT13RT21 RT22RT23 RT31RT32 RT33 TRX TRY TRZ L11L12 "
            "L11L13 L21L22 L21L23 L31L32 L31L33 RBK GBK BBK LR1LR2 LR3LG1 "
            "LG2LG3 LB1LB2 LB3 RFC GFC BFC OFX OFY H DQA DQB ZSF3 ZSF4").split()
GTE_CMD = {0x01: "RTPS", 0x06: "NCLIP", 0x0C: "OP", 0x10: "DPCS", 0x11: "INTPL",
           0x12: "MVMVA", 0x13: "NCDS", 0x14: "CDP", 0x16: "NCDT", 0x1B: "NCCS",
           0x1C: "CC", 0x1E: "NCS", 0x20: "NCT", 0x28: "SQR", 0x29: "DCPL",
           0x2A: "DPCT", 0x2D: "AVSZ3", 0x2E: "AVSZ4", 0x30: "RTPT", 0x3D: "GPF",
           0x3E: "GPL", 0x3F: "NCCT"}


def gte_name(data_register, index):
    table = GTE_DATA if data_register else GTE_CTRL
    return table[index] if index < len(table) else f"r{index}"


def decode_cop2(pc, word):
    op, rs, rt, rd, _, fn = (word >> 26, (word >> 21) & 31, (word >> 16) & 31,
                             (word >> 11) & 31, (word >> 6) & 31, word & 63)
    if op == 0x12:
        if word & (1 << 25):
            cmd = word & 0x3F
            sf = "sf" if word & (1 << 19) else " "
            mm = (word >> 17) & 3
            v = (word >> 15) & 3
            cv = (word >> 13) & 3
            lm = "lm" if word & (1 << 10) else "  "
            name = GTE_CMD.get(cmd, f"cmd{cmd:02X}")
            detail = {"RTPS": f"H=CR27 ({GTE_CTRL[27]}), OFX/OFY=CR25/26, "
                              f"in=CR0-5+TRX/Y/Z, out=SXY2/SZ3/MAC0",
                      "RTPT": "3 points in V0-V2, out SXY0-2/SZ0-3, MAC0",
                      "NCLIP": "2D cross of SXY0-2 -> MAC0 (backface)",
                      "AVSZ3": "sum SZ1-3 * ZSF3 -> OTZ",
                      "AVSZ4": "sum SZ0-3 * ZSF4 -> OTZ",
                      "MVMVA": "matrix*vector -> IR/MAC, mx%d v%d cv%d" % (mm, v, cv)}.get(name, "")
            return f"cop2 {name} {sf} {lm} {detail}".rstrip()
        if rs == 0:
            return f"mfc2 {name_cpu(rt)}, {gte_name(True, rd)}"
        if rs == 2:
            return f"cfc2 {name_cpu(rt)}, {gte_name(False, rd)}"
        if rs == 4:
            return f"mtc2 {name_cpu(rt)}, {gte_name(True, rd)}"
        if rs == 6:
            return f"ctc2 {name_cpu(rt)}, {gte_name(False, rd)}"
        return f"cop2 rs{rs} rt{rt} rd{rd}"
    if op in (0x32, 0x3A):
        mem = "lwc2" if op == 0x32 else "swc2"
        return f"{mem} {gte_name(True, rt)}, {signed(word & 0xffff):+d}({name_cpu(rs)})"
    return None


def name_cpu(index):
    return "zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra".split()[index]


def signed(value):
    return value - 0x10000 if value & 0x8000 else value


class ExeImage:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        digest = hashlib.sha256(self.data).hexdigest()
        if digest != EXE_SHA256:
            raise ValueError(f"Unsupported main EXE hash {digest}")
        self.load = struct.unpack_from("<I", self.data, 0x18)[0]
        self.size = struct.unpack_from("<I", self.data, 0x1C)[0]
        self.entry = struct.unpack_from("<I", self.data, 0x10)[0]

    def file_offset(self, pc):
        offset = 0x800 + (pc - self.load)
        if not 0 <= offset - 0x800 < self.size:
            raise ValueError(f"Outside main EXE: {pc:#x}")
        return offset

    def word(self, pc):
        return struct.unpack_from("<I", self.data, self.file_offset(pc))[0]

    def text(self, pc, word):
        return decode_cop2(pc, word) or decode(pc, word)

    def disasm(self, start, end):
        print(f"main EXE SHA256 {EXE_SHA256} load {self.load:08X} size {self.size:X} entry {self.entry:08X}")
        for pc in range(start, end, 4):
            word = self.word(pc)
            print(f"{pc:08X} {word:08X} {self.text(pc, word)}")

    def gte(self, start, end):
        for pc in range(start, end, 4):
            word = self.word(pc)
            if word >> 26 in (0x12, 0x32, 0x3A):
                text = self.text(pc, word)
                if "cop2 rs" not in text:
                    print(f"{pc:08X} {word:08X} {text}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=ROOT / "disc/SLUS_004.93")
    parser.add_argument("--disc", type=Path, default=ROOT / "disc/Dragon Ball GT - Final Bout (USA).bin")
    parser.add_argument("command", choices=("disasm", "words", "gte", "calls"))
    parser.add_argument("addresses", nargs="*", type=lambda s: int(s, 0))
    args = parser.parse_args()
    image = ExeImage(args.exe)
    if args.command == "disasm":
        image.disasm(*args.addresses)
    elif args.command == "gte":
        image.gte(*args.addresses)
    elif args.command == "words":
        for pc in range(args.addresses[0], args.addresses[1], 4):
            print(f"{pc:08X} {image.word(pc):08X}")
    elif args.command == "calls":
        target = args.addresses[0]
        for pc in range(image.load, image.load + image.size, 4):
            word = image.word(pc)
            if word >> 26 in (2, 3) and (((pc + 4) & 0xF0000000) | ((word & 0x3FFFFFF) << 2)) == target:
                print(f"{pc:08X} {word:08X} {decode(pc, word)}")


if __name__ == "__main__":
    main()
