# Combate Responsive: implementación y evidencia

## Estado vigente — R0 posterior a release (2026-10-19)

Ver `R0_ESTABILIDAD.md` y roadmap §10/§11. Espera bloqueante de trabajadores
tras DONE corregida, publicada en **v0.2.1** y probada desde el ZIP con
reproducción controlada antes/después.121tests, builds y offline PASS; matriz
original5/estándar3/PGXP2 combates,3/3 PASS, pausa/estados y cierre0. Watchdog
intacto. R0-C conserva tres fallos sin atribución definitiva; no cerrar R0
global. El historial visual/R7 siguiente sigue siendo válido.

## Historial — revisión visual y R7 (2026-10-19)

El agente revisó el render del settle (secuencia 2896–2907) y los 13 pares
de cámara ON/OFF. El par relativo 145 conserva el estado de ambos luchadores;
el resto no es determinista. Brazo coherente y encuadre más abierto en los
planos revisados; el vuelo puede recortar a un luchador en ambas variantes.
No se exige verificación humana de esas capturas. R7 cerrado como entrega
experimental; **R0 general reabierto** por dos watchdog del modo original
en paquetes extraídos con sampler=0. No afirmar estabilidad global. Matriz
completa, incluidas pruebas fallidas y comandos, en
`ROADMAP_RELEVO_COMBATE.md` §9. 112 tests/36 grupos C, build y offline PASS.

## Continuación del roadmap: mapa estático de rutas, 2026-10-18

`tools/combat_map.py routes`: cinco accesos de comandos, productores80/200 y
selección98/AA→99/9B/9A. Detalle y límites en `COMBATE_MAPA.md` §9.
Suite **69/69 PASS** (tres pruebas nuevas contra disco/captura privados y
regresión del opcode61 mal etiquetado como flags).34gruposC y matriz942 pasan.
Es evidencia estática: no demuestra un nuevo movimiento ejecutándose. No se
inició otra partida en esta tanda; n sigue siendo la última partida comprobada.
Relevo completo y experimento siguiente en `ROADMAP_RELEVO_COMBATE.md`.

## R1: retención del remate aéreo, implementada y observada (2026-10-18)

Se implementó **una** mejora concreta sobre la ruta demostrada y se observó en
partida. R1 sigue **abierto**: el consumidor 98/AA→99/9B/9A no se reprodujo.

- **Cambio:** `src/mods/dbfb_responsive.c` (`standard_command`, hook `0x80054AE8`).
  Un `cmd25`/`cmd29` reconocido mientras `control+4` no tiene `0x20`/`0x40` se
  retiene y se reinyecta por `control+0x56` (máximo 16 frames de invitado) cuando
  aparece la bandera aérea. No se escribe en `control+4` ni `control+8`. Se cancela
  con otro comando, una acción de continuación (98/AA/99/9A/9B), pausa,
  online/resim, restauración o pérdida de contexto. Contadores
  `dbfb.responsive.followup_wait` y `followup_inject`.
- **Verificación estática nueva:** el consumidor `0x80057608` acepta `0x98` **y**
  `0xAA` (delay slot `0x80057610`); el handler `0x800607A0` escribe `control+8`; la
  puerta consume `control+0x56` en `0x800570F8`→`0x800570FC` (dentro de `0x80056E54`),
  de modo que el hook `0x80054AE8` llega al mismo frame. Detalle en `COMBATE_MAPA.md`
  §9.1.
- **`python -B -m unittest discover -s tools/tests -p "test_*.py"`: 69/69 PASS**,
  con **35 grupos C** (nuevo escenario de retención: suelo→inyección única,
  cancelación por otro comando/continuación, cota, ambos lados, pausa/online/restore).
- **Builds** normal y PGXP enlazados; `python tools/verify_offline.py` **PASS**
  (namespace `cg18_1b6950cb_gc58692d0b_f0`, 1157 DLLs; no se tocó `game.toml`).
- **Partidas privadas** (headless, `--no-launcher`, puertos 4384/4386, carpetas
  propias): retención observada 64× y 16×; `followup_inject`=0. Con `wtrace` sobre
  `control+4`/`control+8` aparecen `0x98`/`0x99` en `control+8` por
  `0x8004EEAC`/`0x80057F94`, pero **no** los stores de limpieza del consumidor
  (`0x800576F8`/`0x80057734`/`0x80057764`) ni los productores de `0x80`
  (`0x80062FF4`/`0x80063030`/`0x80063228`): el consumidor no se ejecutó.
- **Bloqueo:** no se ha mapeado qué entrada/acción arma `control+4` `0x20`/`0x40`
  (productor `0x1D` en `0x8005D900`, y falta el de `0x40`), por lo que el gesto
  sintético no entra en la ventana aérea. Siguiente experimento en
  `ROADMAP_RELEVO_COMBATE.md`.

