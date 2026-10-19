"""Private camera A/B from the same paused state and frame-scheduled inputs.

Copies cards into NEW directories; never modifies the source state. Captures
the runtime's display/history rings, not a reconstructed scene. PNGs and state
payloads belong outside the repository. No third-party modules required.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

from combat_live import query
from combat_map import ROOT


def run(out, source_cards, port, enabled):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))
    out.mkdir()
    shutil.copytree(source_cards, out / 'cards')
    env = dict(os.environ, DBFB_CAMERA_FRAMING=str(int(enabled)))
    report = {'enabled': enabled, 'samples': []}
    process = None
    def q(cmd, **kw):
        return query(cmd, port, **kw)
    def word(addr):
        return int.from_bytes(bytes.fromhex(q('read_ram', addr=hex(addr), len=4)['hex']), 'little')
    try:
        with (out/'stdout.txt').open('xb') as stdout, (out/'stderr.txt').open('xb') as stderr:
            process = subprocess.Popen([str(ROOT/'build-release/DBFinalBout_Recompiled.exe'),
                '--game', str(ROOT/'build-release/game.toml'), '--headless', '--no-launcher',
                '--debug-port', str(port), '--memcard-dir', str(out/'cards')],
                cwd=out, env=env, stdout=stdout, stderr=stderr)
            deadline = time.monotonic()+120
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'Exited {process.returncode}')
                try:
                    q('frame'); break
                except (ValueError, OSError):
                    time.sleep(.2)
            time.sleep(8)
            # The state includes the standard mod's allocated guest arenas.
            # Enter combat first so the receiver has the same memory layout.
            step = 0
            while time.monotonic() < deadline:
                if (word(0x80054A60) == 0x84242856 and
                    17 <= word(0x80072A00) >> 16 <= 36 and
                    word(0x8006F794) >= 0x9F000000):
                    break
                q('press', buttons=65535 ^ (8 if step % 3 == 0 else 0x4000),
                  frames=6, port=1, pad_type=0)
                step += 1
                time.sleep(.8)
            else:
                raise RuntimeError('Combat memory layout was not initialized')
            generation = q('savestate_status')['generation']
            q('savestate', op='load', slot=0)
            while time.monotonic() < deadline:
                status = q('savestate_status')
                if status['generation'] > generation and not status['pending']:
                    if status['last_ok'] != 1:
                        raise RuntimeError(status)
                    report['load'] = status
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('Load timed out')
            if word(0x800A868C) != 1:
                raise RuntimeError('Source must be paused inside the native transition')
            for slot, addr in enumerate((0x80072800, 0x8007287C, 0x800A9FF0)):
                q('set_snapshot', slot=slot, addr=hex(addr))
            q('input_route_clear')
            # Resume at an exact relative frame, then neutral/move/flight/attacks.
            route = [(8, 8), (52, 0), (50, 0x20), (35, 0), (50, 0x80),
                     (35, 0), (45, 0x10), (45, 0), (8, 0x8000), (60, 0),
                     (8, 0x1000), (60, 0), (8, 0x40), (60, 0)]
            for frames, buttons in route:
                q('input_route_append', frames=frames, buttons=65535 ^ buttons)
            anchor = q('frame')['frame']+60
            report['route'] = q('input_route_start', at_frame=anchor)
            offsets = [20, 60, 100, 145, 195, 230, 270, 315, 350, 400, 460, 520, 580]
            for offset in offsets:
                frame = anchor+offset
                while q('frame')['frame'] <= frame+1:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Capture timed out')
                    time.sleep(.01)
                capture = q('display_ring_get', frame=frame, path=str(out/f'{offset:04d}.png'))
                sample = {'offset': offset, 'capture': capture, 'ram': {}}
                for addr, size in ((0x80072800, 124), (0x8007287C, 124), (0x800A9FF0, 32)):
                    sample['ram'][hex(addr)] = q('read_frame_ram', frame=frame,
                                                addr=hex(addr), len=size)['hex']
                report['samples'].append(sample)
            report['counters'] = q('mod_counters')
            report['host'] = q('host_profile')
    except Exception as error:
        report['error'] = str(error)
    finally:
        if process and process.poll() is None:
            try:
                q('clear_input'); q('quit')
            except (OSError, ValueError):
                pass
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                report['forced_shutdown'] = True
                process.terminate(); process.wait(timeout=10)
        report['exit'] = process.returncode if process else None
        (out/'session.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source-cards', type=Path, required=True)
    parser.add_argument('--port', type=int, default=4402)
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir() or not args.source_cards.is_dir():
        parser.error('New output under an existing parent and existing source cards required')
    out = args.out.resolve()
    out.mkdir()
    a = run(out/'on', args.source_cards.resolve(), args.port, True)
    b = run(out/'off', args.source_cards.resolve(), args.port+1, False)
    pairs = []
    for x, y in zip(a['samples'], b['samples']):
        pairs.append({'offset': x['offset'], 'fighter_state_identical': all(
            x['ram'][hex(addr)] == y['ram'][hex(addr)] for addr in (0x80072800, 0x8007287C)),
            'camera_identical': x['ram']['0x800a9ff0'] == y['ram']['0x800a9ff0']})
    summary = {'sessions': [{k: r.get(k) for k in ('enabled', 'exit', 'error', 'forced_shutdown')}
                            for r in (a, b)], 'pairs': pairs}
    summary['passed'] = (len(pairs) == 13 and all(p['fighter_state_identical'] for p in pairs)
                         and all(r.get('exit') == 0 and 'error' not in r for r in (a, b)))
    (out/'comparison.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
