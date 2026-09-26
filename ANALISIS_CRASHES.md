# DBFinalBout Recomp — Análisis de crasheos y plan de corrección

> Análisis histórico de los freezes de overlays y del fallo de transición a
> combate. El fix RI está aplicado y la build compiló el 2026-09-26; aún falta
> validación manual de Little Goku contra Piccolo y comparación con Beetle.

Los apartados 1–8 documentan principalmente freezes históricos del intérprete.
El fail-fast de transición analizado en §9 es un incidente distinto: se detectó
una instrucción SPECIAL inválida en una ranura de handler que el juego estaba
reconstruyendo. El fix RI está compilado, pero no se considera validado hasta la
prueba manual pendiente.

---

## 1. Resumen ejecutivo

Los "crasheos" de Final Bout **no son crashes de código nativo**: son
**congelamientos del intérprete** (`wedge_kind: spin_freeze / slow_frames / fatal`)
que ocurren cuando el **código real del juego (menús + combate) corre en el
intérprete dirty-RAM**, demasiado lento y atascado en bucles de excepción.

La causa raíz arquitectónica:

- **Bloody Roar 2**: todo el juego es un único EXE grande (`0xA0800`) que se
  recompila **nativo de una vez** (1014 seeds). No tiene overlays runtime, por eso
  es estable sin overlay cache.
- **Final Bout**: el EXE es diminuto (`0x2E000`) y **todo el gameplay vive en
  overlays** (`STEP00-03/40/999.BIN` cargados del disco a RAM en tiempo real). Ese
  código de overlay **solo se vuelve nativo vía el pipeline overlay-cache**, que
  en este fork está **inmaduro y con bugs conocidos**. Si el overlay no se
  compila nativo, corre en el intérprete → congelamiento.

La lección de BR2 se **aplicó mal**: el comentario del config desactivado decía
"BR2 es estable sin overlay cache (todo interpretado)". Pero BR2 es estable porque
su código ya es nativo AOT, no porque el intérprete baste. Final Bout *necesita*
el overlay cache; desactivarlo solo cambia un crash nativo por un freeze.

---

## 2. Evidencia de los crasheos

Todos los dumps (`psx_freeze_dump_*.json`) comparten la misma firma:

| Campo | Valor | Lectura |
|---|---|---|
| `wedge_kind` | `5` (spin_freeze) / `4` (fatal) / `3` (slow_frames) | congelamiento, no crash nativo |
| `dispatch_count` | `0` | el loader de overlays **no despachó nada nativo** |
| `overlay_loader.active` | `0` | **el loader estaba DESACTIVADO** |
| `overlay_loader.registered` | `0` | 0 overlays registrados |
| `overlay_loader.loads` | `0` | 0 cargas |
| `dirty_ram_insns` | ~6.7M – 12.8M | todo corriendo en el intérprete |
| `in_exception` | `1` | atascado re-entrando el manejador de excepción |
| `exception_entries` | 18k – 46k | el intérprete da vueltas en bucles de excepción |
| `current_func` | `0x000029CC` | PC bajo = dentro de código de excepción |
| `last_store_pc` | `0x8003EDxx` | código de overlay (STEP40) interpretado |

Conclusión: **el juego corre sus menús/combate 100% interpretados** porque el
overlay cache estaba apagado y/o el overlay de combate no estaba compilado.

---

## 3. Los DOS bugs y el fix aplicado

### 3.1 Bug A — Miscompilación nativa `0xD7FFFFAC` (ya corregido en el árbol)

Con `overlay_cache=true` y overlays recompilados, entrar en combate crasheaba:

```
FAIL-FAST unknown dispatch: addr=0xD7FFFFAC phys=0x17FFFFAC ra=0x8003ED74
```

`ra=0x8003ED74` es código del overlay STEP40; el salto a `0xD7FFFFAC` es un
puntero corrupto → **mala compilación** (load-delay entre fragmentos).

**Estado:** el bug está corregido en el árbol de psxrecomp
(`recompiler/src/code_generator.cpp` ~línea 1907 y
`full_function_emitter.cpp` ~línea 673: el temp `psx_ldd_<addr>` se declara en el
scope del bloque load-delay y el flush solo emite sitios del mismo fragmento).
Verificado: el recompilador `psxrecomp-game.exe` y los shards actuales están
construidos **con el código corregido** (hash codegen `0x5ddbd2c4` en ambos).

### 3.2 Bug B — Config desincronizado: `overlay_cache=false` en el config desplegado (CORREGIDO HOY)

El `build-release/game.toml` (el que el exe lee en runtime) tenía
`overlay_cache = false` con un comentario que citaba el crash de Bug A como razón.
Pero:

