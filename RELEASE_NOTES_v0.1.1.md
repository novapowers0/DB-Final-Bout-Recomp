# DB Final Bout Recompiled v0.1.1

Maintenance release updating the PSXRecomp and recomp-ui framework pins and
shipping a newly built Windows setup-host package.

## Included

- `psxrecomp` at `7d70880d`, with upstream master integrated into the
  `rework-master` title branch. This preserves Final Bout's title integration
  and includes the mid-block Reserved Instruction fix (`d76c5c39`).
- `recomp-ui` at `01bff947` and nested `recomp-net` at `c2338c63`.
- Rebuilt normal and PGXP Windows runtimes with game-version stamp `0.1.1`.
- Setup-host package containing the refreshed framework sources and Windows
  recompiler emitters.

## Validation status

- Both Windows runtime variants compiled and linked with the updated framework.
- Offline project verification passed (configuration, codegen, overlay cache,
  Vulkan/netplay build surfaces and both runtimes).
- The setup-host ZIP passed integrity and required-content checks. It contains
  no disc image or retail BIOS dump.
- **Still pending:** manually test the combat transition with Little Goku vs
  Piccolo. The Reserved Instruction change is compiled, but that specific
  in-game behavior is not yet confirmed. Online ICE/TURN remains disabled.

## Download

`dbfb-0.1.1-setup-host-win64.zip`

The package does not include the game disc or retail BIOS. Provide files from
your own legally obtained copy as described in `baserom.md`.
