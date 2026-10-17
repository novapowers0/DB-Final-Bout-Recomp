# Combate Responsive: implementación y evidencia

Fecha: 2026-10-17. Alcance exclusivo: plugin, su paquete y pruebas propias.

## Resultado y estado del roadmap

Se sustituyó el antiguo «buffer», que solamente prolongaba botones leídos por el
juego, por **dos comportamientos explícitos y excluyentes**:

- **`buffer`**: captura flancos físicos observados en VBlank entre sondeos del
  juego y entrega un toque pendiente una sola vez. No prolonga una pulsación que
  el sondeo ya recibió. Funciona con `trace` desactivado.
- **`hold`**: experimento separado de retención, con duración máxima desde el
  flanco del sondeo original. Una pulsación larga no acumula tiempo para después
  de soltarla. No recupera toques que los sondeos originales nunca observaron.
- **`original`**: el plugin de entrada no lee memoria del invitado, no escribe,
  no reserva memoria y no consulta el mando. Desactivar ambas features es el
  control Original completo. Activar `trace` explícitamente añade únicamente
  observación y escrituras en su memoria de diagnóstico.

Ambas features siguen **desactivadas por defecto**. `trace` conserva el canal
`developer`; la asistencia es `experimental` y **solo offline**. No se afirma
mejor sensación de combate: esta sesión no abrió el juego.

| Apartado del roadmap de combate | Resultado real |
|---|---|
| Instrumentación de entrada | Ampliada con salidas de flancos reales del sondeo original. |
| Vida, ki, animación, hit-stop y estructura de luchador | Sin mapa verificado. Tier 1 sigue parcial. |
| Capa de entrada | Implementada y probada como buffer entre sondeos; retención separada. Tier 2 acotado. |
| Balance, recuperación, cámara, reglas y modo alternativo | No implementados: faltan estados y costuras verificadas. Tiers 3–4 abiertos. |
| Original | Cero accesos/escrituras/reservas por el plugin de entrada; prueba A/B sintética. |
| Netplay | Rechazo efectivo en callbacks, incluido resimulado. Sin contrato de serialización. |
| Cierre global / validación en combate | Pendiente: requiere build integrado y prueba real dirigida. |

Por tanto, este trabajo **no cierra todo `ROADMAP.md`** ni la matriz del handoff.

## Fuentes y comprobación estática

Se leyeron `AGENTS.md`, `MEMORY.md`, `HANDOFF_CLAUDE.md`,
`PLAN_SOLUCION_CRASH_Y_COMBATE.md`, `INFORME_CLAUDE.md`, `ROADMAP.md`, las APIs y
el registro actual de plugins del framework, y:

`..\DB Final Bout\tools\psxrecomp\docs\FINAL_BOUT_RESPONSIVE_ARCHITECTURE.md`.

Se cargó la skill `reverse-engineer-anything`. `rea doctor --client opencode
--json` encontró registro ausente y ningún motor nativo configurado en REA.
No se instaló ni reconfiguró nada. Las observaciones nuevas proceden de **lectura
estática local y decodificación acotada de instrucciones MIPS**, no de una
decompilación REA ni de observación nueva del juego.

Artefactos privados usados solamente en lectura:

| Artefacto | SHA-256 |
|---|---|
| `build-release/vault/overlay_captures.json` | `9eccbe8e5dc888dad689ccbeaf795be930217b63bfbc09f90cf2a5e9e2e65002` |
| `disc/SLUS_004.93` | `507f132cdcbb635bbbf7a75e15c62a9d0d51e22ce4432828da784ec03b67cbcc` |

El vault contiene **distintos contenidos en las mismas direcciones**: se encontró
una tabla de datos y otro código en `0x800539C8`, además del `jal` de combate.
La dirección o un prólogo aislado no bastan. Los guardas comprueban:

| Ventana verificada | Tamaño | FNV-1a 32, bytes little-endian |
|---|---:|---|
| Sondeo + remapeo completos, `0x8003FCF0..0x8003FF84` exclusivo | `0x294` | `829BEBD2` |
| `PadRead`, `0x80010F40..0x8001104C` exclusivo | `0x10C` | `C4EF2A99` |
| Identificador del llamador de combate, `0x800539A8..0x800539D0` exclusivo | `0x28` | `2B7A4598` |

