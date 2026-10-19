"""Package the validated Windows build using the framework's release stager.

Offline: reuse the working local Python and TinyCC, refresh emitters and
headers from this build. Never include developer settings, disc data or states.
Existing stages/archives are refused rather than overwritten.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def bash_path(path):
    p = Path(path).resolve().as_posix()
    return '/' + p[0].lower() + p[2:] if len(p) > 1 and p[1] == ':' else p


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT/'build-release')
    parser.add_argument('--recompiler-build', type=Path, default=ROOT/'build-recompiler')
    parser.add_argument('--installed-toolchain', type=Path, default=ROOT/'psxrecomp/overlay_toolchain')
    parser.add_argument('--mingw-bin', type=Path, default=Path('C:/msys64/mingw64/bin'))
    parser.add_argument('--clang-bin', type=Path, default=Path.home()/'.local/share/retcomm/toolchains/cmake-clang-v1/1.0.14/x86_64-w64-mingw32/bin')
    parser.add_argument('--bash', type=Path, default=Path('C:/Program Files/Git/bin/bash.exe'))
    args = parser.parse_args()
    version = (ROOT/'VERSION').read_text().strip()
    stage = ROOT/'dist/stage-game-windows-x64'
    archive = ROOT/f'dist/dbfb-{version}-windows-x64.zip'
    if stage.exists() or archive.exists():
        parser.error('Stage or ZIP already exists; preserve it under a backup name first')
    for required in (Path(sys.base_prefix)/'python.exe', args.installed_toolchain/'tcc/tcc.exe',
                     args.build/'DBFinalBout_Recompiled_pgxp.exe'):
        if not required.is_file():
            parser.error(f'Missing existing component: {required}')
    env = dict(os.environ, PSX_RELEASE_STAGE_PYTHON=Path(sys.executable).as_posix(),
               PATH=str(args.mingw_bin)+os.pathsep+os.environ.get('PATH', ''))
    def bash(script, *values):
        subprocess.run([str(args.bash), bash_path(script), *map(str, values)],
                       cwd=ROOT, env=env, check=True)
    framework = ROOT/'psxrecomp'
    bash(framework/'tools/package_game_release.sh',
         '--build-dir', bash_path(args.build), '--artifact', 'windows-x64',
         '--zip-prefix', 'dbfb', '--exe-name', 'DBFinalBout_Recompiled',
         '--display-name', 'DB Final Bout Recompiled',
         '--recompiler-build', bash_path(args.recompiler_build),
         '--overlay-cache-root', bash_path(args.build/'cache'),
         '--runtime-bin', bash_path(args.mingw_bin), '--stage-only',
         '--no-overlay-toolchain', '--exclude-dev-mods',
         '--doc', 'baserom.md', '--doc', f'RELEASE_NOTES_v{version}.md')
    tc = stage/'overlay_toolchain'
    tc.mkdir()
    shutil.copytree(args.installed_toolchain/'tcc', tc/'tcc')
    # The checkout's embedded Python may omit its standard-library ZIP. Build a
    # relocatable payload from the working local installation, with no pip or
    # site-packages and no network/download step.
    python_root = Path(sys.base_prefix)
    py = tc/'python'
    py.mkdir()
    for source in [python_root/'python.exe', *python_root.glob('python*.dll'),
                   *python_root.glob('vcruntime*.dll'), python_root/'LICENSE.txt',
                   *(python_root/'DLLs').glob('*.pyd'), *(python_root/'DLLs').glob('*.dll')]:
        shutil.copy2(source, py/source.name)
    stem = f'python{sys.version_info.major}{sys.version_info.minor}'
    with zipfile.ZipFile(py/f'{stem}.zip', 'x', compression=zipfile.ZIP_DEFLATED) as library:
        for source in (python_root/'Lib').rglob('*.py'):
            relative = source.relative_to(python_root/'Lib')
            if not set(relative.parts) & {'site-packages', '__pycache__', 'test', 'tests', 'idlelib', 'tkinter', 'turtledemo'}:
                library.write(source, relative.as_posix())
    (py/f'{stem}._pth').write_text(f'{stem}.zip\n.\n', encoding='ascii')
    subprocess.run([str(py/'python.exe'), '-c',
                    'import encodings,json,tomllib,subprocess,concurrent.futures,zlib; print("Portable Python OK")'],
                   check=True)
    for name in ('psxrecomp-game.exe', 'psxrecomp-bios.exe'):
        shutil.copy2(args.recompiler_build/name, tc/name)
    for name in ('compile_overlays.py', 'bios_module_build.py'):
        shutil.copy2(framework/'tools'/name, tc/name)
    subprocess.run([str(py/'python.exe'), str(tc/'compile_overlays.py'), '--help'],
                   check=True, stdout=subprocess.DEVNULL)
    subprocess.run([str(tc/'tcc/tcc.exe'), '-v'], check=True)
    for rel, pattern in (('runtime/include', '*.h'), ('runtime/include', '*.c.inc'),
                         ('bios', '*.toml'), ('recompiler/seeds', '*.json')):
        dest = tc/('include' if rel == 'runtime/include' else rel)
        dest.mkdir(parents=True, exist_ok=True)
        for source in (framework/rel).glob(pattern):
            shutil.copy2(source, dest/source.name)
    shutil.copy2(args.build/'DBFinalBout_Recompiled_pgxp.exe', stage)
    subprocess.run([sys.executable, str(framework/'tools/release_stage.py'), 'stage-execution',
                    '--binary', str(stage/'DBFinalBout_Recompiled_pgxp.exe'),
                    '--manifest', str(args.build/'DBFinalBout_Recompiled_pgxp.execution.json'),
                    '--output', str(stage/'DBFinalBout_Recompiled_pgxp.execution.json')], check=True)
    for binary in (stage/'DBFinalBout_Recompiled_pgxp.exe', tc/'psxrecomp-game.exe', tc/'psxrecomp-bios.exe'):
        bash(framework/'tools/bundle_mingw_dlls.sh', '--runtime-bin', bash_path(args.mingw_bin),
             '--runtime-bin', bash_path(args.clang_bin), '--exe', bash_path(binary),
             '--dest', bash_path(binary.parent))
    # GCC-generated overlay DLLs resolve their runtime dependencies beside the EXE.
    for name in ('libgcc_s_seh-1.dll', 'libstdc++-6.dll', 'libwinpthread-1.dll'):
        shutil.copy2(args.mingw_bin/name, stage/name)
    for binary in (stage/'libstdc++-6.dll',):
        bash(framework/'tools/bundle_mingw_dlls.sh', '--runtime-bin', bash_path(args.mingw_bin),
             '--exe', bash_path(binary), '--dest', bash_path(stage))
    forbidden_suffixes = {'.cue', '.iso', '.img', '.chd', '.mcd', '.mcr', '.pst', '.png', '.bak'}
    for p in stage.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(stage).as_posix()
        if (p.suffix.lower() in forbidden_suffixes and not rel.startswith('assets/')) or (
            p.suffix.lower() == '.bin' and rel != 'bios/openbios.bin') or p.name in (
                'state.toml', 'disc.cfg', 'rom.cfg', 'bios.cfg', 'settings.toml', 'compiler.txt'):
            raise RuntimeError(f'Private/unwanted payload: {rel}')
    manifests = list((stage/'mods/bundled').glob('*/*/manifest.toml'))
    combat = next(tomllib.loads(p.read_text(encoding='utf-8')) for p in manifests
                  if tomllib.loads(p.read_text(encoding='utf-8'))['id'] == 'dbfb.responsive')
    if {f['id'] for f in combat['feature']} != {'standard', 'unlock-all'} or any(
            f.get('default_enabled') for f in combat['feature']):
        raise RuntimeError('Wrong public combat catalog/defaults')
    files = sorted(p for p in stage.rglob('*') if p.is_file())
    manifest = {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (stage/'SHA256SUMS.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file():
                z.write(p, p.relative_to(stage).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError('ZIP CRC validation failed')
        for name, digest in manifest.items():
            if hashlib.sha256(z.read(name)).hexdigest() != digest:
                raise RuntimeError(f'ZIP hash mismatch: {name}')
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{sha}  {archive.name}\n', encoding='ascii')
    print(json.dumps({'archive': str(archive), 'sha256': sha, 'bytes': archive.stat().st_size,
                      'files': len(manifest)+1, 'public_features': ['standard', 'unlock-all']}, indent=2))


if __name__ == '__main__':
    main()
