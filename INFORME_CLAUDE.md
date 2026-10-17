# INFORME_CLAUDE.md — Sesión de Fase A + Fase B (2026-10-03/04)

Sesión autónoma (sin humano en el bucle). **No se hizo commit ni push.** Todo el
trabajo de juego se hizo con el exe real controlado por el debug server TCP
(puerto 4370); no quedan instancias vivas (`tasklist` limpio al cerrar).

---

## 1. Resumen ejecutivo

1. **Causa raíz de `disp_native=0` encontrada y corregida.** El runtime lee la
   caché `cg13_8ee36729_…` pero el recompilador (`build-recompiler`, de 09-09) y
   los DLL eran `cg10_f2c33ef6_…`: *todos* los overlays corrían interpretados
   (`OVERLAY CACHE HASH MISMATCH` en `overlay_loader_status.last_msg`).
   `verify_offline.py` pasaba igualmente porque comprobaba un hash fijo (`cg10`).
   Corregido: recompilador reconstruido, `verify_offline.py` ahora compara
   runtime ↔ recompilador ↔ caché.
2. **Cobertura nativa del combate:** de `0` a **≈95 % de despachos nativos** en
   el primer combate de una sesión, y de ~94 M a ~0,4–0,6 M instrucciones
   interpretadas por ~1 250–1 880 frames de combate. **Limitación:** a partir del
   2.º combate de la misma sesión el reparto nativo cae a ~7 % (no investigado).
3. **Freeze de transición reproducido dos veces** (sesión 1 con la caché rota; y
   en la 3.ª transición de una campaña con caché nativa). Causa del bucle
   documentada con evidencia (§4.2). La recuperación del callback IRQ de la
   sesión anterior **no se disparaba** (`empty_irq_callback_returns=0`) porque
   exigía "solo NOPs" y la RAM tras el slot contiene una tabla de punteros.
   Generalicé la recuperación (§3). **No verificada**: en las 5 transiciones
   posteriores no volvió a aparecer el freeze, así que el contador sigue en 0.
4. **Segundo combate:** en 8 combates secuenciales (3 en sesión 2 y 5 en la
   campaña) ambos retratos se vieron y no hubo pantalla negra. No se reprodujo el
   fallo, por tanto **no se puede afirmar que esté corregido**.
5. **Fase B – Tier 1 completo en lo verificable; Tier 2 con una feature.** Plugin
   confiable `dbfb.responsive` (manifest v6, features desactivadas por defecto):
   `trace` (solo lectura) e `input-buffer` (única feature con escritura). Se
   verificó en vivo el mecanismo y el control "Original" (cero escrituras).
   **No** se consiguió mapear la estructura del luchador (§5.4) y **no** se
   evaluó el efecto de `input-buffer` en la sensación de combate.
6. **No hecho:** A4 (sombras 3D / oráculo Beetle), A7 (decisión multi-región),
   A5 completo (pausa, rematch, launcher), empaquetado de release.

---

## 2. Estado de partida → final

| Métrica | Partida | Final |
|---|---|---|
| `verify_offline.py` | pasa (hash `cg10` fijo, 10 DLL) | pasa (comprobación real; 110 DLL en `cg13_8ee36729_gc101f51f1_f0`) |
| Hash codegen recompilador | `f2c33ef6` (obsoleto) | `8ee36729` (= runtime) |
| `dispatch_native` / `interp` (sesión 1) | 0 / 1 383 060 | — |
| Sesión 2 (caché `cg13`, sin cobertura STEP40) | — | 4 278 865 nativos / 6 249 523 interp |
| Ventana de combate (tras DLL STEP40) | ~94 M insns interpretadas / 1 238 frames | 0,36 M / 1 241 frames (95,5 % nativo) |
| Combates jugados sin freeze en la sesión de prueba | 0 (freeze en la 1.ª selección) | 5/5 (campaña) |

Artefactos de la línea base A1 (sesión 1, caché rota): frame 3166, `in_exception=1`,
`exception_entries=25724`, `dirty_ram_insns≈8,4 M`, `midblock=255`,
`block_entry=0x1F6C`, `entry_ra=0x293C`, `last_pc=0x2030`, `insn=0x000900FF`,
`empty_irq_callback_returns=0`, `fatal` por guarda de recursión, +1 `psx_freeze_dump`.

---

## 3. Cambios por archivo