Además se comprueban el `jal` en `0x8003FCB4` y su delay slot que pone `$a0=0`.
Son guardas de coincidencia accidental/revisión de estas **costuras de código**,
no una firma criptográfica de todo el disco o EXE. Un parche fuera de estas
ventanas no queda identificado por ellas.

### Datos confirmados del consumidor de entrada

La secuencia después del remapeo carga el pad anterior de `0x1F800004` y calcula:

```text
pressed  = current & ~previous
released = previous & ~current
changed  = pressed | released
previous = current
```

Las direcciones de las escrituras son:

| Dirección | Dato producido por este sondeo | Evidencia estática |
|---|---|---|
| `0x800A9CE8` | Flancos de pulsación, word de dos puertos | `sw` en `0x8003FE34` |
| `0x800AA198` | Flancos de liberación | `sw` en `0x8003FE40` |
| `0x800A9F30` | Unión de ambos | `sw` en `0x8003FE48` |
| `0x1F800004` | Pad anterior para el siguiente sondeo | `sw` en `0x8003FE50` |

Importante: los offsets `0x9CE8`, `0xA198` y `0x9F30` son **con signo** al sumar
al `lui 0x800B`. No son direcciones `0x800B9CE8` / `0x800BA198` / `0x800B9F30`.

Esto verifica un consumidor de **entrada**, no que un luchador haya aceptado
un ataque. `trace` lee los dos primeros words en la entrada del siguiente
sondeo: son los valores visibles del sondeo anterior.

El bloque con la tabla `0x80072548` se salta cuando el argumento original es 0
(`beq s0,zero` en `0x8003FD6C` hacia `0x8003FE1C`). Sus operaciones sobre bits
direccionales y bytes por puerto pertenecen al tratamiento de entrada. Esta
tabla **no demuestra** una estructura de luchador, ni vida, ki o recuperación.
Los guardas restringen la asistencia a la ruta observada con `$a0=0`.

`PadRead` también verifica estado de libpad y tipo de dispositivo. La nueva
asistencia se limita al camino digital: estado 0 e identificador cuyo nibble
alto es 4. Protocolos no verificados y puertos desconectados conservan la entrada
original y descartan su cola. El intercambio de puertos usa el byte verificado
`0x8003BC7E`, antes del remapeo.

## Puertas, duración y reinicios

La asistencia solamente puede escribir después de:

1. Juego iniciado y `psx_netplay_active()==0`, sin resimulado.
2. Coincidencia de las ventanas de código anteriores.
3. Entrada a `0x8003FCF0` desde el retorno `0x8003FCBC`, `$a0=0`, pila válida.
   El sondeo de inicialización que retorna a `0x800539D0` no autoriza asistencia.
4. Entrada al remapeador desde `0x8003FD64`, durante el mismo VBlank del sondeo,
   con `$a0 == SP_del_sondeo - 0x10` y `$sp == SP_del_sondeo - 0x20`.
5. Slot alineado de RAM real de 2 MiB, dispositivo digital preparado y ausencia
   de START/SELECT. No se aceptan mirrors fuera de esos 2 MiB, scratchpad,
   Expansion 1 ni un puntero arbitrario aunque apunte a RAM.

Cada autorización se consume una vez. Un remapeo aislado, tardío o duplicado no
inyecta. Más de dos VBlanks sin el sondeo observado descartan la cola. Esta es
una puerta basada en **la ruta de combate verificada**, no en un estado global
inventado. No está demostrado que cubra todos los modos y fases del juego.

`window` ahora significa **VBlanks del invitado**, 1–6, default 2, incluyendo el
instante de captura. Un evento de edad `>= window` expira. Ya no significa los
«extra polls» del prototipo anterior: el cambio está indicado en la opción.

En `buffer`, una tecla ya presente en el word original consume su pendiente sin
escritura. Un toque recuperado se entrega una vez; si el último word entregado
ya tenía ese bit, debe existir un sondeo de liberación antes de reinyectar. Se
mantiene como máximo un pendiente por botón y puerto; toques repetidos del mismo
botón pueden agruparse. No es una cola FIFO de comandos. Las direcciones son las
actuales del sondeo; no se conserva la dirección asociada al toque antiguo.

La cola se vacía al perder el contexto/código, cambiar de puerto, restaurar un
estado, cambiar una opción en vivo o activar de nuevo la feature. El framework
retira sus callbacks al desactivarla; no ofrece callback de desactivación. El
estado host que pueda permanecer inerte se limpia antes de la siguiente
activación. No hay restauración diferida que pueda escribir al estar apagada.

