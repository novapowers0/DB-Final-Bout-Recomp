"""Own R2/R3 tests. Includes a narrow independent retail-MIPS decoder oracle.

The oracle runs ONLY arithmetic/loads/stores from transform handlers in host
memory, stops before GTE calls, and never starts the game/recompiler/runtime.
Private disc bytes and generated trajectories travel in memory/stdin only.
"""
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combat_rigclip import (ROOT, arc, bridge, compact_model, local_matrix, packets, pose,
                            raw_clip, records, rig, sources, transform, u32)


def sx(v, bits=16):
    return ((v & ((1 << bits)-1)) ^ (1 << (bits-1)))-(1 << (bits-1))


def native_transform(engine, packet, initial, matrix_angles=None):
    """Interpret the ACTUAL disc handler until its first matrix call.

    Bounded instruction vocabulary, branch delay slot, signed/unsigned loads,
    wrap32 and mult low32. No replacement math for the transform under test.
    This window never reads a just-loaded register in its load-delay slot.
    """
    mem = bytearray(512)
    mem[128:128+len(packet['payload'])] = packet['payload']
    struct.pack_into('<3I', mem, 0, *initial['scale'])
    struct.pack_into('<3H', mem, 16, *(v & 65535 for v in initial['angle']))
    struct.pack_into('<3i', mem, 24, *initial['translation'])
    r = [0]*32
    r[16], r[17], r[20] = 0, 128, packet['flags']
    pc, stop = ((0x80042398, 0x800424EC) if packet['op'] == 1 else
                (0x800425A0, 0x8004281C))
    code_base = 0x8003DFA0
    if packet['op'] == 9:
        pc, stop = 0x80042C50, 0x80042CDC
    if matrix_angles is not None:
        struct.pack_into('<3h', mem, 128, *matrix_angles)
        r[4], r[5] = 128, 0
        pc, stop, code_base = 0x8002059C, 0x80020820, 0x8000F800
    pending, lo = None, 0
    for _ in range(300):
        if pc == stop:
            if packet['op'] == 9: return r[2]
            if matrix_angles is not None:
                result = struct.unpack_from('<9h', mem)
                return tuple(tuple(result[3*i+j] for j in range(3)) for i in range(3))
            return {'scale': struct.unpack_from('<3I', mem),
                    'angle': struct.unpack_from('<3h', mem, 16),
                    'translation': struct.unpack_from('<3i', mem, 24)}
        word = struct.unpack_from('<I', engine, pc-code_base)[0]
        op, rs, rt = word >> 26, (word >> 21) & 31, (word >> 16) & 31
        rd, sh, fn, imm = (word >> 11) & 31, (word >> 6) & 31, word & 63, sx(word)
        target, jump = pending, None
        if op == 0:
            if fn == 0: r[rd] = r[rt] << sh
            elif fn == 2: r[rd] = r[rt] >> sh
            elif fn == 3: r[rd] = sx(r[rt], 32) >> sh
            elif fn == 16: raise AssertionError('HI unexpectedly consumed')
            elif fn == 18: r[rd] = lo
            elif fn in (24, 25): lo = (r[rs]*r[rt]) & 0xFFFFFFFF
            elif fn == 33: r[rd] = r[rs]+r[rt]
            elif fn == 35: r[rd] = r[rs]-r[rt]
            elif fn == 36: r[rd] = r[rs] & r[rt]
            else: raise AssertionError(f'Unimplemented native function {fn}')
        elif op == 2: jump = ((pc+4) & 0xF0000000) | ((word & 0x3FFFFFF) << 2)
        elif op in (4, 5):
            if (r[rs] == r[rt]) == (op == 4): jump = pc+4+imm*4
        elif op == 1 and rt == 1:
            if sx(r[rs], 32) >= 0: jump = pc+4+imm*4
        elif op == 9: r[rt] = r[rs]+imm
        elif op == 12: r[rt] = r[rs] & (word & 65535)
        elif op == 13: r[rt] = r[rs] | (word & 65535)
        elif op == 15: r[rt] = (word & 65535) << 16
        elif op in (33, 35, 37, 41, 43):
            addr = (r[rs]+imm) & 0xFFFFFFFF
            size = 4 if op in (35, 43) else 2
            if matrix_angles is not None and op == 35 and addr >= code_base:
                r[rt] = u32(engine, addr-code_base)
                pc = target if target is not None else pc+4
                pending = jump
                continue
            if not 0 <= addr <= len(mem)-size: raise AssertionError('Oracle memory escape')
            if op in (41, 43):
                mem[addr:addr+size] = (r[rt] & ((1 << (size*8))-1)).to_bytes(size, 'little')
            else:
                r[rt] = int.from_bytes(mem[addr:addr+size], 'little', signed=op == 33)
        else: raise AssertionError(f'Unimplemented opcode {op} at {pc:x}')
        r = [v & 0xFFFFFFFF for v in r]
        r[0] = 0
        pc = target if target is not None else pc+4
        pending = jump
    raise AssertionError('Native handler did not reach matrix boundary')