| Archivo | Qué y por qué |
|---|---|
| `tools/verify_offline.py` | Lee versión (`overlay_api.h`) y hash (`overlay_codegen_hash.h`) que usa el runtime, exige que `build-recompiler` tenga el mismo hash y que exista exactamente una caché `cg<ver>_<hash>_…`; mínimo 10 DLL (antes "exactamente 10", hash fijo). Habría detectado el desajuste. |
| `game.toml` | (a) nuevo `[[overlays]]` **`0x8003E000`** (130 entradas, ver §4.3); (b) `0x80060000` pasa de 89 a 106 entradas (reordenadas); (c) `[recompiler] mod_function_entry_funcs = ["0x8003FCF0","0x8003FE68"]`. (c) cambia el hash de configuración → caché nueva `gc101f51f1`. `build-release/game.toml` se sincronizó con el build (no se editó a mano). |
| `psxrecomp/runtime/src/dirty_ram_interp.c` (submódulo, sin commit) | Recuperación del callback IRQ vacío generalizada: ya no exige "solo NOPs"; exige **ninguna escritura ejecutada** (`insns_had_store`) y restaura s0-s7/gp/sp/fp del snapshot de entrada antes de devolver `v0=0` al walker (`ra` 0x293C/0x2950). Contador `empty_irq_callback_returns` sin cambios. |
| `CMakeLists.txt` | `PRELOADED_MODS_DIR mods/preloaded` y `target_sources` del plugin en `psx-runtime` y `psx-runtime-pgxp`. |
| `src/mods/dbfb_responsive.c` (nuevo) | Plugin confiable (ver §5). |
| `mods/preloaded/packages/dbfb.responsive/0.1.0/manifest.toml` (nuevo) | Manifest v6: features `trace` (canal `developer`) e `input-buffer` (canal `experimental`, opción entera `window` 1..6), ambas `default_enabled=false`. |
| `tools/step40_coverage_step.py` (nuevo) | Procedimiento reproducible de cobertura (§4.3). Sin bytes de disco. |
| `INFORME_CLAUDE.md` | Este informe. |

No se editó `generated/`. No se añadió `fprintf` ni log ad-hoc. Los scripts de
piloto automático/análisis usados viven solo en el scratchpad de la sesión
(no se versionan).

Build local, no versionado: `build-recompiler/psxrecomp-game.exe` reconstruido;
`build-release/cache/…/cg13_8ee36729_gc101f51f1_f0` (110 DLL);
`build-release/DBFinalBout_Recompiled[_pgxp].exe` reconstruidos. Se borró la
caché intermedia `cg13_8ee36729_gcb2cea661_f0` (obsoleta tras cambiar la config).

---

## 4. Evidencia (Fase A)

### 4.1 A1 / A2 — desajuste de hash
`overlay_loader_status.last_msg`: *"this build reads gcc/cg13_8ee36729_gcb2cea661_f0
but shards exist under gcc/cg10_f2c33ef6_gcb2cea661_f0 … ALL overlays run
INTERPRETED"*. Arreglo: `cmake --build build-recompiler --target psxrecomp-game`
(hash pasa a `0x8ee36729`) + `compile_overlays.py` (84 shards OK, 0 fallos).
Tras esto, sesión 2: `registered=3→351`, `overlay_native=4,28 M`.

### 4.2 Causa del freeze (estado vivo congelado, dos reproducciones)
- `get_registers`: `EPC=0x2030`, `Cause=0x428` (ExcCode 10 = RI + IP2), `SR=0x40020400`.
- Cadena de IRQ del kernel (base `[0x100]=0x8DE0`): cola 0 → nodo `0x463C` con
  **handler `0x1F6C`**; cola 3 → nodo `0x462C` handler `0x16E4`.
- RAM `0x1F00..0x1FE0` = ceros; desde `0x1FE4` hay una tabla de punteros
  `0x801BC044…` (decodifican como `lb`) y en `0x2030` la palabra `0x000900FF`
  (funct 0x3F, no es instrucción R3000A).
- `I_STAT=0x04` (CD-ROM) pendiente, `I_MASK=0x0D`. El walker (`0x2924..0x2964`)
  llama al handler vacío → RI → el handler del kernel (`0x80000080→0x27AC→0x2818
  →0x3554→0x369C`) vuelve a recorrer la cadena → bucle hasta la guarda de recursión.
- El overlay de transición (`0x80042CBC`, según el análisis previo) limpia esa
  zona; el nodo sigue encolado. **Causa última no demostrada**: probablemente
  entrega de IRQ en una ventana en la que hardware real no la entregaría
  (temporización), como ya apuntaba `PLAN_SOLUCION…`. El arreglo del intérprete
  es una mitigación, no esa corrección.