## Última partida comprobada: sesión n PASS, 2026-10-18

Con locomoción propia de §12:420s,puerto4382,cuatro combates completos,
pausa0→1→0,save/load generaciones1/2 y salida0 sinterminate.65tests y ambos
builds PASS.5.321 intervenciones de locomoción antes de giro/colisiones nativos;
144variantes de técnicas,91transiciones,25ráfagas,200/200 hit-stop.
Nuevo namespace `cg18_1b6950cb_gc58692d0b_f0`,1.157DLLsconranges. Auditoría de
reconstrucción rechazó ocho fragmentos kernel: no fue una compilación totalmente
sin rechazos; fueron excluidos. Verificador offline PASS.

Evidencias privadas `dbfb-rework-smoke-20261018m/` y `...n/` conservadas. m
también pasó cuatro combates antes de integrar locomoción. Métrica de suspensión
del muestreador Windows:123.400µs en m,173.844µs en n. No reproduce ni explica
los12,4s de l: **bloqueo intermitente todavía abierto**.

## Regresión conservada: sesión l FAIL, 2026-10-18

**Bloqueo de entrega vigente.** Tras corregir la escala erróneamente descrita
como movilidad (§11 del rediseño), los 64 tests y ambos builds pasan, pero la
sesión l falla en el segundo combate, frame **11.887**, retorno **2** por
`starvation_watchdog`: **12.414.350 µs** sin heartbeat. Pausa y save/load sí
completaron; solo se confirmó un combate completo. La pasada k descrita debajo
es de la revisión anterior y no certifica el binario actual.

Evidencia privada intacta: `dbfb-rework-smoke-20261018l/`. Cabecera del ring:
12.414.691 µs entre heartbeat y reloj, distinta de los266µs de c. Durante63
muestras del heartbeat (aprox.9s) se mantuvieron frame11887/ciclos6707853641/
dirty_insns11602342/last_store80047068. Después avanzan47.458ciclos y117
instrucciones antes del watchdog. `0x80047068` es guardado de registro de un
prólogo; `0x80041AC8` es SWC2, seguido de LWC2. No prueba un bucle de IRQ.
Sin fatal, unknown dispatch ni mid-block no soportado. Compatible con parada
del hilo host o trabajo nativo sin avanzar ciclos; falta captura de planificación
y pila de hilos durante esa parada. No hay causa demostrada ni se atribuye a
la retirada de la escala de velocidad. No se cambia ni silencia el watchdog.

## Comprobación anterior: sesión k, 2026-10-18

**64/64 tests y ambos builds PASS.** Sesión automatizada de 420 segundos con el
binario actual: **cuatro combates completos vida→KO→menú**, pausa 0→1→0,
guardar/cargar confirmados por generaciones de `savestate_status` y salida
normal **0**. Evidencia privada `dbfb-rework-smoke-20261018k/`; 38.818 frames,
4 KO, 96 frames de cámara de KO, 144 variantes de técnicas publicadas, 96
transiciones, 289/289 llamadas detenidas de script/pose y un comando añadido de
IA. No se reprodujo el watchdog.

**Corrección relevante:** el divisor nativo de guardia usa el bit **`0x40000000`**,
no `0x4000` (`lui` en `0x80066DC8`). Corregidos auxiliar y rotura de guardia,
con tests que contrastan las instrucciones del disco. IA: dificultad efectiva
`0x80072960 + lado*0x24`; CPU = control bit 0. Se conservan decisiones y salidas
defensivas nativas y el control humano, con cadencia 150/120/90 VBlanks según
índice 0/1/2. Las técnicas `0x78..83` cuestan 4/5 de ki, conservando tiempos,
poses y sincronización; 432 scripts cotejados word a word en el arnés.

**El cierre de pruebas anteriores requería corrección:** el script podía matar
el proceso al perder la respuesta TCP de `quit`. Salir con 1 no demostraba un
cierre normal. Ahora espera al proceso y rechaza cierres forzados. La sesión h
completó cuatro KO pero FAIL en cierre; i falló por una captura durante apagado
nativo de pantalla; j y k terminaron con 0. Capturas de transición omitidas se
anotan, no se ocultan errores de ejecución.

Guardar/cargar aquí significa **estado rápido en carpeta temporal nueva**, no
guardado desde el menú nativo en tarjeta. Falta validación humana del balance y
el resto de §10 de `COMBATE_REDISENO.md`; la causa de c sigue sin demostrar.

## Estado de 2026-10-18 (sustituye las conclusiones antiguas de relojes)

