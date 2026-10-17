# Estabilidad del runtime: evidencia y entrega

Fecha: 2026-10-17. Alcance inicial: `psxrecomp/runtime`, sus pruebas y este
informe. Ampliación autorizada posterior: analizador de sesiones y sus pruebas
(§8). Revisión del framework al empezar: `f1ba368dbcf65a8463dad3db80830b174c2f1d5b`.

## Resultado

- **Dos defectos reproducidos y corregidos en la recuperación IRQ existente:**
  error de decodificación que se propaga al llamador y carga diferida que pisa
  un registro ya restaurado.
- **FAIL-FAST `0x2934`: mecanismo del runtime reproducido sin plugin.** La firma
  del incidente conservado es compatible con ese mecanismo. No se ha repetido
  la sesión histórica completa ni se ha exonerado al plugin.
- **Recuperación IRQ ejercitada por pruebas sintéticas**, incluidas las dos
  continuaciones `0x293C` y `0x2950`, restauración de registros y exclusiones.
  La causa original de la entrada en un callback borrado sigue abierta.
- **Caída de cobertura nativa: causa no demostrada con los artefactos revisados.**
  No procede alterar el emparejamiento CRC ni regenerar cachés por conjetura.
- Pruebas aisladas `-O0` y `-O2`: pasan. Verificación offline: pasa.
  **El arreglo está en el fuente; los ejecutables desplegados no se reconstruyeron.**

## 1. Cambios heredados comprobados

Antes de editar, `git -C psxrecomp status --short` mostraba únicamente:

```text
?? runtime/tests/test_irq_callback_recovery.c
?? runtime/tests/test_irq_callback_recovery.py
```

Por tanto esos dos archivos son trabajo heredado del agente cancelado. Se
revisaron y se continuaron; no se atribuyen como creados desde cero en esta
sesión. No había cambios pendientes en el fuente del runtime del submódulo.
El padre ya contenía numerosos cambios de otros trabajos.

## 2. Evidencia del FAIL-FAST conservado

Fuentes locales leídas:

1. `build-release/psx_last_run_report.json`, especialmente `reason`,
   `empty_irq_callback_returns`, `interp_unsupported`, `cpu`, `ram_peeks`,
   `overlay_loader` y `unknown_dispatch_tail`.
2. `build-release/psx_freeze_dump_psx-runtime_1791067602_0.json`, cabecera y
   estado final de CPU: mismo frame y mismos registros que el reporte.
3. `build-release/psx_freeze_heartbeat.json`: sesión posterior, no el mismo fallo.

| Campo del incidente | Valor |
|---|---|
| Fecha del reporte | `2026-10-03T22:46:42Z` |
| Build identificada en el reporte | `nightly-157-g7d70880d-dirty (Sep 26 2026 20:07:11)` |
| Frame | `8418` |
| Dirección rechazada | `0x00002934` |
| `ra` / `s1` / `sp` | `0x293C` / `0x1F6C` / `0x8548` |
| `empty_irq_callback_returns` | **`1`**, también en el freeze dump |
| `interp_unsupported.midblock_count` | `0` |
| Última RI diagnóstica | `(none)`, PC e instrucción `0` |
| `Cause` / `EPC` / `SR` | `0x400` / `0x80041E78` / `0x40020404` |
| `I_STAT` / `I_MASK` en el dump | `0x4` / `0xD` |
| `unknown_dispatch_tail.total` | `1` |

El peek alrededor de `ra` contiene la instrucción `0x0220F809` en `0x2934`:
`jalr ra,s1`, seguida de NOP. Es una instrucción válida; `s1` identifica el
callback `0x1F6C`. El reporte no demuestra una instrucción inválida en `0x2934`.

**Corrección documental para integrar en el roadmap:** la afirmación de que el
contador nunca salió de cero no describe este incidente. Sí salió: el dump del
fallo y el reporte final registran una recuperación. Eso no demuestra que la
mitigación fuese correcta; precisamente el retorno de esa recuperación tenía un
defecto.

El heartbeat posterior tiene `wall_clock_epoch=1791068527`, frame `10603`,
`fatal=null` y contador `0`. No debe combinarse con el reporte del frame `8418`
para declarar una sesión limpia. Antes de la corrección de §8,
`analyze_latest_session.py` imprimía ambos sin correlacionar sus sesiones.

### Mecanismo demostrado

En `dirty_ram_interp.c`:

1. `abort_unsupported()` activa el estado interno compartido
   `g_unsupported_seen`.
