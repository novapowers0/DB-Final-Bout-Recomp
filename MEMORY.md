# MEMORY.md — DBFinalBout Recomp

Memoria durable y destilada del proyecto. **Léela primero**, antes que
`AGENTS.md` o `HANDOFF_CLAUDE.md`. Aquí está lo que se aprendió a golpes y lo
que no debe repetirse. Actualízala al cerrar una sesión si cambia algo de fondo.

---

## 1. Identidad

**Dirección de combate vigente (2026-10-17):** el usuario exige un mod
**activar y jugar**, con un estándar final bueno sin configurar. No dar por
cerrado el trabajo con inputs/velocidad/ki: abarca movimientos, transiciones,
defensa, proyectiles, IA y animaciones. Leer `COMBATE_REDISENO.md` antes de
retomar. El catálogo público tiene solo `standard` y la traza de desarrollo;
las pruebas individuales se conservaron fuera del catálogo. Se estudió el
proyecto B3 HD (Xbox 360/ReXGlue) en lectura, sin importar activos. El perfil
inicial compila y pasa tests, pero **no es el rediseño definitivo**.

- **Qué es:** puerto nativo PC de **Dragon Ball GT: Final Bout** (SLUS-00493,
  USA) con `mstan/psxrecomp` (fork de integración propio `novapowers0`).
- **Ruta local:** `C:\Users\javie\Desktop\PROYECTOS IA\DBFinalBoutRecomp`.
- **Repo:** `https://github.com/novapowers0/DB-Final-Bout-Recomp` (branch
  `master`).
- **Publicación de esta continuación:** `v0.2.0` experimental, asset
  `dbfb-0.2.0-windows-x64.zip`; ver roadmap §9. La estable anterior permanece
  `v0.1.1` (tag `bc69be7`, setup-host), sin reemplazar sus artefactos.
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

- **Vigente §9, 2026-10-19:** R7 cerrado para la entrega experimental 0.2.0;
  visual comprobado por el agente (render real del settle, 26 fotogramas de
  cámara y un par A/B con control de ambos luchadores idéntico). Sin revisión
  humana exigida. **R0 general reabierto:** dos paquetes/modo original salieron
  por watchdog con sampler=0; causa sin demostrar. No atribuirlo al loader por
  descarte. `crash_trace.c` publica tiempos total/máximo/último de carga ya
  medidos por el loader. Estándar/PGXP de ZIP pasan, original tiene fallos y
  una sesión PASS de dos combates; conservar toda la matriz. 112 tests y 26
  comprobaciones del watchdog OK, builds y offline PASS. Empaquetador nuevo
  `tools/package_release.py`: stager oficial + TinyCC existente + Python
  portable de la instalación local (el Python del checkout carecía del ZIP
  estándar). Valida imports, CLI y hashes; sin ROM/estados/configs privadas.
  Núcleo publicado `835f1902`, pins actualizados. Release autorizada; no
  declarar estabilidad universal ni cambiar el watchdog para hacerla pasar.
  ZIP final extraído de nuevo: 3/3 PASS, original2/estándar1/PGXP1 combates,
  pausa/estados y autocompile correcto; no invalida los fallos anteriores.

- **Histórico 2026-10-19, segunda tanda (ver §8 del roadmap):** **R3 settle
  integrado** (`dbfb_pose_settle.h` llamado desde `motion_build`; acción 6 del
  registro 0 clonada con handoff exacto) y **probado en partida** (acción 6 →
  slot creado 245, no el nativo 105). **R4 encuadre general implementado** en el
  seam nuevo `0x80054F88` (`dbfb_camera_frame.h`, escala solo ojo→objetivo
  17/16, guardas completas, contador `camera_framing`; opt-out
  `DBFB_CAMERA_FRAMING=0`): overlays recompilados (1158 OK, 8 rechazos kernel),
  namespace **`cg18_1b6950cb_gc164a1e9a_f0`**, `verify_offline` PASS; en partida
  435 aplicaciones ON / 0 OFF, capturas de combate correctas. **R5**
  `tools/combat_cards.py` mide startup/ventaja/hit-stop reales (cuadrado
  0x72/0x73: startup 17-20 VB, hit-stop 4 VB). **R6** dificultad 0/1/2 verificada
  en partida (acciones CPU/minE 28,0/37,4/42,7). **R1** cmd29/ID6→200→9B
  capturado completo con wtrace. **111 tests OK**, 36 grupos C, build exit 0.
  Quedan: visual del settle, A/B visual de cámara, aéreos/bloqueo en fichas,
  n mayor por dificultad, balance humano, R7.

