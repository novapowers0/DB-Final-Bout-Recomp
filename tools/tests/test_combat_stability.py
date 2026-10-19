"""Release diagnosis must not silently accept degraded runs or tainted payloads."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combat_stability import extract_checked, runtime_checks


class StabilityTests(unittest.TestCase):
    def test_runtime_failure_cannot_be_masked_by_clean_process_exit(self):
        report = {'exit_origin': 'tcp_quit', 'autocompile_degraded': 0,
                  'interp_unsupported': {'midblock_count': 0},
                  'unknown_dispatch_tail': {'total': 0}, 'host_sampler_max_suspend_us': 0}
        self.assertTrue(all(runtime_checks(report).values()))
        for changes in ({'exit_origin': 'starvation_watchdog'}, {'autocompile_degraded': 1},
                        {'interp_unsupported': {'midblock_count': 1}},
                        {'unknown_dispatch_tail': {'total': 1}}, {'host_sampler_max_suspend_us': 1}):
            with self.subTest(changes=changes):
                self.assertFalse(all(runtime_checks({**report, **changes}).values()))
        self.assertFalse(all(runtime_checks({}).values()))

    def archive(self, folder, files, sums=None):
        path = folder / 'test.zip'
        with zipfile.ZipFile(path, 'w') as z:
            for name, value in files.items():
                z.writestr(name, value)
            z.writestr('SHA256SUMS.json', json.dumps(sums if sums is not None else {
                k: hashlib.sha256(v).hexdigest() for k, v in files.items()}))
        return path

    def test_checked_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            archive = self.archive(folder, {'game.toml': b'config'})
            extract_checked(archive, folder / 'payload')
            self.assertEqual((folder / 'payload/game.toml').read_bytes(), b'config')

    def test_bad_hash_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            archive = self.archive(folder, {'game.toml': b'config'}, {'game.toml': '0' * 64})
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                extract_checked(archive, folder / 'payload')
            self.assertFalse((folder / 'payload').exists())

    def test_paths_and_personal_choices_rejected(self):
        for name in ('../escape', '/absolute', 'C:/drive', 'mods\\state.toml', 'mods/state.toml'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                archive = self.archive(folder, {name: b'private'})
                with self.assertRaises(ValueError):
                    extract_checked(archive, folder / 'payload')
                self.assertFalse((folder / 'payload').exists())

    def test_extra_file_not_in_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            archive = self.archive(folder, {'unexpected': b'bytes'}, {})
            with self.assertRaisesRegex(ValueError, 'inventory'):
                extract_checked(archive, folder / 'payload')


if __name__ == '__main__':
    unittest.main()
