"""R4 static evidence regressions against private disc/capture, no C build/game."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combat_camera import HEADER, verify, verify_exe
from combat_exe import ExeImage
from combat_map import BattleImage, ROOT, step40


class CameraEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        disc = ROOT / 'disc/Dragon Ball GT - Final Bout (USA).bin'
        captures = ROOT / 'build-release/vault/overlay_captures.json'
        if not disc.is_file() or not captures.is_file():
            raise unittest.SkipTest('Private USA disc/captures unavailable')
        cls.image = BattleImage(step40(disc)[0], captures)
        cls.header = HEADER.read_text(encoding='utf-8')

    def words(self, expected):
        for pc, word in expected:
            with self.subTest(pc=f'{pc:08X}'):
                self.assertEqual(self.image.word(pc), word)

    def test_selector_publishes_on_both_branches_and_lock_skips_updates(self):
        # The delay slot publishes even when BNE takes the scripted path.
        # Neither mode1 nor direct-node0 proves a cinematic-free shot.
        self.words(((0x80054EC0, 0x24020001), (0x80054EC4, 0x14620048),
                    (0x80054EC8, 0xACC30158), (0x80054ECC, 0x8CC20000),
                    (0x80054ED4, 0x14400095), (0x80055060, 0x8C848680),
                    (0x80055068, 0x14800013)))

    def test_context_reset_and_independent_script_producers(self):
        self.words(((0x80047F8C, 0x2C8201F0), (0x80047F9C, 0x24429FA0),
                    (0x80047FA4, 0xAC229D0C), (0x80054334, 0x0C011FDE),
                    (0x8004E960, 0x92230000), (0x8004E96C, 0xAC23A194),
                    (0x8004E984, 0xAC40006C), (0x8004EA24, 0xAC228680),
                    (0x8004EA38, 0xAC228664), (0x8004EA98, 0xAC22867C)))

    def test_transition_history_is_native_state_not_mod_scratch(self):
        self.words(((0x80044300, 0x8D230050), (0x80044328, 0xAD230070),
                    (0x80044340, 0xAD280084), (0x800476F8, 0x8CC20050),
                    (0x80047700, 0x00441023), (0x80047704, 0xACC200B0),
                    (0x8004472C, 0x252600B0), (0x80044744, 0x00431021),
                    (0x80044748, 0xAC820000), (0x80054F44, 0x0C0110AA),
                    (0x80054F90, 0x0C011209), (0x8004482C, 0x0C009214)))

    def test_probe_identity_and_historical_execution_match_private_image(self):
        checked = verify(self.image, self.header)
        self.assertEqual(checked['executed_seams'], 3)

    def test_wrong_image_is_rejected_before_semantic_claims(self):
        class OtherImage:
            data = b'unsupported camera image'
            base = 0x8003DFA0
        with self.assertRaisesRegex(ValueError, 'Unsupported STEP40'):
            verify(OtherImage(), self.header)

    def test_incorrect_production_guard_is_rejected(self):
        changed = self.header.replace('0xAC229D0Cu', '0xAC229D10u')
        with self.assertRaisesRegex(ValueError, 'guard mismatch'):
            verify(self.image, changed)

    def test_pre_seam_is_overwritten_before_matrix_delivery(self):
        # 442A8 (jal at 54F44) and 4778C (jal at 54F54) execute AFTER 54F34 and
        # rewrite context+0x50; the check word list pins both writers plus the
        # delivery call at 54F90 and the transition delta writer 476C0.
        checked = verify(self.image, self.header)
        self.assertEqual(checked['pre_seam_overwrite_words'], 16)
        self.words(((0x80054F88, 0x3C04800B), (0x80054F8C, 0x8C849D0C),
                    (0x80054F90, 0x0C011209), (0x80054F94, 0x24840050),
                    (0x80044320, 0xAD220004), (0x80044534, 0x080111D6),
                    (0x80044758, 0x3C03800B), (0x80047704, 0xACC200B0)))


class CameraMainExeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        exe = ROOT / 'disc/SLUS_004.93'
        if not exe.is_file():
            raise unittest.SkipTest('Private main EXE unavailable')
        cls.exe = ExeImage(exe)

    def test_general_delivery_reaches_builder_that_writes_matrix(self):
        # 44824 -> 24850; reads eye/at (6 words) PLUS +0x18 (ctx+0x68, negated
        # into 2413C at 248C0-248C4) and +0x1C (ctx+0x6C, gate at 24D48);
        # final 8-word store into 0x8003B920 at 24DF0-24E38.
        checked = verify_exe(self.exe)
        self.assertEqual(checked['exe_checked_words'], 30)
        self.assertEqual(self.exe.word(0x800248BC), 0x8E450018)   # lw a1,+0x18(s2)
        self.assertEqual(self.exe.word(0x80024D48), 0x8E44001C)   # lw a0,+0x1c(s2)
        self.assertEqual(self.exe.word(0x80024DF4), 0x24A5B920)   # 0x8003B920 target

    def test_projection_constants_and_gte_consumers_are_pinned(self):
        self.assertEqual(self.exe.word(0x80020578), 0x4A180001)   # RTPS
        self.assertEqual(self.exe.word(0x80021CD4), 0x4A280030)   # RTPT
        self.assertEqual(self.exe.word(0x800239C0), 0x2408EF9E)   # H
        self.assertEqual(self.exe.word(0x800239B4), 0x240803E8)   # OFY
        self.assertEqual(self.exe.word(0x8002399C), 0x24080155)   # DQB
        self.assertEqual(self.exe.word(0x800239A8), 0x24080100)   # ZSF3
        self.assertEqual(self.exe.word(0x800239CC), 0x3C080140)   # DQA

    def test_transition_delta_writer_words_are_exact(self):
        self.assertEqual(self.exe.word(0x80022C4C), 0x8C880000)   # matrix*vector
        self.assertEqual(self.exe.word(0x80022DAC), 0x8C880000)   # matrix multiply
        self.assertEqual(self.exe.word(0x8002413C), 0x27BDFFC0)   # roll/extra rotation
        self.assertEqual(self.exe.word(0x800241F4), 0x00804821)   # axis rotation builder

    def test_wrong_main_exe_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported main EXE hash'):
            ExeImage(ROOT / 'tools/combat_map.py')


if __name__ == '__main__':
    unittest.main()
