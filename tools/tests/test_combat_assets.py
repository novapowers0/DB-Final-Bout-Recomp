"""Synthetic, disc-free regression tests for the bounded resource reader."""
import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combat_assets import compressed_tables, script_tables, unpack_psdp


def packed(size, body):
    return b'Psdp' + struct.pack('<I', size) + body


class CombatAssetTests(unittest.TestCase):
    def test_literal_groups_and_consumed_extent(self):
        stream = packed(10, b'\xffABCDEFGH\x03IJ')
        body, consumed = unpack_psdp(stream + b'padding')
        self.assertEqual(body, b'ABCDEFGHIJ')
        self.assertEqual(consumed, len(stream))

    def test_overlapping_backreferences(self):
        self.assertEqual(unpack_psdp(packed(6, b'\x07abc\x60\x00'))[0], b'abcabc')
        self.assertEqual(unpack_psdp(packed(8, b'\x01A\x24\x00'))[0], b'AAAAAAAA')

    def test_references_before_output_are_zero_filled(self):
        self.assertEqual(unpack_psdp(packed(3, b'\x00\x40\x00'))[0], bytes(3))

    def test_malformed_streams_are_bounded_and_rejected(self):
        for data in (b'', b'Psdp', packed(0, b''), packed(0x200001, b''),
                     packed(1, b''), packed(1, b'\x01'), packed(3, b'\x00\x40'),
                     packed(3, b'\x00\x00\x00'), packed(2, b'\x00\x40\x00')):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    unpack_psdp(data)

    def test_table_candidates_keep_uncertainty_and_aliases(self):
        entries = list(range(64))
        entries[-2:] = [0, 0xFFFFFFFF]
        body = struct.pack('<I', 64 << 16) + struct.pack('<64I', *entries)
        body += struct.pack('<64I', *([0x01200001] * 64))
        candidates = script_tables(body)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['present_slots'], 63)
        self.assertEqual(candidates[0]['unique_starts'], 62)
        self.assertEqual(candidates[0]['classification'], 'structural_candidate_not_runtime_verified')
        self.assertNotIn('animation_count', candidates[0])
        self.assertFalse(script_tables(bytes(4096)))

    def test_multiple_blocks_and_invalid_headers(self):
        valid = packed(3, b'\x07abc')
        data = packed(0, b'') + valid + bytes(5) + valid
        blocks, rejected = compressed_tables(data)
        self.assertEqual(rejected, 1)
        self.assertEqual(len(blocks), 2)
        self.assertEqual([b['decoded_size'] for b in blocks], [3, 3])
        self.assertEqual(blocks[0]['decoded_sha256'], blocks[1]['decoded_sha256'])


if __name__ == '__main__':
    unittest.main()