- El árbol fuente `game.toml` ya tenía `overlay_cache = true` (actualizado después
  del fix de Bug A).
- El recompilador, el exe y los shards **ya estaban reconstruidos con el fix**
  (timestamps 21:25–21:27 del 18/08).
- El config desplegado (21:20) era **anterior al fix** y quedó desincronizado
  (el POST_BUILD de CMake no se re-ejecutó tras editar `game.toml`).

**Fix aplicado hoy:** copiado `game.toml` → `build-release/game.toml`, de modo que
el runtime usa `overlay_cache = true` con shards ya correctos. Ambos configs
coinciden ahora.

---

## 4. Bloqueo histórico: el overlay de combate (STEP40) NO se compilaba

Este apartado describe el estado previo al trabajo de overlays del 19/08; no es
el estado actual. El STEP40 se compiló después (ver §7), y el problema posterior
de transición a combate se analiza por separado en §9.

Al recompilar los overlays (`compile_overlays.py --check --force`), la región del
combate **se salta como "data-only"**:

```
Overlay  load=0x80068000  size=28676  crc32=0x05DDBCB5
  seeds: 0  dll: ...\00068000_05DDBCB5.dll
  SKIP: no walk-root seeds (data-only region)
```

El capture `[9]` del STEP40 tiene `dispatch_entry_pcs` y 1967 `executed_pcs`, pero
`function_entry_pcs` está **vacío**, y el clasificador (`classify_overlay_seeds`)
rechaza promover los dispatch entries a raíces porque **falla la verificación de
frontera** (`_callable_legacy_seed`: necesita `jr $ra` precedente / prólogo /
inicio de región). Sin raíz → región "data-only" → **nunca se compila nativo** →
el combate siempre va por el intérprete → freeze.

Los shards reales en `cache/` solo cubren:
- `0x800035xx` (8 fragmentos, región 0x1000)
- `0x8001104C` (1)
- `0x800537E0` (2)

**Ninguno cubre el combate (`0x8006xxxx`).**

El intento `--force-interior 0x8006A3C8 ...` **no ayudó**: la fuerza solo aplica
dentro de regiones ya con raíz, y el STEP40 no tiene raíz, así que sigue en "no
walk-root seeds".

---

## 5. Por qué la desactivación era el reflejo equivocado (vs BR2)

| | Bloody Roar 2 | DB Final Bout |
|---|---|---|
| Código del juego | EXE único `0xA0800` | EXE chico `0x2E000` + overlays STEP*.BIN |
| Seeds de funciones | 1014 | 301 |
| Necesita overlay cache | No (todo AOT nativo) | **Sí (gameplay en overlays)** |
| Estable sin cache | Sí | **No → freeze** |
| Lección para FB | maximizar cobertura AOT | **hacer funcionar el overlay cache** |

El comentario "BR2 ship with NO overlay cache (all interpreted) and is stable" es
cierto pero **la conclusión es falsa para Final Bout**.

---

## 6. Qué se ha hecho (entregables)

1. **Diagnóstico definitivo** del root cause (arriba).
2. **Config corregido**: `build-release/game.toml` ahora `overlay_cache = true`,
   alineado con el árbol. El exe arranca con él sin crash inmediato.
3. **Verificado** que recompilador + shards + headers comparten el mismo hash de
   codegen (`0x5ddbd2c4`) y que el exe está reconstruido tras el fix de Bug A.
4. **[19/08] Combate (STEP40) nativo**: 35 fronteras de función reales declaradas
   en `game.toml [[overlays]]`; el STEP40 compila a un shard con 26 funciones del
   combate (ver §7). Elimina el `spin_freeze` de pelea.

---

## 7. Fix del combate (STEP40) aplicado el 19/08 — Opción A ejecutada

**Hecho:** la Opción A (semillas de frontera para el STEP40) se ejecutó sin Ghidra
completo, analizando directamente los bytes del capture.

### Diagnóstico del STEP40
Los 3 "dispatch seeds" del capture `[9]` **no son inicios de función** — son
puntos interiores de código:

| seed | palabra | decode |
|---|---|---|
| `0x8006A3C8` | `0x0801A914` | `j 0x6A450` |
| `0x8006A580` | `0x3231007F` | `andi s1,s1,0x7F` |
| `0x8006DBFC` | `0x8E030000` | `lw v1,0(s0)` |

Por eso `_callable_legacy_seed` los rechazaba → región "data-only" → combate
interpretado.

