# MEMORY.md — DBFinalBout Recomp

Memoria durable y destilada del proyecto. **Léela primero**, antes que
`AGENTS.md` o `HANDOFF_CLAUDE.md`. Aquí está lo que se aprendió a golpes y lo
que no debe repetirse. Actualízala al cerrar una sesión si cambia algo de fondo.

---

## 1. Identidad

- **Qué es:** puerto nativo PC de **Dragon Ball GT: Final Bout** (SLUS-00493,
  USA) con `mstan/psxrecomp` (fork de integración propio `novapowers0`).
- **Ruta local:** `C:\Users\javie\Desktop\PROYECTOS IA\DBFinalBoutRecomp`.
- **Repo:** `https://github.com/novapowers0/DB-Final-Bout-Recomp` (branch
  `master`).
- **Release actual:** `v0.1.1` (tag `bc69be7`), asset
  `dbfb-0.1.1-setup-host-win64.zip`, actualizado in situ el 2026-10-03.
- **Discos (nunca commitear):** en `..\DB Final Bout\` están las ROMs
  USA/EU/Spain; el boot EXE es `disc/SLUS_004.93` (190464 bytes, text `0x2E000`).
- **Objetivo declarado:** que el juego funcione de extremo a extremo y, después,
  un **mod de combate renovado** (el combate original es muy criticado) con
  ingeniería inversa y patrones tomados de `guimaraf/plusalpha-recomp`
  (Street Fighter EX Plus Alpha).

---

## 2. Las reglas de oro (aprendidas, no negociables)

1. **Precisión > recall.** Una función omitida cae al intérprete (correcto pero
   lento); una función **mal compilada es fatal** (corrompe estado y cuelga).
   Declara fronteras solo con prólogos reales (`addiu sp,X,-N`) que además
   aparezcan en `executed_pcs`.
2. **No editar nunca código generado** (`generated/`). El fix va en el
   recompilador (`recompiler/src/`).
3. **No `fprintf`/logs ad-hoc.** Para inspeccionar, usa el debug server TCP
   (puerto 4370) o el reporte/heartbeat existente. Regla del framework
   (`psxrecomp/CLAUDE.md`).
4. **No adivinar direcciones.** Sin evidencia reproducible no hay hook, ni seed,
   ni `[[overlays]]`.
5. **El `game.toml` fuente es la verdad.** No editar a mano
   `build-release/game.toml`; se sincroniza con un build (POST_BUILD).
6. **No dejar instancias del juego vivas.** Dos instancias compitieron por el
   puerto 4370 y los JSON de captura → crash nativo y select bugueada. Matar
   siempre tras el test.
7. **Nunca crear junctions NTFS a archivos** con `mklink /J` (solo directorios).
   Fue la causa del crash `0xC00000FF`. Usa hard link (`mklink /H`) o copia.
8. **No publicar artefactos con bytes del disco** (snapshots de overlay, ROMs,
   BIOS retail). El setup-host solo lleva fuentes/emitters/runtimes y OpenBIOS.
9. **Regla -1 del framework:** el core fiel es la base; nada de parches
   quirúrgicos por juego *para fingir* fidelidad. Los shims por juego son
   legítimos en la fase de *enhancement*, una vez probado el core.

---

## 3. Los bugs y fixes que ya están hechos (historia esencial)

- **Crash 0xC00000FF (arranque):** junction NTFS rota + `filesystem_error` en el
  launcher. Fix: hard link al `.bin` real. Resuelto.
- **Bug A — miscompilación `0xD7FFFFAC`:** fallo de *load-delay* cross-fragment
  en `code_generator.cpp` + `full_function_emitter.cpp`. Resuelto (hash
  `0x5ddbd2c4`).
- **Bug B — config desincronizado:** `build-release/game.toml` tenía
  `overlay_cache=false`. Sincronizar desde el fuente.
- **Fix del combate (19/08):** los dispatch seeds del STEP40 eran interiores; se
  escanearon prólogos `addiu sp,sp,-N` en `executed_pcs` → 35→89 fronteras en
  `game.toml`; el combate pasó a compilar nativo.
- **Fix RI de transición (12/09 → 26/09):** en `dirty_ram_interp.c`, una
  instrucción no soportada mid-block debe levantar **Reserved Instruction
  (ExcCode 10)**, no `cpu->pc=0`. El handler reentraba en la ranura de IRQ ya
  borrada (`0x1F6C`) hasta la guarda de recursión; se añadió una recuperación
  estrecha para el callback vacío cuando `$ra` es `0x293C`/`0x2950`.
- **Contador diagnóstico:** `g_dirty_ram_empty_irq_callback_returns` expuesto como
  `empty_irq_callback_returns` en heartbeat (`freeze_heartbeat.c`) y reporte
  final (`crash_trace.c`); lo muestra `tools/analyze_latest_session.py`.

---

## 4. Hechos técnicos clave

- **Todo el gameplay vive en overlays runtime** `STEP*.BIN` (`STEP00/01/02/03/
  40/999`), no en el EXE. Sin overlay cache nativo, el intérprete dirty-RAM se
  atasca (`wedge_kind: spin_freeze`, `dispatch_count=0`, `dirty_ram_insns`
  7–13M, `in_exception=1`).
- **Overlay de combate = STEP40.** Miembro en file offset `0x22060`, size
  `0x12354`, se DMA a RAM en base **`0x80060000`** (o `0x80068000`/`0x8006A000`
  según qué páginas dirty vea primero; hay DLLs para las tres bases).
- **Recompilar overlays NO requiere recompilar el exe.** El runtime escanea el
  cache y registra cada DLL como *candidate* por (base, CRC de código); si
  coincide → nativo.
- **Compilar overlays desde capturas truncadas es peligroso**: fronteras falsas
  parten funciones reales → salto a basura → crash. Solo desde el archivo
  completo del disco o con fronteras validadas contra `executed_pcs`.
- **La firma de culling de Final Bout** es `slti ...,0x200` (X) + `slti
  ...,0x1E0` (Y) y vive en el STEP40, no en el EXE. `squash=false` es
  obligatorio: el juego lee SXY para culling/UI y el X-squash lo corrompe →
  widescreen **stretch-only**.
- **SIO / 2º combate:** el juego limpia `TX_EN` entre bytes; `sio_no_tx_gate=true`
  (scoped a este título) permitió avanzar. El cuelgue negro del 2º combate
  estaba ligado a overlays de stage-2 sin compilar.
- **La transición colgaba por una ranura de handler que el overlay limpiaba y
  reconstruía**, no por falta de cobertura estática. El fallo es dependiente de
  estado.

---

## 5. Pins actuales (2026-10-03)

- `psxrecomp` `7d70880d` (`rework-master`, ahead 5 de origin/master; 4 archivos
  modificados sin commit: `dirty_ram_interp.[ch]`, `crash_trace.c`,
  `freeze_heartbeat.c`).
- `recomp-ui` `01bff947`; nested `psxrecomp/lib/recomp-net` `c2338c63`.
- `VERSION` = `0.1.1`; `framework_pins.txt` y `catalog_identity.json` lo
  documentan.

---

## 6. Entorno y comandos

- **Shell agente:** PowerShell 5.1; Git Bash en `C:\Program Files\Git\bin\bash.exe`.
- **MSYS2 gcc:** `C:\msys64\mingw64\bin\gcc.exe` (shards de overlays y
  recompilador).
- **Toolchain clang/llvm_mingw:** `...\retcomm\toolchains\cmake-clang-v1\1.0.14`
  (build final del exe; aporta `libc++.dll`/`libunwind.dll`).
- **Python:** en PowerShell `python`; en Git Bash `C:\Python314\python.exe`
  (el packager bash llama `python3`).
- **Git Bash no trae `zip` ni `rsync`** (el packager los pide). ZIP alternativo:
  `C:\Program Files\7-Zip\7z.exe` o `Compress-Archive`; para `libc++.dll` fija
  `PSXRECOMP_RUNTIME_BIN_DIR` al bin de mingw del toolchain.
- **Override obligatorio:** `FETCHCONTENT_SOURCE_DIR_PSX_LIBCHDR` en
  `build-release\CMakeCache.txt` (libchdr es offline). **No perderlo.**
- **Comandos clave:**
  - Jugar/capturar: `play_session.cmd` (o `INICIAR_FINAL_BOUT_NATIVO.bat`).
  - Recompilar overlays: `recompile_overlays.cmd`.
  - Rebuild exe: `cmake --build build-release --target psx-runtime`.
  - Verificación offline: `python tools\verify_offline.py`.
  - Resumen de sesión: `python tools\analyze_latest_session.py`.
  - Nativo vs intérprete: `stall_report.py --port 4370 snap`.
  - Empaquetar: `scripts/package_setup_release.sh build-release
    setup-host-win64 build-recompiler`.
  - Publicar: `gh release upload v0.1.1 <zip> --clobber` + `gh release edit
    v0.1.1 --notes-file RELEASE_NOTES_v0.1.1.md`.

---

## 7. Estado abierto (lo que NO está resuelto)

- **Causalidad del fix:** el playtest estable precedió al contador; falta una
  sesión nueva que confirme `empty_irq_callback_returns`.
- **Cobertura nativa del combate:** el playtest estable seguía casi todo
  interpretado (`disp_native=0`). Recompilar STEP40 completo con captura fresca.
- **2º combate:** retrato del rival y pantalla negra (históricamente ligado a
  overlays de stage-2/menú-VS sin compilar nativo).
- **Sombras 3D "como en la lejanía":** es del port base (proyección Z), no del
  widescreen; diagnosticado pero no corregido.
- **Widescreen:** stretch-only 16:9/adaptive; `squash/auto_screen_x/
  auto_backdrop/precise_nclip` desactivados por regresión visual previa.
- **Multi-región (USA/EU/Spain en 1 exe):** EU+Spain son code-identical (52
  bytes, tabla de idioma); USA es build distinta. Sin decidir arquitectura.
- **Git limpio pendiente:** cambios sin commit en `AGENTS.md`,
  `PLAN_SOLUCION_CRASH_Y_COMBATE.md`, `README*.md`, `RELEASE_NOTES_v0.1.1.md`,
  `scripts/package_setup_release.sh`, `summary.md`,
  `tools/analyze_latest_session.py`, gitlink `psxrecomp`, y sin seguimiento
  (`github/`, launchers `.bat`, `tools/_dump_*.py`). El commit/push los hacemos
  nosotros, no Claude.

---

## 8. Dónde mirar

- `AGENTS.md` — arquitectura, pipeline, comandos, estado.
- `HANDOFF_CLAUDE.md` — misión de la siguiente fase (end-to-end + mod de combate).
- `PLAN_SOLUCION_CRASH_Y_COMBATE.md` — diagnóstico del crash y Tiers 0–4.
- `summary.md` — cronología de sesiones.
- `psxrecomp/docs/FINAL_BOUT_RESPONSIVE_ARCHITECTURE.md` (copia en
  `..\DB Final Bout\tools\psxrecomp\docs\`) — diseño del combate Responsive.
- `psxrecomp/docs/MOD_PACKAGES.md` y `runtime/include/mod_plugins.h` — API de mods.

## 9. Lecciones de la sesión 2026-10-04 (detalle en `INFORME_CLAUDE.md`)

- **Comprobar siempre `overlay_loader_status.last_msg`**: un `OVERLAY CACHE HASH
  MISMATCH` deja *todo* interpretado. Tras actualizar `psxrecomp`, reconstruir
  `build-recompiler` y recompilar overlays; `verify_offline.py` ya lo valida.
  Cambiar `game.toml` (p. ej. `mod_function_entry_funcs`) cambia el tag `gc…` de la
  caché y obliga a recompilar todo.
- El overlay de combate ocupa `0x8003E7F0..0x80072520`. `overlays_out/STEP40.BIN`
  está en sectores crudos de 2352 B: no sirve para copiar bytes 1:1; usar RAM viva.
- Fronteras nuevas = prólogo ejecutado con `jal`, o destino observado cuyo `ra-8`
  es `jal/jalr` (`tools/step40_coverage_step.py`).
- Pad: buffers libpad `0x8003BC00/0x8003BC28`; sondeo `0x8003FCF0` (cada 2 frames
  en combate); remapeo `0x8003FE68` reescribe el word in situ (bytes invertidos
  vs SIO). Plugin `dbfb.responsive` + ring en `0x1F000000`.
- Compilar `psx-runtime` y `psx-runtime-pgxp` por separado (carrera en `mods/bundled`).
- Mis lecturas TCP de 2 MB generan volcados `slow_frames` de 130 MB: leer en trozos.
- Freeze de transición (`0x1F6C`): mitigación generalizada, **sin verificar**.
