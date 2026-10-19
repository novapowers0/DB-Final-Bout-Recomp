"""Offline parser/classifier tests for the measured move cards (no exe, no disc).

Synthetic traces pin the frame arithmetic: press onset, startup, impact,
recovery, advantage on hit, whiff recovery, observed guard windows, interrupted
attacks and the hit-stop counter diff. A sample table is then validated with the
same schema check the live tool runs on its private JSON.
"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combat_cards import (build_cards, classify_trial, combine_reports, damage_events,
                          parse_frame_sample, parse_state, parse_wtrace_entries,
                          select_pads, validate_cards)
from combat_cards import ROOT


def side(action=0, hp=1000, state=0, tick=100, x=0, z=0, cpu=False):
    return {'action': action, 'hp': hp, 'state': state, 'tick': tick, 'x': x, 'z': z,
            'flags': 0, 'ki': 50, 'last_command': -1, 'cpu': cpu, 'side': 0,
            'script_ptr': 0, 'velocity': 0, 'gate': 0, 'max_hp': 1000}


def simple(first, last, attacker_spans, defender_spans, word=0x1000):
    samples = {}
    for frame in range(first, last + 1):
        a = side(action=0, hp=1000)
        d = side(action=0, hp=1000, cpu=True)
        for entry in attacker_spans:
            if entry['start'] <= frame <= entry['end']:
                a.update({key: value for key, value in entry.items()
                          if key not in ('start', 'end')})
        for entry in defender_spans:
            if entry['start'] <= frame <= entry['end']:
                d.update({key: value for key, value in entry.items()
                          if key not in ('start', 'end')})
        pad = 0xFFFF if not (102 <= frame <= 107) else 0xFFFF ^ word
        samples[frame] = {'frame': frame, 'pad': pad, 'sides': [a, d]}
    return samples


def hit_events(frame=110, side_index=1, old=1000, new=900, seq=1):
    address = 0x728BC if side_index == 1 else 0x72840
    return [{'seq': seq, 'addr': address, 'old': old, 'new': new, 'width': 2,
             'frame': frame, 'pc': 0x80066E84, 'ra': 0}]


class ClassifierTests(unittest.TestCase):
    def test_hit_frame_arithmetic(self):
        samples = simple(100, 140,
                         [{'start': 104, 'end': 121, 'action': 0x66}],
                         [{'start': 110, 'end': 115, 'action': 0x53},
                          {'start': 110, 'end': 140, 'hp': 900}])
        metrics = classify_trial(samples, hit_events(), 0x1000,
                                 counters={'dbfb.responsive.hitstop_frame': 3})
        self.assertEqual(metrics['outcome'], 'hit')
        self.assertEqual(metrics['press_frame'], 102)
        self.assertEqual(metrics['attack_start_frame'], 104)
        self.assertEqual(metrics['action_id'], 0x66)
        self.assertEqual(metrics['impact_frame'], 110)
        self.assertEqual(metrics['startup'], 8)
        self.assertEqual(metrics['startup_from_action'], 6)
        self.assertEqual(metrics['attacker_recovery_frame'], 122)
        self.assertEqual(metrics['recovery_hit'], 12)
        self.assertEqual(metrics['defender_recovery_frame'], 116)
        self.assertEqual(metrics['advantage_hit'], -6)
        self.assertEqual(metrics['hitstop_vblanks'], 3)
        self.assertEqual(metrics['defender_hp_loss'], 100)

    def test_whiff_measures_recovery_without_impact(self):
        samples = simple(100, 140,
                         [{'start': 104, 'end': 117, 'action': 0x66}], [])
        metrics = classify_trial(samples, [], 0x1000)
        self.assertEqual(metrics['outcome'], 'whiff')
        self.assertNotIn('startup', metrics)
        self.assertEqual(metrics['whiff_recovery'], 14)
        self.assertEqual(metrics['attacker_hp_loss'], 0)
        self.assertEqual(metrics['defender_hp_loss'], 0)

    def test_blocked_uses_observed_guard_window(self):
        samples = simple(100, 140,
                         [{'start': 104, 'end': 117, 'action': 0x66}],
                         [{'start': 104, 'end': 119, 'action': 0x21}])
        metrics = classify_trial(samples, [], 0x1000)
        self.assertEqual(metrics['outcome'], 'blocked')
        self.assertEqual(metrics['block_start_frame'], 104)
        self.assertEqual(metrics['guard_exit_frame'], 120)
        self.assertEqual(metrics['advantage_block'], 2)
        self.assertNotIn('advantage_hit', metrics)

    def test_guard_with_damage_is_not_a_block(self):
        samples = simple(100, 140,
                         [{'start': 104, 'end': 117, 'action': 0x66}],
                         [{'start': 104, 'end': 119, 'action': 0x21},
                          {'start': 110, 'end': 140, 'hp': 900}])
        metrics = classify_trial(samples, hit_events(), 0x1000)
        self.assertEqual(metrics['outcome'], 'hit')

    def test_interrupted_attack_is_not_a_whiff(self):
        events = hit_events(frame=112, side_index=0, old=1000, new=950)
        samples = simple(100, 140,
                         [{'start': 104, 'end': 120, 'action': 0x66}], [])
        metrics = classify_trial(samples, events, 0x1000)
        self.assertEqual(metrics['outcome'], 'interrupted')
        self.assertEqual(metrics['interruption_frame'], 112)
        self.assertEqual(metrics['attacker_hp_loss'], 50)

    def test_busy_press_is_rejected(self):
        samples = simple(100, 140,
                         [{'start': 100, 'end': 121, 'action': 0x66}], [])
        metrics = classify_trial(samples, [], 0x1000)
        self.assertEqual(metrics['outcome'], 'busy_at_press')

    def test_missing_input_is_reported(self):
        samples = simple(100, 140,
                         [{'start': 104, 'end': 121, 'action': 0x66}], [])
        for frame in samples:
            samples[frame]['pad'] = 0xFFFF
        metrics = classify_trial(samples, [], 0x1000)
        self.assertEqual(metrics['outcome'], 'no_input')

    def test_air_flag_recorded_at_action_start(self):
        samples = simple(100, 140,
                         [{'start': 104, 'end': 121, 'action': 0x68, 'state': 0x20}], [])
        metrics = classify_trial(samples, [], 0x1000)
        self.assertTrue(metrics['air'])
        self.assertEqual(metrics['outcome'], 'whiff')

    def test_defender_stun_end_from_action_write_event(self):
        samples = simple(100, 130,
                         [{'start': 104, 'end': 121, 'action': 0x66}],
                         [{'start': 110, 'end': 130, 'action': 0x53},
                          {'start': 110, 'end': 130, 'hp': 900}])
        events = hit_events() + [
            {'seq': 2, 'addr': 0x72884, 'old': 0x80000053, 'new': 0x80000053,
             'width': 4, 'frame': 126, 'pc': 0x8004EEAC, 'ra': 0},
            {'seq': 3, 'addr': 0x72884, 'old': 0x80000053, 'new': 0x80000000,
             'width': 4, 'frame': 128, 'pc': 0x8004EEAC, 'ra': 0}]
        metrics = classify_trial(samples, events, 0x1000)
        self.assertEqual(metrics['outcome'], 'hit')
        self.assertEqual(metrics['defender_recovery_frame'], 128)
        self.assertEqual(metrics['defender_next_action'], 0)
        self.assertEqual(metrics['advantage_hit'], 6)

    def test_defender_recovery_ignores_writes_after_second_hit(self):
        samples = simple(100, 135,
                         [{'start': 104, 'end': 121, 'action': 0x66}],
                         [{'start': 110, 'end': 135, 'action': 0x53},
                          {'start': 110, 'end': 135, 'hp': 900}])
        events = hit_events() + [
            {'seq': 2, 'addr': 0x728BC, 'old': 900, 'new': 880,
             'width': 2, 'frame': 124, 'pc': 0x80066E90, 'ra': 0},
            {'seq': 3, 'addr': 0x72884, 'old': 0x80000053, 'new': 0x80000000,
             'width': 4, 'frame': 128, 'pc': 0x8004EEAC, 'ra': 0}]
        metrics = classify_trial(samples, events, 0x1000)
        self.assertEqual(metrics['outcome'], 'hit')
        self.assertNotIn('advantage_hit', metrics)

    def test_active_low_pad_semantics(self):
        samples = simple(100, 140,
                         [{'start': 104, 'end': 121, 'action': 0x66}], [])
        for frame in samples:
            samples[frame]['sides'][0]['action'] = 0
        for frame in range(106, 122):
            samples[frame]['sides'][0]['action'] = 0x66
        for frame in range(110, 141):
            samples[frame]['sides'][1]['hp'] = 900
        for frame in samples:
            samples[frame]['pad'] = 0xFFFF
        samples[105]['pad'] = 0xEFFF
        metrics = classify_trial(samples, hit_events(), 0x1000)
        self.assertEqual(metrics['press_frame'], 105)
        self.assertEqual(metrics['press_frames'], 1)
        self.assertEqual(metrics['startup'], 5)


class ParserTests(unittest.TestCase):
    def test_parse_state_block(self):
        blob = bytearray(0x204)
        blob[0x08:0x0C] = (0x66).to_bytes(4, 'little')
        blob[0x40:0x42] = (1000).to_bytes(2, 'little')
        blob[0x42:0x44] = (50).to_bytes(2, 'little')
        blob[0x56:0x58] = (0xFFFF).to_bytes(2, 'little')
        blob[0x7C + 0x08:0x7C + 0x0C] = (0x53).to_bytes(4, 'little')
        blob[0x7C + 0x40:0x7C + 0x42] = (900).to_bytes(2, 'little')
        blob[0x7C:0x7C + 4] = (1).to_bytes(4, 'little')
        blob[0xF8 + 4:0xF8 + 6] = (77).to_bytes(2, 'little')
        blob[0x202:0x204] = (21).to_bytes(2, 'little')
        state = parse_state(bytes(blob))
        self.assertEqual(state['sides'][0]['action'], 0x66)
        self.assertEqual(state['sides'][0]['hp'], 1000)
        self.assertEqual(state['sides'][0]['last_command'], -1)
        self.assertEqual(state['sides'][1]['action'], 0x53)
        self.assertEqual(state['sides'][1]['hp'], 900)
        self.assertTrue(state['sides'][1]['cpu'])
        self.assertEqual(state['sides'][0]['tick'], 77)
        self.assertEqual(state['object_stride'], 21)

    def test_parse_frame_sample_offsets(self):
        control = bytearray(0x7C)
        control[0x08:0x0C] = (0x64).to_bytes(4, 'little')
        script = bytearray(0x60)
        script[0x04:0x06] = (9).to_bytes(2, 'little')
        script[0x30 + 0x04:0x30 + 0x06] = (3).to_bytes(2, 'little')
        sample = parse_frame_sample(7, 0xEFFF, bytes(control).hex() + bytes(control).hex(),
                                    bytes(script).hex())
        self.assertEqual(sample['frame'], 7)
        self.assertEqual(sample['pad'], 0xEFFF)
        self.assertEqual(sample['sides'][0]['action'], 0x64)
        self.assertEqual(sample['sides'][0]['tick'], 9)
        self.assertEqual(sample['sides'][1]['tick'], 3)

    def test_parse_wtrace_entries_sorts_by_seq(self):
        reply = {'entries': [
            {'seq': 2, 'addr': '0x00072840', 'old': '0x000003E8', 'new': '0x00000384',
             'w': 2, 'frame': 9, 'pc': '0x80066E84', 'ra': '0x80060000'},
            {'seq': 1, 'addr': '0x000728BC', 'old': '0x000003E8', 'new': '0x00000384',
             'w': 2, 'frame': 8, 'pc': '0x80066E84', 'ra': '0x80060000'}]}
        entries = parse_wtrace_entries(reply)
        self.assertEqual([e['seq'] for e in entries], [1, 2])
        self.assertEqual(entries[0]['addr'], 0x728BC)

    def test_damage_events_are_side_mapped(self):
        events = parse_wtrace_entries({'entries': [
            {'seq': 1, 'addr': '0x00072840', 'old': '0x000003E8', 'new': '0x000003E8',
             'w': 2, 'frame': 5, 'pc': '0x1', 'ra': '0x2'},
            {'seq': 2, 'addr': '0x000728BC', 'old': '0x000003E8', 'new': '0x00000384',
             'w': 2, 'frame': 6, 'pc': '0x3', 'ra': '0x4'},
            {'seq': 3, 'addr': '0x000728BC', 'old': '0x00000384', 'new': '0x000003E8',
             'w': 2, 'frame': 7, 'pc': '0x5', 'ra': '0x6'}]})
        self.assertEqual(damage_events(events, 0), [])
        self.assertEqual(len(damage_events(events, 1)), 1)
        self.assertEqual(damage_events(events, 1)[0]['loss'], 100)

    def test_select_pads_keeps_filled_records_without_flag(self):
        pads = select_pads([
            {'frame': 10, 'available': False},
            {'frame': 11, 'pad': '0xEFFF', 'verify': 1},
            {'frame': 12, 'pad': '0xFFFF', 'verify': 1}])
        self.assertEqual(pads, {11: 0xEFFF, 12: 0xFFFF})
        self.assertEqual(select_pads([{'frame': 1, 'available': False}]), {})


class CardTableTests(unittest.TestCase):
    def trial(self, name, kind, metrics, word):
        steps = ({'word': word, 'frames': 6},)
        return {'spec': {'name': name, 'kind': kind, 'steps': steps}, 'word': word,
                'metrics': metrics}

    def hit(self, word=0x1000, startup=8, advantage=-6):
        return {'outcome': 'hit', 'word': hex(word), 'startup': startup,
                'startup_from_action': startup - 2, 'recovery_hit': 12,
                'advantage_hit': advantage, 'whiff_recovery': 20,
                'hitstop_vblanks': 3, 'tick_hold_frames': 2,
                'distance_at_action': 1500, 'action_id': 0x66}

    def test_sample_table_is_coherent(self):
        cards = build_cards([
            self.trial('ground_square', 'ground', self.hit(), 0x1000),
            self.trial('ground_square', 'ground', self.hit(startup=9, advantage=-5), 0x1000),
            self.trial('ground_square', 'ground',
                       {'outcome': 'whiff', 'word': hex(0x1000), 'whiff_recovery': 22}, 0x1000)])
        self.assertEqual(validate_cards(cards), [])
        card = cards['ground_square']
        self.assertEqual(card['outcomes'], {'hit': 2, 'whiff': 1})
        self.assertEqual(card['stats']['startup']['n'], 2)
        self.assertEqual(card['stats']['startup']['min'], 8)
        self.assertEqual(card['stats']['startup']['max'], 9)
        self.assertEqual(card['stats']['advantage_hit']['median'], -5.5)
        self.assertEqual(card['stats']['hit_action_ids'], [0x66])

    def test_validate_rejects_broken_stats(self):
        cards = {'x': {'spec': 'x', 'kind': 'ground', 'outcomes': {'hit': 1},
                       'stats': {'startup': {'n': 0}}, 'conditions': {}}}
        self.assertTrue(validate_cards(cards))
        cards = {'x': {'spec': 'x', 'kind': 'nope', 'outcomes': {'hit': 1},
                       'stats': {}, 'conditions': {}}}
        self.assertTrue(validate_cards(cards))
        self.assertTrue(validate_cards({}))

    def test_combine_reports_merges_measured_trials(self):
        spec = {'name': 'ground_square', 'kind': 'ground',
                'steps': ({'word': 0x1000, 'frames': 6},)}
        first = {'source': 'a', 'coverage': {'ground_square': {'valid': 1}},
                 'trials': [{'spec': spec, 'metrics': {'outcome': 'hit', 'startup': 20,
                                                       'advantage_hit': 2}}]}
        second = {'source': 'b', 'trials': [
            {'spec': spec, 'metrics': {'outcome': 'hit', 'startup': 18, 'advantage_hit': 40}},
            {'spec': spec, 'metrics': {'outcome': 'no_action'}}]}
        combined = combine_reports([first, second])
        self.assertEqual(combined['trials'], 3)
        self.assertEqual(validate_cards(combined['cards']), [])
        self.assertEqual(combined['cards']['ground_square']['stats']['startup']['n'], 2)
        self.assertEqual(combined['cards']['ground_square']['outcomes'],
                         {'hit': 2, 'no_action': 1})
        self.assertEqual([source['source'] for source in combined['sources']], ['a', 'b'])
        again = combine_reports([{**combined, 'source': 'combined'}])
        self.assertEqual(again['trials'], 3)
        self.assertEqual(validate_cards(again['cards']), [])

    def test_aerial_card_requires_kind_and_air_confirmation(self):
        cards = build_cards([
            self.trial('air_square', 'aerial',
                       dict(self.hit(), air=True, outcome='hit'), 0x1000),
            self.trial('air_square', 'aerial',
                       dict(self.hit(), air=False, outcome='hit'), 0x1000)])
        self.assertEqual(validate_cards(cards), [])
        self.assertEqual(cards['air_square']['air_confirmed_samples'], 1)


if __name__ == '__main__':
    unittest.main()