### Fix: escanear los bytes del capture por prólogos de función
Recorrí los 28 KB capturados del STEP40 buscando **`addiu sp,sp,-N` que además
aparecen en `executed_pcs`** (frontera de función + código realmente ejecutado).
Encontré **35 candidatos** seguros (precisión > recall: prólogo de pila + evidencia
de ejecución). Los declaré en `game.toml` bajo `[[overlays]]`:

```toml
[[overlays]]
load_addr = "0x80068000"
function_entry_pcs = [ "0x80069228", ... 35 entradas ... ]
```

Sin `bytes_crc`, para que aplique a cualquier capture del STEP40 (robusto a
variaciones). `_collect_toml_overlay_entries()` los lee y `classify_overlay_seeds`
los promueve a raíces.

### Resultado
Recompilado en el cache real (`compile_overlays.py --only-region 0x80068000
--force`):

```
Overlay  load=0x80068000  size=28676  crc32=0x05DDBCB5
  seeds: 47  OK -> ...\00068000_05DDBCB5.dll   (330 KB)
PSX_SHARD_RESULT ok=1 failed=0
```

El shard registra **26 funciones del combate** (rango `0x80069228..0x8006E5FC`),
más aliases. El combate ya no depende del intérprete → se elimina el `spin_freeze`.

### Validación histórica del shard (sesión anterior)
1. Jugar una pelea con `overlay_cache=true` (ya activo) y el shard nuevo.
2. Confirmar que no hay `psx_freeze_dump_*.json` nuevos ni el crash `0xD7FFFFAC`.
3. En aquella validación se propuso comprobar ejecución nativa con
   `python psxrecomp/tools/stall_report.py --port 4370 snap`
   → `dispatch_native` alto frente a `dispatch_interp_fallback` bajo.

### Siguiente mejora (cobertura)
- El capture solo tiene 28 KB del STEP40 (la parte ejecutada en esa sesión). El
  STEP40 real es ~442 KB. Jugar más combates/variedad y recapturar ampliará la
  cobertura (el shard crece con `--force`).
- Otras regiones (menús `0x8003F000`/`0x80047000`) también se saltan como
  data-only: aplicar el mismo escaneo de prólogos les daría cobertura nativa.
- La región boot `0x80001000` falla el audit (5 "unsupported"); usar
  `overlay_native_block` para esos fragmentos si estorba.

---

## 8. Notas de mantenimiento / higiene

Las reglas de mantenimiento de esta sección siguen aplicando a cualquier
recompilacion o cambio de configuracion.

## 9. Crash de transición a combate — 2026-09-11

Durante una sesión manual de prueba iniciada desde
`INICIAR_FINAL_BOUT_CON_CAPTURA.bat`, el juego falló al iniciar un combate. No
se produjo un JSON de captura completo porque la primera versión del capturador
solo escribía el archivo al terminar normalmente. Sí se conservaron los
informes del runtime en `build-release`.

Evidence from `build-release/psx_crash.txt` and
`build-release/psx_last_run_report.json`:

- timestamp: `2026-09-11T16:25:07Z`;
- frame: `5992`;
- `FAIL-FAST unknown dispatch` at `0x00002934`;
- return address: `0x0000293C`;
- `a0 = 0x01000000`, `a1 = 0x00000400`;
- last function address: `0x0000279C`;
- exception EPC: `0x80041E78`;
- one mid-block unsupported instruction at `0x00002030`, word
  `0x000900FF`, classified as `SPECIAL funct`;
- the unknown-dispatch ring contains exactly one entry;
- the tail repeatedly executes the `0x00002914..0x00002964` region before the
  fail-fast.

Initial classification: a recompiler/discovery failure in a low-address
exception or dispatch path. It was not evidence of a gameplay-rule bug and no
Responsive plugin was active. The later RE in §9.1–9.3 refined this diagnosis:
the kernel IRQ walker entered a handler slot being rebuilt, and an unsupported
mid-block instruction caused the fail-fast. Do not add a guessed seed or patch
`0x00002934`; the applied interpreter fix is documented in §9.3.

The capture tool now writes an atomic `.json.partial` checkpoint after every
manual sample, so a repeat of this test will retain evidence even if the game
or terminal is closed unexpectedly.

The second occurrence at `2026-09-11T16:28:51Z` has the same signature as the
first (`0x00002934`, `ra=0x0000293C`, unsupported `0x000900FF` at
`0x00002030`) and occurred while `build-release/settings.toml` selected Vulkan.
The signature is in the CPU dispatch/exception path, so Vulkan is not currently
the leading cause. An A/B launcher, `INICIAR_FINAL_BOUT_OPENGL_CON_CAPTURA.bat`,
now allows a controlled OpenGL comparison without permanently changing the
user's settings. If the same dispatch failure appears, the renderer is ruled
out; if only OpenGL survives, renderer interaction remains a secondary suspect,
but the CPU path still needs the primary fix.

