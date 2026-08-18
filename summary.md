# DBFinalBout Recomp — Session Summary

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

## Sesión 18/08 - Widescreen stretch-only + diagnóstico sombras + Custom Combat (instrumentación)

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
- manifests widescreen/custom-combat: author="NovaPowers".
- game.toml: [widescreen] gte_game_mode=true, squash=false, native_wide=false; cull auto_screen_x/backdrop=true.
- Gate 0x8003C30C REVERTIDO (causaba crash al entrar en combate).

### Custom Combat - progreso instrumentación (mod_builtin_custom_combat.c)
- 0x80072918 NO es el anim_id: es un CONTADOR/timer que avanza SIEMPRE (idle 7->128, 0x31D->0x35B).
- 0x80072800 era el luchador oponente/quieto (no cambiaba al atacar) => la base del luchador 1 es OTRA.
- La zona 0x80071F00 es una tabla de punteros (muchos 0x80071CCC repetidos) => posible tabla de datos/anim.
- Los anim_id son DATA-DRIVEN (se cargan del .bin a RAM), no están en el exe => hay que volcarlos en vivo.
- Script preparado: ghidra_proj/ram_dump.py (volcado RAM a archivo, una conexión por bloque).
- PENDIENTE: localizar la base del luchador 1 y volcar la tabla de animaciones en combate.
