"""The real watchdog retains its deadline; passive counters do not suspend it."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.name == 'nt', 'Windows CPU-time accounting')
class StarvationGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which(os.environ.get('CC', 'gcc'))
        if not cc:
            raise unittest.SkipTest('Existing GCC required')
        cls.out = Path(tempfile.mkdtemp(prefix='dbfb-watchdog-',
                                      dir=Path(tempfile.gettempdir()) / 'opencode'))
        cls.exe = cls.out / 'watchdog.exe'
        runtime = ROOT / 'psxrecomp/runtime'
        subprocess.run([cc, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I', str(runtime / 'include'), str(runtime / 'src/starvation_ring.c'),
                        str(runtime / 'tests/test_starvation_gap.c'), '-o', str(cls.exe)],
                       check=True, timeout=60)

    def run_probe(self, mode, expected):
        out = self.out / mode
        out.mkdir()
        env = dict(os.environ)
        env.pop('PSX_STARVATION_TIMEOUT_US', None)
        result = subprocess.run([str(self.exe), mode], cwd=out, env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, expected, result.stderr)
        return out

    def test_busy_sleep_rewind_and_reset_accounting(self):
        self.run_probe('observe', 0)

    def test_real_busy_loop_still_aborts(self):
        out = self.run_probe('busy-abort', 2)
        meta = json.loads((out / 'starvation_dump.jsonl').read_text().splitlines()[0])['meta']
        self.assertGreater(meta['now_us'] - meta['last_heartbeat_us'], 4_000_000)
        self.assertGreater(meta['psx_cycle_count'], 1_000_000)

    def test_long_host_wait_is_recorded_and_still_aborts(self):
        out = self.run_probe('sleep-abort', 2)
        meta = json.loads((out / 'starvation_dump.jsonl').read_text().splitlines()[0])['meta']
        self.assertEqual(meta['check_gap_cpu_available'], 1)
        self.assertGreater(meta['check_gap_wall_us'], 4_000_000)
        self.assertLess(meta['check_gap_cpu_us'], meta['check_gap_wall_us'] / 2)
        self.assertEqual(meta['check_gap_guest_cycles'], 0)


if __name__ == '__main__':
    unittest.main()
