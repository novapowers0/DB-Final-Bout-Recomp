"""Read-only integration checks against the owner's verified USA disc/captures.

Checks critical branch-delay and field identities behind the route metadata.
No payload fixtures are copied from retail assets into the repository.
"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combat_map import BattleImage, ROOT, native_routes, step40


class NativeRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        disc = ROOT / 'disc/Dragon Ball GT - Final Bout (USA).bin'
        captures = ROOT / 'build-release/vault/overlay_captures.json'
        if not disc.is_file() or not captures.is_file():
            raise unittest.SkipTest('Private USA disc/captures unavailable')
        cls.image = BattleImage(step40(disc)[0], captures)
        cls.report = native_routes(cls.image)

    def test_busy_route_distinguishes_delay_slot_and_both_motion_states(self):
        command = next(c for c in self.report['command_routes'] if c['command'] == 0x25)
        self.assertEqual([s['buttons_internal'] for s in command['steps']], [0x2000, 0x4000, 0x20])
        # Taken BNE executes the 98 delay slot; fallthrough later overwrites
        # v0 with AA, even if the subsequent BEQ is not taken. Flags20 wins.
        for pc, word in ((0x800607FC, 0x30820020), (0x80060800, 0x14400004),
                         (0x80060804, 0x24020098), (0x80060808, 0x30820040),
                         (0x80060810, 0x240200AA), (0x8006081C, 0xAC222808)):
            self.assertEqual(self.image.word(pc), word)
        self.assertEqual(command['fighter_cases'][0]['fighter_id'], 0)
        self.assertEqual(command['fighter_cases'][0]['conditional_actions'], [
            {'flags_all': 0x20, 'action': 0x98},
            {'flags_none': 0x20, 'flags_all': 0x40, 'action': 0xAA}])
        self.assertNotIn(1, [c['fighter_id'] for c in command['fighter_cases']])

    def test_confirmation_writes_attacker_field_and_consumer_clears_it(self):
        # s3=a0 is the attacking side, s5=opponent. Stores are at +2804,
        # not +2800 (which has unrelated bits with the same numerical masks).
        for pc, word in ((0x80062104, 0x00809821), (0x80062140, 0x2E750001),
                         (0x80062FE8, 0x34420080), (0x80062FF4, 0xAC222804),
                         (0x80063030, 0xAC222804), (0x80063228, 0xAC222804),
                         (0x800576C4, 0x30620080), (0x800576CC, 0x30620200),
                         (0x800576F8, 0xAC222804), (0x80057734, 0xAC232804),
                         (0x80057764, 0xAC222804), (0x80057F94, 0xAC232808)):
            self.assertEqual(self.image.word(pc), word)
        supported = set(self.report['continuation']['fighter_ids'])
        for producer in self.report['collision_confirmations']:
            self.assertEqual(producer['field'], 'attacker.control+4')
            self.assertEqual({c['fighter_id'] for c in producer['fighter_cases']}, supported)
        self.assertTrue(self.report['static_only'])

    def test_changed_binary_is_rejected_instead_of_reusing_semantics(self):
        class OtherImage:
            base = 0x8003DFA0
            data = b'not the verified STEP40'
        with self.assertRaisesRegex(ValueError, 'verified USA'):
            native_routes(OtherImage())


if __name__ == '__main__':
    unittest.main()
