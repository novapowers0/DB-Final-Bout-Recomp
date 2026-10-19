"""Exercise the real publication pipeline, including DONE before thread exit."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.name == 'nt', 'Windows worker handoff')
class AutocompilePolicyTests(unittest.TestCase):
    def test_publication_and_nonblocking_worker_completion(self):
        cc = shutil.which(os.environ.get('CC', 'gcc'))
        if not cc:
            self.skipTest('Existing GCC required')
        out = Path(tempfile.mkdtemp(prefix='dbfb-autocompile-',
                                  dir=Path(tempfile.gettempdir()) / 'opencode'))
        exe = out / 'publication.exe'
        runtime = ROOT / 'psxrecomp/runtime'
        subprocess.run([cc, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-DPSX_AUTOCOMPILE_TEST=1', '-I', str(runtime / 'include'),
                        str(runtime / 'src/autocompile.c'),
                        str(runtime / 'tests/test_autocompile_publication.c'), '-o', str(exe)],
                       check=True, timeout=60)
        result = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True, timeout=12)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('DONE-before-thread-exit never blocks', result.stdout)


if __name__ == '__main__':
    unittest.main()