### 9.1 Addendum RE estático — 2026-09-11

Análisis sobre el freeze dump del run que falló
(`psx_freeze_dump_psx-runtime_1789144131_0.json`, frame 5750). Ver
`PLAN_SOLUCION_CRASH_Y_COMBATE.md` para el detalle completo.

**`0x2934` es el despachador de la cadena de IRQ del kernel.** Desensamblado de
`0x291C..0x295C` (`ram_peeks.ra`):

```
lw s1,8(s6) / lw s0,4(s6) / beq s1,0 / jalr s1 / beq v0,0 /
or v1,v0 / jalr s0 / lw s6,0(s6) / beq s6,ra (loop)
```

`gpr[17]=0x1F6C` (handler del juego), `gpr[31]=0x293C` (retorno del `jalr`). Es
el recorredor de la cadena de callbacks de interrupción (`SysEnqIntRP`), no una
función del juego: **no debe sembrarse.**

**`0x2934` no es hueco de cobertura.** En ese mismo run se interpretó **40.740
veces** (`dirty_block`, seq 2595200, frame 5750), la última justo antes del
fallo. El rechazo es dependiente de estado.

**Compuerta inicialmente sospechada, después descartada**
(`dirty_ram_interp.c:2845`): el análisis preliminar consideró que si la página
no estaba dirty y el objetivo no era game-text ni overlay,
`dirty_ram_dispatch` devolvía 0 y llamaba a `psx_unknown_dispatch`. Para `0x2934`:
`g_text_image_lo = 0x10000`, `g_overlay_region_floor = 0x3E000`, así que la
única salida posible es el bit dirty o `psx_kernel_bless_dispatchable`. La
ventana del kernel `[0,0x10000)` está **excluida a propósito** de la heurística
"admitir palabra decodificable" (`dirty_ram_interp.h:79-83`).

**Hipótesis inicial (posteriormente refutada):** la propia instrumentación. El
cliente de captura anterior pedía `gpu_state`/`overlay`/`history` cada 5 s y
volcaba rings de 100.000 entradas, lo que podía desplazar el timing durante la
transición (carga de `STEP40` por CD + escritura de `overlay_cache`). La prueba
con `INICIAR_FINAL_BOUT_NATIVO.bat` reprodujo el fallo sin capturador; véase §9.2
y la hipótesis H1 en el plan.

**Build de diagnóstico (aplicada):** `runtime/src/traps.c` ahora añade al
`psx_crash.txt` una línea `refusal context: dirty=… overlay_region=… in_text=…
kbless=… in_exception=… interp_unsupported=…`. Solo observación, sin cambio de
comportamiento. `DBFinalBout_Recompiled.exe` reconstruido; backups en
`DBFinalBout_Recompiled.exe.bak_pre_diag` y `%TEMP%\opencode\traps.c.bak_pre_diag`.

### 9.2 Addendum — segunda prueba del usuario (2026-09-12)

- `INICIAR_FINAL_BOUT_NATIVO.bat` **también crasheó** (sin capturador) → la
  hipótesis de perturbación por instrumentación queda **descartada**.
- `INICIAR_FINAL_BOUT_SEGURO.bat` (`PSX_FAIL_FAST_UNKNOWN_DISPATCH=0`) **no
  crasheó**; el miss se absorbe y el juego continúa. Patrón reportado: crashes
  con **Piccolo** de rival (jugador Little Goku); sin crash contra Goku adulto.
- `psx_crash.txt` (build con diagnóstico) ahora reporta:
  `dirty=1 overlay_region=0 in_text=0 kbless=0 in_exception=1
  interp_unsupported=SPECIAL funct`.
  - `dirty=1` **descarta la compuerta de página limpia** (`dirty_ram_interp.c:2845`).
  - El intérprete cubre todo el set SPECIAL válido del R3000A, así que ese motivo
    implica **datos ejecutados como código** o un `psx_unknown_dispatch` que **no
    pasó por el intérprete**.
  - El `dirty_block` termina en `0x2924 → 0x2934 → 0x1F6C` sin entrada posterior,
    o sea el fallo **no entró por `dirty_ram_dispatch_inner`**. Vía candidata: el
    preámbulo de overlays nativos
    (`overlay_dispatch_preamble.c.inc:76`) y los stubs de `OpenBIOS_full.c`, que
    invocan `psx_unknown_dispatch` directamente.