2. Un `jalr ra,s1` interpretado puede ejecutar el callback mediante
   `dispatch_nonlocal_call()` → `psx_dispatch_call()` → nuevo
   `dirty_ram_dispatch()`.
3. La recuperación existente devuelve `v0=0` y el PC de continuación, pero no
   consumía el indicador de error interno.
4. Al volver al `exec_one` del llamador, su bucle veía todavía ese indicador.
   Si el JALR era la primera instrucción del bloque, devolvía `0` («no manejado»)
   aunque el callback ya se había recuperado. Es la forma que conduce al
   rechazo de una instrucción válida como `0x2934`, sin registrar una RI
   mid-block. Con un prefijo en el bloque, también podía atribuir el fallo del
   callback al llamador.

La prueba reproduce esa ruta con el **intérprete de producción**, memoria
sintética y una adaptación mínima de `psx_dispatch_call` que exige PC de retorno
y SP correctos. No enlaza el plugin, el juego ni el dispatcher generado completo.

**Límite:** el emisor, intérprete y otros componentes cambiaron desde el
incidente. El decodificador actual trata `0x000900FF` como un SPECIAL indefinido
ignorado (`exec_one_fetched_inner`, rama `default` de SPECIAL); ya no dispara la
recuperación como describía el informe antiguo. Las pruebas usan el opcode
realmente no soportado `0xFC000000` para ejercitar la rama actual y verifican por
separado que `0x000900FF` no la activa. No se cambió esa política de SPECIAL ni se
presenta el caso sintético como reproducción exacta del juego o validación de
fidelidad contra hardware/Beetle.

## 3. Restauración de registros IRQ

El epílogo `OV_FPLOG_RET1` drena las cargas pendientes. Antes del arreglo, la
recuperación restauraba `s0-s7/gp/sp/fp` y **después** llegaba a ese drenaje.
Un `lb s0,0(zero)` inmediatamente anterior al opcode no soportado dejaba una
escritura pendiente: el epílogo sustituía el `s0` restaurado por el byte leído.

Prueba negativa antes del arreglo: `s0` final `0x7F` en lugar de `0xA010` para
ambas continuaciones. Tras el arreglo: `s0=0xA010` en ambas, y restauración de
todos los registros guardados comprobada tras haberlos modificado.

Cambio aplicado en `runtime/src/dirty_ram_interp.c`, solo dentro de la rama de
recuperación ya existente:

- drenar la carga pendiente **antes** de restaurar los registros;
- limpiar `g_unsupported_seen` al consumir la recuperación.

Las condiciones de admisión de la mitigación no se ampliaron. Las pruebas
comprueban que una escritura ejecutada, un retorno ajeno al walker o una entrada
fuera de la ventana siguen tomando la excepción ordinaria con `ExcCode=10` y
EPC exacto. Una instrucción no soportada al principio sigue devolviendo «no
manejado». En la recuperación, COP0 conserva SR/Cause/EPC.

Esta reparación del retorno **no demuestra** la causa de la IRQ original, ni
que la heurística previa de callback vacío modele el hardware correctamente.
El dump anterior `psx_freeze_dump_psx-runtime_1791064831_0.json` sigue siendo
evidencia del problema previo: frame `18369`, contador `0`, `Cause=0x428`,
`EPC=0x2030`, `s1=0x1F6C`, `I_STAT=4`.

## 4. Caída nativa desde combates posteriores

La tabla de `INFORME_CLAUDE.md §4.4` permite afinar la descripción del roadmap:

| Combate | Nativos | Interpretados | Fracción nativa de esos despachos |
|---|---:|---:|---:|
| Goku | 1.976.627 | 86.861 | 95,8 % |
| Trunks | 148.607 | 126.898 | 53,9 % |
| Piccolo | 9.819 | 138.921 | 6,6 % |
| Pan | 9.012 | 129.697 | 6,5 % |
| Cell | 9.005 | 128.944 | 6,5 % |

La degradación empieza en el segundo, pero esa tabla sitúa el ~7 % desde el
tercero. Es fracción de **despachos**, no porcentaje de instrucciones ni de
tiempo. Las cifras proceden del informe histórico, no de una sesión nueva.

En los artefactos actuales revisados no hay la secuencia de
`overlay_loader_status` / `overlay_candidates` por combate que permita decidir
qué variante, rango o política rechazó el código. El reporte del FAIL-FAST tiene
684.176 despachos nativos y 2.421.119 interpretados **acumulados**, 334 entradas
registradas, 5 cargas y cero invalidaciones/revalidaciones/stale-blocked. Esos
totales de otra sesión no prueban la causa de la campaña de cinco combates.
Los freeze dumps revisados guardan trazas y estado de CPU, no una serie de CRC
por candidato antes/después de cada pelea.

