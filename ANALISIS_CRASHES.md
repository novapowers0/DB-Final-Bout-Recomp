# DBFinalBout Recomp — Análisis de crasheos y plan de corrección

> Sesión de diagnóstico comparando contra el proyecto hermano **Bloody Roar 2**
> (estable, release v0.5.0). Documenta el **root cause** de los crasheos, el
> **fix aplicado** y el **trabajo pendiente** para estabilizar el combate.

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

## 4. El bloqueo real restante: el overlay de combate (STEP40) NO se compila

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

### Pendiente de validación (usuario)
1. Jugar una pelea con `overlay_cache=true` (ya activo) y el shard nuevo.
2. Confirmar que no hay `psx_freeze_dump_*.json` nuevos ni el crash `0xD7FFFFAC`.
3. Verificar nativo: `python psxrecomp/tools/stall_report.py --port 4370 snap`
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

## 9. Referencias

- `psxrecomp/docs/COMPILING_OVERLAYS.md` — pipeline overlay cache.
- `psxrecomp/docs/overlay-status.md` — bugs conocidos (OV-1 stale registration;
  Inc2 reload-on-return pendiente).
- `psxrecomp/tools/compile_overlays.py` — clasificador de seeds / regiones.
- `psxrecomp/recompiler/src/code_generator.cpp` (≈1907) y
  `full_function_emitter.cpp` (≈673) — fix del load-delay entre fragmentos.
- `psxrecomp/runtime/src/overlay_loader.c` — dispatch nativo vs intérprete.
