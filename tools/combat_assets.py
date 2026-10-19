"""Read-only inventory of Final Bout action-table candidates in local disc data.

The table layout is derived from STEP40 0x8004E5B4..0x8004E644:
u16 count at +2, count word offsets at +4 (FFFFFFFF = missing), offsets
relative to the word stream immediately after the table. First instructions
are checked against the interpreter's dispatch table. Candidates are NOT a
verified animation count: aliases, unreachable actions and pose data differ.
Only metadata is printed; no disc bytes are extracted or redistributed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

from combat_map import Iso, ROOT

# Actual indices, counted from dispatch base 0x8003E78C (not 0x8003E788).
# 0x83 is deliberately used by the shipped action tables. Its dispatch target
# is the default/empty handler (0x8004EDFC); it is a valid no-op, not corruption.
OPCODES = {0, 1, *range(0x20, 0x27), 0x40, 0x41, 0x60, 0x61, 0x62, *range(0x80, 0x85)}


def unpack_psdp(data, offset=0, max_size=0x200000):
    """STEP40 0x80042D50..D98 + 0x80042E30..F14, in host memory only.

    LSB-first flags: 1 literal, 0 LE-u16 backreference; distance=token>>5,
    length=(token&31)+3. References before the output start produce zeros.
    Self-reference would read uninitialized guest memory, so it is rejected.
    """
    if offset < 0 or offset + 8 > len(data) or data[offset:offset + 4] != b'Psdp':
        raise ValueError('Missing Psdp header')
    size = struct.unpack_from('<I', data, offset + 4)[0]
    if not 0 < size <= max_size:
        raise ValueError('Psdp output size outside inventory bound')
    out, cursor, flags = bytearray(), offset + 8, 0
    while len(out) < size:
        flags >>= 1
        if not flags & 0x100:
            if cursor >= len(data):
                raise ValueError('Truncated Psdp flags')
            flags = data[cursor] | 0xFF00
            cursor += 1
        if flags & 1:
            if cursor >= len(data):
                raise ValueError('Truncated Psdp literal')
            out.append(data[cursor])
            cursor += 1
        else:
            if cursor + 2 > len(data):
                raise ValueError('Truncated Psdp reference')
            token = struct.unpack_from('<H', data, cursor)[0]
            cursor += 2
            distance, length = token >> 5, (token & 31) + 3
            if not distance or len(out) + length > size:
                raise ValueError('Invalid Psdp reference')
            for _ in range(length):
                source = len(out) - distance
                out.append(out[source] if source >= 0 else 0)
    return bytes(out), cursor - offset


def compressed_tables(data):
    blocks, rejected, offset = [], 0, 0
    while True:
        offset = data.find(b'Psdp', offset)
        if offset < 0:
            break
        try:
            body, consumed = unpack_psdp(data, offset)
        except ValueError:
            rejected += 1
            offset += 4
            continue
        blocks.append({"file_offset": offset, "compressed_bytes_consumed": consumed,
                       "decoded_size": len(body), "decoded_sha256": hashlib.sha256(body).hexdigest(),
                       "candidates": script_tables(body)})
        offset += consumed
    return blocks, rejected


def script_tables(data):
    """Conservative structural candidates; no inference of timing or bone count."""
    out = []
    for offset in range(0, len(data) - 260, 4):
        count = struct.unpack_from('<H', data, offset + 2)[0]
        if not 64 <= count <= 512:
            continue
        stream = offset + 4 * (count + 1)
        if stream + 4 > len(data):
            continue
        sample = struct.unpack_from('<8I', data, offset + 4)
        if any(v != 0xFFFFFFFF and v >= (len(data) - stream) // 4 for v in sample):
            continue
        entries = struct.unpack_from('<' + 'I' * count, data, offset + 4)
        present = [v for v in entries if v != 0xFFFFFFFF]
        unique = sorted(set(present))
        if len(present) < 32 or len(unique) < 16:
            continue
        if any(v >= (len(data) - stream) // 4 for v in present):
            continue
        valid = sum(((struct.unpack_from('<I', data, stream + v * 4)[0] >> 16) & 255) in OPCODES
                    for v in unique)
        if valid != len(unique):
            continue
        out.append({"file_offset": offset, "action_slots": count,
                    "present_slots": len(present), "unique_starts": len(unique),
                    "missing_slots": count - len(present),
                    "classification": "structural_candidate_not_runtime_verified"})
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disc', type=Path, default=ROOT / 'disc/Dragon Ball GT - Final Bout (USA).bin')
    parser.add_argument('--file', default='TITLE/BTCHARA.DAT')
    parser.add_argument('--detail', action='store_true', help='Print all decoded block metadata')
    args = parser.parse_args()
    iso = Iso(args.disc)
    found = [(name, lba, size) for name, lba, size in iso.files() if name.upper() == args.file.upper()]
    if len(found) != 1:
        raise ValueError(f'Expected one exact ISO file: {args.file}')
    name, lba, size = found[0]
    data = iso.read(lba, size)
    blocks, rejected = compressed_tables(data)
    summary = {"decoded_blocks": len(blocks), "decoded_bytes": sum(b['decoded_size'] for b in blocks),
               "blocks_with_candidate_tables": sum(bool(b['candidates']) for b in blocks)}
    print(json.dumps({"iso_file": name, "size": size, "sha256": hashlib.sha256(data).hexdigest(),
                      "candidates": script_tables(data),
                      "decoded_summary": summary,
                      "psdp_blocks": blocks if args.detail else [b for b in blocks if b['candidates']],
                      "rejected_psdp_headers": rejected,
                      "limits": "Structural candidates only; not unique animations, usable moves or measured frame data."},
                     indent=2))


if __name__ == '__main__':
    main()