Inspección del cargador actual:

- `ov_ranges_crc()` / `cand_live_crc()` validan los **rangos del manifiesto por
  función**, no indiscriminadamente todo el archivo del overlay.
- `overlay_loader_dispatch_seg()` compara generación de páginas y CRC;
  reintenta candidatos invalidados cuando cambia la generación. Un match de
  vuelta puede incrementar `revalidations`.
- El segmento de ejecución también debe coincidir con el de la DLL. Hay otros
  motivos de fallback, incluidos los modos de verificación y bloqueo existentes.
- Ya existen `overlay_loader_status` y `overlay_candidates` con consulta `pc` y
  `lazy`, que exponen hashes, generaciones y estado. No se necesita añadir logs
  ad-hoc para empezar a atribuir la caída.

Por ello no se ha cambiado el cargador por la hipótesis de «cambiaron páginas
de datos». Hacen falta los rangos/CRC concretos que dejaron de emparejar.
Tampoco basta con contar DLL: la verificación offline confirma coherencia de
namespaces y archivos, no emparejamiento del segundo combate en vivo.

## 5. Pruebas y comandos ejecutados

Directorio de trabajo de los comandos, salvo indicación:
`C:\Users\javie\Desktop\PROYECTOS IA\DBFinalBoutRecomp`.
Compilador existente: `C:\msys64\mingw64\bin\gcc.exe`.

Preparación de las pruebas aisladas:

```powershell
$env:PATH = "C:\msys64\mingw64\bin;" + $env:PATH
$env:PYTHONDONTWRITEBYTECODE = "1"
```

Se verificó con `Test-Path` el padre temporal aprobado y se crearon directorios
vacíos distintos. Ningún artefacto de prueba se borró.

### Prueba negativa antes de editar el runtime

```powershell
python psxrecomp/runtime/tests/test_irq_callback_recovery.py --cc "C:\msys64\mingw64\bin\gcc.exe" --out-dir "C:\Users\javie\AppData\Local\Temp\opencode\dbfb-estabilidad-baseline4-20261017"
```

**FALLÓ** (`-O0`, salida 1): cinco comprobaciones, incluyendo las dos
restauraciones de `s0` y el manejo/continuación del JALR válido. No se llegó a
`-O2` porque el runner se detiene ante el primer fallo. Este ensayo ya usaba el
opcode sintético `0xFC000000`. Los ensayos exploratorios anteriores detectaron
problemas de la prueba heredada (SPECIAL ahora ignorado y dependencias de
widescreen de ADDIU); se corrigió la prueba antes de atribuir fallos al runtime.

### Prueba final del arreglo

```powershell
python psxrecomp/runtime/tests/test_irq_callback_recovery.py --cc "C:\msys64\mingw64\bin\gcc.exe" --out-dir "C:\Users\javie\AppData\Local\Temp\opencode\dbfb-estabilidad-final-20261017"
```

**PASA**, salida 0: `-O0` y `-O2`. Trece escenarios por optimización:
cuatro recuperaciones directas, cuatro llamadas JALR anidadas (dos sitios, con
y sin prefijo), control del SPECIAL histórico, tres exclusiones y rechazo de
una primera instrucción no soportada. Enlaza `dirty_ram_interp.c` de producción
con `PSX_HAS_GAME_DISPATCH` y `PSX_NO_DEBUG_TOOLS`. No valida temporización de
dispositivos ni la integración completa del juego.

También se ejecutó directamente `fixtureO0.exe` de ese directorio: salida 0;
cuatro recuperaciones directas y cuatro anidadas con contador +1 por caso,
retornos correctos y `s0=0xA010` en los casos con carga pendiente.

### Regresión de continuaciones de texto rechazado

Se reutilizó la prueba existente mediante su helper, conservando sus artefactos
en vez de usar el wrapper que limpia automáticamente un directorio temporal:

```powershell
python -c "import sys; from pathlib import Path; sys.path.insert(0, 'psxrecomp/runtime/tests'); from fixture_link import build_and_run; here = Path('psxrecomp/runtime/tests').resolve(); out = Path(r'C:\Users\javie\AppData\Local\Temp\opencode\dbfb-estabilidad-continuaciones-20261017'); [build_and_run(r'C:\msys64\mingw64\bin\gcc.exe', here, here.parent, opt, out, ['dirty_ram_interp.c'], 'test_interp_refused_game_text.c', defines=('PSX_HAS_GAME_DISPATCH', 'PSX_NO_DEBUG_TOOLS')) for opt in ('-O0', '-O2')]; print('PASS: refused game text O0/O2; artifacts preserved')"
```

