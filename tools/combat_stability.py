"""Repeatable, isolated original/renewed/PGXP regression from a checked ZIP.

No installs, personal settings, saves or disc files are copied. A local build
may replace the package executables explicitly for diagnosis. PASS describes
only these sessions, not an explanation of older intermittent failures.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FEATURES = '''format_version = 2
[[feature]]
package_id = "dbfb.responsive"
id = "standard"
enabled = true
[[feature]]
package_id = "dbfb.responsive"
id = "unlock-all"
enabled = true
'''


def runtime_checks(report):
    return {
        'normal_runtime_exit': report.get('exit_origin') == 'tcp_quit',
        'autocompile_ready': report.get('autocompile_degraded') == 0,
        'no_unsupported_instruction': report.get('interp_unsupported', {}).get('midblock_count') == 0,
        'no_unknown_dispatch': report.get('unknown_dispatch_tail', {}).get('total') == 0,
        'no_sampler_suspension': report.get('host_sampler_max_suspend_us') == 0,
    }


def extract_checked(archive, destination):
    """Check the entire archive before extracting into a new private folder."""
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive entries')
        for name in names:
            if (name.startswith('/') or Path(name).is_absolute() or '\\' in name or ':' in name or
                    '..' in Path(name).parts):
                raise ValueError(f'Unsafe archive path: {name}')
        sums = json.loads(z.read('SHA256SUMS.json'))
        if set(names) != set(sums) | {'SHA256SUMS.json'}:
            raise ValueError('Archive file inventory differs from its checksum manifest')
        for name, digest in sums.items():
            if hashlib.sha256(z.read(name)).hexdigest() != digest:
                raise ValueError(f'Archive hash mismatch: {name}')
        if 'mods/state.toml' in names:
            raise ValueError('A public package must not contain personal mod choices')
        destination.mkdir()
        z.extractall(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    parser.add_argument('--archive', type=Path, default=ROOT / f'dist/dbfb-{version}-windows-x64.zip')
    parser.add_argument('--build', type=Path, help='Explicit local diagnostic executables and execution manifests')
    parser.add_argument('--disc', type=Path, default=ROOT / 'disc/Dragon Ball GT - Final Bout (USA).bin')
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--original-seconds', type=int, default=600)
    parser.add_argument('--rounds', type=int, default=1)
    parser.add_argument('--modes', nargs='+', choices=('original', 'standard', 'pgxp'),
                        default=['original', 'standard', 'pgxp'])
    parser.add_argument('--stop-on-failure', action='store_true')
    parser.add_argument('--port', type=int, default=4410)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if not (30 <= args.seconds <= 600 and 30 <= args.original_seconds <= 600 and
            1 <= args.rounds <= 3 and 1024 <= args.port <= 65535):
        parser.error('Use 30..600 seconds, 1..3 rounds and an unprivileged port')
    if args.out.exists() or not args.out.parent.is_dir() or not args.disc.is_file():
        parser.error('Use a new output folder under an existing parent and a local disc')
    args.out.mkdir()
    results = []
    for iteration in range(1, args.rounds + 1):
        for mode in args.modes:
            label = f'{iteration}-{mode}'
            payload = args.out / f'{label}-payload'
            extract_checked(args.archive, payload)
            if args.build:
                for suffix in ('', '_pgxp'):
                    stem = 'DBFinalBout_Recompiled' + suffix
                    for extension in ('.exe', '.execution.json'):
                        shutil.copy2(args.build / (stem + extension), payload)
            if mode != 'original':
                (payload / 'mods/state.toml').write_text(FEATURES, encoding='utf-8')
            seconds = args.original_seconds if mode == 'original' else args.seconds
            run = args.out / label
            command = [sys.executable, '-B', str(ROOT / 'tools/combat_smoke.py'), '--launch',
                       '--runtime-dir', str(payload), '--disc', str(args.disc.resolve()),
                       '--seconds', str(seconds), '--port', str(args.port), '--kos', '1',
                       '--savestate', '--movement', '--summary', '--out', str(run)]
            command += ['--expect-original'] if mode == 'original' else ['--pgxp'] if mode == 'pgxp' else []
            result = subprocess.run(command, cwd=ROOT, timeout=seconds + 120)
            smoke = json.loads((run / 'smoke.json').read_text(encoding='utf-8'))
            report_path = run / 'psx_last_run_report.json'
            report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
            checks = runtime_checks(report)
            results.append({'label': label, 'seconds': seconds, 'exit': result.returncode,
                            'passed': result.returncode == 0 and all(checks.values()),
                            'checks': {**smoke.get('checks', {}), **checks},
                            'completed_combats': smoke.get('completed_combats'),
                            'build': report.get('build'),
                            'watchdog_max_check_gap': report.get('watchdog_max_check_gap'),
                            'watchdog_host_sections': report.get('watchdog_host_sections'),
                            'overlay_load_max_us': report.get('overlay_load_max_us'),
                            'binary_sha256': hashlib.sha256((payload / (
                                'DBFinalBout_Recompiled_pgxp.exe' if mode == 'pgxp' else
                                'DBFinalBout_Recompiled.exe')).read_bytes()).hexdigest()})
            (args.out / 'matrix.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
            if args.stop_on_failure and not results[-1]['passed']:
                print(json.dumps(results, indent=2))
                return 1
    print(json.dumps(results, indent=2))
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
