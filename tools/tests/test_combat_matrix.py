"""Integrated combat matrix over every locally mounted roster record and side."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_responsive import private_fixture
from test_responsive_evidence import ROOT
sys.path.insert(0, str(ROOT / 'tools'))


class CombatMatrixTests(unittest.TestCase):
    def test_all_local_records_both_sides(self):
        from combat_map import Iso
        from combat_moves import roster
        disc = ROOT / 'disc/Dragon Ball GT - Final Bout (USA).bin'
        if not disc.is_file():
            self.skipTest('Private local USA disc required')
        iso = Iso(disc)
        _, lba, size = next(f for f in iso.files() if f[0] == 'TITLE/BTCHARA.DAT')
        data = iso.read(lba, size)
        characters = roster(data)
        self.assertEqual(len(characters), 18)
        fixture = private_fixture() + b''.join(
            data[c['animation_table_offset']:c['animation_table_offset']+0x50800]
            for c in characters)
        compiler = os.environ.get('CC') or shutil.which('gcc') or r'C:\msys64\mingw64\bin\gcc.exe'
        parent = Path(os.environ['TEMP']) / 'opencode'
        self.assertTrue(parent.is_dir())
        build = Path(tempfile.mkdtemp(prefix='dbfb-combat-matrix-', dir=parent))
        binary = build / 'matrix.exe'
        command = [compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-I', str(ROOT / 'psxrecomp/runtime/include'),
                   str(Path(__file__).with_name('test_combat_matrix_harness.c')), '-o', str(binary)]
        env = dict(os.environ, PATH=str(Path(compiler).parent)+os.pathsep+os.environ['PATH'])
        compiled = subprocess.run(command, capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(compiled.returncode, 0, compiled.stdout+compiled.stderr)
        ran = subprocess.run([str(binary)], input=fixture, capture_output=True, env=env, timeout=60)
        output = (ran.stdout+ran.stderr).decode(errors='replace')
        print(output)
        self.assertEqual(ran.returncode, 0, output)
        self.assertIn('PASS integrated matrix: 942 variants', output)


if __name__ == '__main__':
    unittest.main(verbosity=2)
