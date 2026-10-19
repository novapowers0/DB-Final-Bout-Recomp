"""Bounded local smoke session with private output and guaranteed process cleanup.

Launches the existing runtime only on --launch. Uses fresh memory cards, never
edits RAM or mod choices, and reports observed counters rather than claiming a
human playtest. The PS1 debug word has START at bit 3 (0x0008), not 0x0800.
"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import time

from combat_live import query
from combat_map import ROOT


def assess(report, required_kos=1):
    """Observed requirements, independent of the runtime's quit exit convention."""
    counters = {c['name']: c['count'] for c in report.get('counters', {}).get('counters', [])}
    active = knocked_out = False
    completed = 0
    for step in report.get('steps', []):
        if not step.get('battle_code'):
            if active and knocked_out:
                completed += 1
            active = knocked_out = False
        elif 17 <= step.get('object_stride', 0) <= 36:
            hp = [p['hp'] for p in step.get('fighters', [])]
            if len(hp) == 2:
                if all(0 < value <= 32767 for value in hp) and not active:
                    active = True
                elif active and 0 in hp:
                    knocked_out = True
    report['completed_combats'] = completed
    checks = {
        'combat': (completed > 0 if report.get('expect_original') else
                   counters.get('dbfb.responsive.combat_poll', 0) > 0),
        'kos': (completed >= required_kos if report.get('expect_original') else
                counters.get('dbfb.responsive.ko_impact', 0) >= required_kos),
        'completed_combats': completed >= required_kos,
        'pause_and_resume': bool(report.get('pause')) and all(
            p['before'] == 0 and p['paused'] == 1 and p['resumed'] == 0 for p in report['pause']),
        'normal_shutdown': report.get('process_exit') == 0 and not report.get('forced_shutdown'),
        'no_error': 'error' not in report,
    }
    if report.get('savestate_requested'):
        checks['save_and_load'] = all(report.get('savestate', {}).get(op, {}).get('last_ok') == 1
                                      for op in ('save', 'load'))
    if report.get('movement_requested'):
        if not report.get('expect_original'):
            checks['self_locomotion'] = counters.get('dbfb.responsive.locomotion', 0) > 0
    if report.get('expect_original'):
        checks['original_inert'] = not any(value for name, value in counters.items()
                                          if name.startswith('dbfb.responsive.'))
    report['checks'] = checks
    report['passed'] = all(checks.values())
    return report['passed']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launch', action='store_true', required=True)
    parser.add_argument('--port', type=int, default=4372)
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--kos', type=int, default=1, help='Minimum observed KOs (1..10)')
    parser.add_argument('--savestate', action='store_true', help='Save/load slot 0 in the fresh private card directory')
    parser.add_argument('--movement', action='store_true', help='Exercise native directions alongside attacks')
    parser.add_argument('--summary', action='store_true', help='Print compact results; retain the full private report')
    parser.add_argument('--runtime-dir', type=Path, default=ROOT/'build-release',
                        help='Existing build or extracted release (never edits its choices)')
    parser.add_argument('--pgxp', action='store_true', help='Use the PGXP executable')
    parser.add_argument('--disc', type=Path, help='Explicit private disc for a clean extracted release')
    parser.add_argument('--expect-original', action='store_true', help='Require default-off combat and native KOs')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if not 30 <= args.seconds <= 600 or not 1024 <= args.port <= 65535 or not 1 <= args.kos <= 10:
        parser.error('Session must be 30..600 seconds and use an unprivileged port')
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error('Use a NEW output folder under an existing parent')
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', args.port))
        except OSError:
            parser.error('Debug port is already in use; no existing session will be touched')
    args.out.mkdir()
    out = args.out.resolve()
    report = {'human_playtest': False, 'steps': [], 'combat_observed': False, 'pause': [],
              'savestate_requested': args.savestate, 'movement_requested': args.movement,
              'expect_original': args.expect_original}
    runtime = args.runtime_dir.resolve()
    executable = runtime/('DBFinalBout_Recompiled_pgxp.exe' if args.pgxp else 'DBFinalBout_Recompiled.exe')
    command = [str(executable),
               '--game', str(runtime/'game.toml'), '--headless',
               '--no-launcher', '--debug-port', str(args.port), '--memcard-dir', str(out / 'cards')]
    if args.disc:
        command += ['--disc', str(args.disc.resolve())]
    report['command'] = command
    process = None

    def q(cmd, **params):
        return query(cmd, args.port, **params)

    def read(address):
        return int.from_bytes(bytes.fromhex(q('read_ram', addr=hex(address), len=4)['hex']), 'little')

    def snapshot(label):
        record = {'label': label, 'frame': q('frame')['frame'],
                  'roster_word': hex(read(0x8003BCC4)), 'object_stride': read(0x80072A00) >> 16,
                   'battle_code': read(0x80054A60) == 0x84242856}
        if record['battle_code']:
            record['fighters'] = [{'hp': read(0x80072840+side*0x7C) & 0xFFFF,
                                   'action': read(0x80072808+side*0x7C) & 255,
                                   'cpu': bool(read(0x80072800+side*0x7C) & 1),
                                   'difficulty': read(0x80072960+side*0x24) & 0xFFFF}
                                  for side in range(2)]
        report['steps'].append(record)
        # Keep the last good observation even if the process later crashes.
        report['counters'] = q('mod_counters')
        try:
            q('screenshot_file', path=str(out / f'{len(report["steps"]):03d}-{label}.png'))
        except ValueError as error:
            if 'display disabled' not in str(error):
                raise
            record['screenshot_skipped'] = 'native display disabled during transition'
        return record

    def state_probe():
        report['savestate'] = {}
        for op in ('save', 'load'):
            generation = q('savestate_status')['generation']
            q('savestate', op=op, slot=0)
            until = min(deadline, time.monotonic()+20)
            while time.monotonic() < until:
                status = q('savestate_status')
                if status['generation'] > generation and not status['pending']:
                    report['savestate'][op] = status
                    if status['last_ok'] != 1 or status['last_op'] != op:
                        raise RuntimeError(f'Savestate {op} failed: {status}')
                    break
                time.sleep(.2)
            else:
                raise RuntimeError(f'Savestate {op} did not complete at a safe boundary')
        snapshot('after-load')

    try:
        with (out / 'runtime.stdout').open('wb') as stdout, (out / 'runtime.stderr').open('wb') as stderr:
            process = subprocess.Popen(command, cwd=out, stdout=stdout, stderr=stderr)
            deadline = time.monotonic()+args.seconds
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'Runtime exited before connection: {process.returncode}')
                try:
                    q('frame'); break
                except (OSError, ValueError):
                    time.sleep(.5)
            else:
                raise RuntimeError('Debug server did not become available')
            time.sleep(8)
            snapshot('boot')
            pause_probed = False
            step = 0
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'Runtime exited during session: {process.returncode}')
                battle = read(0x80054A60) == 0x84242856
                if battle:
                    report['combat_observed'] = True
                    buttons = (0x0020, 0x1000, 0x0080, 0x4000, 0x8000) if args.movement else (0x1000, 0x4000, 0x8000)
                    button = buttons[step % len(buttons)]
                else:
                    button = 0x0008 if step % 3 == 0 else 0x4000
                q('press', buttons=0xFFFF ^ button, frames=8, port=1, pad_type=0)
                time.sleep(.5)
                q('clear_input')
                time.sleep(1.5)
                if step % 3 == 0:
                    snapshot('combat' if battle else 'menu')
                if (battle and not pause_probed and
                    17 <= (read(0x80072A00) >> 16) <= 36 and
                    all(read(0x80072840+side*0x7C) & 0xFFFF for side in range(2))):
                    pause_probed = True
                    before = read(0x800A868C)
                    paused = resumed = None
                    for _ in range(4):
                        q('press', buttons=0xFFFF ^ 0x0008, frames=8, port=1, pad_type=0)
                        time.sleep(1.0); q('clear_input'); time.sleep(1.0)
                        if read(0x800A868C) != before:
                            paused = read(0x800A868C); break
                    for _ in range(4):
                        if paused is None:
                            break
                        q('press', buttons=0xFFFF ^ 0x0008, frames=8, port=1, pad_type=0)
                        time.sleep(1.0); q('clear_input'); time.sleep(1.0)
                        if read(0x800A868C) == before:
                            resumed = read(0x800A868C); break
                    report['pause'].append({'frame': q('frame')['frame'], 'before': before,
                                             'paused': paused, 'resumed': resumed})
                    if before != 0 or paused != 1 or resumed != 0:
                        raise RuntimeError('Native pause/resume was not confirmed')
                    if args.savestate:
                        state_probe()
                step += 1
            report['counters'] = q('mod_counters')
            report['combat_observed'] = any(
                c['name'] == 'dbfb.responsive.combat_poll' and c['count'] > 0
                for c in report['counters'].get('counters', []))
            report['loader'] = q('overlay_loader_status')
            snapshot('final')
    except Exception as error:
        report['error'] = str(error)
    finally:
        if process is not None and process.poll() is None:
            try:
                q('quit')
            except (OSError, ValueError) as error:
                # The server may close its socket before the OK is delivered.
                # A lost reply is not evidence that the process needs killing.
                report['quit_reply_error'] = str(error)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                report['forced_shutdown'] = True
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=10)
        if process is not None:
            report['process_exit'] = process.returncode
        assess(report, args.kos)
        (out / 'smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        if args.summary:
            print(json.dumps({key: report.get(key) for key in
                              ('passed', 'checks', 'process_exit', 'completed_combats', 'error')}, indent=2))
        else:
            print(json.dumps(report, indent=2))
        print(f'Private evidence: {out}')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
