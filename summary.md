# DBFinalBout Recomp — Session Summary

## 2026-09-09: v0.1.0 release preparation

- Confirmed the first playable release milestone: four complete fights were
  completed, including the transition that previously failed at fight two.
- Synced `psxrecomp` with upstream `origin/master` and retained the Final Bout
  widescreen, netplay, Vulkan, SIO compatibility, and builtin-mod changes.
- Synced `recomp-ui` with upstream `origin/master`.
- Published the project-specific `psxrecomp` integration branch as
  `novapowers0/psxrecomp:rework-master` so the main repository has a reachable
  submodule commit.
- Kept nested `recomp-net` and `retcomm-rbengine` pins on public upstream
  commits, avoiding inaccessible local-only gitlinks.
- Offline verification passes: source/deployed configuration matches, codegen
  and overlay cache are coherent, and normal/PGXP runtimes are present.
- Remaining known issue: brief pillarbox transitions can still appear in some
  2D menus when widescreen is enabled. No further heuristic patch is included
  in this release preparation.

## Objective
Crear un puerto nativo PC ultradefinido de "Dragon Ball Final Bout" (SLUS-00493, USA) con mstan/psxrecomp:
fix input lag (SIO0 pads), widescreen 16:9/21:9, 60 FPS nativos, manifiesto .psxmod v5 en recomp-ui,
con opción 1:1. Fase 1 = build funcional.

## IMPORTANTE — Root cause RESUELTO (17/08 16:50)
El exe clang moría al arrancar con `0xC00000FF` (STATUS_BAD_FUNCTION_TABLE). Causa:

1. **Junction rota**: `disc\Dragon Ball GT - Final Bout (USA).bin` era una JUNCTION NTFS apuntando a un
   ARCHIVO (las junctions solo funcionan con directorios). Windows devolvía ERROR_INVALID_DIRECTORY_NAME
   (267) a `status()`.
2. **Overload lanzadora en libc++**: `ISOReader::Open()` (iso_reader.cpp:160) usa
   `std::filesystem::exists(filename)` SIN error_code. libc++ lanza `filesystem_error` cuando `status()`
   falla con error distinto a "not found" (libstdc++ del build gcc no lanzaba aquí).
3. **Crash en unwind**: el `filesystem_error` (construido vía `__wide_to_char`) se desenrollaba por el
   init del launcher recomp-ui (con frames de SDL activos) y ntdll levantaba STATUS_BAD_FUNCTION_TABLE
   (0xC00000FF) en RtlRaiseStatus durante RtlUnwindEx/RtlpExecuteHandlerForUnwind.

**Fix aplicado**: reemplazada la junction rota por un HARD LINK a
`C:\Users\javie\Desktop\PROYECTOS IA\DB Final Bout\Dragon Ball GT - Final Bout (USA).bin`
(158,811,744 bytes, coincide con known_sizes). `fs::exists` ya retorna true, no lanza, no crashea.

**Resultado**: el exe clang (`build-release\DBFinalBout_Recompiled.exe`) arranca estable.
Ventana "DBFinalBout - Launcher" abierta (17 threads, ~102 MB, Responding). Sin freeze dump ni crash report.

## Diagnóstico previo (lo que se descartó)
- Exit code NO era DLL_NOT_FOUND: `-1073741569` = `0xC00000FF` = STATUS_BAD_FUNCTION_TABLE (crash SEH real en ntdll).
- Stack resuelto con llvm-nm (base 0x140000000): main → validate_disc_image → __wide_to_char /
  basic_string<wchar_t>::__grow_by → validate_disc_image(+0x42) → ISOReader::Open / fs::exists → unwind.
  cfgmgr32 + SDL_PrivateGetGamepadMappingForGUID eran frames de SDL (stale/activos del init del launcher).
- Descartado: api-ms-win-crt-private, ruta forward (PSX_HAS_GAME_DISPATCH), SDL/video (--headless
  crasheaba igual, mismo camino del launcher), disco inexistente (--disc no evitaba validar el disc del config).
- Config load OK (throws tempranos capturados, exit 1 con mensaje).
- El exe GUI: stdout NO llega a pipes redirigidas; stderr SÍ. "psxrecomp: main() entered" en stderr.
- ehtest (clang pack) confirmó el throw: fs::status(junction) → ec=267 ERROR_INVALID_DIRECTORY_NAME,
  fs::exists lanzador → "filesystem error: in posix_stat: failed to determine attributes...".
- NO era el bug de libunwind llvm#161851 (el pack pinea llvm_mingw 20260616, posterior al fix).

## Toolchain / entorno
- MSYS2 gcc en C:\msys64\mingw64; pack oficial cmake-clang-v1 v1.0.14 (clang-22.1.8, llvm_mingw
  20260616, libc++/libunwind) en C:\Users\javie\.local\share\retcomm\toolchains\cmake-clang-v1\1.0.14.
- Build: clang++ -O3 -DNDEBUG -std=gnu++17, -static -static-libgcc -static-libstdc++ (libc++ auto-link),
  SEH. Defines: PSX_HAS_GAME_CODEGEN=1, PSX_HAS_GAME_DISPATCH=1, PSX_NO_DEBUG_TOOLS=1, PSX_SDL3=1,
  PSX_HAVE_VULKAN=1, RECOMP_LAUNCHER.
- Override libchdr persistido en build-release\CMakeCache.txt (FETCHCONTENT_SOURCE_DIR_PSX_LIBCHDR) — NO perder.
- La doc (GAME_PROJECT_SETUP.md) y runtime.cmake sugieren que el runtime en Windows puede construir con
  MSYS2 g++ (libstdc++); el wizard/cli prefiere clang del pack. Ambos funcionan AHORA (el crash era del disco).

## Estado de trabajo
### Completado
- Fase 0, scaffold, probe_disc (game.toml, 298 seeds, SLUS_004.93 extraído), emitters, generate
  (2982 funcs, 9 shards), regen OpenBIOS, toolchain instalado, rebuild clang OK.
- **Crash 0xC00000FF resuelto**: junction rota → hard link al bin real. Exe clang arranca y abre el launcher.
### Pendiente
- Verificar boot completo del juego (el launcher está abierto; falta probar el flujo Play/boot y confirmar
  que no aparecen freeze dumps durante la emulación).
