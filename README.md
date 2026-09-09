# Dragon Ball GT: Final Bout Recompiled

[English](README.md) | [Español](README_ES.md)

[![Release](https://img.shields.io/github/v/release/novapowers0/DB-Final-Bout-Recomp?sort=semver&style=flat-square&color=orange&label=Release)](https://github.com/novapowers0/DB-Final-Bout-Recomp/releases/latest)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6?style=flat-square)](https://github.com/novapowers0/DB-Final-Bout-Recomp/releases/latest)
[![License](https://img.shields.io/github/license/novapowers0/DB-Final-Bout-Recomp?style=flat-square)](LICENSE)
[![Stars](https://img.shields.io/github/stars/novapowers0/DB-Final-Bout-Recomp?style=flat-square&color=yellow)](https://github.com/novapowers0/DB-Final-Bout-Recomp)
[![Built with](https://img.shields.io/badge/built%20with-PSXRecomp-8A2BE2?style=flat-square)](https://github.com/mstan/psxrecomp)

Static recompilation for PC of *Dragon Ball GT: Final Bout* for PlayStation,
based on [PSXRecomp](https://github.com/mstan/psxrecomp) and
[recomp-ui](https://github.com/mstan/recomp-ui).

The original MIPS code is recompiled as native Windows code and integrated into
an independent executable with a launcher, mod support and rendering settings.
This is not a traditional emulator.

| | |
|---|---|
| **Players** | 1-2 |
| **Platform** | Windows x64 |
| **Region** | USA |
| **Serial** | SLUS-00493 |
| **Genre** | 3D fighting |
| **Version** | v0.1.0 |

Copyright (c) 2026 **NovaPowers**. MIT License (see `LICENSE`).

---

## Legal Notice

The game and its data are **not distributed**. You must provide files from your
**legally owned** copy of *Dragon Ball GT: Final Bout*.

- This project expects the USA version `SLUS-00493`.
- See `baserom.md` for the expected size, serial, volume and checksums.
- Disc images, retail BIOS files and generated game code are not included.
- Recompiled code is generated locally from your own game files.

This is an unofficial, non-commercial research and preservation project. It is
not affiliated with or endorsed by Bandai, Shueisha, Toei Animation or any other
Dragon Ball rightsholder.

---

## Playing

1. Download `dbfb-0.1.0-setup-host-win64.zip` from
   [Releases](https://github.com/novapowers0/DB-Final-Bout-Recomp/releases/latest).
2. Extract the package to a Windows folder.
3. Provide your legally owned copy following the identity in `baserom.md`.
4. Run `DBFinalBout_Recompiled.exe` or open the included launcher.
5. Keep widescreen disabled for faithful 4:3 presentation, or enable
   `psx.enhancement.widescreen` for 16:9/adaptive presentation.

The setup-host package may request the game files during first-time setup. Do
not download BIOS files or disc images from this repository.

### Recommended Settings

- **Renderer:** software, as the reference path.
- **Widescreen:** stretch-only; 16:9/adaptive available.
- **Vulkan:** available as an experimental option.
- **PGXP:** separate precision variant included for testing.
- **Netplay:** LAN/direct-IP available; online ICE/TURN is not enabled.

---

## Features

| Feature | Status |
|---|---|
| Static recompilation of the PS1 executable | Functional |
| Windows launcher | Included |
| Overlay cache and native overlay recompilation | Included in the validated build |
| 16:9/adaptive widescreen | Functional in stretch-only mode |
| Experimental FOV/culling | Disabled for stability |
| Software renderer | Reference path |
| Vulkan renderer | Experimental |
| Normal and PGXP runtimes | Included |
| LAN/direct-IP netplay | Compiled, pending full manual testing |
| Online ICE/TURN | Not enabled |

Widescreen preserves the game's original guest coordinates. Some 2D menus may
show a brief 4:3 pillarbox transition when changing scenes.

---

## Repository Structure

```text
DB-Final-Bout-Recomp/
├── psxrecomp/       # Recompiler and runtime submodule
├── recomp-ui/       # Launcher and UI submodule
├── mods/            # Mod configuration and manifests
├── seeds/           # Final Bout executable seeds
├── ghidra_proj/     # Reverse-engineering and analysis tools
├── tools/           # Build, diagnostic and validation scripts
├── generated/       # NOT included: locally generated code
├── disc/            # NOT included: your legally owned disc image
├── game.toml        # Runtime configuration
└── CMakeLists.txt   # Project build definition
```

---

## Building From Source

Main requirements:

- Windows x64.
- Git with submodules.
- CMake 3.20 or newer.
- Ninja or another supported CMake generator.
- Python 3.
- A toolchain compatible with PSXRecomp.
- The legally owned disc described in `baserom.md`.

```bash
git clone --recurse-submodules https://github.com/novapowers0/DB-Final-Bout-Recomp.git
cd DB-Final-Bout-Recomp

git submodule update --init --recursive
./psxrecomp/tools/ci/build_emitters.sh

python3 psxrecomp/psxrecomp_cli.py generate \
  --config game.toml \
  --project-root . \
  --disc "disc/<your-disc>.cue"

cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --target psx-runtime
```

To validate the installation without launching the game:

```bash
python tools/verify_offline.py
```

The contents of `generated/` are derived from your disc and must never be
committed. Build artifacts and game images are ignored by Git.

---

## Documentation and Diagnostics

- `baserom.md`: disc identity and checksums.
- `AGENTS.md`: project rules and technical state.
- `ANALISIS_CRASHES.md`: freeze and overlay investigation.
- `SESSION_ANALYSIS.md`: session capture and analysis workflow.
- `summary.md`: detailed decision and validation history.
- `tools/verify_offline.py`: reproducible validation without launching the game.

---

## Version History

### v0.1.0

First playable and validated release, with the updated runtime, overlay cache,
stretch-only widescreen, experimental Vulkan and compiled netplay support.

The original `v0.0.1` publication was withdrawn because it was too unstable,
with crashes/freezes during menu and fight transitions and insufficient
validation to present it as a supported release.

---

## Credits

- [PSXRecomp](https://github.com/mstan/psxrecomp): PS1 recompiler and runtime.
- [recomp-ui](https://github.com/mstan/recomp-ui): launcher and UI components.
- [recomp-net](https://github.com/TechnicallyComputers/recomp-net): netplay
  transport and support.
- **NovaPowers**: Final Bout integration, configuration, mods and tooling.
