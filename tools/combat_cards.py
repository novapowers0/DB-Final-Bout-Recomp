"""Measured per-move cards: startup/impact/recovery and advantage in game VBlanks.

Every clock here is the retail one, never the host clock: control+8 (action
byte), script+0/+4 (pointer and countdown tick) and the runtime's per-frame RAM
snapshot ring served by `read_frame_ram`. Write traces (`wtrace_add/dump`) give
the exact frame and producer PC of HP/action/flag stores. Field anchors are the
ones verified in COMBATE_MAPA.md (control 0x80072800/0x7C, script
0x800728F8/0x30); nothing is inferred beyond what the private evidence shows.

A trial presses a native pad word (active-low bytes, injected through the debug
server so the stock recognizer still runs), then reconstructs the frame window
from the ring and classifies it:

- startup: press frame -> impact (HP store of the defender, by wtrace frame)
- recovery: impact -> first frame the attacker's action is neutral/guard again
- advantage on hit: defender's first post-stun action frame minus the
  attacker's recovery frame (positive = attacker acts first)
- hit-stop: delta of the plugin's own VBlank counter over the same window,
  never a host stopwatch; the direct tick-hold measurement is reported too
- block: only when a guard action (0x21/0x22/0x23) is actually observed and the
  defender took no damage; otherwise the card says null instead of guessing

The output JSON is private: it may contain raw retail memory windows and is
written only under the caller-provided private folder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import socket
import subprocess
import time

from combat_live import query
from combat_map import ROOT
from combat_smoke import assess

CONTROL_BASE = 0x80072800
CONTROL_STRIDE = 0x7C
SCRIPT_BASE = 0x800728F8
SCRIPT_STRIDE = 0x30
BATTLE_CODE_ADDR = 0x80054A60
BATTLE_CODE = 0x84242856
OBJECT_STRIDE_ADDR = 0x80072A00
PAUSE_ADDR = 0x800A868C
STATE_READ_LEN = 0x204
NEUTRAL_MAX = 0x23
GUARD_ACTIONS = (0x21, 0x22, 0x23)
AIR_FLAG = 0x20
HP_RANGES = {0: (0x72840, 0x72842), 1: (0x728BC, 0x728BE)}
ACTION_RANGES = {0: (0x72808, 0x7280C), 1: (0x72884, 0x72888)}

WT_RANGES = ((0x72800, 0x72804), (0x72804, 0x72808), (0x72808, 0x7280C),
             (0x72840, 0x72842), (0x72842, 0x72844),
             (0x7287C, 0x72880), (0x72880, 0x72884), (0x72884, 0x72888),
             (0x728BC, 0x728BE), (0x728BE, 0x728C0))
SNAPSHOT_REGIONS = ((0x80072800, 0x7C), (0x8007287C, 0x7C), (0x800728F8, 0x60))
SNAPSHOT_MAX_FRAME_SPAN = 200
WINDOW_CAP = 150

GROUND_SPECS = (
    {'name': 'ground_square', 'kind': 'ground', 'steps': ({'word': 0x1000, 'frames': 6},)},
    {'name': 'ground_triangle', 'kind': 'ground', 'steps': ({'word': 0x8000, 'frames': 6},)},
    {'name': 'ground_up', 'kind': 'ground', 'steps': ({'word': 0x0010, 'frames': 6},)},
    {'name': 'ground_cross', 'kind': 'ground', 'steps': ({'word': 0x2000, 'frames': 6},)},
    {'name': 'ground_circle', 'kind': 'ground', 'steps': ({'word': 0x4000, 'frames': 6},)},
)
AERIAL_SPECS = (
    {'name': 'air_triangle', 'kind': 'aerial', 'steps': ({'word': 0x8000, 'frames': 6, 'after_jump': True},)},
    {'name': 'air_circle', 'kind': 'aerial', 'steps': ({'word': 0x4000, 'frames': 6, 'after_jump': True},)},
    {'name': 'air_square', 'kind': 'aerial', 'steps': ({'word': 0x1000, 'frames': 6, 'after_jump': True},)},
)
JUMP_CANDIDATES = (0x2000, 0x0010)


def le16(blob, offset):
    return int.from_bytes(blob[offset:offset+2], 'little')


def le32(blob, offset):
    return int.from_bytes(blob[offset:offset+4], 'little')


def sle16(blob, offset):
    value = le16(blob, offset)
    return value - 0x10000 if value & 0x8000 else value


def sle32(blob, offset):
    value = le32(blob, offset)
    return value - 0x100000000 if value & 0x80000000 else value


def parse_side(control, script, side):
    return {
        'flags': le32(control, 0), 'state': le32(control, 4),
        'action': le32(control, 8) & 0xFF,
        'max_hp': sle16(control, 0x3E), 'hp': sle16(control, 0x40),
        'ki': sle16(control, 0x42), 'last_command': sle16(control, 0x56),
        'cpu': bool(le32(control, 0) & 1), 'side': side,
        'x': sle32(control, 0x2C), 'z': sle32(control, 0x34),
        'script_ptr': le32(script, 0), 'tick': le16(script, 4),
        'velocity': sle16(script, 0xC), 'gate': le16(script, 0x22),
    }


def parse_state(blob):
    """Live block 0x80072800..0x80072A04: both controls, both scripts, stride."""
    return {'sides': [parse_side(blob[side*CONTROL_STRIDE:], blob[0xF8+side*SCRIPT_STRIDE:], side)
                      for side in range(2)],
            'object_stride': le16(blob, 0x202)}


def parse_frame_sample(frame, pad, control_hex, script_hex):
    controls = bytes.fromhex(control_hex)
    scripts = bytes.fromhex(script_hex)
    if len(controls) < 2 * CONTROL_STRIDE or len(scripts) < 2 * SCRIPT_STRIDE:
        raise ValueError('Short frame snapshot')
    return {'frame': frame, 'pad': pad,
            'sides': [parse_side(controls[side*CONTROL_STRIDE:], scripts[side*SCRIPT_STRIDE:], side)
                      for side in range(2)]}


def parse_wtrace_entries(reply):
    entries = []
    for item in reply.get('entries', []):
        entries.append({'seq': item['seq'], 'addr': int(item['addr'], 16),
                        'old': int(item['old'], 16), 'new': int(item['new'], 16),
                        'width': item.get('w', 4), 'frame': item.get('frame', -1),
                        'pc': int(item['pc'], 16), 'ra': int(item['ra'], 16)})
    entries.sort(key=lambda e: e['seq'])
    return entries


def damage_events(events, side):
    lo, hi = HP_RANGES[side]
    found = []
    for event in events:
        if not lo <= event['addr'] < hi:
            continue
        old = event['old'] & 0xFFFF
        new = event['new'] & 0xFFFF
        if new < old:
            found.append(dict(event, old=old, new=new, loss=old-new))
    found.sort(key=lambda e: (e['frame'], e['seq']))
    return found


def _actionable(samples, frames, side, start):
    for index, frame in enumerate(frames):
        if frame < start:
            continue
        if samples[frame]['sides'][side]['action'] <= NEUTRAL_MAX:
            after = frames[index+1:index+2]
            if after and samples[after[0]]['sides'][side]['action'] <= NEUTRAL_MAX:
                return frame
    return None


def _transitions(samples, frames, side, start, end):
    result = []
    previous = None
    for frame in frames:
        if frame < start or frame > end:
            continue
        action = samples[frame]['sides'][side]['action']
        if previous is None or action != previous:
            result.append({'frame': frame, 'action': action})
        previous = action
    return result


def classify_trial(samples, events, word, attacker=0, defender=1, counters=None):
    """Frame-truth classification of one pressed move, from parsed ring data."""
    metrics = {'outcome': 'inconclusive', 'word': hex(word), 'attacker': attacker,
               'defender': defender, 'hitstop_vblanks': None, 'hitstop_script': None,
               'hitstop_pose': None, 'attacker_hp_loss': 0, 'defender_hp_loss': 0}
    if not samples:
        return metrics
    frames = sorted(samples)
    pressed = [f for f in frames if (samples[f]['pad'] & word) != word]
    if not pressed:
        metrics['outcome'] = 'no_input'
        return metrics
    press_frame, press_last = pressed[0], pressed[-1]
    metrics['press_frame'] = press_frame
    metrics['press_frames'] = press_last - press_frame + 1
    metrics['jump_seen'] = any(samples[f]['sides'][attacker]['action'] == 0x1D or
                               samples[f]['sides'][attacker]['state'] & AIR_FLAG
                               for f in frames if f >= press_frame)
    metrics['jump_action_seen'] = any(samples[f]['sides'][attacker]['action'] == 0x1D
                                      for f in frames if f >= press_frame)
    base = samples.get(press_frame-1, samples[press_frame])
    metrics['pre_action'] = base['sides'][attacker]['action']
    dx = base['sides'][defender]['x'] - base['sides'][attacker]['x']
    dz = base['sides'][defender]['z'] - base['sides'][attacker]['z']
    metrics['distance_at_press'] = int(math.isqrt(dx*dx + dz*dz))
    if base['sides'][attacker]['action'] > NEUTRAL_MAX:
        metrics['outcome'] = 'busy_at_press'
        return metrics

    attack_start = None
    for frame in frames:
        if frame < press_frame:
            continue
        action = samples[frame]['sides'][attacker]['action']
        if action > NEUTRAL_MAX:
            previous = samples.get(frame-1)
            if previous is None or previous['sides'][attacker]['action'] <= NEUTRAL_MAX:
                attack_start = frame
                break
    if attack_start is None:
        metrics['outcome'] = 'no_action'
        metrics['transitions'] = _transitions(samples, frames, attacker, press_frame, frames[-1])
        return metrics
    metrics['attack_start_frame'] = attack_start
    metrics['action_id'] = samples[attack_start]['sides'][attacker]['action']
    metrics['air'] = bool(samples[attack_start]['sides'][attacker]['state'] & AIR_FLAG)
    start_state = samples[attack_start]['sides'][attacker]
    impact_state = samples[attack_start]['sides'][defender]
    dx = impact_state['x'] - start_state['x']
    dz = impact_state['z'] - start_state['z']
    metrics['distance_at_action'] = int(math.isqrt(dx*dx + dz*dz))

    attacker_losses = damage_events(events, attacker)
    defender_losses = damage_events(events, defender)
    window_start = press_frame - 2
    attacker_window = [e for e in attacker_losses if e['frame'] >= window_start]
    defender_window = [e for e in defender_losses if e['frame'] >= window_start]
    metrics['attacker_hp_loss'] = sum(e['loss'] for e in attacker_window)
    metrics['defender_hp_loss'] = sum(e['loss'] for e in defender_window)
    impact = defender_window[0] if defender_window else None
    if impact:
        metrics['impact_frame'] = impact['frame']
        metrics['impact_writer_pc'] = hex(impact['pc'])
        metrics['impact_loss'] = impact['loss']
        if impact['frame'] < attack_start:
            impact = None

    sample_impact = None
    hp_before = samples[press_frame]['sides'][defender]['hp']
    for frame in frames:
        if frame >= attack_start and samples[frame]['sides'][defender]['hp'] < hp_before:
            sample_impact = frame
            break
    if sample_impact is not None and impact is None:
        impact = {'frame': sample_impact}
        metrics['impact_frame'] = sample_impact
        metrics['impact_source'] = 'snapshot'

    interrupted = bool(attacker_window)
    if interrupted:
        metrics['interruption_frame'] = attacker_window[0]['frame']

    attacker_recovery = _actionable(samples, frames, attacker,
                                    (impact['frame'] if impact else attack_start) + 1)
    if attacker_recovery is not None:
        metrics['attacker_recovery_frame'] = attacker_recovery
        start = (impact['frame'] if impact else attack_start)
        metrics['recovery_from_impact'] = attacker_recovery - start
        if not impact:
            metrics['whiff_recovery'] = attacker_recovery - attack_start
        else:
            metrics['startup'] = impact['frame'] - press_frame
            metrics['startup_from_action'] = impact['frame'] - attack_start
            metrics['recovery_hit'] = attacker_recovery - impact['frame']

    if impact:
        stun_action = samples[impact['frame']]['sides'][defender]['action'] \
            if impact['frame'] in samples else None
        candidates = []
        for frame in frames:
            if frame <= impact['frame']:
                continue
            if any(impact['frame'] < e['frame'] <= frame for e in defender_window):
                continue
            action = samples[frame]['sides'][defender]['action']
            if stun_action is None:
                if action <= NEUTRAL_MAX:
                    candidates.append((frame, action))
                    break
            elif action != stun_action:
                candidates.append((frame, action))
                break
        action_lo, action_hi = ACTION_RANGES[defender]
        for event in events:
            if not action_lo <= event['addr'] < action_hi:
                continue
            if event['frame'] <= impact['frame']:
                continue
            if any(impact['frame'] < e['frame'] <= event['frame'] for e in defender_window):
                continue
            action = event['new'] & 0xFF
            if stun_action is None or action != stun_action:
                candidates.append((event['frame'], action))
        if candidates:
            frame, action = min(candidates)
            metrics['defender_recovery_frame'] = frame
            metrics['stun_action'] = stun_action
            metrics['defender_next_action'] = action
            if attacker_recovery is not None:
                metrics['advantage_hit'] = frame - attacker_recovery

    guard_frames = [f for f in frames if f >= attack_start and
                    samples[f]['sides'][defender]['action'] in GUARD_ACTIONS]
    if guard_frames and not defender_window:
        guard_start = guard_frames[0]
        metrics['block_start_frame'] = guard_start
        guard_exit = None
        for frame in frames:
            if frame <= guard_start:
                continue
            if samples[frame]['sides'][defender]['action'] not in GUARD_ACTIONS:
                guard_exit = frame
                break
        if guard_exit is not None:
            metrics['guard_exit_frame'] = guard_exit
            if attacker_recovery is not None:
                metrics['advantage_block'] = guard_exit - attacker_recovery

    if interrupted:
        metrics['outcome'] = 'interrupted'
    elif impact and attacker_recovery is not None:
        metrics['outcome'] = 'hit'
    elif guard_frames and not defender_window:
        metrics['outcome'] = 'blocked'
    elif attacker_recovery is not None:
        metrics['outcome'] = 'whiff'
    elif attack_start is not None:
        metrics['outcome'] = 'unresolved'

    for key in ('hitstop_vblanks', 'hitstop_script', 'hitstop_pose'):
        metrics[key] = None
    if counters:
        metrics['hitstop_vblanks'] = counters.get('dbfb.responsive.hitstop_frame', 0)
        metrics['hitstop_script'] = counters.get('dbfb.responsive.hitstop_script', 0)
        metrics['hitstop_pose'] = counters.get('dbfb.responsive.hitstop_pose', 0)
    if impact and impact['frame'] in samples:
        hold = 0
        frame = impact['frame']
        action = samples[frame]['sides'][attacker]['action']
        tick = samples[frame]['sides'][attacker]['tick']
        while frame in samples and samples[frame]['sides'][attacker]['action'] == action \
                and samples[frame]['sides'][attacker]['tick'] == tick:
            hold += 1
            frame += 1
        metrics['tick_hold_frames'] = hold - 1

    metrics['transitions'] = _transitions(samples, frames, attacker, press_frame,
                                          frames[-1])
    metrics['defender_transitions'] = _transitions(samples, frames, defender, press_frame,
                                                   frames[-1])
    return metrics


def stats(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle-1] + ordered[middle]) / 2
    return {'n': len(ordered), 'min': ordered[0], 'max': ordered[-1],
            'mean': round(sum(ordered) / len(ordered), 2), 'median': median}


CARD_METRICS = ('startup', 'startup_from_action', 'recovery_hit', 'advantage_hit',
                'whiff_recovery', 'advantage_block', 'hitstop_vblanks', 'tick_hold_frames',
                'distance_at_action')


def build_cards(trials):
    cards = {}
    for trial in trials:
        spec = trial['spec']
        card = cards.setdefault(spec['name'], {'spec': spec['name'], 'kind': spec['kind'],
                                               'steps': spec['steps'], 'inputs': [],
                                               'outcomes': {}, 'stats': {},
                                               'conditions': {'defender': 'native CPU (side 2)',
                                                              'attacker_side': 0,
                                                              'mod_plugin': 'dbfb.responsive active'}})
        word = trial.get('word')
        if word is not None and word not in card['inputs']:
            card['inputs'].append(word)
        outcome = trial['metrics'].get('outcome', 'inconclusive')
        card['outcomes'][outcome] = card['outcomes'].get(outcome, 0) + 1
        counters = card.setdefault('counters', {})
        for key, value in (trial.get('counters') or {}).items():
            counters[key] = counters.get(key, 0) + value
        card.setdefault('samples', []).append({key: value for key, value in trial['metrics'].items()
                                               if key not in ('transitions', 'defender_transitions')})
    for card in cards.values():
        samples = card.get('samples', [])
        if card['kind'] == 'aerial':
            card['air_confirmed_samples'] = sum(1 for s in samples if s.get('air'))
        for metric in CARD_METRICS:
            values = [s.get(metric) for s in samples if s.get('outcome') in ('hit', 'blocked', 'whiff')]
            card['stats'][metric] = stats(values)
        hit = [s for s in samples if s.get('outcome') == 'hit']
        card['stats']['hit_action_ids'] = sorted({s.get('action_id') for s in hit if s.get('action_id') is not None})
    return cards


def validate_cards(cards):
    problems = []
    if not isinstance(cards, dict) or not cards:
        return ['cards must be a non-empty mapping']
    for name, card in cards.items():
        for field in ('spec', 'kind', 'outcomes', 'stats', 'conditions'):
            if field not in card:
                problems.append(f'{name}: missing {field}')
        if card.get('kind') not in ('ground', 'aerial'):
            problems.append(f'{name}: unknown kind {card.get("kind")!r}')
        if not isinstance(card.get('outcomes'), dict) or not card.get('outcomes'):
            problems.append(f'{name}: outcomes must be a non-empty mapping')
        for metric, value in card.get('stats', {}).items():
            if metric == 'hit_action_ids':
                if not isinstance(value, list):
                    problems.append(f'{name}.{metric}: must be a list')
                continue
            if value is None:
                continue
            if not isinstance(value, dict) or value.get('n', 0) < 1:
                problems.append(f'{name}.{metric}: invalid sample stats')
                continue
            if not value['min'] <= value['median'] <= value['max']:
                problems.append(f'{name}.{metric}: min/median/max out of order')
            if value['min'] > value['mean'] or value['mean'] > value['max']:
                problems.append(f'{name}.{metric}: mean outside range')
    return problems


def select_pads(records):
    """Filled frame_range records carry a pad field; unfilled ones only carry
    {"available":false}. Keying off the flag alone drops every real frame."""
    return {record['frame']: int(record['pad'], 16) for record in records
            if 'pad' in record}


def combine_reports(reports):
    """Merge already-measured trials from several private sessions into one table.

    Inputs are the session/combined JSONs the tool wrote (cards were built from
    these exact trial metrics); no reclassification and no new assumptions.
    """
    trials = []
    sources = []
    for report in reports:
        source = report.get('source') or report.get('conditions', {}).get('out', 'session')
        entries = report.get('measured_trials')
        if not isinstance(entries, list):
            entries = report.get('trials')
        if not isinstance(entries, list):
            entries = []
        sources.append({'source': source, 'trials': len(entries),
                        'coverage': report.get('coverage')})
        for trial in entries:
            if 'metrics' not in trial or 'spec' not in trial:
                continue
            trials.append({'spec': trial['spec'],
                           'word': trial['spec']['steps'][-1]['word'],
                           'metrics': trial['metrics'], 'counters': trial.get('counters')})
    cards = build_cards(trials)
    return {'cards': cards, 'trials': len(trials), 'measured_trials': trials,
            'sources': sources,
            'cards_problems': validate_cards(cards) if cards else ['no measured cards']}


def counter_map(reply):
    return {item['name']: item['count'] for item in reply.get('counters', [])}


def counter_diff(before, after):
    return {key: after.get(key, 0) - before.get(key, 0) for key in set(before) | set(after)}


class Session:
    def __init__(self, port, out):
        self.port = port
        self.out = out
        self.armed = False
        self.snapshot_since = None
        self.evidence = {}

    def q(self, command, **params):
        return query(command, self.port, **params)

    def frame(self):
        return self.q('frame')['frame']

    def state(self):
        reply = self.q('read_ram', addr=hex(CONTROL_BASE), len=STATE_READ_LEN)
        return parse_state(bytes.fromhex(reply['hex']))

    def read_word(self, address):
        reply = self.q('read_ram', addr=hex(address), len=4)
        return int.from_bytes(bytes.fromhex(reply['hex']), 'little')

    def battle(self, state=None):
        state = state or self.state()
        return (self.read_word(BATTLE_CODE_ADDR) == BATTLE_CODE and
                state['sides'][0]['hp'] > 0 and state['sides'][1]['hp'] > 0)

    def arm(self):
        self.q('wtrace_disarm_all')
        self.q('wtrace_clear')
        for lo, hi in WT_RANGES:
            self.q('wtrace_add', lo=hex(lo), hi=hex(hi))
        for slot, (address, length) in enumerate(SNAPSHOT_REGIONS):
            self.q('set_snapshot', slot=slot, addr=hex(address), size=length)
        self.snapshot_since = self.frame()
        self.evidence['wtrace_ranges'] = self.q('wtrace_ranges')
        self.evidence['snapshots'] = self.q('get_snapshots')
        self.evidence['armed_at_frame'] = self.snapshot_since
        self.armed = True

    def counters(self):
        return counter_map(self.q('mod_counters'))

    def wait_frames(self, count, deadline, poll=0.03):
        target = self.frame() + count
        while time.monotonic() < deadline:
            if self.frame() >= target:
                return True
            time.sleep(poll)
        return False

    def wait_air(self, side, deadline, timeout_frames=30, poll=0.03):
        start = self.frame()
        while time.monotonic() < deadline and self.frame() - start < timeout_frames:
            state = self.state()['sides'][side]
            if state['state'] & AIR_FLAG or state['action'] == 0x1D:
                return True
            time.sleep(poll)
        return False

    def samples(self, first, last):
        frames = {}
        start = max(first, self.snapshot_since)
        for frame in range(start, last + 1):
            try:
                c0 = self.q('read_frame_ram', addr=hex(SNAPSHOT_REGIONS[0][0]), len=SNAPSHOT_REGIONS[0][1], frame=frame)['hex']
                c1 = self.q('read_frame_ram', addr=hex(SNAPSHOT_REGIONS[1][0]), len=SNAPSHOT_REGIONS[1][1], frame=frame)['hex']
                ss = self.q('read_frame_ram', addr=hex(SNAPSHOT_REGIONS[2][0]), len=SNAPSHOT_REGIONS[2][1], frame=frame)['hex']
            except ValueError:
                continue
            frames[frame] = (c0, c1, ss)
        return frames

    def pad_window(self, first, last):
        """frame_range answers unfilled frames with {"available":false}; filled
        ones carry a pad field and no flag. Never key off the flag alone."""
        pads = {}
        frame = first
        while frame <= last:
            end = min(frame + SNAPSHOT_MAX_FRAME_SPAN - 1, last)
            reply = self.q('frame_range', start=frame, end=end)
            pads.update(select_pads(reply['frames']))
            frame = end + 1
        return pads

    def wtrace_window(self, first, last):
        reply = self.q('wtrace_dump', frame_lo=first, frame_hi=last, count=2048, newest=1)
        return parse_wtrace_entries(reply)


def run_trial(session, spec, jump_word, deadline):
    report = {'spec': spec, 'attempted_at': session.frame(), 'notes': []}
    if spec['kind'] == 'aerial':
        jump = jump_word
        if jump is None:
            report['metrics'] = {'outcome': 'no_jump_discovered'}
            return report
        steps = ({'word': jump, 'frames': 4},) + spec['steps']
    else:
        steps = spec['steps']
    start_frame = session.frame()
    counters_before = session.counters()
    session.q('clear_input')
    for step in steps:
        if step.get('after_jump'):
            if session.wait_air(0, deadline):
                session.wait_frames(4, deadline)
            else:
                report['notes'].append('air flag not observed before the attack press')
        word = step['word']
        session.q('press', buttons=0xFFFF ^ word, frames=step['frames'], port=1, pad_type=0)
        time.sleep(0.12)
    press_time = time.monotonic()
    session.wait_frames(8, deadline)
    while time.monotonic() < deadline:
        attacker = session.state()['sides'][0]['action']
        if attacker <= NEUTRAL_MAX and time.monotonic() - press_time > 0.5:
            break
        time.sleep(0.05)
    session.wait_frames(20, deadline)
    recovered_frame = session.frame()
    defender_action = session.state()['sides'][1]['action']
    tail_start = session.frame()
    while time.monotonic() < deadline and session.frame() - tail_start < 90:
        if session.state()['sides'][1]['action'] != defender_action:
            break
        time.sleep(0.05)
    session.q('clear_input')
    end_frame = session.frame()
    counters_after = session.counters()
    first = max(start_frame - 2, session.snapshot_since)
    sample_last = min(recovered_frame + 2, first + WINDOW_CAP)
    report['window'] = {'first': first, 'sample_last': sample_last, 'last': end_frame,
                        'truncated': recovered_frame + 2 > sample_last}
    raw = session.samples(first, sample_last)
    pads = session.pad_window(first, end_frame)
    samples = {}
    for frame, (c0, c1, ss) in raw.items():
        try:
            samples[frame] = parse_frame_sample(frame, pads.get(frame, 0xFFFF), c0 + c1, ss)
        except ValueError:
            continue
    events = session.wtrace_window(first, end_frame + 2)
    if len(samples) < 5:
        report['metrics'] = {'outcome': 'ring_incomplete',
                             'sampled_frames': len(samples)}
        return report
    diff = counter_diff(counters_before, counters_after)
    report['counters'] = diff
    report['metrics'] = classify_trial(samples, events, steps[-1]['word'],
                                       counters=diff)
    report['events'] = [{'seq': e['seq'], 'addr': hex(e['addr']), 'old': hex(e['old']),
                         'new': hex(e['new']), 'frame': e['frame'], 'pc': hex(e['pc'])}
                        for e in events]
    report['timeline'] = [{'frame': frame, 'pad': pads.get(frame, 0xFFFF),
                           'a0': sample['sides'][0]['action'],
                           'a1': sample['sides'][1]['action'],
                           'hp0': sample['sides'][0]['hp'], 'hp1': sample['sides'][1]['hp'],
                           't0': sample['sides'][0]['tick'], 't1': sample['sides'][1]['tick'],
                           'g0': sample['sides'][0]['gate'], 'g1': sample['sides'][1]['gate'],
                           's0': sample['sides'][0]['state'], 's1': sample['sides'][1]['state']}
                          for frame, sample in sorted(samples.items())]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launch', action='store_true')
    parser.add_argument('--combine', nargs='*', type=Path, default=None,
                        help='Merge measured trials from private session/combined JSONs')
    parser.add_argument('--port', type=int, default=4390)
    parser.add_argument('--seconds', type=int, default=360)
    parser.add_argument('--kos', type=int, default=2, help='Minimum observed KOs (1..10)')
    parser.add_argument('--samples', type=int, default=3, help='Valid samples per move spec')
    parser.add_argument('--attempts', type=int, default=8, help='Attempts per move spec')
    parser.add_argument('--only', default='', help='Comma-separated spec names to run')
    parser.add_argument('--summary', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.combine is not None:
        if args.launch:
            parser.error('--combine and --launch are mutually exclusive')
        reports = []
        for path in args.combine:
            report = json.loads(Path(path).read_text(encoding='utf-8'))
            report['source'] = str(Path(path).resolve())
            reports.append(report)
        combined = combine_reports(reports)
        if args.out.exists() or not args.out.parent.is_dir():
            parser.error('Use a NEW output folder under an existing parent')
        args.out.mkdir()
        (args.out / 'combined_cards.json').write_text(json.dumps(combined, indent=2),
                                                      encoding='utf-8')
        print(json.dumps({name: {'kind': card['kind'], 'outcomes': card['outcomes'],
                                 'startup': card['stats'].get('startup'),
                                 'advantage_hit': card['stats'].get('advantage_hit'),
                                 'advantage_block': card['stats'].get('advantage_block'),
                                 'whiff_recovery': card['stats'].get('whiff_recovery'),
                                 'hitstop_vblanks': card['stats'].get('hitstop_vblanks')}
                          for name, card in combined['cards'].items()}, indent=2))
        print(json.dumps({'trials': combined['trials'], 'sources': combined['sources'],
                          'cards_problems': combined['cards_problems']}, indent=2))
        print(f'Private evidence: {args.out.resolve()}')
        return 0 if not combined['cards_problems'] else 1
    if not args.launch:
        parser.error('Use --launch for a session or --combine for merging private JSONs')
    if not 300 <= args.seconds <= 420 or not 1024 <= args.port <= 65535 or \
            not 1 <= args.kos <= 10 or not 1 <= args.samples <= 6 or not 1 <= args.attempts <= 12:
        parser.error('Session must be 300..420 seconds, --kos 1..10, --samples 1..6, --attempts 1..12')
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error('Use a NEW output folder under an existing parent')
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', args.port))
        except OSError:
            parser.error('Debug port is already in use; no existing session will be touched')
    args.out.mkdir()
    out = args.out.resolve()

    exe = ROOT / 'build-release/DBFinalBout_Recompiled.exe'
    game_toml = ROOT / 'build-release/game.toml'
    report = {'human_playtest': False, 'steps': [], 'pause': [], 'trials': [],
              'conditions': {'port': args.port, 'seconds': args.seconds, 'kos': args.kos,
                             'opponent': 'native CPU side 2; player attacks injected on pad port 1',
                             'plugin': 'dbfb.responsive active (stock build-release runtime)',
                             'clock': 'game VBlanks (frame ring / script tick), not host time',
                             'exe_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
                             'game_toml_sha256': hashlib.sha256(game_toml.read_bytes()).hexdigest()}}
    session = Session(args.port, out)
    specs = [spec for spec in GROUND_SPECS + AERIAL_SPECS
             if not args.only or spec['name'] in args.only.split(',')]
    progress = {spec['name']: {'valid': 0, 'attempts': 0} for spec in specs}
    jump_word = None
    jump_evidence = []
    paused_probe = False
    command = [str(exe), '--game', str(game_toml), '--headless', '--no-launcher',
               '--debug-port', str(args.port), '--memcard-dir', str(out / 'cards')]
    process = None

    def snapshot(label):
        state = session.state()
        record = {'label': label, 'frame': session.frame(),
                  'roster_word': hex(session.read_word(0x8003BCC4)),
                  'object_stride': state['object_stride'],
                  'battle_code': session.read_word(BATTLE_CODE_ADDR) == BATTLE_CODE}
        if record['battle_code']:
            record['fighters'] = [{'hp': s['hp'], 'action': s['action'], 'cpu': s['cpu']}
                                  for s in state['sides']]
        report['steps'].append(record)
        report['counters'] = session.q('mod_counters')
        return record

    def menu_press(step):
        word = 0x0008 if step % 3 == 0 else 0x4000
        session.q('press', buttons=0xFFFF ^ word, frames=8, port=1, pad_type=0)
        time.sleep(0.5)
        session.q('clear_input')
        time.sleep(1.2)

    def battle_press(step):
        word = (0x1000, 0x8000, 0x4000)[step % 3]
        session.q('press', buttons=0xFFFF ^ word, frames=6, port=1, pad_type=0)
        time.sleep(0.3)
        session.q('clear_input')
        time.sleep(0.6)

    def pause_probe():
        before = session.read_word(PAUSE_ADDR)
        paused = resumed = None
        for _ in range(4):
            session.q('press', buttons=0xFFFF ^ 0x0008, frames=8, port=1, pad_type=0)
            time.sleep(1.0)
            session.q('clear_input')
            time.sleep(1.0)
            value = session.read_word(PAUSE_ADDR)
            if value != before:
                paused = value
                break
        for _ in range(4):
            if paused is None:
                break
            session.q('press', buttons=0xFFFF ^ 0x0008, frames=8, port=1, pad_type=0)
            time.sleep(1.0)
            session.q('clear_input')
            time.sleep(1.0)
            if session.read_word(PAUSE_ADDR) == before:
                resumed = before
                break
        report['pause'].append({'frame': session.frame(), 'before': before,
                                'paused': paused, 'resumed': resumed})
        if before != 0 or paused != 1 or resumed != 0:
            raise RuntimeError('Native pause/resume was not confirmed')

    try:
        with (out / 'runtime.stdout').open('wb') as stdout, (out / 'runtime.stderr').open('wb') as stderr:
            process = subprocess.Popen(command, cwd=out, stdout=stdout, stderr=stderr)
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'Runtime exited before connection: {process.returncode}')
                try:
                    session.q('frame')
                    break
                except (OSError, ValueError):
                    time.sleep(0.5)
            else:
                raise RuntimeError('Debug server did not become available')
            time.sleep(8)
            snapshot('boot')
            measure_until = deadline - 45
            step = 0
            idle_run = 0
            next_snapshot = time.monotonic() + 6
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'Runtime exited during session: {process.returncode}')
                state = session.state()
                battle = session.read_word(BATTLE_CODE_ADDR) == BATTLE_CODE
                if not battle or state['sides'][0]['hp'] <= 0 or state['sides'][1]['hp'] <= 0:
                    idle_run = 0
                    menu_press(step)
                    if time.monotonic() >= next_snapshot:
                        snapshot('transition')
                        next_snapshot = time.monotonic() + 6
                    step += 1
                    continue
                if not session.armed:
                    session.arm()
                    snapshot('battle-armed')
                    continue
                if not paused_probe:
                    paused_probe = True
                    pause_probe()
                    continue
                pending = [spec for spec in specs
                           if progress[spec['name']]['valid'] < args.samples and
                           progress[spec['name']]['attempts'] < args.attempts and
                           (spec['kind'] == 'ground' or jump_word is not None)]
                neutral = state['sides'][0]['action'] <= NEUTRAL_MAX
                idle_run = idle_run + 1 if neutral else 0
                measuring = time.monotonic() < measure_until and pending and neutral and idle_run >= 8
                if measuring:
                    idle_run = 0
                    spec = min(pending, key=lambda item: (progress[item['name']]['attempts'],
                                                          specs.index(item)))
                    trial = run_trial(session, spec, jump_word, min(deadline - 5, time.monotonic() + 30))
                    progress[spec['name']]['attempts'] += 1
                    metrics = trial['metrics']
                    if metrics.get('outcome') in ('hit', 'blocked', 'whiff'):
                        progress[spec['name']]['valid'] += 1
                    jumpish = (spec['name'] == 'ground_up' and metrics.get('jump_seen')) or \
                        (spec['name'] == 'ground_cross' and metrics.get('jump_action_seen'))
                    if spec['kind'] == 'ground' and jumpish:
                        jump_word = spec['steps'][0]['word']
                        jump_evidence.append({'spec': spec['name'], 'frame': metrics.get('press_frame'),
                                              'action': metrics.get('action_id')})
                    report['trials'].append(trial)
                    if time.monotonic() >= next_snapshot:
                        snapshot('trial')
                        next_snapshot = time.monotonic() + 6
                    continue
                if time.monotonic() >= next_snapshot:
                    snapshot('battle-idle')
                    next_snapshot = time.monotonic() + 6
                if not pending or time.monotonic() >= measure_until:
                    battle_press(step)
                    step += 1
                else:
                    time.sleep(0.2)
            report['counters'] = session.q('mod_counters')
            snapshot('final')
    except Exception as error:
        report['error'] = str(error)
    finally:
        if process is not None and process.poll() is None:
            try:
                session.q('quit')
            except (OSError, ValueError) as error:
                report['quit_reply_error'] = str(error)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                report['forced_shutdown'] = True
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        if process is not None:
            report['process_exit'] = process.returncode
        trial_reports = [t for t in report['trials'] if 'metrics' in t]
        report['evidence'] = session.evidence
        try:
            cards = build_cards([{'spec': t['spec'], 'word': t['spec']['steps'][-1]['word'],
                                  'metrics': t['metrics'], 'counters': t.get('counters')}
                                 for t in trial_reports])
            report['cards_problems'] = validate_cards(cards) if cards else ['no measured cards']
        except Exception as error:
            cards = {}
            report['cards_error'] = str(error)
            report['cards_problems'] = ['cards build failed']
        report['jump_word'] = None if jump_word is None else hex(jump_word)
        report['jump_evidence'] = jump_evidence
        report['cards'] = cards
        report['coverage'] = {spec['name']: progress[spec['name']] for spec in specs}
        report['limits'] = [
            'Advantage uses the engine action byte: attacker recovery is the first'
            ' stable frame with action <= 0x23; defender recovery is the first frame'
            ' the post-impact action changes without taking further damage (a CPU may'
            ' act on that very frame, so its number is a lower bound).',
            'Only observed samples are reported; interrupted or busy presses are kept'
            ' as attempts, not merged into the measured stats.',
            'Hit-stop is the plugin VBlank counter delta over the trial window plus a'
            ' direct tick-hold cross-check; both come from game state, not host time.',
            'Blocked advantage exists only when a guard action was actually observed;'
            ' otherwise the card reports null instead of inventing a guard window.',
            'Whiff startup has no impact frame: only whiff_recovery (action start to'
            ' neutral) is measured for those samples.',
        ]
        assess(report, args.kos)
        (out / 'session.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        (out / 'combat_cards.json').write_text(
            json.dumps({'tool': 'tools/combat_cards.py', 'conditions': report['conditions'],
                        'jump_word': report['jump_word'], 'coverage': report['coverage'],
                        'cards': cards, 'trials': trial_reports, 'limits': report['limits'],
                        'cards_problems': report['cards_problems']}, indent=2),
            encoding='utf-8')
        summary = {'passed': report.get('passed'), 'checks': report.get('checks'),
                   'process_exit': report.get('process_exit'),
                   'coverage': report['coverage'], 'jump_word': report['jump_word'],
                   'cards_problems': report['cards_problems'],
                   'cards': {name: {'kind': card['kind'], 'outcomes': card['outcomes'],
                                    'startup': card['stats'].get('startup'),
                                    'advantage_hit': card['stats'].get('advantage_hit'),
                                    'advantage_block': card['stats'].get('advantage_block'),
                                    'whiff_recovery': card['stats'].get('whiff_recovery'),
                                    'hitstop_vblanks': card['stats'].get('hitstop_vblanks')}
                             for name, card in cards.items()},
                   'error': report.get('error')}
        print(json.dumps(summary if args.summary else report, indent=2))
        print(f'Private evidence: {out}')
    return 0 if report.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