**Pausa, límite deliberado:** no hay flag de pausa confirmado. Observar START o
SELECT suspende la asistencia hasta abandonar el contexto de código o una nueva
activación. Soltar el botón no se interpreta como «reanudar». Si la pausa mantiene
el mismo código residente, la asistencia puede permanecer suspendida el resto
de esa pelea. Es preferible a inyectar botones en una pantalla no identificada.
No sustituye la verificación dirigida de pausa y transiciones en el juego real.

## Contrato de escritura

| Dueño del dato | Dirección | Ancho | Restauración |
|---|---|---:|---|
| Juego, slot temporal de entrada; plugin modifica solo este consumo | `$a0`, validado como `SP_del_sondeo - 0x10` | 4 bytes | El sondeo original vuelve a producirlo desde `PadRead` en cada llamada. No se conserva puntero para escribir después. |
| Plugin `trace`, memoria Expansion 1 propia | Dirección devuelta por `psx_mod_alloc_guest_memory` | Words de 4 bytes | No es estado de gameplay; se reserva solo tras un sondeo offline verificado. |

Solo se añaden bits `0x00FF` en cada mitad del word: botones de cara y hombros.
No se altera ningún registro del CPU, instrucción, dirección, START/SELECT,
timer, daño, estado de luchador, animación ni dato de balance.

Las features poseen sus propios callbacks. Esto corrige la dependencia anterior:
los hooks registrados únicamente bajo `trace` no pertenecían al plan cuando
solo se activaba `input-buffer`. El framework actual ejecuta únicamente hooks
del plan resuelto; no se reutilizan flags host de «feature activa» entre planes.

## Diagnóstico disponible

`trace` conserva un ring de 4096 registros de 32 bytes. Cabecera de ocho words:

```text
magic=0x42464244, version=2, capacity=4096, record_bytes=32,
head, VBlanks_del_trace, feature_mask=1, reserved=0
```

El contador es relativo a la activación del trace y se recupera de su cabecera
al restaurar ese ring; no es un número absoluto de frame del emulador.

Cada registro contiene `frame, kind, a, b, c, d, e, f`:

| Kind | Datos |
|---|---|
| 1 `VBLANK` | `a/b`: pad SIO crudo por puerto en bits 0–15 y flancos físicos en 16–31. |
| 2 `POLL` | `a`: PC; `b`: RA; `c`: argumento; `d`: SP; `e/f`: últimos words visibles en `0x800A9CE8` / `0x800AA198`. |
| 3 `REMAP` | `a`: PC; `b`: RA; `c`: slot; `d`: word observado; `e`: pad anterior de scratchpad; `f`: candidato de flanco `d & ~e` antes del remapeo. |

Si ambos plugins están activos, el word observado por el trace puede ser anterior
o posterior a la inyección según el orden del plan. El candidato de flanco no
es la salida final del remapeador ni una confirmación de ataque. La entrada
efectiva resultante de la asistencia es independiente de ese orden, probado en C.

El ring v2 no usa el antiguo kind 4 `BUFFER`. Las inyecciones se cuentan mediante
el comando TCP existente `mod_counters`:

- `dbfb.responsive.captured_button`
- `dbfb.responsive.delivered_button`
- `dbfb.responsive.delivery_age_vblanks` — suma de edades de entrega por botón.
- `dbfb.responsive.buffer_write` / `dbfb.responsive.hold_write`
- `dbfb.responsive.rejected_remap`
- `dbfb.responsive.code_mismatch`
- `dbfb.responsive.invalid_option`
- `dbfb.responsive.trace_allocation_failed`

Sin `trace`, la asistencia no reserva Expansion 1 ni escribe un ring. Al cargar
un estado con ring válido se recuperan cabeza y reloj sin reservar otro ring.
Un fallo de reserva del trace no desactiva la asistencia de entrada.

## Pruebas ejecutadas

Desde la raíz del proyecto, PowerShell:

```powershell
$env:CC = 'C:\msys64\mingw64\bin\gcc.exe'
python -B tools/tests/test_responsive.py
python -B tools/tests/test_responsive_evidence.py --inspect
python tools/verify_offline.py
```

Resultado final:

- GCC **16.2.0**, compilación `-std=c11 -O2 -Wall -Wextra -Werror`: pasa.
- **2 pruebas Python**, incluida compilación/enlace y ejecución del C real:
  **OK**. El plugin se compila como unidad separada, sin reemplazar sus funciones
  internas por una implementación Python.