- Reproducciones: sesión 1 (Piccolo vs Piccolo, caché rota, 1.ª transición) y
  campaña 1 (caché nativa, **3.ª** transición, selección de Piccolo). Con Piccolo
  en la 1.ª transición de sesión limpia: 4/4 sin freeze. Es dependiente del estado.
- Campaña 2 (5 combates: Goku, Trunks, Piccolo, Pan, Cell) con el arreglo del
  intérprete: sin freeze, contador 0 → **el arreglo no se ejercitó**.

### 4.3 Cobertura nativa del combate (STEP40)
- `overlays_out/STEP40.BIN` es un volcado en **sectores crudos de 2352 bytes**
  (offset `0x22060` no corresponde 1:1 a RAM; cada 2048 B de usuario van 304 B de
  cabecera/ECC). La regla "no compilar desde capturas truncadas" se cumplió
  usando la **RAM viva completa** del combate: 0 discrepancias en 182 315
  comparaciones de PCs ejecutados contra las capturas históricas por página.
- El overlay de combate ocupa **`0x8003E7F0..0x80072520`**, no solo `0x80060000+`.
  La parte baja (`0x8003E000..0x80060000`) estaba sin declarar y concentraba el
  64–70 % de las instrucciones interpretadas.
- Criterios de aceptación de una frontera nueva (todas con evidencia):
  prólogo estricto `addiu sp,sp,-N` **ejecutado** y con ≥1 `jal` en la RAM viva
  (95 entradas), o destino observado por el intérprete cuyo `ra-8` es un
  `jal`/`jalr` (callbacks de hoja sin prólogo, p. ej. `0x800402D4`,
  `0x80040400`, y la función de render `0x80054684`, llamada por `jalr`).
  No se declararon 28 prólogos ejecutados sin `jal`.
- Resultado: `0003E000_*` 196 funciones, `00060000_*` 117 funciones.
- Ciclo repetible: `python tools/step40_coverage_step.py` con un combate en
  pantalla (ver §6).
- **Límite:** `0x80055278`/`0x800551E8` son hojas GTE sin prólogo ni `jal`; tras
  cubrir `0x80054684` dejaron de dominar, pero no se declaran por separado.
  Cobertura medida solo en el primer combate de cada proceso (§1.2).

### 4.4 Campaña de humo (5 combates, un proceso)
| Combate | frames | nativos | interp | insns interpretadas |
|---|---|---|---|---|
| Goku | 1878 | 1 976 627 | 86 861 | 579 791 |
| Trunks | 1872 | 148 607 | 126 898 | 1 035 123 |
| Piccolo | 1870 | 9 819 | 138 921 | 1 127 120 |
| Pan | 1844 | 9 012 | 129 697 | 1 075 574 |
| Cell | 1849 | 9 005 | 128 944 | 1 074 512 |

Todos terminaron; ninguno se congeló; `fatal=no`; `empty_irq_callback_returns=0`.
La caída nativa a partir del 2.º combate **no está explicada** (hipótesis sin
probar: las páginas de datos del overlay difieren y el CRC de código ya no
empareja; hay que mirar `overlay_loader_status` por combate).

### 4.5 Matriz de humo (lo que se probó realmente)
| Caso | Resultado |
|---|---|
| Boot / intro / título | ✔ (capturas) |
| Launcher | **no probado** (siempre `--no-launcher`) |
| Menús (principal, VS COM, opciones, memory card) | ✔ |
| Selección de personaje | ✔ (Goku, Trunks, Pan, Piccolo, Cell; rivales Cell/Boo) |
| ≥3 combates | ✔ (8 en total entre sesiones 2 y campaña 2) |
| Ataques/movimiento/vuelo (↑) | entradas aleatorias; aparece HUD "Meteor 03" en un combo |
| Pausa | **no confirmado** (un START en combate sin efecto visible) |
| Especiales | **no confirmado** de forma dirigida |
| Rematch | **no probado** |
| Cierre | ✔ (`quit`/`atexit`; ver nota sobre `emu busy`) |

### 4.6 Incidencias sin explicar
- `FAIL-FAST unknown dispatch 0x2934` a **frame 8418** (menús, `trace` activo, sin
  instrucción no soportada, `a0=0xF2000000`→`0x00B17000`). Evidencia conservada
  en el scratchpad (`ev3/report_failfast_0046.json`). Dos ejecuciones ociosas
  posteriores (con y sin `trace`) llegaron a ~10 600 frames sin fallo: **no
  reproducido, causa no determinada, no se puede descartar el plugin**.
- Dos volcados automáticos `slow_frames` (130 MB c/u, en `build-release/`,
  ignorados por git) causados por mis lecturas TCP de 2 MB / `dirty_ram_stats`.
  `quit` por TCP responde `emu busy or frozen` pero el proceso termina.
