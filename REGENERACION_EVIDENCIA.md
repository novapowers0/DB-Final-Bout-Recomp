# Regeneración oficial — P1.4 / P1.5

Fecha: 2026-10-17. Proyecto: `C:\Users\javie\Desktop\PROYECTOS IA\DBFinalBoutRecomp`.

## Resultado

| Trabajo | Resultado real |
| --- | --- |
| P1.5: regeneración del C del juego | **Ejecutada, salida 0**, con `build-recompiler/psxrecomp-game.exe` actual. |
| P1.4: regeneración de OpenBIOS | **Bloqueada antes de emitir C**: el build de frescura del script oficial falla por dos tests locales sin registrar. |
| Verificación offline del proyecto | **PASA**, salida 0. No valida compilación ni ejecución del C nuevo. |
| Comprobación oficial de huella BIOS | **FALLA**, salida 1 antes y después: OpenBIOS sigue stale. |
| Build del runtime / prueba de juego | No ejecutados, según el alcance solicitado. |

No se declara cerrado P1.4. La emisión del juego produjo **35 avisos** de saltos/ramas fuera de función; están íntegros en el log. No se modificaron seeds ni valores funcionales para silenciarlos.

## Respaldo previo, íntegro y verificado

Ubicación:

```text
C:\Users\javie\Desktop\PROYECTOS IA\DBFinalBoutRecomp\build-recompiler\respaldo_regeneracion_20261017\
```

La carpeta está ignorada por `/build-*/` del `.gitignore`, comprobado antes de crearla. No se modificó `.gitignore`.

En `copia/` se copiaron **íntegros** estos directorios, sin filtrar sus archivos:

- `generated/` del juego, 13 archivos.
- `psxrecomp/generated/`, 4 archivos de OpenBIOS, incluida su huella original.
- `psxrecomp/bios/`, con imagen local de OpenBIOS, licencia y todos los perfiles.

También se copiaron los dos recompiladores, ambos `game.toml`, seeds de juego/OpenBIOS, cabeceras de hash, los dos `CMakeCache.txt` y los archivos locales cuyo nombre contiene `SCPH1001`.

Total del respaldo: **37 archivos, 32.464.480 bytes**. Todos los SHA-256 de las copias coinciden con el original. La copia y su verificación finalizaron a las **14:36:51 +02:00**, antes de cualquier intento de regeneración.

Pruebas: `backup_manifest.json`, `backup_verified.json` y `generated_before.json` dentro del respaldo. La caché de overlays se inventarió y verificó por hash; no forma parte de la copia de los directorios de C generado.

## Revisión de seguridad de los comandos

Se leyeron `MEMORY.md`, `AGENTS.md`, `psxrecomp/AGENTS.md`, `psxrecomp/CLAUDE.md`, el plan interno y los scripts/emisores aplicables.

- `psxrecomp/tools/regen_bios.sh` cambia su directorio al framework. Por ello, la ruta correcta del build en esta instalación es **`PSXRECOMP_BIOS_BUILD=../build-recompiler`**.
- El script primero ejecuta `cmake --build ... --target psxrecomp-bios`; solo si pasa llama al emisor y escribe la huella con la herramienta oficial.
- `bios/OpenBIOS.toml` declara `out_dir = "generated"` y `out_stem = "OpenBIOS"`, relativos al framework. El emisor BIOS escribe archivos con ese prefijo; no limpia el directorio completo ni elimina otros backends (`full_function_emitter.cpp`, líneas 2951–2997).
- El emisor del juego solo elimina el monolito y posibles fragmentos sobrantes de su propio prefijo `SLUS_004.93` (`main_psx.cpp`, líneas 1759–1767). No hubo archivos eliminados en esta regeneración.
- Se utilizó el emisor de juego directamente; no el flujo global de preparación/rebuild, que abarca operaciones ajenas a esta tarea.
- No se editó a mano ningún archivo de `generated/`. No se cambiaron archivos fuente, scripts ni herramientas del padre o del framework. El único documento nuevo del padre es este informe. El auxiliar de captura de evidencia quedó en el árbol ignorado: `build-recompiler/_regeneracion_audit.py`.

