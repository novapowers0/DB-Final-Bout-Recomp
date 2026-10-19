"""Attribute exact native pose samples and PNG frames from own R3 sessions.

Read-only sessions/disc; optional NEW metadata report. Never modifies a game.
Checks real angle stores from the retail decoder against both trajectories;
the new trajectory must differ inside and equal the original at its endpoint.
"""
import argparse
import json
from pathlib import Path

from combat_rigclip import ROOT, animation_tables, pose, raw_clip, packets, sources, truncdiv


def analyze(folder, archive):
    folder = Path(folder)
    data = json.loads((folder/'bridge-session.json').read_text(encoding='utf-8'))
    table = animation_tables(archive)[0]
    source = pose(raw_clip(archive, table, 2))
    target = pose(raw_clip(archive, table, 105), source)
    original, body = [], bytearray()
    groups = packets(raw_clip(archive, table, 105))
    raw = raw_clip(archive, table, 105)
    at = 4
    for _ in groups:
        words = int.from_bytes(raw[at:at+2], 'little')
        at += 4*words
        partial = bytearray(raw[:at]); partial[2:4] = (len(original)+1).to_bytes(2, 'little')
        original.append(pose(partial, source))
    binding = data['transition_bindings'][0]
    is_own = binding['slot'] >= 218
    private = int(binding['target'], 0)
    objects = {int(j['object'], 0) & 0x1FFFFFFF: j['part'] for j in data['joint_objects']}
    angles, action, context, trial, trials = {}, None, None, None, []
    for event in sorted(data['trace'], key=lambda e: e['seq']):
        addr, value, pc = (int(event[k], 0) for k in ('addr', 'new', 'pc'))
        frame = event['frame']
        if addr == 0x72808: action = value & 255
        if addr == 0xA8624:
            context = value
            if action == 6 and (value == private if is_own else value != 0x800CFA18):
                trial = {'start_frame': frame, 'context': hex(value), 'samples': [], 'ended': False}
                trials.append(trial)
            elif trial: trial = None
        for obj, part in objects.items():
            if event['w'] == 2 and obj+0x10 <= addr <= obj+0x14 and not (addr & 1):
                angles.setdefault(part, {})[(addr-obj-0x10)//2] = value & 65535
        if trial and addr == 0xA862C and pc == 0x8004229C and value == 0:
            trial['ended'] = True
            trial['end_frame'] = frame
        if trial and addr == 0xA8628 and pc == 0x800422AC and 2 <= value <= 6:
            tick = value-1
            sample = {'tick': tick, 'frame': frame, 'angles': {}, 'matches': True, 'differs_from_original': False}
            for part in (8, 9):
                actual = [angles.get(part, {}).get(axis) for axis in range(3)]
                baseline = [v & 65535 for v in original[tick-1][part]['angle']]
                expected = baseline
                if is_own:
                    weight = tick*tick*(15-2*tick)
                    total = [((b-a+32768) & 65535)-32768 for a, b in zip(source[part]['angle'], target[part]['angle'])]
                    expected = [(a+truncdiv(v*weight, 125)) & 65535 for a, v in zip(source[part]['angle'], total)]
                sample['angles'][part] = {'observed_u16': actual, 'expected_u16': expected, 'original_u16': baseline}
                sample['matches'] &= actual == expected
                sample['differs_from_original'] |= actual != baseline
            sample['pngs'] = [c for c in data['captures'] if c['frame'] in (frame, frame+1)]
            trial['samples'].append(sample)
    complete = [t for t in trials if t['ended'] and {s['tick'] for s in t['samples']} == {1, 2, 3, 4, 5}]
    verified = [t for t in complete if all(s['matches'] for s in t['samples'])]
    result = {'folder': str(folder), 'binding': binding, 'own_transition': is_own,
              'starts': len(trials), 'complete': len(complete), 'pose_verified': len(verified),
              'changed_inner_samples': sum(s['differs_from_original'] for t in verified for s in t['samples'] if s['tick'] < 5),
              'exact_original_endpoints': sum(not t['samples'][-1]['differs_from_original'] for t in verified),
              'process_exit': data.get('process_exit'), 'error': data.get('error'),
              'first_verified': verified[0] if verified else None,
              'lifecycle': {k: data.get(k) for k in ('pause_inside_own_clip', 'pause_context_unchanged',
                  'load_restored_paused_context', 'resumed_after_load')}}
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('folders', nargs='+', type=Path)
    p.add_argument('--disc', type=Path, default=ROOT/'disc/Dragon Ball GT - Final Bout (USA).bin')
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    archive, _, _, _ = sources(args.disc)
    result = [analyze(folder, archive) for folder in args.folders]
    text = json.dumps(result, indent=2)
    if args.out:
        if not args.out.parent.is_dir(): raise ValueError('Existing output parent required')
        with args.out.open('x', encoding='utf-8') as stream: stream.write(text)
    print(text)
