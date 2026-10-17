"""Read-only inspection of retained local STEP40 captures (no game launch).

These captures are private disc-derived artifacts, not test fixtures to ship.
Run with --inspect to print the narrow input path and candidate callers.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]


def fnv(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value


def regions(path):
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        records = [records]
    for record in records:
        yield int(record["load_addr"], 16), base64.b64decode(record["bytes_b64"])


def inspect(path):
    print(f"Capture: {path}")
    print(f"SHA256: {hashlib.sha256(path.read_bytes()).hexdigest()}")
    seen = set()
    for base, data in regions(path):
        # Only a region carrying both verified poll and remap prologues.
        off = 0x8003FCF0 - base
        if off < 0 or off + 0x294 > len(data):
            continue
        if struct.unpack_from("<I", data, off)[0] != 0x27BDFFE0:
            continue
        identity = hashlib.sha256(data[off:off + 0x294]).hexdigest()
        if identity in seen:
            continue
        seen.add(identity)
        print(f"Region {base:#010x}, input-path SHA256 {identity}")
        print(f"Poll/remap FNV1a: {fnv(data[off:off + 0x294]):08X}")
        for lo, hi in ((0x8003FD64, 0x8003FDA0), (0x8003FE1C, 0x8003FE54)):
            for pc in range(lo, hi, 4):
                o = pc - base
                if 0 <= o <= len(data) - 4:
                    w = struct.unpack_from("<I", data, o)[0]
                    op, rs, rt = w >> 26, (w >> 21) & 31, (w >> 16) & 31
                    detail = ""
                    if op == 3:
                        detail = f"jal {((pc + 4) & 0xf0000000) | ((w & 0x3ffffff) << 2):#010x}"
                    elif op in (9, 35, 43, 37, 41, 15, 13, 12):
                        name = {9: "addiu", 35: "lw", 43: "sw", 37: "lhu", 41: "sh", 15: "lui", 13: "ori", 12: "andi"}[op]
                        detail = f"{name} rt={rt} rs={rs} imm={w & 0xffff:#06x}"
                    elif op == 0:
                        name = {0: "sll", 2: "srl", 33: "addu", 36: "and", 37: "or", 38: "xor", 39: "nor"}.get(w & 63, "SPECIAL")
                        detail = f"{name} rd={(w >> 11) & 31} rs={rs} rt={rt} shift={(w >> 6) & 31}"
                    elif op in (4, 5):
                        displacement = ((w & 0xffff) ^ 0x8000) - 0x8000
                        detail = f"{'beq' if op == 4 else 'bne'} rs={rs} rt={rt} target={pc + 4 + displacement * 4:#010x}"
                    print(f"  {pc:08X} {w:08X} {detail}")
        for pc in (0x8003FE34, 0x8003FE40, 0x8003FE48):
            word = struct.unpack_from("<I", data, pc-base)[0]
            signed_offset = ((word & 0xffff) ^ 0x8000) - 0x8000
            print(f"Edge store at {pc:#010x}: 0x800B0000 + ({signed_offset}) = {0x800B0000 + signed_offset:#010x}")
    input_count = len(seen)
    for base, data in regions(path):
        lo, hi = 0x80053990, 0x80053A30
        if base <= lo and hi <= base + len(data) and struct.unpack_from("<I", data, 0x800539C8-base)[0] == 0x0C00FF3C:
            key = data[lo-base:hi-base]
            if key in seen:
                continue
            seen.add(key)
            print(f"Caller region {base:#010x}")
            print(f"Caller FNV1a: {fnv(data[0x800539A8-base:0x800539D0-base]):08X}")
            for pc in range(lo, hi, 4):
                w = struct.unpack_from("<I", data, pc-base)[0]
                print(f"  {pc:08X} {w:08X}")
    print(f"Distinct input paths: {input_count}")
    exe = (ROOT / "disc/SLUS_004.93").read_bytes()
    load = struct.unpack_from("<I", exe, 0x18)[0]
    offset = 0x80010F40 - load + 0x800
    print(f"EXE SHA256: {hashlib.sha256(exe).hexdigest()}")
    print(f"PadRead full FNV1a: {fnv(exe[offset:offset+0x10c]):08X}")
    for pc in range(0x80011040, 0x8001104C, 4):
        print(f"  {pc:08X} {struct.unpack_from('<I', exe, pc-load+0x800)[0]:08X}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", required=True)
    parser.add_argument("--capture", type=Path, default=ROOT / "build-release/vault/overlay_captures.json")
    args = parser.parse_args()
    inspect(args.capture)