- A4 (sombras 3D): **no se investigó**. A7 (multi-región): **sin decidir**.
- Las imágenes `.png` del debug server son sin comprimir; no aparecen en el repo.

---

## 5. Mod de combate

### 5.1 Hechos del invitado verificados (evidencia viva + desensamblado)
| Dirección | Hecho |
|---|---|
| `0x8003BC00` / `0x8003BC28` | buffers libpad puerto 1 / 2 (datos en `+2/+3`). Pad p1 activo-bajo `FFFF` en reposo; `FFDF`=→, `FF7F`=←, `7FDF`=→+□, `DFBF`=↓+○ (4 condiciones). |
| `0x80010F40` | `PadRead` (EXE, hoja). Devuelve `((~p2)<<16)\|~p1` con cada mitad **con bytes intercambiados** respecto al word SIO. |
| `0x8003FCF0` | sondeo de entrada (prólogo `addiu sp,sp,-0x20`, `jal 0x80010F40` en `0x8003FD00`). Llamadores `0x8003FCB4`, `0x800539C8`. **En combate se llama cada 2 frames** (hooks en frames 8267, 8269, 8271…). |
| `0x8003FE68` | remapeo de botones por puerto; `$a0` apunta al word de pad (slot de pila del llamador) y lo reescribe in situ según los modos de `0x8003BC70/72`. En la entrada, `*$a0` es el pad crudo. |
| Layout del word del juego | byte bajo (bits 0-7): L2 R2 L1 R1 △ ○ ✕ □; byte alto: SELECT L3 R3 START ↑ → ↓ ←. Observado: →+□ = `0x2080`. |

### 5.2 Plugin `dbfb.responsive` (`src/mods/dbfb_responsive.c`)
- Registro por constructor; ganchos en `0x8003FCF0` y `0x8003FE68` (también en
  `mod_function_entry_funcs` para los DLL). Cada gancho comprueba que la primera
  instrucción coincide con la observada (`0x27BDFFE0` / `0x27BDFFF8`) y que
  `$a0` es un puntero de RAM; si no, **desactiva solo su feature** y lo marca en
  la máscara de fallo de la cabecera del ring.
- Superficie de datos (sin logs): ring de 4096 registros × 32 B en memoria de
  Expansion 1 propiedad del plugin (primera asignación = `0x1F000000`), leído con
  el comando TCP existente `read_ram`. Cabecera: magic `DBFB`, versión, capacidad,
  tamaño de registro, cabeza, contador de VBlank, máscaras de feature/fallo.
  Registros: `VBLANK` (pad1/pad2 SIO + flancos de pulsación), `POLL`, `REMAP`
  (pad crudo), `BUFFER` (antes/después).

### 5.3 Features
| Feature | Canal | Escrituras | Estado |
|---|---|---|---|
| `trace` | developer | solo el ring propio (Expansion 1) | **Verificado en vivo**: magic correcto, flancos (START=`0x8FFF7`, →+□ = `0x80207FDF`), 429 `POLL`/429 `REMAP` en ~860 frames de combate. |
| `input-buffer` | experimental, opción `window` 1..6 (def. 2) | **4 bytes**: el word de pad en `*$a0` (dueño: este plugin; es un slot de pila recomputado en cada sondeo, por lo que desactivar la feature no deja estado que restaurar). Solo botones del byte bajo; nunca direcciones. | **Mecanismo verificado**: un toque de ○ (`0x20`, 1 sondeo) se reafirma en los 3 sondeos siguientes con `window=3`. **Efecto en el juego no evaluado**. Es un "hold-extend" del pad, no un buffer que re-genere flancos; no sabemos cómo el juego consume los flancos. |

Control **Original** (features fuera de `state.toml`): `read_ram 0x1F000000` →
`FF…` (bus abierto), sin ring, sin escrituras.
Cumplimiento de criterios 4.5 del handoff: Original sin escrituras ✔; escritura
de `Responsive` documentada (dirección/dueño/ancho/restauración) ✔; revisión
equivocada de exe/overlay → fail-closed por guarda de código ✔ (no ejercitado con
un exe distinto); hook fallido desactiva solo su feature ✔ (por inspección, no
ejercitado); entrada idéntica → traza idéntica **no probado**; matriz de humo con
la feature activa **no corrida**; netplay: **marcar offline-only** (modifica
entrada del invitado, sin contrato de serialización).

