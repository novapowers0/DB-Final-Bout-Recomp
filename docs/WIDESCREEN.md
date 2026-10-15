# Native widescreen preview

This default-disabled SLUS-00493 mod offers fixed 16:9 or an adaptive combat view
from 4:3 through 21:9. Select OpenGL in the launcher before enabling **Final Bout
Native Widescreen (OpenGL Preview)**. Software remains the default 4:3 reference
renderer. Native-wide behavior on software/Vulkan is not qualified by this work.

The package is `finalbout.enhancement.widescreen`, version 0.1.0. It replaces the
framework-owned stretch package in this project's shipped catalog so two mods
cannot compete for the aspect. Both normal and PGXP targets compile the title
plugin, and setup-host packaging includes its source and preloaded manifest.

The generated entry hook at `80028D80` runs before static PsyQ DMA submission.
It validates the combat overlay and bounded packet lists before offering exact
HUD/background packets to the renderer's content/freshness guards. The mod does
not write guest RAM, change GTE projection, widen guest culling or alter gameplay
timing. A regeneration is required to insert the entry hook; rebuilding an old
generated dispatch alone is insufficient.

HUD recognition covers two 512-coordinate combat banks at `80072A14`, stride
`30C`. VS/PAUSE remain centred; other fields use their signed-X anchors. Eleven
disc-certified stage layouts have tiles 32x32, map widths 16/24/32 and heights up
to eleven rows. Recognition proves map/atlas identity, complete row geometry/UV/
link order, odd-scroll FT4 strips, stage-specific gradients and alternate OT
links. Queued origins come from serialized packets, rather than a later camera/
scroll value. Disabled panoramas and nearby effects remain excluded. The maximum
198 panorama primitives plus three gradients fit the existing `0x3000` bank;
there is no guest buffer or admission expansion.

## Dependency prerequisite

The original project pins a custom `psxrecomp` fork at `7d70880d`. Its upstream
base predates the explicit opaque-sprite background service required by this
mod. The prepared local fork refresh merges landed upstream `f9c287f5` and
preserves the fork's SIO compatibility option, RI dispatch/diagnostics, legacy
widescreen registration and spectator restriction. It includes the landed CD
FIFO fix and opaque sprite background service. Two merge conflicts were resolved
by retaining both SIO/direct-shortcut parser fields and all mod source entries.
The UI pin is updated to `41c88ffe`. The fork refresh also advances nested network
dependencies, so it needs separate dependency review before accepting this draft.

Framework merge `237ef8dc` includes the reviewed retained-composite scale fix from
upstream PR #665, which is still awaiting upstream integration. LAN/direct-IP
scope is preserved by keeping ICE disabled in the title build.

The framework merge is published in the [companion framework draft](https://github.com/novapowers0/psxrecomp/pull/1),
and its pinned commit is fetchable through this project's framework remote.
Do not treat this draft as a released dependency set until the companion framework
changes are reviewed. First-run generation must refresh BIOS/game C
and native overlay caches with that framework. The local setup-host configure
reports a stale OpenBIOS emitter stamp after preserving the fork's config
additions; the guard has not been suppressed. BIOS regeneration remains part of
the prerequisite before gameplay acceptance.

## Evidence and remaining work

Local source profile verification, catalog staging and title-plugin compilation
for normal/PGXP targets pass. The normal first-run setup host also builds with
native Windows Clang 22 at two jobs. This does not establish a generated-game
build, the full PGXP executable or gameplay in this repository.
The full offline verifier was run and stops at the missing deployed
`build-release/game.toml` in this source-only checkout; it has not passed.

The transferred implementation was checked independently in a separate
SLUS-00493 project: all eleven stage assets and 88 producer/bank/scroll layouts
were audited, including actual MIPS producer execution; live checks covered four
stages with composed 16:9/21:9 captures and 4:3 return. High-level human review
accepted the sampled result. A rare background overlap remains unresolved.
That prior evidence does not establish this fork's complete-game compatibility,
all live stages, widened terrain culling or every effect/HUD state.

For a source-only check on a clean checkout:

```powershell
python tools/verify_offline.py --profile-only
```

After dependencies are published/reviewed, regenerate and build with the
project's documented source workflow. Select OpenGL and perform a short fight
with resize 16:9 -> 21:9 -> 4:3. Confirm HUD placement, panorama coverage and menu
return before accepting the preview. Run the full offline verifier against the
regenerated artifacts; its ten-shard release-footprint check is retained.
