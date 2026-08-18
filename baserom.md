# Required game files

Provide these files locally from your **legally obtained** copy of *Dragon Ball
GT: Final Bout* (USA, SLUS-00493) for the Sony PlayStation. **None of them are
distributed by this project.** This document lets you verify that you have the
exact files the recompile expects, the same way other static-recompilation
projects do (e.g. `baserom.md` in mstan's recomp projects).

## Disc image (`.bin` / `.cue`)

The PlayStation game is distributed on a single-disc CD-ROM. The recompile
reads the data track (Track 01) as a `.bin` plus its `.cue`.

- Expected path: `disc/Dragon Ball GT - Final Bout (USA).bin`
- Data track size: **158,811,744 bytes** (158.8 MB)
- MD5: `2f869f926514278b72ffbd671e69b9f7`
- SHA-1: `8a2373f133788256cba64a1a0ba9fbb4b4667f71`
- Volume ID: `DRAGON_BALL_FB`
- Serial: `SLUS-00493`
- Boot EXE: `SLUS_004.93` (load `0x80010000`, entry `0x80010B98`)

> The `.bin` / `.cue` are **copyrighted** and are **not distributed** by this
> project. You must dump them yourself from the original PlayStation disc you
> own (a Redump-format dump with a full multi-track cue is recommended).

## Extracting the boot executable (optional, advanced)

The boot EXE `SLUS_004.93` lives inside the data track. The `prepare_disc`
step of the toolchain extracts it automatically; you normally do not need to
touch it by hand.