## P1.5 — C del juego regenerado

Directorio de ejecución: raíz del juego.

```powershell
.\build-recompiler\psxrecomp-game.exe --config game.toml --project-root "C:\Users\javie\Desktop\PROYECTOS IA\DBFinalBoutRecomp"
```

Entradas resueltas por la configuración:

- EXE: `disc/SLUS_004.93`.
- Seeds: `seeds/ghidra_funcs.txt`, 298 direcciones adicionales.
- Salida: `generated/` del juego.

Resultado: **2.982 funciones generadas**, **10 fragmentos**, **367.598 líneas** entre fragmentos y **748 entradas de dispatch**. Log completo: `regen_game.log`; argumentos, directorio y salida: `regen_game.command.json`.

### Archivos emitidos

Actualizados por el recompilador, con cambios reales incluso después de normalizar CR/LF:

```text
generated/SLUS_004.93_decls.h
generated/SLUS_004.93_dispatch.c
generated/SLUS_004.93_full_00.c
generated/SLUS_004.93_full_01.c
generated/SLUS_004.93_full_02.c
generated/SLUS_004.93_full_03.c
generated/SLUS_004.93_full_04.c
generated/SLUS_004.93_full_05.c
generated/SLUS_004.93_full_06.c
generated/SLUS_004.93_full_07.c
generated/SLUS_004.93_full_08.c
generated/SLUS_004.93_full_09.c
```

`generated/SLUS_004.93_full.ranges` fue recalculado por el emisor y quedó idéntico. No se añadieron ni eliminaron archivos en los directorios generados.

SHA-256 después:

| Archivo | SHA-256 |
| --- | --- |
| `SLUS_004.93_decls.h` | `868727b9a8d27272cb0fde87c945ee85a01af044e8518483091e2e0aa8429243` |
| `SLUS_004.93_dispatch.c` | `c7188ef71a7cca6ccf3457098e15c94dabdecc1195d35c40c397f8b509865dd5` |
| `SLUS_004.93_full.ranges` | `e68fedd80aed4164bc07480b3e6e88d4c78f6c13e94f507c9aaef1bc7c15b446` |

Los hashes completos de **todos** los fragmentos, antes y después, están en `generated_before.json` y `generated_after.json`; el inventario de cambios está en `generated_delta.json`.

## P1.4 — stale real y bloqueo de OpenBIOS

La imagen local `psxrecomp/bios/openbios.bin` existe y su SHA-256 coincide con el perfil:

```text
fabe498fbf224e4721f12f31b6f5fe0659205e341dc4e5c5f91b9bd1a1011c57
```

También están disponibles `bios/OpenBIOS.toml` y `recompiler/seeds/openbios_elf_seeds.json`. No falta descargar ni compilar una imagen BIOS para esta operación.

La herramienta oficial calcula estas huellas:

```text
Guardada: eccaa6de7bfea72a91022053298870d0e7e468ac4c5dc67d4a0cea45a8872177
Actual:  71482d9f26b414818f7af5aee54275a1c4590bdc9f0fd6f16ca6aca98be6feae
```

El desacuerdo se reprodujo con `tools/ci/check_bios_stamps.sh` y con `cmake -DPROFILE=bios/OpenBIOS.toml -P tools/bios_emitter_fingerprint.cmake`. Esta implementación normaliza los retornos de carro: no es solo un aviso antiguo del build ni una comparación ingenua CRLF/LF. Prueba la desactualización de la **huella**; no se pudo determinar el delta del C de BIOS porque la regeneración se detuvo antes de emitirlo.

Comando oficial intentado desde `psxrecomp/`, con Git Bash:

