"""Production C motion compiler, with private mounted-disc fixtures via stdin."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combat_map import Iso, ROOT, BattleImage, step40
from combat_moves import roster


class MotionCompilerTests(unittest.TestCase):
    def test_production_motion_all_roster_entries(self):
        disc = ROOT / 'disc/Dragon Ball GT - Final Bout (USA).bin'
        if not disc.exists():
            self.skipTest('Local private disc required; synthetic readers remain testable')
        compiler = Path.home() / '.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/gcc.exe'
        self.assertTrue(compiler.is_file())
        iso = Iso(disc)
        _, lba, size = next(x for x in iso.files() if x[0] == 'TITLE/BTCHARA.DAT')
        data = iso.read(lba, size)
        characters = roster(data)
        self.assertEqual(len(characters), 18)
        fixture = b''.join(data[c['animation_table_offset']:c['animation_table_offset']+0x50800]
                           for c in characters)
        self.assertEqual(len(fixture), 18 * 0x50800)
        engine, _ = step40(disc)
        image = BattleImage(engine, ROOT / 'build-release/vault/overlay_captures.json')
        fixture = (engine[0x8004E530-image.base:0x8004F014-image.base] +
                   engine[0x800420EC-image.base:0x80042D10-image.base] + fixture)
        with tempfile.TemporaryDirectory(prefix='dbfb-motion-', dir=Path(os.environ['TEMP']) / 'opencode') as tmp:
            exe = Path(tmp) / 'motion.exe'
            subprocess.run([str(compiler), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT / 'psxrecomp/runtime/include'),
                            str(Path(__file__).with_name('test_motion_harness.c')), '-o', str(exe)], check=True)
            result = subprocess.run([str(exe)], input=fixture, capture_output=True, timeout=30)
            print(result.stdout.decode(errors='replace'))
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
