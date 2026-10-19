"""The production host profiler must never suspend gameplay by default."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.name == 'nt', 'Windows-specific suspension policy')
class HostSamplerPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which(os.environ.get('CC', 'gcc'))
        if not cc:
            raise unittest.SkipTest('Existing GCC is required; nothing is installed')
        out = Path(tempfile.mkdtemp(prefix='dbfb-sampler-', dir=Path(tempfile.gettempdir()) / 'opencode'))
        cls.exe = out / 'host_sampler_policy.exe'
        runtime = ROOT / 'psxrecomp/runtime'
        subprocess.run([cc, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I', str(runtime / 'include'),
                        str(runtime / 'src/host_sampler.c'),
                        str(runtime / 'tests/test_host_sampler_policy.c'),
                        '-o', str(cls.exe)], check=True, timeout=60)
        print(f'Retained sampler policy test: {out}')

    def test_no_suspension_by_default(self):
        subprocess.run([str(self.exe), 'default'], check=True, timeout=10)

    def test_invalid_opt_in_does_not_suspend(self):
        subprocess.run([str(self.exe), 'invalid'], check=True, timeout=10)

    def test_explicit_diagnostic_still_samples(self):
        subprocess.run([str(self.exe), 'enabled'], check=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