- **Tanda 2026-10-19 (primera, ver §7 del roadmap):** **R0 corregido de clase** — el
  sampler de host suspendía el hilo de emulación desde otro hilo sin cota de
  latencia (causa del congelamiento `l`, no bucle MIPS); ahora el sampler
  suspend-based de Windows es **opt-in** (`PSX_HOST_SAMPLER_SUSPEND=1`) y por
  defecto no suspende; watchdog intacto. Nuevo `test_host_sampler_policy`. **R1
  cmd25 entregado**: `followup_lift()` sustituye solo los argumentos de entrada
  nativos para que el motor original haga el despegue y luego entrega `25` por
  `control+0x56`; observado ambos lados `25→20→98→80→99` y `98→9A`; pendiente
  `cmd29/ID6→200→9B`. **R2/R3:** geometría/anatomía parciales (registro0) y
  transición propia `dbfb_rig_bridge.h` (no integrada). **R4:** propiedad de cámara
  mapeada y sonda `dbfb_camera.h` (sin encuadre). **86tests/35gruposC**, builds
  normal/PGXP PASS, namespace `cg18_1b6950cb_gc58692d0b_f0` (1157DLLs), partida
  `dbfb-final-20261019` 4combates/salida0/`max_suspend_us=0`. Restan giro propio,
  clips nuevos renderizados, cámara general, fichas nominales y balance humano.

- **Histórico l FAIL (ya explicado):** la sesión l cayó en combate2 frame11887 por
  `starvation_watchdog`, retorno2, gap12.414.350µs; 9s sin avance de
  frame/ciclos/insns. El mecanismo quedó medido y separado (suspensión host,
  holds reales 82 ms–1,944 s con 0 µs de CPU del objetivo), y la corrección opt-in
  de 2026-10-19 lo elimina por defecto. Evidencia privada
  `dbfb-rework-smoke-20261018l/` y `dbfb-r0-fixed-20261019a/` intactas.
- **Corrección de movilidad (§11):** script+c desplaza al **rival** en
  `0x8006639C`, no demuestra locomoción. Estándar ahora `SPEED_ORIGINAL`; no
  anunciar125%movilidad. Ritmo por retiming conjunto de ataques/poses. Locomoción
  real extrae raíz en `0x800678D0`; necesita mapear entrada/bucles/paquetes.
  Cámara relativa convierte en `0x800506C8`; la general usa ramaAA194==1 y otro
  contexto, no basta modificar las seis coords directas.

- **Último resultado 2026-10-18, ver §10 del rediseño:** 64/64 tests, ambos builds;
  sesión **k** (420s) PASS: cuatro combates vida→KO→menú, pausa0→1→0,
  guardar/cargar confirmados (generaciones1/2) en carpeta temporal y **salida0**.
  El smoke anterior mataba al perder el ACK de quit: **salida1 no probaba cierre
  normal**. Ahora espera al proceso y exige salida0 sin terminate. h tuvo cuatro
  KO pero falló cierre; i falló por screenshot en transición; j/k PASS. k:
  38.818frames, 144 técnicas publicadas (incluye rebuild tras load), 96 poses,
  289/289 script/pose detenidos. No es prueba de guardado nativo en tarjeta.
- **Defensa corregida:** el bit del divisor dos es `0x40000000`, no `0x4000`
  (`lui` en `0x80066DC8`); helper y rotura ya corregidos. **Dificultad efectiva**
  half `0x80072960+lado*0x24` (opción byte `0x8003BC74`; menú0..2, modos43/44/45
  fuerzan2). CPU = control bit0. IA extra solo J2CPU/J1humano, cadencia150/120/90
  VBlanks y prioridad para comandos, botones y defensas originales. El segundo
  mando físico no identifica al dueño. `0x80034FD4` NO es dificultad.
- **Técnicas 78..83:** coste positivo op84 a4/5 en scripts privados; resto exacto,
  sin retiming ni daño/cancelación añadidos; contador `technique_variants`.
  432 scripts verificados en18registros/ambos lados. Directas78..7A/7E..80,
  coordinadas7B..7D/81..83. `--cards` añade familias/handler/coste. Op60 es audio,
  no salto de acción. Faltan clips nuevos/anatomía, rutas/remates aéreos,
  locomoción propia, cámara general/relativa, fichas nominales y balance humano.

