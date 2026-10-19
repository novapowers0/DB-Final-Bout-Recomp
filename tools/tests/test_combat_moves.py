"""Disc-free boundary/timing checks for the action and animation readers."""
import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combat_assets import script_tables
from combat_moves import action, animation_tables, clip, move_card


def group(tick, packets=1, payload=(0x02350003, 0)):
    return struct.pack('<HHI', 2 + len(payload), packets, tick) + struct.pack('<' + 'I' * len(payload), *payload)


class CombatMoveTests(unittest.TestCase):
    def test_special_routes_keep_timings_and_adjust_only_positive_costs(self):
        for move, command, coordinated in ((0x78, 1, False), (0x7B, 1, True),
                                            (0x7E, 0, False), (0x81, 0, True)):
            for cost in (80, 100, 40, 50, 0, -1):
                with self.subTest(move=move, cost=cost):
                    data = struct.pack('<5I', 0x08200090, 0x02840000,
                                       ((cost & 255) << 24) | 7, 9, 0)
                    parsed = dict(action(data, 0, len(data)), id=move)
                    card = move_card({'roster_index': 0, 'actions': [parsed]}, parsed)
                    self.assertEqual(card['standard_static_ticks'], card['source_static_ticks'])
                    self.assertEqual(card['checkpoints'][1]['standard_ki_cost'],
                                     max(1, cost*4//5) if cost > 0 else cost)
                    self.assertEqual(card['native_special_route']['command'], command)
                    self.assertEqual(card['native_special_route']['coordinated'], coordinated)
                    self.assertFalse(card['standard_variant_candidate'])

    def test_audio_bank_is_not_an_action_jump(self):
        parsed = action(struct.pack('<2I', 0x01607801, 0), 0, 8)
        self.assertEqual(parsed['events'][0]['name'], 'audio_bank_event')
        self.assertFalse(parsed['contains_control'])

    def test_audio_channel_event_is_not_fighter_flag_producer(self):
        parsed = action(struct.pack('<2I', 0x01610080, 0), 0, 8)
        self.assertEqual(parsed['events'][0]['name'], 'audio_channel_event')
        self.assertFalse(parsed['contains_control'])

    def test_static_card_reports_cost_without_inventing_frame_data(self):
        data = struct.pack('<7I', 0x05200078, 0x02840000, 0x05000001,
                           0, 0x01230000, 0, 0)
        # A spawn has five words; bound this fixture to attack parameters only.
        data = data[:16] + struct.pack('<I', 0)
        parsed = dict(action(data, 0, len(data)), id=0x72)
        card = move_card({'roster_index': 0, 'actions': [parsed]}, parsed)
        self.assertEqual(card['checkpoints'][1]['native_ki_cost'], 5)
        self.assertEqual(card['checkpoints'][1]['standard_ki_cost'], 3)
        self.assertEqual(card['source_static_ticks'], 7)
        self.assertEqual(card['standard_static_ticks'], 4)
        self.assertIsNone(card['measured_startup_active_recovery'])
        self.assertIsNone(card['character_and_move_names'])
        self.assertTrue(card['standard_variant_candidate'])

    def test_signed_cost_and_aliases_are_preserved(self):
        data = struct.pack('<4I', 0x00840000, 0xFF000001, 0, 0)
        parsed = dict(action(data, 0, len(data)), id=0x64)
        alias = dict(parsed, id=0x65)
        card = move_card({'roster_index': 3, 'actions': [parsed, alias]}, parsed)
        self.assertEqual(card['checkpoints'][0]['native_ki_cost'], -1)
        self.assertEqual(card['action_aliases'], ['0x65'])
        self.assertFalse(card['standard_variant_candidate'])

    def test_real_empty_handler_opcodes_are_valid_starts(self):
        # Real DB tables use 0x83 as their first event. Omitting it silently
        # discarded every character in the initial resource inventory.
        data = struct.pack('<I64I', 64 << 16 | 0x4244, *range(64))
        data += struct.pack('<64I', *([0x00830000, 0x00010000] * 32))
        self.assertEqual(len(script_tables(data)), 1)

    def test_operands_are_not_misidentified_as_events(self):
        words = [0x01410000, 0xDEADBEEF, 0xFFFFFFFF, 0xCC00CC00,
                 0x02800000, 0xFF00FF00, 0xEE00EE00,
                 0x03810002, 0x04050607, 0]
        parsed = action(struct.pack('<10I', *words), 0, 40)
        self.assertEqual([e['opcode'] for e in parsed['events']], [0x41, 0x80, 0x81, 0])
        self.assertEqual([e['tick'] for e in parsed['events']], [0, 1, 3, 6])
        self.assertEqual(parsed['static_ticks'], 6)
        self.assertTrue(parsed['contains_control'])
        self.assertTrue(parsed['waits_animation'])

    def test_end_wait_preserves_opaque_trailing_data(self):
        parsed = action(struct.pack('<4I', 0x00200001, 0, 0xFF3C0000, 0x100), 0, 16)
        self.assertEqual(len(parsed['events']), 2)
        self.assertEqual(parsed['trailing_bytes'], 8)

    def test_truncation_and_unknown_events_rejected(self):
        for data, start, end in [(b'\0' * 8, 1, 8), (b'\0' * 8, 0, 12),
                                 (struct.pack('<I', 0x00410000), 0, 4),
                                 (struct.pack('<I', 0x007F0000), 0, 4)]:
            with self.subTest(data=data, start=start, end=end), self.assertRaises(ValueError):
                action(data, start, end)

    def test_frame_groups_have_separate_times_and_packet_counts(self):
        body = struct.pack('<HH', 0x4F, 2) + group(0) + group(5, 2, (1, 2, 3))
        parsed = clip(body, 0, len(body))
        self.assertEqual([g['tick'] for g in parsed['groups']], [0, 5])
        self.assertEqual([g['packets'] for g in parsed['groups']], [1, 2])
        self.assertEqual(parsed['decoded_bytes'], len(body))
        self.assertEqual(parsed['last_tick'], 5)
        self.assertNotIn('bone_count', parsed)

    def test_bad_frames_rejected_before_crossing_boundaries(self):
        for body in [b'', struct.pack('<HH', 0x4F, 0),
                     struct.pack('<HH', 0x4F, 1) + group(0)[:-1],
                     struct.pack('<HH', 0x4F, 2) + group(1) + group(1),
                     struct.pack('<HHHHI', 0x4F, 1, 2, 1, 0),
                     struct.pack('<HHHHI', 0x4F, 1, 20, 1, 0)]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                clip(body, 0, len(body))

    def test_animation_offsets_are_bytes_and_keep_aliases(self):
        first = struct.pack('<HH', 0x4F, 1) + group(0)
        second = struct.pack('<HH', 0x4F, 1) + group(2)
        data = struct.pack('<HH32I', 0x826A, 32, *([0, len(first)] * 16)) + first + second
        tables = animation_tables(data)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]['unique_offsets'], 2)
        self.assertEqual(tables[0]['slots'], 32)
        self.assertEqual(tables[0]['clips'][len(first)]['last_tick'], 2)


if __name__ == '__main__':
    unittest.main()
