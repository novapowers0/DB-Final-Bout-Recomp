# Dragon Ball GT: Final Bout Recompiled v0.1.1

Maintenance release updating the PSXRecomp and recomp-ui framework pins, with a
runtime recovery for a stale, cleared IRQ callback that could wedge a combat
transition.

## Included

- `psxrecomp` at `7d70880d` on the Final Bout `rework-master` integration branch,
  including the upstream merge and the mid-block Reserved Instruction fix.
- Narrow handling for a stale all-NOP IRQ callback in low RAM when reached from
  the kernel's IRQ walker. Other unsupported instructions retain the regular RI
  exception path.
- `empty_irq_callback_returns` telemetry in freeze heartbeats and crash reports
  to show whether the recovery path was exercised in a session.
- Refreshed `recomp-ui` at `01bff947` and nested `recomp-net` at `c2338c63`.
- Rebuilt Windows setup-host package and normal/PGXP runtimes with version stamp
  `0.1.1`.

## Validation

- Normal and PGXP Windows runtimes compiled and linked.
- Offline verification passed, including configuration, code generation,
  overlay-cache, Vulkan/netplay build surfaces and runtime presence.
- Manual gameplay completed Piccolo vs Goku and proceeded to Piccolo vs Little
  Goku Super Saiyan without a hang. The session closed normally with no fatal
  error, unknown dispatch, or mid-block unsupported instruction.
- That playtest's logs predate the new callback counter, so they do not establish
  whether the recovery path ran during that session. Later sessions expose the
  counter for direct confirmation. This is evidence for the tested sequence,
  not a guarantee against every possible hang or configuration.
- Online ICE/TURN remains disabled. Vulkan and PGXP are optional variants;
  software rendering remains the reference path.

## Download

`dbfb-0.1.1-setup-host-win64.zip`

The setup package does not include the game disc image or retail BIOS. Provide
files from your own legally obtained copy as described in `baserom.md`.
