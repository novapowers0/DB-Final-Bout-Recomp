"""Read-only, offline Final Bout MIPS investigation. Standard library only.

Reads the ISO directory and complete STEP40 file in memory. Does not extract
disc bytes, write guest memory, launch software, install packages or use network.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
REG = "zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra".split()
MEM = {32: ("lb", 1), 33: ("lh", 2), 34: ("lwl", 4), 35: ("lw", 4),
       36: ("lbu", 1), 37: ("lhu", 2), 38: ("lwr", 4), 40: ("sb", 1),
       41: ("sh", 2), 42: ("swl", 4), 43: ("sw", 4), 46: ("swr", 4)}
TEXT_START, TEXT_END = 0x8003E7F0, 0x80072520


def decode(pc, word):
    op, rs, rt, rd, shift, func = word >> 26, (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31, (word >> 6) & 31, word & 63
    immediate = word & 0xffff
    if not word:
        return "nop"
    if op in MEM:
        return f"{MEM[op][0]} {REG[rt]},{sx(immediate):+#x}({REG[rs]})"
    if op in (2, 3):
        return f"{'jal' if op == 3 else 'j'} {((pc+4) & 0xf0000000) | ((word & 0x3ffffff) << 2):#010x}"
    if op in (4, 5, 6, 7, 1):
        name = {4: "beq", 5: "bne", 6: "blez", 7: "bgtz", 1: {0: "bltz", 1: "bgez", 16: "bltzal", 17: "bgezal"}.get(rt, "REGIMM")}[op]
        args = f"{REG[rs]},{REG[rt]}," if op in (4, 5) else f"{REG[rs]},"
        return f"{name} {args}{pc + 4 + sx(immediate)*4:#010x}"
    if op == 0:
        if func in (0, 2, 3):
            return f"{ {0:'sll', 2:'srl', 3:'sra'}[func]} {REG[rd]},{REG[rt]},{shift}"
        if func in (8, 9):
            return f"{'jalr ' + REG[rd] + ',' if func == 9 else 'jr '}{REG[rs]}"
        if func in (16, 18):
            return f"{'mfhi' if func == 16 else 'mflo'} {REG[rd]}"
        if func in (24, 25, 26, 27):
            return f"{ {24:'mult',25:'multu',26:'div',27:'divu'}[func]} {REG[rs]},{REG[rt]}"
        names = {4: 'sllv', 6: 'srlv', 7: 'srav', 32:'add',33:'addu',34:'sub',35:'subu',36:'and',37:'or',38:'xor',39:'nor',42:'slt',43:'sltu'}
        if func in names:
            return f"{names[func]} {REG[rd]},{REG[rs]},{REG[rt]}"
    names = {8: 'addi',9:'addiu',10:'slti',11:'sltiu',12:'andi',13:'ori',14:'xori',15:'lui'}
    if op in names:
        return f"{names[op]} {REG[rt]}," + ("" if op == 15 else f"{REG[rs]},") + f"{immediate:#06x}"
    return f".word {word:#010x}"


class BattleImage:
    def __init__(self, data, cap_path):
        self.data = data
        records = list(captures(cap_path))
        bases = set()
        for start, body, _ in records:
            off = 0x8003FCF0 - start
            if 0 <= off and off + 0x294 <= len(body):
                pattern = body[off:off+0x294]
                if sha(pattern) != "ce359330a257f1023023c0eaf8657fc9ad4423a4e264c4ed3e14c95e9d46c09c":
                    continue
                found = data.find(pattern)
                if found >= 0 and data.find(pattern, found+1) < 0:
                    bases.add(0x8003FCF0 - found)
        if len(bases) != 1:
            raise ValueError(f"Unverified/nonunique STEP40 relocation: {bases}")
        self.base = bases.pop()
        self.executed = set()
        for start, body, record in records:
            for raw in record.get("executed_pcs", []):
                pc = int(raw, 16) if isinstance(raw, str) else raw
                off, file_off = pc-start, pc-self.base
                # Execution evidence only when 16 contiguous code bytes agree.
                if (TEXT_START <= pc < TEXT_END and 0 <= off and off+16 <= len(body)
                        and body[off:off+16] == data[file_off:file_off+16]):
                    self.executed.add(pc)

    def word(self, pc):
        off = pc - self.base
        if off < 0 or off + 4 > len(self.data):
            raise ValueError(f"Outside complete STEP40: {pc:#x}")
        return struct.unpack_from("<I", self.data, off)[0]

    def disasm(self, start, end):
        if start & 3 or end & 3 or end <= start or end-start > 0x8000:
            raise ValueError("Disassembly requires aligned bounded window")
        body = self.data[start-self.base:end-self.base]
        print(f"range {start:08X}..{end:08X} file +{start-self.base:X} size {len(body):X} SHA256 {sha(body)}")
        for pc in range(start, end, 4):
            word = self.word(pc)
            print(f"{'E' if pc in self.executed else '-'} {pc:08X} +{pc-self.base:06X} {word:08X} {decode(pc, word)}")

    def xrefs(self):
        """Conservative constants within straight-line blocks; loads have a
        one-instruction delay. No constant crosses a branch/call's delay slot.
        This deliberately misses inter-block/indirect aliases, never assumes ABI.
        """
        values = [None] * 32
        values[0] = 0
        pending = None
        reset_next = False
        for pc in range(TEXT_START, TEXT_END, 4):
            word = self.word(pc)
            op, rs, rt, rd, sh, fn = word >> 26, (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31, (word >> 6) & 31, word & 63
            reset_after = reset_next
            reset_next = op in (1, 2, 3, 4, 5, 6, 7) or (op == 0 and fn in (8, 9))
            a, b = values[rs], values[rt]
            result, destination, next_pending = None, None, None
            if op in MEM:
                if a is not None:
                    yield pc, (a + sx(word)) & 0xffffffff, MEM[op][0], MEM[op][1]
                if op < 40:
                    next_pending = rt
            elif op == 15:
                destination, result = rt, (word & 0xffff) << 16
            elif op in (8, 9, 10, 11, 12, 13, 14):
                destination = rt
                if a is not None:
                    imm = word & 0xffff
                    if op in (8, 9): result = (a + sx(imm)) & 0xffffffff
                    elif op == 12: result = a & imm
                    elif op == 13: result = a | imm
                    elif op == 14: result = a ^ imm
            elif op == 0:
                if fn not in (8, 12, 13, 17, 19, 24, 25, 26, 27): destination = rd
                if fn in (0, 2, 3) and b is not None:
                    result = ((b << sh) if fn == 0 else b >> sh) & 0xffffffff
                if fn in (32, 33, 34, 35, 36, 37, 38, 39) and a is not None and b is not None:
                    result = {32:lambda:a+b,33:lambda:a+b,34:lambda:a-b,35:lambda:a-b,
                              36:lambda:a&b,37:lambda:a|b,38:lambda:a^b,39:lambda:~(a|b)}[fn]() & 0xffffffff
            elif op in (16, 18) and rs in (0, 2):
                next_pending = rt
            if pending:
                values[pending] = None
            if destination:
                values[destination] = result
                if result is not None:
                    yield pc, result, "address", 0
            pending = next_pending
            if reset_after:
                values = [None] * 32
                values[0] = 0
                pending = None

    def calls_to(self, target):
        for pc in range(TEXT_START, TEXT_END, 4):
            word = self.word(pc)
            if word >> 26 in (2, 3) and (((pc+4)&0xf0000000) | ((word&0x3ffffff)<<2)) == target:
                print(f"{'E' if pc in self.executed else '-'} {pc:08X} {decode(pc, word)}")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sx(value):
    return ((value & 0xffff) ^ 0x8000) - 0x8000


class Iso:
    def __init__(self, path):
        self.path = Path(path)
        with self.path.open("rb") as stream:
            first = stream.read(24)
        self.stride = 2352 if first[:12] == SYNC else 2048
        self.offset = (24 if first[15] == 2 else 16) if self.stride == 2352 else 0
        pvd = self.read(16, 2048)
        if pvd[:7] != b"\x01CD001\x01":
            raise ValueError("ISO9660 PVD missing")
        self.root = struct.unpack_from("<I", pvd, 158)[0], struct.unpack_from("<I", pvd, 166)[0]

    def read(self, lba, size):
        if lba < 0 or not 0 <= size <= 16 * 1024 * 1024:
            raise ValueError("Invalid ISO extent")
        chunks = []
        with self.path.open("rb") as stream:
            for offset in range(0, size, 2048):
                stream.seek((lba + offset // 2048) * self.stride)
                sector = stream.read(self.stride)
                if len(sector) != self.stride:
                    raise ValueError("Truncated sector")
                if self.stride == 2352 and (sector[:12] != SYNC or sector[15] not in (1, 2)):
                    raise ValueError("Invalid raw sector")
                if self.offset == 24 and sector[18] & 0x20:
                    raise ValueError("Mode2 Form2 is not executable user data")
                chunks.append(sector[self.offset:self.offset + min(2048, size-offset)])
        return b"".join(chunks)

    def files(self, directory=None, prefix="", depth=0):
        if depth > 8:
            raise ValueError("Directory recursion limit")
        data = self.read(*(directory or self.root))
        pos = 0
        while pos < len(data):
            length = data[pos]
            if not length:
                pos = (pos // 2048 + 1) * 2048
                continue
            record = data[pos:pos+length]
            if length < 34 or len(record) != length or 33 + record[32] > length:
                raise ValueError("Invalid ISO directory record")
            name = record[33:33+record[32]]
            if name not in (b"\x00", b"\x01"):
                name = name.decode("ascii").split(";")[0]
                lba, size = struct.unpack_from("<I", record, 2)[0], struct.unpack_from("<I", record, 10)[0]
                path = prefix + name
                if record[25] & 2:
                    yield from self.files((lba, size), path + "/", depth+1)
                else:
                    yield path, lba, size
            pos += length


def step40(path):
    iso = Iso(path)
    matches = [(name, lba, size) for name, lba, size in iso.files() if name.upper().split("/")[-1] == "STEP40.BIN"]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one STEP40.BIN, found {len(matches)}")
    name, lba, size = matches[0]
    return iso.read(lba, size), {"iso_path": name, "lba": lba, "size": size, "sector_stride": iso.stride}


def captures(path):
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        records = [records]
    for record in records:
        yield int(record["load_addr"], 16), base64.b64decode(record["bytes_b64"]), record


def inventory(data, metadata, cap_path):
    print(json.dumps(metadata, indent=2))
    print(f"STEP40 cooked SHA256 {sha(data)}")
    for offset in range(0, 0x100, 16):
        print(f"file {offset:06X}: " + " ".join(f"{word:08X}" for word in struct.unpack_from("<4I", data, offset)))
    anchors = (0x8003FCF0, 0x8003FE68, 0x800539C8, 0x80060000, 0x80069228)
    found = set()
    for base, body, record in captures(cap_path):
        for pc in anchors:
            off = pc - base
            if 0 <= off and off + 32 <= len(body):
                pattern = body[off:off+32]
                if len(set(pattern)) < 4:
                    continue
                start = data.find(pattern)
                if start < 0 or data.find(pattern, start+1) >= 0:
                    continue
                key = (pc, start, base, len(body))
                if key not in found:
                    found.add(key)
                    print(f"anchor PC={pc:08X} file={start:06X} delta={pc-start:08X} capture={base:08X}+{len(body):X} executed_pcs={len(record.get('executed_pcs', []))}")


def native_routes(image):
    """Static command/collision/continuation linkage, pinned to verified USA code.

    Fighter ID is control-4, NOT an archive index or an anatomical/move name.
    A table target proves a possible path, never that it occurred in a match.
    """
    expected = '001adcdc2e129d3bd715c29b64e393fa8c2901a7ef39c2347874b321aae6b9dd'
    if image.base != 0x8003DFA0 or sha(image.data) != expected:
        raise ValueError('Native route semantics require the verified USA STEP40')

    def cases(table, first, count, targets):
        return [{'fighter_id': first+i, **targets[target]}
                for i in range(count)
                if (target := image.word(table+i*4)) in targets]

    command_specs = {
        0x25: (0x800607A0, 0x8003EE54, 0, 16, {
            0x800607E0: {'requires_flags_any': 0x60, 'conditional_actions': [
                {'flags_all': 0x20, 'action': 0x98},
                {'flags_none': 0x20, 'flags_all': 0x40, 'action': 0xAA}]}}),
        0x28: (0x80060930, 0x8003EEDC, 1, 16, {
            0x80060974: {'action': 0x98}, 0x80060988: {'action': 0x9B},
            0x8006099C: {'action': 0x9C}}),
        0x29: (0x800609C0, 0x8003EF1C, 1, 15, {
            0x80060A48: {'action': 0x97}, 0x80060A5C: {'action': 0x9C},
            0x80060A70: {'action': 0x98, 'requires_flags_any': 0x60,
                         'sets_flags': 0x200},
            0x80060AC8: {'action': 0x9E}, 0x80060ADC: {'action': 0x99}}),
        0x2B: (0x80060BA4, 0x8003EF94, 3, 14, {
            0x80060BE8: {'action': 0x98}, 0x80060BFC: {'action': 0x97},
            0x80060C10: {'action': 0x9D}}),
        0x2C: (0x80060C34, None, 0, 0, {
            2: {'action': 0x96}, 8: {'action': 0x98},
            15: {'action': 0x96}, 17: {'action': 0x98}}),
    }
    commands = []
    for row in range(34):
        address = 0x8006EDC8+row*0x24
        command = image.word(address+4) >> 16
        if command not in command_specs:
            continue
        handler, table, first, count, targets = command_specs[command]
        # The dispatcher remaps command IDs >=34 by subtracting31.
        if image.word(0x8006ED04+(command-31)*4) != handler:
            raise ValueError('Native route dispatch disagrees with command table')
        steps = []
        for i in range(7):
            word = image.word(address+8+i*4)
            if not word:
                break
            steps.append({'buttons_internal': word & 0xFFFF,
                          'encoded_window': word >> 16})
        commands.append({'command': command, 'handler': hex(handler),
                         'command_row': row, 'steps': steps,
                         'fighter_cases': (cases(table, first, count, targets) if table else
                                           [{'fighter_id': i, **v} for i, v in targets.items()]),
                         'entry_guard': ('flags20/40 reject except fighter6'
                                         if command == 0x29 else None)})

    confirmations = []
    for action, target, table, count, writers in (
            (0x98, 0x80062F48, 0x8003F24C, 18,
             {0x80062FC8: 0x80062FF4, 0x80063008: 0x80063030}),
            (0xAA, 0x800631BC, 0x8003F2DC, 17,
             {0x800631FC: 0x80063228})):
        if image.word(0x8003F004+(action-0x62)*4) != target:
            raise ValueError('Collision action dispatch mismatch')
        confirmations.append({'action': action, 'collision_selector': hex(target),
                              'field': 'attacker.control+4', 'set_mask': 0x80,
                              'fighter_cases': cases(table, 0, count,
                                  {pc: {'store_pc': hex(store)} for pc, store in writers.items()})})
    supported = [0, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 15, 16]
    return {'source_sha256': expected, 'static_only': True,
            'command_routes': commands, 'collision_confirmations': confirmations,
            'continuation': {
                'candidate_actions': [0x98, 0xAA], 'fighter_ids': supported,
                'candidate_storage': 'caller.sp+0x48',
                'field': 'control+4', 'selector_pc': '0x800576BC',
                'final_action_store_pc': '0x80057F94',
                'outcomes': [
                    {'flags_all': 0x280, 'action': 0x9B, 'clear_mask': 0x280},
                    {'flags_all': 0x80, 'flags_none': 0x200,
                     'action': 0x99, 'clear_mask': 0x80},
                    {'flags_none': 0x80, 'action': 0x9A, 'clear_mask': 0x200}],
                'requests_native_action_change': True},
            'limits': ['Fighter IDs are not mapped to character names/archive order.',
                       'Collision branch prerequisites before 0x80062AB4 still apply.',
                       'Static paths are not observed hits or measured frame data.',
                       'The selector consumes a stack candidate, not a sampled action transition.',
                       'No new aerial move or timing change is implemented by this report.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disc", type=Path, default=ROOT / "disc/Dragon Ball GT - Final Bout (USA).bin")
    parser.add_argument("--captures", type=Path, default=ROOT / "build-release/vault/overlay_captures.json")
    parser.add_argument("command", choices=("inventory", "files", "immediates", "disasm", "xrefs", "calls", "pointers", "words", "fieldrefs", "commands", "routes"))
    parser.add_argument("addresses", nargs="*", type=lambda s: int(s, 0))
    parser.add_argument("--size", type=lambda s: int(s, 0), default=4)
    args = parser.parse_args()
    if args.command == "files":
        iso = Iso(args.disc)
        for name, lba, size in iso.files():
            print(f"{name} lba={lba} size={size}")
        return
    data, metadata = step40(args.disc)
    if args.command == "inventory":
        inventory(data, metadata, args.captures)
        return
    image = BattleImage(data, args.captures)
    if args.command == 'routes':
        print(json.dumps(native_routes(image), indent=2))
        return
    print(f"STEP40 SHA256 {sha(data)}, verified base {image.base:08X}, matching executed PCs {len(image.executed)}")
    if args.command == "disasm":
        image.disasm(*args.addresses)
    elif args.command == "xrefs":
        for pc, target, kind, width in image.xrefs():
            if any(address <= target < address + args.size for address in args.addresses):
                print(f"{'E' if pc in image.executed else '-'} {pc:08X} +{pc-image.base:06X} {decode(pc, image.word(pc))} -> {target:08X} {kind} width={width}")
    elif args.command == "calls":
        for target in args.addresses:
            image.calls_to(target)
    elif args.command == "pointers":
        for offset in range(0, len(data)-3, 4):
            value = struct.unpack_from("<I", data, offset)[0]
            if any(address <= value < address + args.size for address in args.addresses):
                print(f"word at {image.base+offset:08X} file +{offset:06X} -> {value:08X} (data/code classification not inferred)")
    elif args.command == "words":
        for address in args.addresses:
            for pc in range(address, address + args.size, 16):
                print(f"{pc:08X} +{pc-image.base:06X}: " + " ".join(f"{image.word(a):08X}" for a in range(pc, min(pc+16, address+args.size), 4)))
    elif args.command == "immediates":
        for pc in range(TEXT_START, TEXT_END, 4):
            word = image.word(pc)
            if word >> 26 in (9, 10, 11, 12, 13) and (word & 0xffff) in args.addresses:
                print(f"{'E' if pc in image.executed else '-'} {pc:08X} {decode(pc, word)}")
    elif args.command == "fieldrefs":
        for pc in range(TEXT_START, TEXT_END, 4):
            word = image.word(pc)
            if word >> 26 in MEM and (word & 0xffff) in args.addresses:
                print(f"{'E' if pc in image.executed else '-'} {pc:08X} +{pc-image.base:06X} {decode(pc, word)} width={MEM[word >> 26][1]} (base/index MUST be verified in control-flow)")
    elif args.command == "commands":
        for index in range(34):
            pc = 0x8006EDC8 + index * 0x24
            steps = [image.word(pc+8+i*4) for i in range(7)]
            result = image.word(pc+4) >> 16
            dispatch = result - 31 if result >= 34 else result
            handler = "bypassed by 0x80061140" if result == 0x18 else f"handler={image.word(0x8006ED04 + dispatch*4):08X}"
            print(f"row {index:02d} {pc:08X} output={result:04X} {handler} steps=" + ", ".join(f"{word & 0xffff:04X}/wait_field={word>>16}" if word else "END" for word in steps))


if __name__ == "__main__":
    main()
