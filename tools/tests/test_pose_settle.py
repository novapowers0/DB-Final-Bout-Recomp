"""Production publishing + native-MIPS proof for the new action6 transition."""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from combat_rigclip import ROOT, packets, pose, raw_clip, sources, animation_tables
from combat_moves import roster
from test_combat_rigclip import native_transform


class NativeSettleTests(unittest.TestCase):
    def test_production_publication_and_native_relative_handoff(self):
        disc = ROOT/'disc/Dragon Ball GT - Final Bout (USA).bin'
        if not disc.exists(): self.skipTest('Private USA disc required')
        archive, _, _, engine = sources(disc)
        chars, tables = roster(archive), animation_tables(archive)
        fixture = engine[0x8004E530-0x8003DFA0:0x8004F014-0x8003DFA0]
        fixture += engine[0x800420EC-0x8003DFA0:0x80042D10-0x8003DFA0]
        fixture += b''.join(archive[c['animation_table_offset']:c['animation_table_offset']+0x50800] for c in chars)
        parent = Path(os.environ['TEMP'])/'opencode'
        self.assertTrue(parent.is_dir())
        out = Path(tempfile.mkdtemp(prefix='dbfb-settle-test-', dir=parent))
        compiler = Path.home()/'.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/gcc.exe'
        exe = out/'settle-tests.exe'
        subprocess.run([str(compiler), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I', str(ROOT/'psxrecomp/runtime/include'),
                        str(Path(__file__).with_name('test_pose_settle_harness.c')), '-o', str(exe)], check=True)
        result = subprocess.run([str(exe)], input=fixture, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(len(result.stdout), 912)
        own = packets(result.stdout)
        stock = packets(raw_clip(archive, tables[0], 105))
        self.assertEqual([tick for tick, _ in own], [1, 2, 3, 4, 5])
        # All original packets, including carriers and end, unchanged in order.
        for (_, a), (_, b) in zip(own, stock):
            self.assertEqual(a[2:], b)
            self.assertEqual([(p['part'], p['op'], p['flags']) for p in a[:2]], [(8, 1, 3), (9, 1, 3)])
        changes = 0
        for seed in (-32760, 0, 32760):
            for joint in (8, 9):
                initial = {'angle': (seed, seed+2, seed+4), 'translation': (-50, 12, 24), 'scale': (4096,)*3}
                a, b = dict(initial), dict(initial)
                for (tick, own_group), (_, stock_group) in zip(own, stock):
                    for packet in own_group:
                        if packet['part'] == joint and packet['op'] in (1, 5): a = native_transform(engine, packet, a)
                    for packet in stock_group:
                        if packet['part'] == joint and packet['op'] in (1, 5): b = native_transform(engine, packet, b)
                    self.assertEqual(a['translation'], b['translation'])
                    self.assertEqual(a['scale'], b['scale'])
                    if tick < 5: changes += a['angle'] != b['angle']
                self.assertEqual(a, b)  # exact modulo16 handoff, arbitrary entry
        self.assertGreater(changes, 12)
        source2 = pose(raw_clip(archive, tables[0], 2))
        final = pose(result.stdout, source2)
        expected = pose(raw_clip(archive, tables[0], 105), source2)
        self.assertEqual(final, expected)
        # Native timing/entry guarantee is NOT inferred from slot numbers.
        action = chars[0]['actions'][6]
        self.assertEqual([(e['opcode'], e['operand'], e['duration']) for e in action['events']],
                         [(0x20, 2, 1), (0x20, 105, 0), (0, 0, 0)])
        print(f'Native-owned settle PASS: both sides, 17 untouched records, restored group pointer, {changes} distinct inner poses; {exe}')


if __name__ == '__main__': unittest.main()