**Bloqueo de cierre:** la prueba c falló en menú, frame 3.303, retorno 2 por
`starvation_watchdog`. Las repeticiones d/e/g del mismo linaje completaron
combate/KO/regreso a menú (f quedó en combate tras su sonda de pausa) sin volver
a disparar el watchdog, pero no resuelven la intermitencia ni demuestran su causa. Se corrigió una carrera de doble lectura
del heartbeat (`starvation_watchdog_confirmed_stale`; el dump de c mostraba un
heartbeat de 266 µs al escribir la cabecera, coherente con un falso positivo),
sin silenciar ni ampliar el watchdog. Diagnósticos preservados; ver última
subsección de `COMBATE_REDISENO.md` §9.

Ver `COMBATE_REDISENO.md` §9 para direcciones y límites completos. Se corrigió
la cuenta atrás de eventos, el hit-stop y la confirmación de cancelación; se
añadieron ráfagas básicas al 125% con 64 VBlanks de vida/choques 3D, costes de ki
coherentes y acercamiento de KO. Suite **58/58**, **33 grupos C**, matriz de
**942 variantes**, runtimes normal/PGXP compilados y 1.158 DLLs en
`cg18_1b6950cb_gc2c269e7c_f0` (ocho rechazos IRQ/BIOS conservadores).

La sesión real `dbfb-rework-smoke-20261018b` observó 8 nacimientos de ráfaga,
290 ajustes de velocidad, 2 expiraciones, 31 llamadas de script/31 de pose
detenidas, una cancelación y 24 frames de cámara de KO. Nuevos contadores:
`ki_spawn`, `ki_speed`, `ki_expired`, `ki_trade`, `hitstop_script`,
`hitstop_pose`, `ko_camera` (prefijo `dbfb.responsive.`). `ki_trade` solo se
ejercitó en la matriz sintética. La sesión se cerró por debug con retorno 1;
no se presenta como salida normal del jugador ni test humano.

**Desbloqueo corregido:** `0x8003BCC4` (inmediato con signo), no `0x8004BCC4`.
START debug = `0x0008`. Captura privada `004-menu.png` muestra los 17 retratos,
incluido SSJ4.

**Transiciones de pose nativas (2026-10-18):** `src/mods/dbfb_pose.h` ya no
inserta huecos vacíos (los clips nativos traen una muestra por tick); da forma a
**una muestra interior existente** entre dos anclas de recuperación con
correcciones angulares relativas compensadas (`+c`/`−c`) que se cancelan al
ancla siguiente para cualquier pose de entrada. Conserva tiempos, eventos,
traslación, escala, geometría, jerarquía y poses de extremo; contador renombrado
`dbfb.responsive.pose_transitions`. La sesión g publica **17** en combate.

**Pausa real verificada (2026-10-18):** `tools/combat_smoke.py` sondea la bandera
nativa `0x800A868C` durante el combate; START la alterna 0→1→0 y el perfil
suspende/reanuda escrituras solo (sesión g: `before=0, paused=1, resumed=0`).

Quedan pendientes animaciones nuevas con jerarquía de huesos, nombres/medidas
nominales por golpe, rutas/remates, IA por dificultad, técnicas especiales,
encuadre general y balance humano. Los apartados siguientes conservan la
evidencia histórica.

Fecha: 2026-10-17. Alcance exclusivo: plugin, su paquete y pruebas propias.

## Cierre del 2026-10-17: partida real, caché nueva y coherencia de daño

- Caché de overlays regenerada con los puntos de integración del combate:
  **351 shards construidos** y **8 rechazos** en regiones IRQ/BIOS por
  instrucciones no soportadas (quedan interpretadas; el combate STEP40 compiló).
  Total verificado: **1.157 DLLs** en `cg18_1b6950cb_gcb5146b81_f0`.
- `tools/verify_offline.py` ahora obtiene el tag de caché del serializador
  canónico del framework en lugar de asumir una única carpeta; antes fallaba con
  dos configuraciones coexistiendo.
- **Primera sesión real del estándar**, headless y con mandos sintéticos:
  132.905 frames, cierre limpio, `fatal=no`, cero despachos desconocidos y cero
  bloques interpretados a mitad de bloque; **91% de despacho nativo**
  (37.565.732 nativos / 3.698.052 interpretados). Contadores del mod activos:
  594 variantes de movimiento, 11 parches de ventana, 2.864 ganancias de ki,
  514 escrituras de velocidad, 47 daños ajustados. No mide sensación humana.
- El daño ya no se reduce si la animación acortada no se instaló: se comprueba
  tabla privada publicada, magia/hash del arena y que la acción concreta tenga
  clip retimado. Sin compilador ejecutado, el daño sigue el original.

## Estado vigente: un único perfil estándar

La directriz posterior del usuario y el estado actual viven en
`COMBATE_REDISENO.md`: **una activación, sin ajustes necesarios**. Las reglas
aisladas descritas en las secciones históricas de abajo ya no aparecen en el
catálogo público. Su manifiesto se conserva en `mods/development/`.