**PASA**, salida 0, `-O0/-O2`: interpretación hasta una continuación aceptada y
entrega de control al salir a una página limpia fuera del texto.

### Comprobaciones auxiliares

| Comando | Resultado |
|---|---|
| `python tools/analyze_latest_session.py` | Salida 0. Expone el fallo histórico y los contadores distintos del heartbeat posterior; no es una prueba de estabilidad. |
| `python tools/verify_offline.py` | **PASA**, salida 0: configuración idéntica (14.564 bytes), codegen `1b6950cb`, 1117 DLL con `.ranges` en `cg18_1b6950cb_gc101f51f1_f0`, runtimes normal/PGXP presentes. |
| `git diff --check` dentro de `psxrecomp` | Salida 0; solo aviso de conversión LF/CRLF. |

## 6. Archivos de esta entrega

1. `psxrecomp/runtime/src/dirty_ram_interp.c`: reparación del epílogo de recuperación.
2. `psxrecomp/runtime/tests/test_irq_callback_recovery.c`: prueba heredada corregida
   y ampliada, usando instrucciones sintéticas y exclusiones comprobadas.
3. `psxrecomp/runtime/tests/test_irq_callback_recovery.py`: runner heredado validado,
   conservado sin cambios en su contenido; forma parte de la entrega sin seguimiento.
4. `ESTABILIDAD_EVIDENCIA.md`: este informe para integrar los resultados en el roadmap.

## 7. Pendientes reales y criterio de cierre

- Integrar el arreglo en una build posterior autorizada y repetir la secuencia
  problemática con/sin `trace`. Hoy no hay prueba en juego de estos fuentes.
- Comparar la primera divergencia con Beetle para determinar por qué se entra en
  el callback borrado. No se ha demostrado un error concreto de entrega de IRQ.
- Para el primer, segundo y tercer combate, conservar muestras delimitadas por
  frame de `overlay_loader_status` y de `overlay_candidates` sobre los PCs que
  pasan a interpretarse. Comparar diferencias de contadores, segmento, CRC vivo
  y esperado, rangos y generación. Solo entonces corregir una causa demostrada.
- Mantener abiertos los puntos P1.1/P1.2/P1.3 del roadmap en lo que requiere
  validación integral; P1.3 sí tiene ahora cobertura automatizada del retorno y
  P1.1 un defecto interno aislado y reparado.

En la entrega inicial no se ejecutaron el juego, Beetle, un build general,
instalaciones, commits, pushes ni borrados. No se editaron plugin, configuración,
`CMakeLists.txt`, herramientas del padre ni código generado. La ampliación
autorizada de herramientas del padre se detalla a continuación.

## 8. Ampliación: análisis de artefactos sin mezclar sesiones

Encargo adicional autorizado: corregir `tools/analyze_latest_session.py`, crear
`tools/tests/test_session_analysis.py` y actualizar únicamente este informe.
No se hicieron nuevas ediciones en el runtime ni sus pruebas.

### Esquema real y política de relación

Se contrastaron los JSON locales y sus serializadores actuales:

- `crash_trace.c`: reporte con `timestamp` ISO-8601 UTC, `frame`, `build`,
  `reason`, `exit_origin`, `unknown_dispatch_tail.total` e
  `interp_unsupported.midblock_count`. No registra el contador de dumps
  automáticos del heartbeat.
- `freeze_heartbeat.c`: heartbeat con `wall_clock_epoch`, `frame_count`,
  `fatal`, `automatic_freeze_dumps`, `failed_freeze_dumps` y
  `suppressed_freeze_events`. No registra `build`, el total de despachos
  desconocidos ni el total de RI mid-block del reporte.
- No hay un identificador compartido de proceso/sesión en esos esquemas.
  Un fatal puede seguir generando heartbeats mientras el proceso permanece
  detenido sirviendo diagnóstico. El frame del invitado también puede retroceder.

El analizador conserva ahora dos bloques independientes, `report` y `heartbeat`,
con sus metadatos, métricas, errores y evidencia ausente. En texto cada dato
lleva el prefijo de su fuente; en JSON los valores ausentes son `null`.
No convierte ausencia en cero ni hereda el fatal o los contadores del otro
artefacto. `reason=atexit` solo indica ausencia de un motivo fatal registrado,
no certifica un cierre correcto ni una sesión validada.

