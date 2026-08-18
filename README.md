# DBFinalBout Recompiled

Copyright (c) 2026 **NovaPowers**. Released under the MIT License (see `LICENSE`).

Static recompilation of **Dragon Ball GT: Final Bout** (USA, SLUS-00493) for the
Sony PlayStation, built on [psxrecomp](https://github.com/mstan/psxrecomp) and
[recomp-ui](https://github.com/mstan/recomp-ui), targeting a native Windows PC
port.

| | |
|---|---|
| Players | 2 |
| Region | USA |
| Serial | SLUS-00493 |
| Publisher | Bandai |
| Year | 1997 |

---

## ⚖️ Copyright / Legal

**The game and its data are NOT distributed.** You must supply the files from
your **legally obtained** copy of *Dragon Ball GT: Final Bout* (the `.bin` /
`.cue` disc image). This project follows the "copyright-friendly" convention of
the static-recompilation community (e.g. `mstan`'s recomp projects): the code,
launcher and tools are distributed; **the game's copyrighted content is not**.

- See `baserom.md` for the exact file identity (size and checksums) and how to
  obtain the dump.
- The recompiled code (`generated/`) is generated **locally** from your disc and
  is **never committed** to the repository.
- Disc images under `disc/` are gitignored and must never be committed. Retail
  BIOS dumps are not redistributed; OpenBIOS is used for Generate unless you
  supply your own SCPH locally.

Unofficial, non-commercial, research and preservation project. Not affiliated
with or endorsed by Bandai, Shueisha, Toei Animation, or any rightsholder of
Dragon Ball.

---

## ⚠️ Status

Both enhancements shipped in this repository are **WORK IN PROGRESS**:

- **Widescreen** (`psx.enhancement.widescreen`) — works in stretch-only mode.
  Known issue: shadow/far-depth projection problems exist on the vanilla (4:3)
  port and are not fixed by this mod.
- **Custom Combat Engine** (`psx.enhancement.custom-combat`) — **NOT
  RECOMMENDED FOR USE.** The guest bridge (animation IDs / fighter base) is
  incomplete; do not enable it on a real fight.

---

## Estructura de carpetas

```
DBFinalBoutRecomp/
├── disc/                # NO incluido. Tu copia legal del juego (.bin/.cue) — ver baserom.md
├── src / psxrecomp/     # Runtime + recompiler (submodule con los mods de NovaPowers)
├── mods/                # Manifiestos .psxmod de los mods (widescreen WIP, custom-combat WIP)
├── generated/           # NO incluido. Código recompilado generado localmente (ver abajo)
├── seeds/               # Seeds de primera pasada del boot EXE
├── ghidra_proj/         # Scripts de análisis / ingeniería inversa
├── tools/               # Utilidades
└── docs/                # Documentación de sesiones y estado
```

## Quick start (dev)

```bash
git submodule update --init --recursive
./psxrecomp/tools/ci/build_emitters.sh
python3 psxrecomp/psxrecomp_cli.py generate \
  --config game.toml --project-root . --disc disc/<your>.cue
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --target psx-runtime
```

Zip prefix for CI artifacts: `dbfb`.

## Symbols

Progressive map: `symbols.toml` → `python3 tools/sync_symbols.py` →
`psx_symbols.h` (`PSX_FN_*`). See `psxrecomp/docs/SYMBOLS.md`.

## Framework pins

Submodule gitlinks (`psxrecomp`, optional `recomp-ui`, nested `recomp-net`)
are authoritative. `framework_pins.txt` is an optional scaffold snapshot;
release CI logs SHAs with `record_pins.sh` but builds whatever the gitlinks
resolve to. Bump submodules deliberately — do not float on `main`/`master`
in release CI.