El perfil inicial reúne entradas, movilidad, ki y una ventana **acotada** de
encadenado. La pausa se reconoce con la bandera nativa `0x800A868C` y se reanuda
automáticamente. La traza de desarrollo ahora incluye el estado de ambos
luchadores/scripts. Verificación actual: **46 tests pasan**, incluidos **26
grupos C**; compilan normal y PGXP y pasa la verificación offline (1.117 DLLs).
Todavía no hay animaciones nuevas ni rediseño completo de movimientos/defensa/IA.

## Ampliación posterior: tres reglas experimentales integradas

El estado de esta ampliación se detalla en `COMBATE_MAPA.md` (§3–6), que
actualiza el diagnóstico inicial conservado debajo: ya existe mapa estático de
vida/ki/acción y están implementadas `ki-economy`, `speed-scale` y `chain-window`.
Las cinco features del paquete están desactivadas por defecto. Para el control
Original completo deben permanecer desactivadas todas, no solo entrada y traza.

Verificación final: **40 tests Python pasan**, con **22 grupos de escenarios C**
del plugin de producción; ambos ejecutables normal/PGXP compilan, el catálogo se
despliega y `verify_offline.py` pasa con **1.117 DLLs** de overlays. No hubo una
prueba nueva en partida. Daño, IA, frame-data, ráfagas y modo alternativo siguen
pendientes; los resultados de abajo corresponden a la etapa anterior de entrada.

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
- `dbfb.responsive.combat_poll` / `guard_entry` / `guard_block` / `just_guard` /
  `guard_perfect` / `guard_break` — defensa (2026-10-17b).
- `dbfb.responsive.hitstop_frame` / `pushback` / `camera_shake` / `ko_impact` —
  impacto y cámara (2026-10-17b).
- `dbfb.responsive.cancel_window` / `combo_scaled` / `ai_command` —
  ataque, balance e IA (2026-10-17b).

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

## Cierre 2026-10-17b: defensa, impacto, cancelacion, IA y camara

- Nuevo punto de enganche verificado `0x80054A60` (`lh a0,+0x2856(at)`,
  `0x84242856`) anadido a `mod_instruction_sites`; la cache se regenero en el
  namespace `cg18_1b6950cb_gc41ea2caf_f0` con **1.158 DLLs** (`ok=1158
  failed=8 skipped=330`; los 8 rechazos siguen siendo IRQ/BIOS interpretados).
- `dbfb_motion.h` guarda la linea de tiempo retimada por accion
  (`motion_total_ticks`) y expone `motion_clip_live`; el dano y la
  cancelacion solo actuan con la tabla privada publicada.
- `src/mods/dbfb_combat.h` implementa: reproduccion de la prueba de bloqueo
  nativa con medidor/rotura/just-guard/perfect-guard; hit-stop en ambos relojes;
  empuje vectorial con tope; sacudida de camara acotada sobre
  `0x800A8664/0x800A8668` (solo con `0x800A8680 == 0`); ventana de
  cancelacion en recuperacion tardia con impacto confirmado; IA que inyecta un
  comando real en `+0x2856` del lado 2 antes de la puerta; y prorrateo de combo.
- Pruebas: **54/54 PASS**, **31 grupos C**; build normal y PGXP PASS;
  `verify_offline.py` PASS con 1.158 DLLs.
- Sesion real headless sin mandos humanos: `fatal=no`, cero volcados nuevos,
  91% nativo; contadores nuevos observados en combate (7.204 sondeos, 216
  variantes, 40 empujes, 40 danos, 108 hit-stop, 346 camara, 27 IA, 6 entradas de
  guardia, 2 bloqueos, 3 combos). No mide sensacion humana.
- Siguen abiertos: fichas nominales por golpe, animaciones nuevas, velocidad/vida
  de proyectiles, camara de KO propia y balance fino.

## Cierre 2026-10-19 (segunda tanda)

- Evidencia privada nueva: `dbfb-r3-verify{,2,3,4}-20261019` (sonda de arena:
  accion 6 -> slot 245), `dbfb-r4-verify-20261019` (camera_framing=435),
  `dbfb-r4-verify-off-20261019` (0, opt-out), `dbfb-r4-shots-20261019` (capturas
  de combate), `dbfb-r1-cmd29-20261019` (cadena 0x200/0x98/0x80/0x9B con PCs y
  seq), `dbfb-r5-cards-{b,c2,d,e}-20261019` + `dbfb-r5-combined-b-20261019`
  (tabla medida), `dbfb-r6-diff{0,1,2}-20261019` (dificultad).
- Suite 111 tests OK (36 grupos C), build exit 0, `verify_offline` PASS
  (namespace `cg18_1b6950cb_gc164a1e9a_f0`, 1158 DLLs), `combat_camera.py
  --check` PASS. Detalle en `ROADMAP_RELEVO_COMBATE.md` §8.