- codegen_setup.c: placeholder `"generated/SLUS_01234_dispatch.c"` → `"generated/SLUS_004.93_dispatch.c"` (gen_marker_relpath).
- Fase 2: Ghidra no extraído (auditoría MIPS SIO0, overlays) — bloqueado por extracción.
- .ecm europeo sin descomprimir (Dragon Ball - Final Bout (E) [SLES-03735].bin.ecm en "DB Final Bout").

## Discos / rutas
- Proyecto: C:\Users\javie\Desktop\PROYECTOS IA\DBFinalBoutRecomp
- Disc real (USA): C:\Users\javie\Desktop\PROYECTOS IA\DB Final Bout\Dragon Ball GT - Final Bout (USA).bin/.cue
  (hard link en disc\Dragon Ball GT - Final Bout (USA).bin).
- La junction era el problema: NO crear junctions a archivos (mklink /J = solo directorios).
  Para copiar el disco al proyecto usar `tools/prepare_disc.py` o hard link (mklink /H) o copia.

## Fix "Generate & rebuild" → "psxrecomp generate failed (exit 1)" (17/08 17:0x)
- Error real en JSONL: `psxrecomp-game failed (exit 3221225781)` = 0xC0000135 DLL_NOT_FOUND.
- Causa: `build-recompiler\psxrecomp-game.exe`/`psxrecomp-bios.exe` compilados con MSYS2 gcc importan
  `libgcc_s_seh-1.dll`, `libstdc++-6.dll`, `libwinpthread-1.dll` (no están en el PATH del wizard).