La relación es:

- **`unknown`** si falta algún artefacto o no hay prueba de identidad. Ni siquiera
  hora/frame/build coincidentes bastan para confirmar la misma sesión.
- **`different`** ante contradicciones observables: builds distintas cuando
  ambas constan, reinicio de contadores de proceso en una observación posterior,
  o desaparición de un estado fatal previamente registrado. La ordenación por
  hora admite la resolución de un segundo de los serializadores.

No se usan la fecha de modificación de archivos ni una estimación de FPS para
inventar una sesión. Las capturas conservan su resumen de regiones/raíces pero
quedan sin atribución de sesión. Los dumps se enumeran por nombre de archivo,
sin leer los volcados grandes: su presencia histórica **no** se suma a los dumps
automáticos del heartbeat ni se atribuye al reporte.

### CLI y modo estricto

```powershell
python tools/analyze_latest_session.py
python tools/analyze_latest_session.py --directory build-release --json
python tools/analyze_latest_session.py --directory build-release --strict
```

Sin argumentos sigue inspeccionando `build-release` sin arrancar nada. Se
conservan los datos útiles de overlays, capturas y recuperación IRQ.

- Inspección normal: salida **0** aunque muestre incidentes históricos; ese
  código significa que la lectura fue correcta, no que el juego sea estable.
- `--strict`: salida **1** si hay incidentes o evidencia insuficiente.
- JSON/esquema inválido o directorio incorrecto: salida **2**, no aprobación.
  Los errores de artefactos se incluyen en el resumen; los argumentos inválidos
  usan el error normal de CLI.

Para aprobar en estricto se exige un reporte final autocontenido con fecha,
build, frame positivo y evidencia propia de fatal/unknown-dispatch/mid-block/dumps
sin incidentes. No se unen los contadores complementarios de dos artefactos sin
identidad compartida. Un reporte importado que contenga explícitamente toda esa
evidencia puede aprobar; los esquemas desplegados actuales no la aportan por sí
solos. Esto es un límite deliberado del diagnóstico, no un test fallido del juego.

### Resultado sobre los artefactos actuales

`--directory build-release --strict` identifica **`session_relation=different`**:

| Fuente | Fatal | Unknown dispatch | Mid-block | Dumps automáticos | Recuperación IRQ |
|---|---|---|---|---|---|
| Reporte, frame 8418 | sí | 1 | 0 | desconocido | 1 |
| Heartbeat, frame 10603 | no | desconocido | desconocido | 0 | 0 |

Evidencias de separación: `process_counter_reset:empty_irq_callback_returns` y
`fatal_state_cleared`. Se enumeran **55** archivos de dump con relación de
sesión desconocida. No se etiquetan como 55 fallos de la última ejecución.
El modo estricto devuelve **1**, como corresponde; no declara limpia la sesión.

### Pruebas ejecutadas y archivos

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m unittest discover -s tools/tests -p test_session_analysis.py -v
python tools/analyze_latest_session.py --directory build-release --json --strict
python tools/analyze_latest_session.py --directory build-release --strict
git diff --check -- tools/analyze_latest_session.py tools/tests/test_session_analysis.py ESTABILIDAD_EVIDENCIA.md
```

- **27 pruebas pasan**: incidente real en esquema sintético, metadatos ambiguos,
  builds distintas, heartbeat posterior a fatal detenido, orden temporal inverso,
  artefactos faltantes/vacíos, contadores ausentes o inválidos, RI y dumps de cada
  fuente, JSON corrupto/no finito, hora sin zona, capturas, inventario histórico,
  aprobación solo con evidencia autocontenida y CLI real por subproceso.
- Los tests verifican también que los archivos de entrada permanecen idénticos.
  Los fixtures se conservan en `TEMP/opencode/dbfb-session-analysis-*`.
- CLI sobre artefactos reales: lectura correcta, relación `different`,
  rechazo estricto esperado. La salida JSON y la textual mantienen las fuentes
  separadas.
- `git diff --check`: pasa.

Archivos de esta ampliación: `tools/analyze_latest_session.py`,
`tools/tests/test_session_analysis.py` y `ESTABILIDAD_EVIDENCIA.md`.
Para confirmar positivamente la identidad de dos artefactos haría falta
evidencia compartida que los serializadores actuales no producen. No se amplió
el runtime para crearla. Los pendientes de estabilidad en juego de §7 continúan
abiertos; no se ejecutaron juego ni builds generales en esta ampliación.