```bash
PSXRECOMP_BIOS_BUILD=../build-recompiler \
PSX_LIBCHDR_SOURCE_DIR='C:/Users/javie/Desktop/PROYECTOS IA/DBFinalBoutRecomp/deps/libchdr' \
PSX_DEPS_OFFLINE=1 CMAKE_BUILD_PARALLEL_LEVEL=2 \
bash tools/regen_bios.sh --config bios/OpenBIOS.toml
```

**Salida 1.** El paso de build intenta regenerar CMake por un cambio en la lista de tests y falla en `runtime/check_test_registration.cmake:134`:

```text
Test file(s) present on disk but registered nowhere:
    runtime/tests/test_irq_callback_recovery.c
    runtime/tests/test_irq_callback_recovery.py
ninja: error: rebuilding 'build.ninja': subcommand failed
```

Ambos archivos ya estaban sin seguimiento al comenzar esta sesión. No se movieron, borraron, registraron ni ocultaron. No se evitó la comprobación ni se sustituyó la huella a mano.

Los cuatro archivos de `psxrecomp/generated/OpenBIOS*` siguen **idénticos por SHA-256** al respaldo. Ambos recompiladores también siguen idénticos: el intento falló en la configuración, antes de recompilar el binario BIOS.

Efecto del intento en el árbol de build ignorado: `build-recompiler/CMakeCache.txt` quedó apuntando a la copia **local** `deps/libchdr` en lugar de `_deps/psx_libchdr-src`. Diferencia completa: `recompiler_cache_delta.log`. El valor cacheado `PSX_DEPS_OFFLINE` ya era `OFF` y siguió así; la dependencia se resolvió sin red mediante el override local explícito. El cache de `build-release` permanece intacto.

Para reanudar P1.4 se necesita resolver primero el registro de esos tests en el framework y repetir el mismo script oficial. Esa modificación está fuera del alcance de esta entrega. No hay una regeneración BIOS satisfactoria que entregar.

## Conservación de SCPH1001, configuración y caché

- La búsqueda en todo el proyecto, incluidos árboles ignorados, encontró **tres perfiles** `SCPH1001.toml`: en `psxrecomp/bios/`, `psxrecomp/overlay_toolchain/bios/` y `dist/stage-setup-setup-host-win64/psxrecomp/bios/`. Se copiaron y sus hashes se mantuvieron.
- No se encontró un dump llamado `SCPH1001.BIN` ni archivos C `SCPH1001_*` en este proyecto antes de regenerar. No se borró ni regeneró ningún backend retail. Inventarios: `retail_before.json` / `retail_after.json`.
- `game.toml` fuente y desplegado siguen idénticos: **14.564 bytes**, SHA-256 `e8f94dd6d9b391a3f509a20b5def2fdc7e8594abcf8d6dc6de44a9e28fd29239`. No se cambiaron siquiera sus comentarios en esta sesión.
- Hash de emisor: **`1b6950cb`**, confirmado tanto por `--codegen-hash` como recalculándolo con el script CMake oficial a un archivo nuevo del respaldo, sin escribir la cabecera runtime.
- Hash de configuración de overlays: **`101f51f1`** antes y después.
- Caché actual: **`cg18_1b6950cb_gc101f51f1_f0`**, **1.117 DLL**, todas con `.ranges`.
- Se comprobaron por SHA-256 los **4.732 archivos de toda `build-release/cache/`**, 378.343.268 bytes: ninguno cambió, desapareció ni se añadió.
- Ambos ejecutables runtime, ambas cabeceras de hash y `build-release/CMakeCache.txt` también son idénticos. En total: **4.739 archivos protegidos**, 419.208.596 bytes, sin diferencias.
- SHA-256 del recompilador juego: `38572a820efa1abc3d3f278f97b5c6a1afcc1b58617e4a6dd4e50b8bebd3a20e`.
- SHA-256 del recompilador BIOS: `0932ea619a5eecb86ef9d1c7f35a964b89f2b6d92b6c0887ce0cc01729bbe266`.

## Comprobaciones y evidencia local