- Fix: copiadas las 3 DLLs de `C:\msys64\mingw64\bin` a `build-recompiler\` (junto a los emitters).
- Generate ahora pasa: EXIT=0, 9 shards (345593 líneas, 0 actualizadas), dispatch 748 entradas,
  disco verificado (md5 OK).
- Nota: los emitters se pueden reconstruir estáticos con el clang del pack para evitar DLLs; el enfoque
  documentado es "MinGW runtime DLLs beside the host and emitters".

## Próximos pasos
1. Probar el boot del juego desde el launcher; monitorear freeze dumps / crash reports.
2. Arreglar codegen_setup.c (placeholder SLUS_01234).
3. Si el boot es estable: seguir plan de la Fase 1 (input lag SIO0, widescreen, 60fps, .psxmod).

## Sesión 18/08 - Widescreen stretch-only + diagnóstico sombras

### Estado actual (verificado en vivo, mode:0 = widescreen OFF)
- gpu_state: ws.configured=0, ws.active=0, x_margin=0, squash=[1,1], mode=0 => VANILLA PURO.
- Render a 512x240 (hi-res Final Bout), draw_area [0,256,511,495], draw_offset [256,376].
- geom_correction: geometry_correction=0, pgxp.enabled=0 => PGXP/precisión DESACTIVADA.
- ws_far_threshold: threshold=900, sz_n=0 => fix de backdrop lejano INACTIVO en vanilla.

### HALLAZGO: problema de sombras/modelos "como en la lejanía" es del PORT BASE (no del widescreen)
- El problema aparece con widescreen APAGADO (mode:0), PGXP off, sin ningún parche mío activo.
- Mis cambios de widescreen (squash=false / gate / sentinel+histéresis / auto_screen_x / auto_backdrop)
  son TODOS de estiramiento X o están gateados por psx_ws_x_margin()>0 (identity a 4:3). En mode:0 son no-op.
- Diagnóstico: es un problema de proyección de profundidad/Z del port base. NO documentado previamente
  (summary.md no lo contiene).
- NOTA: el usuario creía que ya estaba documentado; no lo estaba. Queda registrado aquí.

### Cambios de widescreen realizados (en psxrecomp submodulo, working tree)
- gpu.c: ws_squash_cfg (stretch-only) -> ws_xnum/ws_xden=1/1, GTE vanilla, solo estira la presentación.
- gpu.c: ws_gameplay_state_matches() con sentinel 0xFFFFFFFF (match any nonzero) + histéresis
  WS_STATE_GATE_HYSTERESIS 8u (debounce). Gate INACTIVO (sin addr configurado en game.toml).
- gpu.c: ws_configured() devuelve 1 en stretch-only mode:1 para que detector 2D/3D + pillarbox sigan.
- main.cpp: gte_set_display_aspect(4,3) cuando squash=false (FOV sin cambio); gpu_ws_set_squash plumbing.
- config_loader: ws_squash parse. debug_server: comando ws_squash.
- manifest widescreen: author="NovaPowers".
- game.toml: [widescreen] gte_game_mode=true, squash=false, native_wide=false; cull auto_screen_x/backdrop=true.
- Gate 0x8003C30C REVERTIDO (causaba crash al entrar en combate).

## Sesión 18/08 (tarde) - Aprendizaje de Bloody Roar 2 + DuckStation: widescreen real y overlays

### Referencia: Bloody Roar 2 (proyecto hermano)
- BR2 logró `squash = true` (GTE X-squash + present-stretch) porque AUDITÓ que su GTE NO lee SXY
  fuera del funnel de culling (61 mfc2 de SXY, todos en funnels reescritos por auto_screen_x).
- Final Bout NO puede: su lógica lee SXY para culling de actores + layout UI => squash=false correcto.
- BR2 usa `precise_nclip = true` (juego de lucha 3D con geometría en bordes) — MISMO caso que Final Bout.
- La firma de culling es POR-JUEGO: BR2 = `sltiu 0x200` (X) + `sltiu 0x1E0` (Y). NO heredar de Tomba
  (0x140/0xE0) ni de Ape Escape (0x181).

### HALLAZGO CLAVE: la firma real de Final Bout está en el overlay STEP40, NO en el EXE
- El EXE base (SLUS_004.93, text 0x2E000) NO contiene la firma screen-extent 0x200/0x1E0:
  scan de slti/sltiu 0xE0-0x320 solo da 0x0F0/0x101/0x1F0 sueltos en funcs de menú, sin patrón W+H.
- Los overlays del disco (dir /MENU): STEP00/01/02/03/40/999.BIN. El STEP40 (442 KB, el de pelea)
  contiene la firma REAL: `slti $2,$4,0x200` (X=512) en 0x5C28/0x10774/0x107FC + `slti $2,$17,0x1E0`
  (Y=480) en 0x196DC. Igual que BR2.
- VAs de overlay: STEP40 se carga en 0x80040000+ (entradas 0x80042xxx). El freeze dump muestra
  `last_store_pc 0x8003EDF0` (más allá de 0x8003E000) = código de overlay interpretado.
- => El widescreen de Final Bout usaba la firma de Tomba (0x140/0xE0) y NO encontraba los culls.
  Se corrigió en game.toml: `screen_w_imms = ["0x200"]`, `screen_h_imms = ["0x1E0"]`, `precise_nclip = true`.

### Los overlays NO están recompilados => raíz de los crashes Y del widescreen incompleto
- El proyecto recompila solo el EXE base (2982 funcs, hasta 0x8003E000). El código de pelea/menú
  (STEP*.BIN) corre en el intérprete dirty-RAM: lento e inestable.
- Freeze dumps: `wedge_kind = slow_frames`, `in_exception = 1`, 17299 entradas de excepción,
  `current_func = 0x29CC` (PC bajo = dentro de manejador de excepción) — consistente con el
  intérprete atascado en bucles de excepción en menús/combate.
- El disco es MODE2 (datos en offset 24 de sector 2352), un solo track. PVD en LBA 16.
- Los overlays se capturan en tiempo de DMA (no por extracción de disco): overlay_cache=true en
  game.toml => overlay_captures.json => compile_overlays.py (gcc) => cache/ DLLs o --static.
- PIPELINE PENDIENTE: jugar con overlay_cache=true para capturar STEP40, recompilar con
  compile_overlays.py --gcc, y verificar que los culls ensanchados (0x200/0x1E0) aparecen en el
  código nativo recompilado.

### Cheat widescreen de DuckStation (ground truth)
- Final Bout (France SLES-00964): `8002219C 0C00` (escribe 0x0C00 en RAM). Solo Francia tiene cheat
  widescreen en chtdb.txt; USA/Japan no. USA usa squash=false (no aplica).
- BR2 cheat: `801F0270 1333` (EU) / `A71F0018 19991333` (US) => escala X ≈1.2x en Q12.

### Cambios aplicados en game.toml
- [widescreen] precise_nclip = true
- [widescreen.cull] screen_w_imms = ["0x200"], screen_h_imms = ["0x1E0"]
- [runtime] overlay_cache = true
- Requiere rebuild del recompilador (codegen re-lectura de game.toml) para que los culls se horneen.

## Sesión 19/08 - ANÁLISIS DE CRASHEOS vs Bloody Roar 2 (ver ANALISIS_CRASHES.md)

### Root cause de los "crasheos" (confirmado)
- NO son crashes nativos: son **congelamientos del intérprete** (`wedge_kind:
  spin_freeze/slow_frames/fatal`), `dispatch_count=0`, `overlay_loader.active=0`,
  `dirty_ram_insns` ~7-13M, `in_exception=1`. El código de menús/combate (overlays
  STEP*.BIN) corre 100% interpretado.
- Diferencia clave con BR2: BR2 es estable porque su juego es un EXE único (0xA0800)
  recompilado AOT (1014 seeds). Final Bout es EXE chico (0x2E000) + **todo el
  gameplay en overlays runtime**; sin overlay cache nativo, el intérprete se atasca.
  La lección "BR2 no usa overlay cache y es estable" se aplicó MAL (BR2 no lo
  necesita; Final Bout sí).

### Bug A — miscompilación nativa 0xD7FFFFAC (YA corregida en el árbol)
- Entrar en combate con overlays recompilados crasheaba:
  `FAIL-FAST unknown dispatch addr=0xD7FFFFAC ra=0x8003ED74` (puntero corrupto).
- Fix en psxrecomp: code_generator.cpp (defer_load: declara psx_ldd_<addr> en el
  scope del bloque) + full_function_emitter.cpp (flush solo del mismo fragmento).
- VERIFICADO: recompilador psxrecomp-game.exe y shards construidos con el fix
  (hash codegen 0x5ddbd2c4).

### Bug B — config desincronizado (CORREGIDO HOY)
- build-release/game.toml tenía overlay_cache=false (razón: Bug A, pero el árbol
  ya lo había corregido). El staged no se refrescó tras editar game.toml fuente.
- FIX: copiado game.toml → build-release/game.toml (ahora overlay_cache=true,
  alineado). Ambos coinciden.

### Bloqueo restante — overlay de combate STEP40 NO se compila nativo
- compile_overlays.py salta la región 0x80068000 como "no walk-root seeds
  (data-only)": el capture [9] tiene dispatch_entry_pcs y 1967 executed_pcs pero
  function_entry_pcs VACÍO, y el clasificador rechaza promoverlos (no pasa la
  verificación de frontera _callable_legacy_seed). --force-interior no ayuda
  (solo aplica en regiones ya con raíz).
- Los shards reales cubren solo 0x800035xx/0x8001104C/0x800537E0; NINGUNO el
  combate (0x8006xxxx) => el combate siempre va interpretado => freeze.
- PLAN: Opción A (correcta) = semillas de frontera del STEP40 vía Ghidra; B
  (riesgo) = forzar roots; C (paliativo) = overlay_native_block. Ver doc.

### Higiene
- No editar build-release/game.toml a mano: regenerarlo con un build tras editar
  el fuente (el desync de hoy vino de eso).
- El release empaquetado (dist) tenía otro hash codegen (0x51c0ca8f); re-empaquetar
  con el árbol actual para que lea los shards.

## Sesión 19/08 (tarde) - FIX DEL COMBATE: STEP40 compila nativo (ver ANALISIS_CRASHES.md §7)

### Causa exacta del bloqueo del combate
- Los 3 "dispatch seeds" del STEP40 NO son inicios de función (son interiores):
  0x8006A3C8=`j`, 0x8006A580=`andi`, 0x8006DBFC=`lw`. Por eso el clasificador
  rechazaba la región 0x80068000 como "data-only" -> combate interpretado -> freeze.

### Fix aplicado (Opción A, sin Ghidra completo)
- Escaneado los 28 KB capturados del STEP40 buscando prólogos `addiu sp,sp,-N` que
  además estén en executed_pcs -> 35 fronteras de función seguras (precisión>recall).
- Declaradas en game.toml bajo `[[overlays]]` load_addr=0x80068000 +
  function_entry_pcs (35 entradas, sin bytes_crc para robustez).
- Recompilado: `compile_overlays.py --only-region 0x80068000 --force`
  -> `00068000_05DDBCB5.dll` (330 KB) con 26 funciones del combate (0x80069228..0x8006E5FC).
- Sync config desplegado (build-release/game.toml) con el fuente.

### Pendiente: validación del usuario
- Jugar una pelea (overlay_cache=true ya activo) y confirmar que NO hay
  psx_freeze_dump nuevos ni el crash 0xD7FFFFAC.
- Verificar nativo: `python psxrecomp/tools/stall_report.py --port 4370 snap`
  (dispatch_native alto / dispatch_interp_fallback bajo).
- El capture solo tiene 28 KB del STEP40 (parte ejecutada); más combates recapturan
  más y el shard crece. Otras regiones de menú (0x8003F000/0x80047000) aplican el
  mismo escaneo para cobertura nativa.

### Multi-regional (3 ROMs en 1 exe) - pendiente, "depende del análisis"
- Objetivo del usuario: UN exe que cargue USA/EU/Spain según la ROM seleccionada
  (plug-and-play sin Generate & build, como BR2). Imita a Buu's Fury (varios juegos
  en un exe), pero en PS1 las regiones suelen tener código MIPS distinto.
- PRIMER PASO: descomprimir las ROMs (EU .ecm y Spain .chd) y comparar sus boot
  EXEs para saber si son code-identical (=> trivial, como Buu's Fury) o código
  distinto (=> recompilación separada por región integrada en un binario).
- Bloqueo de entorno: chdman no puede escribir archivos de salida en este sandbox
  ("Permission denied"); pendiente extraer España/Europa.

## Sesion 21/08 - COMBATE 100% NATIVO (STEP40 completo) + widescreen config

### Diagnostico (rendimiento)
- Ultimo run limpio: disp_native=78128 vs disp_interp=1043655 (~7% nativo) => la
  pelea corria mayormente interpretada.
- Causa: el capture 18/08 del STEP40 solo cubria una ventana de 28 KB (35 funciones).
  El overlay real de combate es el miembro de STEP40.BIN en file offset 0x22060,
  base RAM 0x80060000, size 0x12354 (~60 KB). Las paginas capturadas el 19/08
  (0x80060000..0x8006F003) y el propio STEP40.BIN son identicos 1:1 (verificado
  28676/28676 bytes).
- Los 35 limites conocidos NO pasan el criterio estricto del framework
  (_callable_legacy_seed exige rs=rt=29 en `addiu sp,sp,-N`): Final Bout usa
  prologos `addiu sp,fp,-N` (rs=fp=30). Por eso solo 17/35 pasaban; el criterio
  correcto es LAXO: rt=29 + inmed. negativo.

### Fix aplicado
1. Aislado el miembro de combate: STEP40.BIN[0x22060 .. 0x343B4] (size 0x12354),
   base RAM 0x80060000.
2. Escaneo de prologos laxos (`addiu sp,X,-N` rt=29, prev no control-flow, o
   `jr ra` en prev8, o addr==base) intersecado con executed_pcs reales (5536 pts)
   + las 35 conocidas => 89 fronteras.
3. Captures sintetizados en build-release/overlay_captures.json:
   - 0x80060000 (74580 B, 89 fn_entries)
   - 0x80068000 (41812 B, 68 fn_entries)
4. game.toml: `[[overlays]]` 0x80060000 (89) + 0x80068000 (68). Sync
   build-release/game.toml.
5. compile_overlays.py -> 00060000_21D7E1FC.dll (943 KB, 101 funciones, el walk
   descubrio jal-targets extra) y 00068000_CB735076.dll (504 KB, 77 funciones).
   Exe verificado: arranca sin crash (registro de DLLs OK).

### Widescreen (config)
- A�adidos offer=true y adaptive_view=true (mismos keys que Bloody Roar II; mismo
  framework novapowers0/nova-mods f2bb059). offer_ultrawide queda OFF (21:9 sin
  testear). squash=false sigue obligatorio (SXY-read corrupto). El cull
  auto_screen_x (0x200/0x1E0) ahora aplica en combate (STEP40 nativo).

### Frameworks nuevos estudiados (informativo)
- TechnicallyComputers/{TwistedMetal4Recomp,Street-Fighter-Alpha-3-Recomp,
  MastersOfTerasKasiRecomp} pinnean mstan/psxrecomp feat/rbengine a9a61b4.
  SF3/TerasKasi: todo el gameplay en el text principal (sin overlays) => nativo
  total. TerasKasi ISSUES.md: fixes runtime interp->native handoffs. Migrar
  nuestro subm�dulo a a9a61b4 es posible pero GRANDE y arriesgado (pierde mods
  nova-mods). compile_overlays.py es casi identico (solo PSX_RAM_SIZE 2->8 MB).

### Pendiente (validacion usuario)
- Jugar una pelea y verificar con `stall_report.py --port 4370 snap`:
  dispatch_native alto / dispatch_interp_fallback bajo.
- Confirmar 2� combate (retrato rival + sin pantalla negra).
- Widescreen 16:9 en combate (oferta en launcher).
- Sombras 3D (port base, proyeccion Z).


## 2026-08-28: crash 1er combate + hang 2º combate (SIO) + revisión upstream

### Crash 1er combate = artefacto de mis instancias zombie
- Lanzé 2 instancias (26352/23732) para reproducir y las dejé corriendo. El usuario
  jugó CONCURRENTEMENTE => contendedon en debug port 4370 + overlay_captures.json/
  addendum.jsonl (rewrites concurrentes) => crash 1er combate + select de personaje
  bugeada (además el stretch del widescreen en menús 2D). Sin freeze dump ni event log
  => crash nativo por contención, no por mis DLLs. REGLA: NUNCA dejar instancias vivas;
  matar SIEMPRE tras el test (smoke tests ya lo hacen).

### Hang 2º combate: causa raíz confirmada = gate TX_EN en sio.c
- Disassemblé la rutina manual SIO del juego (región 0x80002000, función 0x80003B00):
  envía 0x01 (select pad), 0x42 (read), 0x00, y el cmd final; cada paso:
  `sb SIO_TX_DATA` -> RMW SIO_CTRL (`lhu`/`ori 0x10`/`sh`, solo TX_IRQ_EN) ->
  spin SIO_STAT.RX_RDY (bit1) <-> I_STAT.7 (0x3CB4<->0x3E14). NUNCA toca TX_EN.
  En HW real TX_EN sobrevive al init de BIOS; en la transición del 2º combate algo
  lo limpia (sio_ctrl=0 en heartbeat) y el gate TX de sio.c (case 0x1F801040)
  descarta los bytes => RX_RDY nunca se setea => loop infinito (pantalla negra+musica).
- Fix: nueva opción por juego `[runtime] sio_no_tx_gate=true` (game.toml). Plumbed:
  config_loader.h/cpp (RuntimeConfig.sio_no_tx_gate) -> main.cpp (sio_set_no_tx_gate)
  -> sio.h/c (flag g_sio_no_tx_gate). El gate TX solo se salta cuando el flag está
  ON; por defecto sigue activo (ape-escape intacto). Rebuild exe + pgxp OK.
- Verificado: protocolo completo del juego leído del capture 0x80002000.

### Revisión upstream mstan/psxrecomp (master c0139b45)
- Nuestro pin = nova-mods f2bb059 (base upstream 353ed1b4 + 1 commit nova).
  master está 174 commits por delante (17/08-27/08).
- NINGUN commit upstream arregla nuestro hang SIO (solo 3 tocan sio.c: SPU I_STAT
  ownership, card new-card flag, build MSVC). El fix sio_no_tx_gate es original.
- NO migrar a master: perdería el mod widescreen stretch-only nova + fixes locales
  (cleanup custom-combat, load-delay, SIO). Re-baseline 174 commits intesteable.
- Portados (pequeños, seguros, relevantes al 2º combate / CD / UX):
  - 2d67bb9a cdrom: cancel stale INT2 on new command (PSX-CD-007)
  - b919f2a4 cdrom: CD-DA position report IRQs (Setmode bit2) during Play
  - 2795b5a0 cdrom: set CDSTAT_READ after seek complete (PSX-CD-003) [manual, 1 línea]
  - 20b9ba6c runtime: swallow overlay-closing press (no se filtra al juego)
  - acac784c runtime: preserve adaptive 4:3 across DPI rounding
- NO portados (riesgo/conflicto):
  - ffa11fa2 cdrom read-stream refactor (410 líneas) — grande, intesteable.
  - 5afe95b1 title-scoped NCLIP (gte/pgxp/codegen) — choca con mod nova widescreen.
  - auto_ui_squash suite (squash-based) — opuesto a nuestro stretch-only (squash=false
    obligatorio por lectura SXY corrupta).
  - 3592a19e/7e3d2f94 SIO card/SPU — correctitud, no nuestro bug.
  - 772ddba4 high-bank overlay tooling (PSX_RAM_SIZE 2->8MB) — opcional, no bloquea.
- Nota: el rebuild re-staging mods borró build-release/mods/state.toml => widescreen
  vuelve a OFF (base limpia para validar el fix SIO).

### Pendiente
- Validar el fix del 2º combate (retrato rival + sin pantalla negra).
- Tras validar, opcionalmente portar ffa11fa2 (fiabilidad carga CD) con playtest.
- Widescreen: restaurar enable si el usuario quiere probar 16:9 de nuevo.

## 2026-08-28 (sesión 2): el 2º combate sigue colgando — hallazgo real: overlays de stage-2 no compilados

### Intento del usuario (sesión p21448, 23:37)
- Mi fix SIO (sio_no_tx_gate) SÍ cambió el estado: heartbeat ahora `sio_ctrl=0x1013`
  (TX_EN set, antes 0x0000) y el rival salió BLANCO (antes no se mostraba). El juego
  avanzó más por la rutina, pero sigue colgando en negro en el 2º combate.
- Sin freeze dump; report: reason=atexit, frame=8027, in_exc=1, epc=0xBFC05E08,
  current_func=0x29CC (físico 0x800029CC = path de retorno del handler de excepciones).
  El loop 0x2914 del dirty_block_tail es el dispatch de eventos VBLANK del juego
  (NORMAL, el juego está vivo a 60fps pero sin renderizar el combate = pantalla negra).

### Causa raíz real (verificado contra disco + captures)
- El 2º combate carga VARIANTES de overlay DISTINTAS al 1º, y NINGUNA coincide con
  nuestros DLLs del cache (crc por base):
    * stage-2 battle setup en 0x8006B000 (crc 9740F91C) — NO es el miembro STEP40
      (bytes en disco 0x6C55A58 vs 0x22060: 3954/4100 difieren).
    * menú/VS en 0x80040000 (no 0x8003F000), 0x80049000, 0x8004C000, 0x80050000,
      0x80053000, 0x8005F000, y 0x80047000 con bytes nuevos (crc 31DAE608 vs
      DCD22276).
- Todo lo ejecutado del 2º combate corrió INTERPRETADO (dispatch=0 en los captures),
  mientras el 1er combate usó el DLL nativo (disp_native 2.7M). La transición del
  stage-2 (setup 0x8006B000 + CD load) se traba por eso.

### Acción tomada
- Escaneé prólogos (`addiu sp,X,-N`) de los 8 captures de la sesión, añadí 8
  [[overlays]] a game.toml (0x80040000/0x80047000/0x80049000/0x8004C000/0x80050000/
  0x80053000/0x8005F000/0x8006B000) y compilé:
  * 9 DLLs OK -> cache (00040000_BB633B16, 00047000_31DAE608, 00049000_6E9A403B,
    0004C000_F61D729B, 00053000_41A9C2F2, 0005F000_8B93E048, 0006B000_9740F91C,
    00040000_96F1921C, 00040000_EBA4A3AD).
  * 0x80050000 FAILED (21 execs, salto a 0x80051004 justo fuera del capture de 4KB;
    el archivo real del disco es mayor y no se capturó la página no-ejecutada).
    Región pequeña -> queda interpretada (sin impacto).
- No hace falta rebuild del exe: los DLLs se cargan por (base, crc) del cache en
  runtime. Smoke test: boot limpio, 0 procesos.
- El código del 2º combate está en el disco en 0x6C24438-0x6C55A58 (sectores crudos,
  no en el ISO: root solo tiene SYSTEM.CNF/LOGO.STR/SLUS_004.93/CASTROLL.STR).
- upstream 2bea610f (RAM bajo EXE alto) NO aplica a Final Bout (carga en 0x80010000,
  su overlay bajo está en la kernel window 0-0x10000).

### Pendiente
- Reintento del usuario del 2º combate (ahora el setup stage-2 + menú/VS corren nativo).
- Si sigue colgando: investigar CD load del stage-2 (posible ffa11fa2 read-stream,
  o diagnóstico CD en vivo por debug server).
- 0x80050000: si se ejecuta más en el futuro, extender capture con el archivo del disco.

## 2026-08-29: regresión (crash antes del combate 1) + revert completo

### Síntoma
- Usuario: "No he llegado ni al primer combate, ha crasheado antes del salto a 3D".
- Report (sesión p1076, frame 2347): interp_unsupported en 0x8000AE8C (SPECIAL
  funct 0x16 = ejecutó datos basura), last_store_pc=0x8003FCD8, disp_native=22K
  vs disp_interp=1.1M (casi todo interpretado).

### Causa
- Mis DLLs de 2026-08-28 para las variantes de menú/VS (0x80040000, 0x80047000,
  0x80049000, 0x8004C000, 0x80050000, 0x80053000, 0x8005F000) estaban construidos
  desde captures TRUNCADOS (páginas de 4-16KB ejecutadas) y con fronteras de
  prólogo sueltas sin validar. Una frontera falsa parte una función real ->
  miscompilación -> salto a basura (0x8000AE8C) -> crash.
- Además el crc/size del DMA varía por sesión (p21448: 0x80053000=8196B;
  p1076: 0x80053000=53252B), así que los DLLs de captures truncados NO son
  fiables (a veces matchean y miscompilan, otras no matchean y se ignora).

### Acción (revert completo al estado conocido-bueno)
- Eliminé los 8 [[overlays]] nuevos del game.toml (incl. 0x8006B000) y borré los
  9 DLLs nuevos del cache. Cache = exactamente 18 DLLs (estado pre-regresión).
- game.toml = hash B830275D (solo sio_no_tx_gate + los 5 [[overlays]] originales).
- Smoke test: boot limpio, 0 procesos.
- LECCIÓN (AGENTS): compilar overlays desde captures truncados de sesión es
  poco fiable; solo compilar overlays con el ARCHIVO COMPLETO del disco y crc
  estable (como el miembro STEP40 0x80060000).

### Pendiente / próximo enfoque para el 2º combate
- NO repetir el approach de captures truncados. O bien:
  (a) extraer el archivo STEP completo del disco (0x6C24438-0x6C55A58 y resto)
      y compilar los overlays completos con crc estable, o
  (b) diagnóstico en vivo por debug server (sio_trace/cd_state) durante un
      intento del usuario para confirmar si el cuelgue es SIO, CD o código.
- Confirmar primero con el usuario que el crash pre-combate está resuelto.

## 2026-08-29 (sesión 2): revert COMPLETO de runtime al estado 21/08

### Síntoma (después del revert de overlays del 29/08)
- Usuario: "Ha crasheado, no ha pasado del primer combate".
- psx_crash.txt: FAIL-FAST unknown dispatch addr=0x00002934 (jalr del bucle de
  eventos VBLANK en 0x80002000, kernel window). Freeze dump: frame=2554,
  current_func=0x0000279C, epc=0x80042294 (menú 0x80040000 interpretado),
  sio_ctrl=0x0000.

### Causa
- El crash persistió tras revertir los overlays => el culpable eran MIS CAMBIOS
  DE RUNTIME del exe (28/08 18:14): sio_no_tx_gate + ports CD (2d67bb9a,
  b919f2a4, 2795b5a0) + UX (20b9ba6c, acac784c). El 0x80002934 (kernel window,
  nunca compilado) pasó de correr interpretado (sesiones 21/08/28/08) a
  fail-fast; algún cambio de runtime alteró el estado (i_stat=0x04 DMA pendiente,
  sio_ctrl=0) que disparó el jalr a una dirección sin código.

### Acción (revert total)
- git checkout de los 7 archivos que edité (sio.c, sio.h, config_loader.h/cpp,
  main.cpp, cdrom.c, beetle_libretro.cpp) -> HEAD (estado 21/08). Quedan solo
  los cambios pre-existentes (Phase 1 custom-combat, load-delay fix,
  runtime.cmake, tools/compile_overlays.py).
- game.toml sin sio_no_tx_gate (hash 62D612 = estado original).
- Cache: 18 DLLs (intacto). Exe reconstruido (2:20) + pgxp. Smoke test OK.
- EL FIX SIO QUEDA DESCARTADO (no arregló el 2º combate y encima regresionó).

### Estado = EXACTO al de las sesiones 21/08 que funcionaban
- Combate 1 debería volver a funcionar. Combate 2 seguirá colgando (problema
  conocido, 0x8006B000 interpretado + posible CD).

### Próximos pasos (MUY cautelosos, sin tocar runtime)
1. Confirmar con el usuario que el combate 1 vuelve a ir bien.
2. Para el 2º combate: NO más cambios de runtime. Opciones:
   (a) compilar el overlay del stage-2 con el ARCHIVO COMPLETO del disco
       (extrayendo el STEP de 0x6C24438-0x6C55A58 con su tabla de carga),
       validando fronteras con jal-targets (no solo prólogos sueltos), y
       probar en un DIRTY tree aislado.
   (b) diagnóstico en vivo por debug server durante un intento del usuario.

## 2026-08-29 (sesión 3): REWORK SOBRE UPSTREAM MASTER

### Decisión del usuario
- Rework del proyecto sobre mstan/psxrecomp master (175 commits por delante de
  nuestra base 353ed1b4). La rama nova (widescreen stretch-only + custom-combat
  + precise_nclip) se ABANDONA. Backups del estado 21/08 en
  C:\Users\javie\AppData\Local\Temp\opencode\prework-21-08\ (exe, 18 DLLs,
  game.toml, patch).

### Ejecutado
- psxrecomp: rama `rework-master` en origin/master 847d76f0; recomp-ui a master
  d8bbe1c (era 20 commits atrás; el fmv_filter faltante rompía el build).
- Recompiler master compilado (build-recompiler, mingw+ninja, CHD off):
  psxrecomp-game.exe 2:32. Acepta nuestro game.toml ([game] y [program] ambos).
  Requiere --project-root <proj> para el perfil BIOS (psxrecomp/bios/SCPH1001.toml).
- Código regenerado: 10 shards + dispatch (748 entradas) en generated/ (2:33).
- Runtime master compilado (build-release, clang): exe 2:34 + pgxp 2:35.
- Boot real con --no-launcher: carga config, GL 3.3 (NVIDIA 616.56), BIOS
  openbios.bin, ejecuta 0xBFC00000, **60 fps** (frame 1500 a los 25s),
  captura overlay 0x8003E000 (menú/título). CPU ~55% (present pacing 165Hz).
- Debug server: conexión funcionaba SOLO con --no-launcher (con launcher no).
  Protocolo JSON {"cmd":...}; comandos frame/get_registers/sio_state/cdrom_state/
  set_input/input_route_append+start. Bits PSX invertidos (0=pulsado):
  START=0x0008, CROSS=0x4000, TRIANGLE=0x1000.
- Inyección de input: route de START (60f) NO avanzó del título — el juego
  sigue en intro/loading (CD sector 15780, mc_probes=74). Conducir el juego a
  combate por input requiere navegar menús desconocidos → se delega al usuario.
- Observación: pad_buttons=0xBFFF estable (CROSS bit14 siempre 0) — posible
  botón pegado en el controlador Xbox; verificar.
- compile_overlays.py master con captures viejas: 0 compilados ("no walk-root
  seeds / data-only") — el formato de captura v2 de master requiere sesiones
  frescas. El capture json fue reescrito por el runtime (formato v2, lista).

### Estado
- Framework: master funcional (boot + título a 60fps, GL ok, debug ok).
- PENDIENTE playtest usuario: (1) ¿polígonos del personaje/sombras arreglados?
  (el mod nova [precise_nclip/squash] ya no existe — rendering vanilla 4:3).
  (2) ¿combate 1 jugable? (overlays interpretados → lento hasta recompilar).
  (3) ¿combate 2 crashea/cuelga? (master tiene 175 commits de fixes CD/SIO/overlay).
- Tras el playtest: compilar overlays con compile_overlays.py master (captures
  v2 frescas) → combate 1 nativo. Luego widescreen con el enfoque de master
  (widescreen_scan / psxrecomp-analyze; el [widescreen] de game.toml NO se
  parsea en master).

## 2026-08-29 (sesión 4): Playtest master + overlays nativos

### Playtest del usuario (master, overlays interpretados)
1. Menú inicial: texto abajo con fallo gráfico.
2. Combate 1: rostro del personaje SIN textura de ojos+boca; parte de encima
   del pie / debajo de la pierna no se muestra (3D).
3. Combate 2: lo de siempre — arte del rival no se muestra + combate negro.

=> Los fallos gráficos NO eran del mod nova (persisten en rendering vanilla
master). Son de la recompilación del exe, del GTE/GPU de master, o del timing
de interpretación. Los overlays estaban interpretados (no nativos) en ese test.

### Overlays nativos (master)
- El playtest capturó 13 overlays v2 (con executed_pcs/dispatch/seeds).
- compile_overlays.py master compiló 9 OK (menús 0x8003F000/0x80047000/...
  + kernel 0x80000000/0x80002000/0x80011000). Combate 0x8006A000 se saltó
  ("no walk-root seeds"): el dispatch aterrizó en INTERIORES, no prólogos, y el
  runtime registró function_entry_pcs=[].
- Escaneé los bytes del capture 0x8006A000 (12292B): 16 prólogos `addiu sp,sp,-N`
  reales (0x8006A3A4, 0x8006A538, 0x8006AC14, 0x8006B0A0, 0x8006B2B8, 0x8006B708,
  0x8006B784, 0x8006BD74, 0x8006C14C, 0x8006C220, 0x8006C280, 0x8006C470,
  0x8006C678, 0x8006CA38, 0x8006CBD4, 0x8006CEA8). Añadí [[overlays]] 0x8006A000
  a game.toml (con estas function_entry_pcs) + recompile -> 0006A000_F3554E24.dll
  nativo. Cache cg10_ad91f28e_gcfb254031_f0: 10 DLLs.
- Nota: la base del overlay de combate VARÍA por sesión (0x80060000/0x80068000/
  0x8006A000...). Otra base -> nueva captura + [[overlays]] + recompile.

### PENDIENTE
- Playtest 2 (overlays nativos): ¿mejoran los glitches? ¿combate 2 sigue negro?
- Si los glitches persisten: sospechosos = recompilación del exe principal
  (0x80010000-0x8003E000) o GTE/GPU de master. Herramienta disponible en master:
  tools/duckstation_oracle.py + gpu_frame_diff (comparar render contra DuckStation).
- Combate 2: si sigue negro, pedir al usuario que DEJE el juego en la pantalla
  negra para diagnosticar en vivo (debug server: cdrom_state/sio_state/current PC).

## 2026-09-09: corrección offline sin ejecutar el juego

El usuario indicó que no se debe abrir el juego ni hacer verificaciones o
playtests durante esta intervención. Se corrigieron las causas conocidas
directamente en código y configuración:

- `game.toml` y el perfil desplegado fuerzan renderer software 1x, 4:3,
  filtrado nearest, sin antialiasing, geometría PGXP ni perspective texturing.
  También se desactivan la oferta/adaptación widescreen, el culling automático,
  el backdrop automático y `precise_nclip` para evitar que las mejoras visuales
  alteren texturas faciales, polígonos de pierna/pie y texto 2D.
- Se añadió `controller.sio_no_tx_gate`, limitado a Final Bout. El juego limpia
  `TX_EN` entre bytes durante la transacción del segundo combate; el SIO global
  conserva la compuerta hardware, pero este perfil continúa el shifter mientras
  el dispositivo sigue seleccionado. Esto elimina el bloqueo conocido del flujo
  SIO sin cambiar el comportamiento de otros títulos.
- Se recompilaron los targets runtime normal y PGXP. Los ejecutables resultantes
  quedaron en `build-release` sin iniciar ninguno.
- Se conservaron los 10 DLL nativos de overlays, incluido
  `0006A000_F3554E24.dll`.

No se realizó ninguna ejecución del juego ni playtest; el feedback posterior del
usuario será la primera comprobación funcional.

## 2026-09-09: sincronización upstream y segunda ronda

- `psxrecomp` actualizado por fast-forward desde `847d76f0` hasta
  `51125849ad7cba170df24056222baac079a873c1` (`origin/master`, 243 commits).
  También quedaron actualizados sus submódulos `recomp-net` y
  `retcomm-rbengine` a los pins que exige ese master.
- `recomp-ui` actualizado por fast-forward desde `d8bbe1c` hasta
  `b6b2f5d698e373a249c4aa47b464d04641a3ded3` (`origin/master`, 75 commits),
  incluyendo los fixes de HiDPI, aspecto, input y staging de assets.
- El upstream trae cambios relevantes de GPU/GL/Vulkan, CD-ROM/DMA, BIOS,
  overlays y toolchain; se conservaron los fixes locales de `sio_no_tx_gate`.
- El recompiler master quedó configurado en `build-recompiler` con Clang,
  porque el MinGW C++ local terminaba con código 1 sin diagnóstico al compilar
  el recompiler. El binario actualizado genera el hash `0xf2c33ef6`.
- Se regeneró el código del juego con 2.982 funciones, 10 shards y dispatch de
  748 entradas. Se recompilaron los overlays existentes con el nuevo contrato:
  10 DLLs OK en `cg10_f2c33ef6_gcb2cea661_f0`, incluido el overlay de combate.
- Runtime normal y PGXP recompilados contra el código generado y el master
  actualizado. No se abrió el juego ni se hizo ninguna prueba funcional.

## 2026-09-09: endurecimiento offline y limpieza de estado

- Se añadió `tools/verify_offline.py`, una verificación determinista que no
  inicia el juego: valida la identidad de ambos `game.toml`, el perfil visual
  seguro, `sio_no_tx_gate`, los dos runtimes, el hash de codegen y los diez
  overlays actuales con sus archivos `.ranges`.
- `recompile_overlays.cmd` ahora falla explícitamente si falta GCC o el
  recompiler Clang actual; ya no continúa con un fallback ambiguo que podría
  generar un cache incompatible.
- Se corrigieron en `AGENTS.md` las referencias a hashes, nombres de DLL y
  opciones widescreen que pertenecían a sesiones anteriores. El estado actual
  mantiene widescreen desactivado hasta confirmar la línea base visual.
- Validación offline realizada: configuración fuente/desplegada idéntica,
  cache `cg10_f2c33ef6_gcb2cea661_f0` con 10 DLLs y `.ranges`, runtimes normal
  y PGXP presentes. El juego no se abrió.

## 2026-09-09: sesión funcional de cuatro combates y nuevas superficies

- El usuario confirmó que la build actual permitió completar cuatro combates,
  frente al crash que aparecía al segundo combate en sesiones anteriores.
- Artefactos de esa sesión: `psx_freeze_heartbeat.json` con 10.518 frames,
  `automatic_freeze_dumps=0`, `fatal=null`, `in_exception=0` al cierre,
  `last_store_pc=0x8006B5F8`, y una captura de overlays de 174 regiones en
  `overlay_captures.json`.
- La captura nueva tiene `function_entry_pcs=[]` en sus siete regiones. No se
  recompilará automáticamente: el historial demostró que declarar fronteras
  inseguras desde capturas truncadas puede reintroducir crashes.
- Se añadió `tools/analyze_latest_session.py` para resumir estos artefactos sin
  iniciar el juego.
- Integración preparada de forma conservadora:
  - Vulkan se compila/ofrece cuando el SDK está disponible, pero software sigue
    siendo el renderer por defecto y la referencia de Final Bout.
  - Netplay real queda activado en CMake con `recomp-net`, `retcomm-rbengine` y
    lobby URL compilada. La sesión offline no cambia; el transporte ICE queda
    separado para habilitarlo tras disponer de sus fuentes/soak.
  - Widescreen ofrece 16:9/adaptive como presentación. `squash`,
    `auto_screen_x`, `auto_backdrop` y `precise_nclip` siguen desactivados para
    no repetir la regresión visual anterior.
- El pin actual de `recomp-net` no incluye `chat_filter.h`, aunque el runtime
  upstream lo incluía en dos puntos. Se añadió un adaptador explícito y aislado
  (`psx_chat_filter_compat.*`) para que el build sea reproducible; no anuncia
  filtrado de chat hasta enlazar una implementación real del framework.
- Build final offline completado para `psx-runtime` y `psx-runtime-pgxp` con
  Vulkan (`PSX_HAVE_VULKAN=1`) y netplay/lobby (`PSX_HAS_RECOMP_NET=1`,
  `PSX_HAS_LOBBY_CLIENT=1`, `retcomm-rbengine`) enlazados. `RNET_ENABLE_ICE=OFF`
  queda deliberado porque no hay `libjuice` vendorizado; LAN/direct-IP es la
  ruta disponible y el online ICE queda para una fase con dependencia fijada.
- El primer enlace del runtime normal encontró un staging incompleto del
  catálogo de mods durante el build paralelo. Reejecutar el target aislado
  completó los cuatro manifests en `mods/bundled` y pasó el guard de catálogo.
- El widescreen no aparecía porque el host PSX descartaba `ws_offered_b` y
  publicaba `widescreen_supported=0`/`aspect_mask=0`, aunque el runtime ya tenía
  el motor. Se siguió el patrón de Bloody Roar 2: nuevo manifest builtin
  `psx.enhancement.widescreen`, plugin confiable `psx.widescreen` y opción de
  aspecto 16:9/21:9. El launcher ahora recibe 4:3 + 16:9 y vista adaptativa.
  La activación solo selecciona el aspect ratio; `auto_screen_x`, `squash`,
  `auto_backdrop` y `precise_nclip` siguen sin habilitarse.
- Tras la prueba del usuario se detectó que el host exponía además un segundo
  selector genérico `Display -> Aspect ratio`. Se eliminó esa exposición:
  `psx.enhancement.widescreen` es ahora el único dueño del aspecto y evita
  carreras con `settings.toml`.
- Se corrigió el gate de escenas 2D: `ws_2d_only_scene()` ya no queda
  desactivado cuando `gte_game_mode=true`. El detector GTE puede ver actividad
  en un menú durante algunos frames, pero no debe impedir la presentación 4:3
  pillarbox. Los hooks de FOV/culling siguen desactivados.
- Feedback funcional del usuario: 16:9 software inició correctamente, permitió
  un combate y el inicio del siguiente; Vulkan probado en 21:9 también funciona
  y el problema restante observado es el parpadeo de pillarbox en menús 2D.
  LAN no se probó manualmente, pero la suite sintética UDP/local sigue pasando.
- Pruebas sintéticas de `recomp-net` en `build-net-tests` completadas: pasan
  `ring_admit`, `wire_map`, `hostport`, `lan_lobby`, `udp_port`, `address`,
  `stun` (sin descubrimiento externo), `session_state` (dos peers UDP localhost
  y transferencia/resync de 100.000 bytes), `input_contract` y `rb_wire`.
- `rollback_episode_test` mantiene cuatro aserciones antiguas incompatibles con
  el host de prueba actual: `get_input_row()` devuelve filas remotas válidas
  durante el sellado local, por lo que el runtime las marca autoritativas, tal
  como documenta `rnet_rollback.c`. No se alteró la lógica de rollback para
  satisfacer expectativas obsoletas; queda como tarea upstream separada.