- **17 grupos de escenarios C: todos pasan**. Cubren constructor sin efectos,
  Original, captura y consumo único sin trace, entrada visible sin duplicación,
  los 32 bits de ambos puertos, swap, vencimiento 1–6, liberación antes de
  re-disparo, hold finito y pulsación larga, timeout/rutas desconocidas, código
  cambiado incluso después del poll, punteros y pila inválidos, online/resimulado/
  pregame, START/SELECT/restore/desactivación, dispositivos no preparados,
  opciones inválidas y cambios en vivo, ring inicializado y circular, diez
  restauraciones sin reserva extra, fallo aislado de trace, paridad A/B de
  Original y repetibilidad de una secuencia de 160 VBlanks.
- La comparación A/B usa `memcmp` byte a byte sobre memoria de 2 MiB, secuencia
  de words entregados y, en repetición con trace, memoria del ring; todos los
  hooks comprueban también que los registros CPU no cambien. Se prueban ambos órdenes de hooks
  y la asistencia sola. No es una comparación de una partida ejecutada por PSX.
- La prueba detectó el caso START coincidiendo con el primer sondeo perdido;
  se corrigió y el escenario pasa con la suspensión conservadora.
- `verify_offline.py`: **OFFLINE VERIFICATION PASSED**, codegen `1b6950cb`,
  1117 DLLs con rangos, configuraciones fuente/desplegada idénticas, ambos
  runtimes existentes. Comprueba la build previa; no compila este nuevo plugin.

Último binario del harness conservado:

`C:\Users\javie\AppData\Local\Temp\opencode\dbfb-responsive-9_m9uje3\test_responsive.exe`.

El harness simula exclusivamente servicios del runtime: memoria, mandos,
opciones, registro/selección de plugins y sesión. Usa headers reales del
framework y el C de producción. **No ejecuta el motor MIPS ni prueba el launcher
o el resolver del framework de extremo a extremo.**

Las ventanas privadas de código se leen de los artefactos existentes y se pasan
por stdin en binario; no se guardan fixtures de disco. Sin esos artefactos la
prueba C se indica como **skipped**, no como validación del plugin. Se pueden
indicar `DBFB_RESPONSIVE_CAPTURE`, `DBFB_RESPONSIVE_EXE` y `CC`. Las salidas de
compilación se conservan en una carpeta temporal nueva; no se borran datos.

## Archivos de esta entrega

1. `src/mods/dbfb_responsive.c` — implementación, puertas y diagnóstico.
2. `mods/preloaded/packages/dbfb.responsive/0.1.0/manifest.toml` — modos claros,
   unidades coherentes, default-off, descripción offline y límite de pausa.
3. `tools/tests/test_responsive.py` — validación de manifiesto y driver de GCC.
4. `tools/tests/test_responsive_harness.c` — escenarios contra el C real.
5. `tools/tests/test_responsive_evidence.py` — inspección estática reproducible.
6. `COMBATE_EVIDENCIA.md` — este informe exclusivo.

No se modificaron el runtime/framework, `game.toml`, `CMakeLists.txt`, código
generado ni documentos compartidos. No se abrió el juego, no hubo build global,
instalaciones, publicaciones, commits, push ni borrado de datos.

## Bloqueos y siguiente evidencia necesaria

- Mapear el consumidor **de los flancos de entrada** hasta una transición de
  acción de un luchador, con fuente, ancho, identidad de estructura y estado.
  Las direcciones de entrada anteriores son un punto de partida comprobado,
  no sustituyen ese mapa.
- Medir con una nueva build integrada Original vs buffer vs hold en una secuencia
  dirigida, incluidos dos combates, pausa, especiales, vuelo y rematch. Comprobar
  que los dos hooks llegan también por los overlays nativos de esa build.
- Confirmar un estado real de pausa/round/transición antes de relajar la puerta
  conservadora. Cobertura de todos los modos y otras revisiones: no confirmada.
- Vida/ki, animación, timers, golpe registrado, hit-stop, recuperación, cámara y
  geometría de impacto siguen sin mapa reproducible en el material analizado.
  No se introducen offsets, estados ni balance arbitrario para aparentar tiers
  completos.
- No se atribuye a este cambio la solución del `0x2934`, los freezes de IRQ,
  sombras o pérdida de cobertura nativa del segundo combate. Esos apartados
  requieren su propia evidencia y quedan fuera de estos archivos exclusivos.