Comando de verificación ejecutado:

```powershell
python tools/verify_offline.py
```

Resultado: **`OFFLINE VERIFICATION PASSED`**, salida 0. Confirma configuración idéntica, emisor/caché coherentes, 1.117 DLL con rangos y presencia de ambas variantes runtime. No certifica que el C recién generado compile o que el juego funcione; esas pruebas corresponden al build/prueba posterior del usuario.

Todos estos archivos están en la carpeta de respaldo indicada arriba:

| Evidencia | Contenido |
| --- | --- |
| `regen_game.log` | Salida completa del emisor de juego, incluidos los 35 avisos. |
| `regen_openbios.log` | Fallo completo del comando oficial BIOS. |
| `bios_stamp_before.log`, `bios_stamp_after.log` | Mismatch reproducido y hashes de cada entrada del fingerprint. |
| `bios_fingerprint_full.log` | Huella actual completa calculada por CMake. |
| `codegen_before.log`, `codegen_after.log`, `codegen_recomputed.log` | Hash del binario y cálculo canónico. |
| `config_hash_before.log`, `config_hash_after.log` | Hash de configuración conservado. |
| `verify_offline.log` | Resultado de la verificación offline. |
| `protected_before.json`, `protected_after.json` | SHA-256 de todos los archivos protegidos, incluida toda la caché. |
| `generated_before.json`, `generated_after.json`, `generated_delta.json` | Inventario completo y cambios del C generado. |
| `backup_manifest.json`, `backup_verified.json` | Integridad de la copia previa. |
| `retail_before.json`, `retail_after.json` | Perfiles SCPH1001 conservados. |
| `verification.json`, `details.json` | Resumen de comprobaciones y hashes de entradas/binarios. |
| `status_*`, `diff_*` | Estado y diferencias Git previos/posteriores de ambos repositorios. |
| `*.command.json` | Argumentos, directorio, fecha y código de salida de cada comando capturado. |

La diferencia de archivos seguidos por Git del padre y del framework fue idéntica antes/después de las operaciones, antes de añadir este documento. Los cambios preexistentes permanecen. No hubo instalaciones, red, commits, pushes ni builds del runtime.

## Actualización (sesión de cierre) — P1.4 resuelto

- **Causa raíz:** el fallo del comando oficial no era del emisor ni de la imagen.
  `runtime/check_test_registration.cmake` aborta **cualquier** configure cuando hay
  tests en `runtime/tests/` sin registrar; los dos tests nuevos de IRQ
  (`test_irq_callback_recovery.{c,py}`) estaban sin registrar.
- **Arreglo (registro real, no whitelist):** se registró el test en
  `runtime/CMakeLists.txt` (`irq_callback_recovery_test`); al compartir nombre base
  con el `.c`, ambos quedan declarados. El `.py` ahora crea un directorio temporal si
  no se le pasa `--out-dir` (repetible en ctest) y resuelve `nm` junto al compilador.
  Se usa un GCC descubierto (el test es solo-GNU: `nm` + diagnóstico de `ld`) en vez
  de `${CMAKE_C_COMPILER}`, porque clang usa `ld.lld` con otro texto de error.
- **Regeneración ejecutada:**
  `PSXRECOMP_BIOS_BUILD=../build-recompiler psxrecomp/tools/regen_bios.sh --config bios/OpenBIOS.toml`
  → `EMIT OK emitted=651 interpreted=0 skipped=4 instructions=17526 dispatch_entries=3990`;
  huella escrita en `psxrecomp/generated/OpenBIOS.emitter.sha`. Salida 0.
- **Build:** `psx-runtime` y `psx-runtime-pgxp` reconstruidos enlazando el C de
  OpenBIOS nuevo; enlace OK.
- **Verificación:** `python tools/verify_offline.py` → **PASA**. OpenBIOS ya **no** está
  stale; SCPH1001 y su respaldo permanecen intactos. P1.4 queda **cerrado**.