- **Bloqueo nuevo/intermitente observado 2026-10-18:** sesión headless c cae en
  menú frame 3.303 por `starvation_watchdog` (retorno 2, >10 s sin heartbeat),
  espera `0x8001BD34/68`/OpenBIOS `0x1FC060E4`, `I_STAT=0`. No mid-block ni
  unknown dispatch; causa pendiente, no atribuirla sin evidencia al mod/core.
  Repeticiones d/e/g con el mismo linaje completan combate/KO/menú (f quedó en
  combate tras la sonda de pausa) sin reincidir, pero **no resuelven la causa**. Se corrigió una carrera de doble
  lectura del heartbeat (`starvation_watchdog_confirmed_stale`, 26/26 PASS) que
  explica un posible falso positivo (el dump c tenía heartbeat de 266 µs), sin
  silenciar el watchdog. **No declarar estabilidad cerrada.** Dumps privados en
  `%TEMP%/opencode/dbfb-rework-smoke-20261018{c..g}/`.

- **Estado vigente 2026-10-18, sustituye errores de 17b:** `script+4` cuenta
  hacia atrás por evento. Hit-stop real mediante filtros del intérprete
  `0x8004E530` y pose `0x80042240`; cancelaciones con script privado, cierre de
  ataque y confirmación desde daño, no el bit de embestida. Ráfagas básicas:
  `dbfb_projectiles.h`, nacimiento `0x8004F5A0`, trig 125% en `0x800592A8/2FC`,
  duración 64 VBlanks y choques 3D. Paso de objetos dinámico: **21 observado**,
  acotado 17..36. Coste/daño de esas ráfagas 3/4. KO directo: punch-in 8%/24
  VBlanks. Transiciones de pose nativas en `dbfb_pose.h`: **reperfilan una
  muestra interior existente** con correcciones angulares relativas compensadas
  (`0x03310000|parte`), conservando extremos/tiempos (contador
  `pose_transitions`; 17 en sesión g). Caché vigente
  **`cg18_1b6950cb_gc2c269e7c_f0`**, 1.158 DLLs; mismos ocho rechazos IRQ/BIOS.
  58 tests, 33 grupos C y matriz de 942 variantes.
- **Unlock realmente corregido:** dirección **`0x8003BCC4`**, pues `lui 0x8004`
  más `-0x433c` NO da `0x8004BCC4`. START debug = **`0x0008`**. Captura privada
  `dbfb-rework-smoke-20261018b/004-menu.png`: 17 retratos y word `0x1FFFF`.
  Sesión real b registra ráfagas aceleradas/expiradas, hit-stop de pose,
  cancelación y KO; choque de ráfagas solo sintético. Sesión g añade **pausa
  real** (`0x800A868C` 0→1→0 con START y reanudación automática) y 17
  transiciones de pose. Ver §9 del rediseño. Faltan animaciones nuevas con
  jerarquía de huesos, fichas nominales/medidas, rutas/remates, IA por
  dificultad, técnicas especiales, encuadre general y balance humano.

- **Causalidad del fix:** el playtest estable precedió al contador. El
  2026-10-17 el contador quedó en 0 en 132.905 frames; aun así no prueba que la
  ruta de recuperación se haya ejecutado, solo que no fue necesaria.
- **Cobertura nativa del combate:** medida el 2026-10-17 en sesión headless:
  37.565.732 despachos nativos frente a 3.698.052 interpretados (**91%**), sin
  `fatal`, `unknown_dispatch` ni `midblock`, y sin volcados de freeze nuevos.
  Sigue siendo una prueba automatizada, no una validación de sensación.
- **Ampliación de combate 2026-10-17b:** nuevo punto de enganche `0x80054A60`
  (comando antes de la puerta) → caché `cg18_1b6950cb_gc41ea2caf_f0` con **1.158
  DLLs**. `src/mods/dbfb_combat.h` añade defensa (guardia con medidor, rotura,
  just-guard, perfect-guard), hit-stop, empuje vectorial, sacudida de cámara,
  cancelación en recuperación confirmada, IA por el slot nativo del lado 2 y
  prorrateo de combo. `dbfb_motion.h` expone `motion_clip_live` y
  `motion_total_ticks`. 54 tests / 31 grupos C; sesión real con esos contadores
  activos y `fatal=no`. Siguen abiertos: fichas nominales por golpe, animaciones
  nuevas, proyectiles avanzados, cámara de KO y balance fino.
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