- Diagnóstico ampliado otra vez: `psx_crash.txt` incluye
  `interp detail: last_unsupported_pc / insn / block_entry / entry_ra / midblock /
  aborts`. Build reconstruida.

### 9.3 Addendum — causa raíz definitiva (reproducción Piccolo, frame 2356)

```
interp detail: last_unsupported_pc=0x00002030 insn=0x000900FF
               block_entry=0x00001F6C entry_ra=0x0000293C midblock=1 aborts=1
```

1. El recorredor de IRQ del kernel (`0x291C..0x2954`) salta vía `jalr s1` al
   handler `0x1F6C` (ranura de la tabla de handlers/eventos del juego).
2. En el mismo frame, overlay de VS/transición `0x8003F000` (`pc=0x80042CBC`,
   `ra=0x80042328`) **escribe ceros** sobre `[0x1F00,0x1FE0)` y pointers en
   `0x1FE4+`: está limpiando/reconstruyendo esa tabla.
3. `0x1F6C` está a ceros; el intérprete la ejecuta como código (49 NOPs) y en
   `0x2030` encuentra `0x000900FF` (funct `0x3F`), no válida.
4. `abort_unsupported(...,"SPECIAL funct")` → mid-block → `cpu->pc=0` → el
   dispatch cae en `psx_unknown_dispatch(0x2934)` → fail-fast.

En hardware, el paso 3 levanta **Reserved Instruction (ExcCode 10)** y corre el
manejador del juego; el intérprete abortaba en lugar de excepcionar. **Fix
aplicado** en `psxrecomp/runtime/src/dirty_ram_interp.c`: el caso mid-block de
opcode no soportado llama a `interp_exception(cpu, 10, 0, g_unsupported_pc)`;
el caso de primera instrucción sigue devolviendo `0` para preservar la resolución
de trampolines. El cambio está commiteado en `psxrecomp` (`d76c5c39`) e integrado
con upstream en `7d70880d`. La build Release se recompiló correctamente el
2026-09-26. **La prueba manual de Little Goku contra Piccolo y la validación
contra Beetle siguen pendientes**; no afirmar que la transición ya está
corregida en ejecución. El disparador observado es la entrega de IRQ mientras
se reconstruye la tabla; el timing fiel sigue siendo el arreglo de fondo. Ver
`PLAN_SOLUCION_CRASH_Y_COMBATE.md` §3.2.

### 9.4 Actualización de frameworks — 2026-09-26

- `psxrecomp` actualizado con merge de upstream master en `rework-master`:
  `7d70880d` (base upstream `d62f4b44`), publicado en el fork
  `novapowers0/psxrecomp`.
- `recomp-ui` actualizado a `01bff947` (fast-forward de upstream master).
- Submódulo anidado `psxrecomp/lib/recomp-net`: `c2338c63`.
- `DBFinalBout_Recompiled.exe` se recompiló con Ninja/clang; el target enlazó
  correctamente. Esto verifica build, no el comportamiento manual del juego.
- Versión del proyecto: `0.1.1`; la release empaquetada `v0.1.0` no se modificó.

- **Nunca editar solo `build-release/game.toml`**: es regenerado por CMake
  (POST_BUILD `copy_if_different`). Editar el fuente `game.toml` y **rehacer el
  build** para que el staged se refresque. El desync de hoy vino de editar el
  fuente después del último build.
- El hash de codegen (`0x5ddbd2c4`) **bloquea la reutilización de shards viejos**:
  al tocar `code_generator.cpp`/`full_function_emitter.cpp`, recompilar shards con
  el nuevo hash (no es un bug, es el guard de versiones funcionando).
- `overlay_captures.json` contiene código del juego de TU disco: **no subirlo**.
- El release empaquetado (`dist/stage-...`) tenía otro hash (`0x51c0ca8f`): si se
  empaqueta, los shards del dev box (0x5ddbd2c4) no los leerá el exe del release
  hasta que se reconstruya el empaquetado con el árbol actual.

---

## 10. Referencias

- `psxrecomp/docs/COMPILING_OVERLAYS.md` — pipeline overlay cache.
- `psxrecomp/docs/overlay-status.md` — bugs conocidos (OV-1 stale registration;
  Inc2 reload-on-return pendiente).
- `psxrecomp/tools/compile_overlays.py` — clasificador de seeds / regiones.
- `psxrecomp/recompiler/src/code_generator.cpp` (≈1907) y
  `full_function_emitter.cpp` (≈673) — fix del load-delay entre fragmentos.
- `psxrecomp/runtime/src/overlay_loader.c` — dispatch nativo vs intérprete.
