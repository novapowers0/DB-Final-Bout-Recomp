"""A smoke run must fail for crashes, unresumed pause or insufficient KOs."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combat_smoke import assess


class SmokeVerdictTests(unittest.TestCase):
    def report(self):
        return {'counters': {'counters': [
            {'name': 'dbfb.responsive.combat_poll', 'count': 10},
            {'name': 'dbfb.responsive.ko_impact', 'count': 3}]},
            'pause': [{'before': 0, 'paused': 1, 'resumed': 0}], 'process_exit': 0,
            'steps': [
                {'battle_code': True, 'object_stride': 21, 'fighters': [{'hp': 100}, {'hp': 100}]},
                {'battle_code': True, 'object_stride': 21, 'fighters': [{'hp': 0}, {'hp': 100}]},
                {'battle_code': False}] * 3}

    def test_three_kos_and_clean_quit(self):
        self.assertTrue(assess(self.report(), 3))

    def test_crash_after_combat_fails(self):
        report = self.report()
        report['process_exit'] = 2
        self.assertFalse(assess(report))

    def test_movement_requires_observed_native_hook(self):
        report = self.report()
        report['movement_requested'] = True
        self.assertFalse(assess(report))
        report['counters']['counters'].append({'name': 'dbfb.responsive.locomotion', 'count': 1})
        self.assertTrue(assess(report))

    def test_incomplete_session_fails(self):
        for change in ({'pause': []}, {'forced_shutdown': True}, {'error': 'lost connection'},
                       {'steps': []}, {'process_exit': 1},
                       {'pause': [{'before': 0, 'paused': 0, 'resumed': 1}]}):
            with self.subTest(change=change):
                report = self.report()
                report.update(change)
                self.assertFalse(assess(report))
        self.assertFalse(assess(self.report(), 4))
        report = self.report()
        report['savestate_requested'] = True
        report['savestate'] = {'save': {'last_ok': 1}}
        self.assertFalse(assess(report))
        report['savestate']['load'] = {'last_ok': 1}
        self.assertTrue(assess(report))

    def test_original_requires_native_completion_and_inert_plugin(self):
        report = self.report()
        report['expect_original'] = True
        report['counters'] = {'counters': []}
        self.assertTrue(assess(report, 3))
        report['counters']['counters'] = [{'name': 'dbfb.responsive.locomotion', 'count': 1}]
        self.assertFalse(assess(report, 3))
        report['counters']['counters'] = []
        report['steps'] = []
        self.assertFalse(assess(report, 1))


if __name__ == '__main__':
    unittest.main()