### 5.4 Qué NO se consiguió
- **Mapa de la estructura de luchador**: dos intentos diferenciales (instantáneas
  de RAM con →, ←, ataque) solo dieron punteros de heap. Sin evidencia no se
  declaró ningún offset. Por tanto el Tier 1 no incluye estado/animación/vida/ki/
  hit-stop. Siguiente vía: desensamblar los consumidores del word de pad dentro de
  `0x8003FCF0`/`0x8003FD7C…` (tabla en `0x80072548`) y los llamadores de
  `0x8003FCF0`.
- Tiers 3 y 4: no iniciados.
- Plugin no probado en `DBFinalBout_Recompiled_pgxp.exe` (compila y enlaza).

---

## 6. Cómo verificar

```bash
# 1. Coherencia offline (runtime ↔ recompilador ↔ caché)
python tools/verify_offline.py

# 2. Reconstruir recompilador y exe (secuencial: en paralelo falla el staging de mods/bundled)
cmake --build build-recompiler --target psxrecomp-game
cmake --build build-release --target psx-runtime
cmake --build build-release --target psx-runtime-pgxp

# 3. Cobertura STEP40 (con un combate en pantalla y el juego en --debug-port 4370)
python tools/step40_coverage_step.py      # añade fronteras con evidencia y recompila
#    cerrar el juego; borrar generaciones antiguas 0003E000_*/00060000_* del caché; sincronizar
#    game.toml con un build; python tools/verify_offline.py

# 4. Cuánto corre nativo (con el juego abierto)
python psxrecomp/tools/stall_report.py --port 4370 snap

# 5. Plugin: activar la feature en build-release/mods/state.toml
#    [[feature]] package_id="dbfb.responsive" id="trace" enabled=true
#    y leer el ring: read_ram addr=0x1F000000 len=131104 (magic 0x42464244 'DBFB')

# 6. Resumen de sesión
python tools/analyze_latest_session.py
```

---

## 7. Incógnitas y límites (resumen)
- Mitigación del freeze **no confirmada** (contador 0 en todas las pruebas tras el cambio).
- Causa última del freeze (temporización de IRQ) **no confirmada**.
- Caída de cobertura nativa desde el 2.º combate: **no investigada**.
- `fail-fast` del frame 8418: **no reproducido ni explicado**.
- Segundo combate: no reproducido el fallo previo; nada demuestra que esté arreglado.
- A4, A7, pausa/especiales/rematch/launcher, empaquetado y release: **no hechos**.
- Efecto de `input-buffer` en el combate **no evaluado**.
- Tiers 3–4 y mapa de luchador: **no hechos**.
- La campaña usó entradas pseudoaleatorias; "5 combates" no es garantía universal.

## 8. Siguientes pasos recomendados
1. Instrumentar por combate (`overlay_loader_status`) para explicar la caída
   nativa tras el 1.er combate (CRC por rango/regiones invalidadas).
2. Forzar la reproducción del freeze (3.ª transición) con la caché nativa y la
   build nueva para ejercitar `empty_irq_callback_returns`; a la vez comparar con
   Beetle (`find_first_divergence`) el momento de entrega del IRQ de CD.
3. Mapear luchadores desde los consumidores del pad (`0x8003FD7C…`).
4. Evaluar `input-buffer` con una traza de latencia (ring) antes de cualquier
   afirmación de mejora; decidir si es hold-extend o buffer real.
5. Decidir multi-región (EU+España code-identical; USA aparte).

## 9. Archivos sin commit (para preparar el commit)
Modificados por esta sesión: `CMakeLists.txt`, `game.toml`,
`tools/verify_offline.py`, `psxrecomp/runtime/src/dirty_ram_interp.c` (submódulo,
junto con los 3 archivos que ya estaban modificados allí).
Nuevos por esta sesión: `INFORME_CLAUDE.md`, `src/mods/dbfb_responsive.c`,
`mods/preloaded/packages/dbfb.responsive/0.1.0/manifest.toml`,
`tools/step40_coverage_step.py`.
Ya sin commit al empezar (no tocados por mí salvo lo indicado): `AGENTS.md`,
`PLAN_SOLUCION_CRASH_Y_COMBATE.md`, `README.md`, `README_ES.md`,
`RELEASE_NOTES_v0.1.1.md`, `scripts/package_setup_release.sh`, `summary.md`,
`tools/analyze_latest_session.py`, `HANDOFF_CLAUDE.md`, `MEMORY.md`, `github/`,
lanzadores `.bat`, `tools/_dump_*.py`.
No publicar: `build-release/overlay_captures*`, `psx_freeze_dump_*` (130 MB c/u),
cualquier captura con bytes de disco. `build-release/mods/state.toml` se dejó
como estaba al empezar.
