"""Own bounded R3 session: native inputs, exclusive traces, frame-exact PNGs.

Never writes game RAM or selections. New output directory/cards; port must be
free. Own process only. This observes the native action6 / slot2 -> slot105 path.
"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import time
import struct
import hashlib

from combat_live import query
from combat_map import ROOT


def run(out, seconds=150, port=4387, lifecycle=False, pgxp=False):
    out = Path(out).resolve()
    if out.exists() or not out.parent.is_dir(): raise ValueError('New output folder required')
    with socket.socket() as test: test.bind(('127.0.0.1', port))
    out.mkdir()
    report = {'steps': [], 'trace': [], 'captures': [], 'inputs': [], 'human_playtest': False}
    executable = ROOT/'build-release'/('DBFinalBout_Recompiled_pgxp.exe' if pgxp else 'DBFinalBout_Recompiled.exe')
    report['executable'] = str(executable)
    report['executable_sha256'] = hashlib.sha256(executable.read_bytes()).hexdigest()
    slots, process, saved, seen = [], None, set(), set()
    lifecycle_stage = 0
    def q(cmd, **params): return query(cmd, port, **params)
    def read(addr, size=4): return bytes.fromhex(q('read_ram', addr=hex(addr), len=size)['hex'])
    def word(addr): return int.from_bytes(read(addr), 'little')
    def state_op(op):
        generation = q('savestate_status')['generation']
        q('savestate', op=op, slot=0)
        end = time.monotonic()+20
        while time.monotonic() < end:
            status = q('savestate_status')
            if status['generation'] > generation and not status['pending']:
                if status['last_ok'] != 1: raise RuntimeError(f'Savestate failed: {status}')
                return status
            time.sleep(.1)
        raise RuntimeError(f'Savestate {op} timed out')
    def shot(frame, label):
        if frame in saved or frame < 0: return
        try:
            reply = q('display_ring_get', frame=frame, path=str(out/f'{frame:07d}-{label}.png'))
            report['captures'].append(reply)
            saved.add(frame)
        except ValueError as e: report.setdefault('capture_errors', []).append(str(e))
    deadline = time.monotonic()+seconds
    try:
        with (out/'runtime.stdout').open('xb') as stdout, (out/'runtime.stderr').open('xb') as stderr:
            process = subprocess.Popen([str(executable),
                '--game', str(ROOT/'build-release/game.toml'), '--headless', '--no-launcher',
                '--debug-port', str(port), '--memcard-dir', str(out/'cards')], cwd=out, stdout=stdout, stderr=stderr)
            while time.monotonic() < deadline:
                if process.poll() is not None: raise RuntimeError(f'Exited {process.returncode}')
                try: q('frame'); break
                except (OSError, ValueError): time.sleep(.3)
            time.sleep(7)
            battle, step, last_input, last_dump = False, 0, 0, 0
            while time.monotonic() < deadline:
                if process.poll() is not None: raise RuntimeError(f'Exited {process.returncode}')
                now = time.monotonic()
                valid = word(0x80054A60) == 0x84242856
                if (valid and not battle and 17 <= word(0x80072A00) >> 16 <= 36 and
                    word(0x800CF000) & 65535 == 0x826B and
                    all(word(0x80072840+s*0x7C) & 65535 for s in range(2))):
                    battle = True
                    report['ranges_before'] = q('wtrace_ranges')
                    for lo, hi in ((0x80072808, 0x8007280C), (0x800A8624, 0x800A8630),
                                   (0x80072884, 0x80072888), (0x800A8644, 0x800A8650)):
                        result = q('wtrace_add', lo=hex(lo), hi=hex(hi))
                        slots.append(result['slot'])
                    report['animation_tables'] = [read(a, 4*4).hex() for a in (0x800CF000, 0x80147800)]
                    report['control_ids'] = [word(0x800727FC+s*0x7C) & 255 for s in range(2)]
                    report['transition_bindings'] = []
                    for side in range(2):
                        scripts, animations = word(0x8006F794+4*side), word(0x8007EF3C+4*side)
                        script = (scripts+4*174+4*word(scripts+28)) & 0xFFFFFFFF
                        action_words = struct.unpack('<3I', read(script, 12))
                        slot = action_words[1] & 65535
                        target = word(animations+4*(slot+1))
                        report['transition_bindings'].append({'side': side, 'scripts': hex(scripts),
                            'script6': hex(script), 'words': [hex(w) for w in action_words],
                            'slot': slot, 'target': hex(target), 'target_header': read(target, 8).hex()})
                    report['joint_objects'] = []
                    head = word(0x800A8630)
                    nodes, count = word(head), int.from_bytes(read(head+4, 2), 'little')
                    if not 0 < count <= 40: raise ValueError(f'Invalid native node count {count}')
                    for i in range(count):
                        node = nodes+20*i
                        part = int.from_bytes(read(node+16, 2), 'little')
                        if part in (8, 9):
                            coord = word(node+4); obj = word(coord+0x44)
                            report['joint_objects'].append({'part': part, 'object': hex(obj)})
                            result = q('wtrace_add', lo=hex(obj+0x10), hi=hex(obj+0x16))
                            slots.append(result['slot'])
                    report['battle_start_frame'] = q('frame')['frame']
                    shot(report['battle_start_frame']-1, 'battle-start')
                    last_input, step = 0, 0
                    if lifecycle:
                        q('input_route_clear')
                        for duration, button in ((100, 0), (40, 0x40), (6, 0), (4, 8), (200, 0)):
                            q('input_route_append', frames=duration, buttons=65535 ^ button)
                        report['lifecycle_route'] = q('input_route_start', at_frame=q('frame')['frame']+30)
                        lifecycle_stage = 1
                if lifecycle_stage == 1 and word(0x800A868C) == 1:
                    q('input_route_stop'); q('clear_input')
                    before = read(0x800A8624, 32)
                    report['paused_context'] = before.hex()
                    report['paused_action'] = word(0x80072808)
                    # A private, active group is required; neutral pause is insufficient.
                    target = int(report['transition_bindings'][0]['target'], 0)
                    report['pause_inside_own_clip'] = (int.from_bytes(before[:4], 'little') == target and
                        int.from_bytes(before[8:12], 'little') != 0)
                    time.sleep(.7)
                    report['pause_context_unchanged'] = before == read(0x800A8624, 32)
                    report['save_status'] = state_op('save')
                    q('press', buttons=65535 ^ 8, frames=8, port=1, pad_type=0)
                    end = time.monotonic()+4
                    while time.monotonic() < end and word(0x800A868C): time.sleep(.1)
                    report['resumed_before_load'] = word(0x800A868C) == 0
                    time.sleep(.5)
                    report['load_status'] = state_op('load')
                    report['load_restored_paused_context'] = (word(0x800A868C) == 1 and
                        before == read(0x800A8624, 32))
                    q('clear_input')
                    q('press', buttons=65535 ^ 8, frames=8, port=1, pad_type=0)
                    end = time.monotonic()+4
                    while time.monotonic() < end and word(0x800A868C): time.sleep(.1)
                    report['resumed_after_load'] = word(0x800A868C) == 0
                    lifecycle_stage = 2
                    last_input = 0
                if lifecycle_stage != 1 and now-last_input > (.4 if battle else .8):
                    # Native DOWN then release: action5 -> action6 when allowed.
                    # No approach/attacks that would obscure the pose return.
                    button = ((0x0040 if step % 2 == 0 else 0)
                              if battle else (0x0008 if step % 3 == 0 else 0x4000))
                    reply = q('press', buttons=65535 ^ button, frames=16 if battle else 6, port=1, pad_type=0)
                    report['inputs'].append({'button': button, 'reply': reply, 'battle': battle, 'frame': q('frame')['frame']})
                    last_input, step = now, step+1
                if battle and now-last_dump > .2:
                    dump = q('wtrace_dump', count=2048, newest=1)
                    events = dump.get('entries', dump.get('records', dump.get('writes', [])))
                    if not events and 'trace_schema' not in report: report['trace_schema'] = dump
                    for event in events:
                        key = event.get('seq', json.dumps(event, sort_keys=True))
                        if key not in seen:
                            seen.add(key); report['trace'].append(event)
                    frame = q('frame')['frame']
                    state = {'frame_query': frame, 'control': [read(0x80072800+s*0x7C, 12).hex() for s in range(2)],
                             'hp': [word(0x80072840+s*0x7C) & 65535 for s in range(2)],
                             'contexts': [read(0x800A8624+s*0x20, 32).hex() for s in range(2)]}
                    report['steps'].append(state)
                    if len(saved) < 70 and any((int.from_bytes(bytes.fromhex(c)[8:12], 'little') & 255) == 6 for c in state['control']):
                        for f in range(frame-8, frame+1): shot(f, 'action6')
                    # Exact-frame history remains available after action6 has passed.
                    for event in events:
                        value = event.get('new', -1)
                        if isinstance(value, str): value = int(value, 0)
                        addr = event.get('addr', event.get('address', 0))
                        if isinstance(addr, str): addr = int(addr, 0)
                        if len(saved) < 70 and addr in (0x72808, 0x72884) and value & 255 == 6:
                            f = event.get('frame', -1)
                            for image_frame in range(f-2, min(f+9, frame+1)): shot(image_frame, 'native6')
                        if len(saved) < 70 and addr == 0xA8628 and int(event.get('pc', '0'), 0) == 0x800422AC and 2 <= value <= 6:
                            # Only consume samples while this exact action owns the context.
                            active = [x for x in report['trace'][-2048:]
                                      if x.get('addr') == '0x00072808' and x['seq'] <= event['seq']]
                            if active and int(max(active, key=lambda x: x['seq'])['new'], 0) & 255 == 6:
                                shot(event['frame'], f'settle-sample{value-1}')
                    last_dump = now
                time.sleep(.025)
            report['counters'] = q('mod_counters')
            report['ring'] = q('display_ring_stats')
    except Exception as error:
        report['error'] = str(error)
    finally:
        if process and process.poll() is None:
            for slot in sorted(slots, reverse=True):
                try: q('wtrace_del', slot=slot)
                except (ValueError, OSError): pass
            try: q('clear_input'); q('quit')
            except (ValueError, OSError): pass
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                report['forced_shutdown'] = True
                process.terminate(); process.wait(timeout=10)
        if process: report['process_exit'] = process.returncode
        (out/'bridge-session.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return {k: report.get(k) for k in ('battle_start_frame', 'control_ids', 'process_exit', 'error', 'trace_schema')} | {
        'steps': len(report['steps']), 'trace_events': len(report['trace']), 'captures': len(report['captures']),
        'lifecycle': {k: report.get(k) for k in ('pause_inside_own_clip', 'pause_context_unchanged',
                    'resumed_before_load', 'load_restored_paused_context', 'resumed_after_load')}}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--seconds', type=int, default=150)
    p.add_argument('--port', type=int, default=4387)
    p.add_argument('--lifecycle', action='store_true', help='Pause and save/load the native transition owner')
    p.add_argument('--pgxp', action='store_true', help='Use the existing PGXP executable')
    args = p.parse_args()
    if not 30 <= args.seconds <= 600: p.error('Duration 30..600 required')
    print(json.dumps(run(args.out, args.seconds, args.port, args.lifecycle, args.pgxp), indent=2))