def fixture_pose(state):
    return b''.join(struct.pack('<6h3HI', *state.get(i, {}).get('angle', (0,)*3),
        *state.get(i, {}).get('translation', (0,)*3),
        *state.get(i, {}).get('scale', (0,)*3),
        7 if set(state.get(i, {})) == {'angle', 'translation', 'scale'} else 0) for i in range(64))


class RigBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        disc = ROOT/'disc/Dragon Ball GT - Final Bout (USA).bin'
        if not disc.exists(): raise unittest.SkipTest('Private USA disc required')
        cls.archive, cls.menu, cls.exe, cls.engine = sources(disc)
        cls.rows = list(records(cls.archive, cls.menu))

    def test_geometry_binding_is_remapped_not_part_index(self):
        self.assertEqual(len(self.rows), 18)
        _, _, model_at, meshes, mapping = self.rows[0]
        self.assertEqual(model_at, 0xE000)
        self.assertEqual(len(meshes), 29)
        self.assertEqual(mapping['mesh'][3], 0)
        self.assertEqual(mapping['mesh'][2], 24)
        self.assertEqual(mapping['mesh'][6], 2)
        self.assertEqual(mapping['parents'][6], 5)
        self.assertEqual(mapping['parents'][5], 4)
        self.assertEqual(mapping['protected'], {1, 2})
        # Native converter's source cursor and optional six-halfword bounds.
        self.assertEqual(struct.unpack_from('<I', self.exe, 0x80011C7C-0x8000F800)[0], 0x26100014)
        self.assertEqual(struct.unpack_from('<I', self.exe, 0x80011C98-0x8000F800)[0], 0x32E20002)
        self.assertEqual(meshes[0]['bounds'], (-228, -346, -162, 228, 0, 150))
        self.assertTrue(all(mesh['bounds'] == mesh['decoded_vertex_bounds']
                            for _, _, _, model, _ in self.rows for mesh in model))
        handlers = {1: 0x80011EE0, 8: 0x800127C0, 9: 0x80012910, 10: 0x80012A80,
                    11: 0x80012BE8, 12: 0x80012D64, 13: 0x80012E20,
                    14: 0x80012EDC, 15: 0x80012FD0}
        for kind, address in handlers.items():
            self.assertEqual(u32(self.exe, 0x8002BD90-0x8000F800+4*kind), address)

    def test_rotation_axes_and_order_against_native_matrix_routine(self):
        initial = {'scale': (4096,)*3, 'angle': (0,)*3, 'translation': (0,)*3}
        dummy = {'payload': b'', 'op': 1, 'flags': 0}
        angles = [(0, 0, 0), (1024, 0, 0), (0, 1024, 0), (0, 0, 1024),
                  (-1024, 0, 0), (4090, -4090, 6), (-32768, 32767, 2048)]
        for _, table, _, _, _ in self.rows:
            angles += [v['angle'] for v in pose(raw_clip(self.archive, table, 1)).values() if 'angle' in v]
        for value in angles:
            self.assertEqual(local_matrix(self.exe, value),
                native_transform(self.exe, dummy, initial, matrix_angles=value))
        self.assertEqual(local_matrix(self.exe, (1024, 0, 0)),
                         ((4096, 0, 0), (0, 0, -4096), (0, 4096, 0)))
        print(f'Native RotMatrix oracle: {len(angles)} angle triples OK')

    def test_all_endpoint_packets_against_actual_native_decoder(self):
        tested = 0
        initial = {'angle': (-32760, 32760, 4090), 'scale': (4096,)*3,
                   'translation': (-2000, 2000, 10)}
        for _, table, _, _, _ in self.rows:
            for slot in (1, 2):
                for _, group in packets(raw_clip(self.archive, table, slot)):
                    for packet in group:
                        if packet['op'] not in (1, 5): continue
                        body = struct.pack('<HHHHI', 0x4F, 1, 3+len(packet['payload'])//4, 1, 0)
                        h = ((len(packet['payload'])//4+1) << 24 | packet['flags'] << 20 |
                             packet['op'] << 16 | packet['part'])
                        body += struct.pack('<I', h)+packet['payload']
                        actual = native_transform(self.engine, packet, initial)
                        expected = pose(body, {packet['part']: initial})[packet['part']]
                        self.assertEqual(actual, expected)
                        tested += 1
        self.assertGreater(tested, 700)
        print(f'Native disc transform oracle: {tested} endpoint packets OK')

    def test_own_bridges_native_decode_endpoints_and_new_interior(self):
        count, changed = 0, 0
        for _, table, _, _, mapping in self.rows:
            a, b = (pose(raw_clip(self.archive, table, slot)) for slot in (2, 1))
            own, parts = bridge(a, b, mapping)
            frames = packets(own)
            self.assertEqual(len(packets(raw_clip(self.archive, table, 1))), 1)
            self.assertEqual(len(packets(raw_clip(self.archive, table, 2))), 1)
            self.assertEqual([t for t, _ in frames], list(range(7)))
            self.assertFalse(set(parts) & mapping['protected'])
            final = pose(own, a)
            for carrier in mapping['protected']:
                self.assertEqual(final.get(carrier), a.get(carrier))
            for index, (_, group) in enumerate(frames):
                self.assertEqual({p['part'] for p in group if p['op'] != 9}, set(parts))
                for packet in group:
                    if packet['op'] == 9:
                        self.assertEqual(index, 6)
                        self.assertEqual(packet['flags'], 0)
                        self.assertEqual(native_transform(self.engine, packet, a[parts[0]]), 0)
                        self.assertEqual(u32(self.engine, 0x8004229C-0x8003DFA0), 0xAE020008)
                        continue
                    part = packet['part']
                    actual = native_transform(self.engine, packet, a[part])
                    if index == 0: self.assertEqual(actual, a[part])
                    elif index == 6: self.assertEqual(actual, b[part])
                    elif actual != a[part] and actual != b[part]: changed += 1
                    self.assertEqual(actual['scale'], a[part]['scale'])
                    count += 1
        self.assertGreater(changed, 100)
        print(f'Own bridge native oracle: {count} packets; {changed} new interior samples OK')

    def test_c_emitter_matches_disc_trajectories(self):
        compiler = (shutil.which('gcc') or str(Path.home()/
                    '.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/gcc.exe'))
        if not Path(compiler).is_file(): self.fail('Existing C test compiler unavailable')
        parent = Path(os.environ['TEMP'])/'opencode'
        self.assertTrue(parent.is_dir())
        # Preserve own artifacts. No cleanup/deletion and no retail fixture files.
        temp = Path(tempfile.mkdtemp(prefix='dbfb-rig-bridge-tests-', dir=parent))
        exe = temp/'rig-bridge-tests.exe'
        subprocess.run([compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-pedantic',
                        str(Path(__file__).with_name('test_rig_bridge_harness.c')), '-o', str(exe)], check=True)
        fixture, expected = bytearray(), bytearray()
        for _, table, _, _, mapping in self.rows:
            a, b = (pose(raw_clip(self.archive, table, slot)) for slot in (2, 1))
            own, selected = bridge(a, b, mapping)
            mask = sum(1 << p for p in selected)
            protected = sum(1 << p for p in mapping['protected'])
            fixture += struct.pack('<QQI', mask, protected, 6)+fixture_pose(a)+fixture_pose(b)
            expected += struct.pack('<I', len(own))+own
        result = subprocess.run([str(exe)], input=fixture, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(result.stdout, expected)
        print(f'C emitter: 18 records byte-identical; own test executable retained: {exe}')

    def test_boundaries_unknowns_cycles_and_scale_rejected(self):
        _, table, _, _, mapping = self.rows[0]
        a, b = (pose(raw_clip(self.archive, table, slot)) for slot in (2, 1))
        for ticks in (0, 1, 33):
            with self.assertRaises(ValueError): bridge(a, b, mapping, ticks)
        bad = {p: dict(v) for p, v in a.items()}
        del bad[3]['angle']
        with self.assertRaises(ValueError): bridge(bad, b, mapping)
        bad = {p: dict(v) for p, v in a.items()}
        bad[3]['scale'] = (1, 2, 3)
        with self.assertRaises(ValueError): bridge(bad, b, mapping)
        init = bytearray(raw_clip(self.archive, table, 0))
        # Change root parent 0 -> root itself: parser must reject the cycle.
        marker = struct.pack('<II', 0x02030001, 0)
        offset = init.index(marker)
        struct.pack_into('<I', init, offset+4, 1)
        with self.assertRaises(ValueError): rig(init)
        with self.assertRaises(ValueError): compact_model(b'\0'*32)
        own, _ = bridge(a, b, mapping)
        for truncated in (own[:-1], own[:12], own[:3]):
            with self.assertRaises(ValueError): packets(truncated)

    def test_shortest_arc_uses_turn_not_storage_width(self):
        self.assertEqual(arc(4090, 6), 12)
        self.assertEqual(arc(6, 4090), -12)
        self.assertEqual(arc(0, 2048), -2048)
        packed = {'op': 5, 'flags': 6, 'payload': struct.pack('<2I', 0x200 | (511 << 10), 64 | (64 << 10) | (64 << 20))}
        self.assertEqual(transform(packed)['angle'], (-512, 511, 0))
        self.assertEqual(transform(packed)['scale'], (4096,)*3)


if __name__ == '__main__':
    unittest.main()
