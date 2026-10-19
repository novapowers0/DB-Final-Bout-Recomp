# DBFinalBout Recomp — Session Summary

## 2026-10-19: R0 investigado; espera de trabajadores corregida y probada localmente

- Estado preciso en `R0_ESTABILIDAD.md` y roadmap §10. R0-A (sampler) ya estaba
  resuelto en v0.2.0. R0-B corregido en fuentes/build locales: el preparador
  publica `DONE` antes de terminar el hilo; VBlank usaba `Wait(..., INFINITE)`.
  Ahora consulta ambos trabajadores sin esperar y conserva DONE/recursos hasta
  que terminen; finalización/rescan exactamente una vez. No se modifica watchdog.
- Prueba real enlazada `test_autocompile_publication.c`: retener al trabajador
  con eventos después de DONE bloqueaba el test12s antes del parche; PASS después.
  Cubre también al lector aún vivo,300publicaciones,contrapresión y referencias.
- R0-C **no cerrado**: `dbfb-r0-matrix-20261019/1-original` reprodujo watchdog
  frame7236, gap5.241.554µs/CPU1.046.875µs/69.625ciclos; sampler0,cargaDLLmax4744µs.
  Ocurrió antes de añadir medición por sección; no atribuirlo sin prueba a R0-B.
- Telemetría pasiva `watchdog_max_check_gap` y ocho `watchdog_host_sections` en
  reporte final. No suspensiones nuevas ni cambios de heartbeat/umbrales. Tests
  reales siguen saliendo2 ante espera4,5s y bucle sin heartbeat. Hay rescans
  del proveedor1,1–1,4s medidos que este parche no elimina.
- Nuevo `tools/combat_stability.py`: ZIP verificado, carpeta/tarjetas por modo,
  runtime original/renovado/PGXP explícito, hashes y checks de runtime además de
  los del smoke. Evita confundir un original con copia cuyo mod ya está activo.
- Verificación final: build normal+PGXP, **121 tests OK**,36gruposC,offline PASS,
  caché1158/`cg18_1b6950cb_gc164a1e9a_f0`. Matriz
  `dbfb-r0-verified-final-20261019`: original600s/5combates,
  estándar300s/3,PGXP300s/2;3/3 PASS, pausa/estados,autocompile,quit0,sampler0.
- Evidencia previa al parche:9sesiones originales600s/48combates PASS **y** el
  fallo anterior. Esos PASS previos muestran por qué no bastan para cerrar R0-C.
  WPR perdió eventos (no prueba causal); xperf reducido sin avisos de pérdida,
  pero su sesión no falló. Evidencia privada en `%TEMP%/opencode/`.
- Núcleo sobre835f1902 con cambios locales dirty; binarios finalesSHA256:
  normal `13d093c1b1554b52bbfc0b8d4068e60c2c4f642158a7ef414041f26750d49e4e`,
  PGXP `49b4bf4199140f0ec031761dfafac5e2dc1e85e3b28ac73ef39446593f8c8d26`.
  La v0.2.0 pública conserva sus assets; no incorpora este parche. Sin nueva
  publicación, commit ni push en esta continuación. `github/` ajeno preservado.

## 2026-10-19: visual revisado por el agente, R7 y publicación experimental 0.2.0

- Render real del settle: 71 capturas; montaje 2896–2907 revisado por el agente,
  brazo/mano unidos, postura final estable, sin rotura observada. Pausa dentro
  del clip + guardar/cargar conserva exactamente el contexto y reanuda.
- Cámara: 13 pares ON/OFF, 26 imágenes revisadas; par relativo 145 con 124 bytes
  de control idénticos en ambos luchadores y encuadre más abierto. Los otros
  pares divergen, por lo que NO hay PASS determinista global. En vuelo hay
  recortes tanto ON como OFF, registrados como límite.
- Matriz del ZIP ampliada: estándar/PGXP PASS; original dos watchdog con
  sampler=0 (frames 9781/17850), otra sesión de 300 s PASS con dos combates y
  otra sin crash pero sin KO suficiente. **R0 general reabierto**, sin causa
  asignada. Reporte añade tiempos de carga existentes para atribución futura.
- Empaquetado corrige Python auxiliar incompleto, valida herramientas locales
  portables, 1158 DLLs, catálogo público apagado, ausencia de datos privados y
  CRC/SHA256. Fuentes del núcleo commit `835f1902` publicadas en el fork.
- 112 tests/36 grupos C OK, 26 comprobaciones watchdog OK, builds normal/PGXP
  y offline PASS. Comandos y resultados completos en roadmap §9.
- R7 cerrado como integración/entrega **experimental**, con límites explícitos,
  sin exigir verificación humana ni afirmar que R0–R6 estén globalmente cerrados.
- Autorización de usuario: commit + push + release. Versión 0.2.0; notas en
  `RELEASE_NOTES_v0.2.0.md`, paquete Windows compilado, no setup-host.
- ZIP final extraído y probado: original 300 s/2 combates, estándar 180 s/1,
  PGXP 180 s/1; **3/3 PASS**, pausa/estados, salida 0, sampler=0 y autocompile
  correcto. Los fallos previos siguen registrados. ZIP 83.480.650 bytes,
  SHA256 `c1e17b089f3d5868c1970575b50344b74a576060b73022466b6bb1f2aabcfb6d`.
- **Publicación completada:** commit `285cb7f` subido a master; tag y
  pre-release `v0.2.0` publicados. ZIP y checksum en estado `uploaded`, digest
  remoto idéntico al local. URL:
  https://github.com/novapowers0/DB-Final-Bout-Recomp/releases/tag/v0.2.0
  La release estable `v0.1.1` se conserva. Solo queda ajeno sin añadir `github/`.

## 2026-10-19 (segunda tanda): R3 integrado y probado; R4 implementado; R5/R6 medidos; R1 cerrado

- **R3 (transición de clip):** integrada como settle nativo
  (`src/mods/dbfb_pose_settle.h` + llamada en `motion_build`, `dbfb_motion.h`):
  clona la pista 105 de la acción 6 del registro 0 con dos paquetes relativos
  nuevos (partes 8/9) que telescopan a cero, conserva todo lo original y publica
  un slot nuevo. Oráculo offline (handoff exacto módulo-16) y **prueba en
  partida** con sonda: la acción 6 apunta al slot creado 245, no al nativo 105
  (solo el settle escribe esa entrada). Límite: sin comprobación visual a ojo.
- **R4 (cámara general):** el seam correcto es `0x80054F88` (tras las
  reescrituras nativas; `0x80054F34` se perdía). Nuevo
  `src/mods/dbfb_camera_frame.h`: escala solo el vector ojo→objetivo nativo
  (17/16) con guardas (modo/lock/transición/KO/pausa/online/rango) y contador
  `camera_framing`. Requirió sitio nuevo en `game.toml` + **recompilación de
  overlays** (1158 OK, 8 rechazos kernel conocidos) → namespace
  `cg18_1b6950cb_gc164a1e9a_f0`, `verify_offline` PASS. Partidas A/B: ON 435
  aplicaciones, `DBFB_CAMERA_FRAMING=0` 0; capturas en combate con render
  correcto. Límite: A/B visual exacto del 6,25 % no demostrado.
- **R5 (fichas medidas):** `tools/combat_cards.py` mide startup/recuperación/
  ventaja/hit-stop en VBlanks reales; cuadrado 0x72/0x73 startup 17-20 VB,
  ventaja 2-40, hit-stop 4 VB (n=3-6); triángulo 0x64/0x65 startup 14-23.
  Círculo/cruz/aéreos sin muestras válidas. 20 tests nuevos.
- **R6 (dificultad):** 0/1/2 verificados en partida (stores nativos
  `0x80053DE4`/`0x80053EFC`, 100 % de muestras); acciones CPU/minE 28,0/37,4/
  42,7. Cadencia extra del mod no distinguible (gate cerrado). Balance humano
  no automatizable.
- **R1:** cadena `cmd29/ID6 →0x200→0x98→0x80→0x9B` capturada completa con
  wtrace (PCs/seq exactos) y ventana pausa/restore observada sin corrupción.
- **Verificación:** **111 tests OK** (36 grupos C), build exit 0,
  `verify_offline` PASS (1158 DLLs), `combat_camera.py --check` PASS, 13
  sesiones de verificación con salida 0. Detalle en
  `ROADMAP_RELEVO_COMBATE.md` §8. Sin commit/push.

## 2026-10-19: R0 corregido de clase; R1 cmd25 entregado; R2–R4 avanzados

- **R0 (bloqueo intermitente):** el muestreador de host suspendía el hilo de
  emulación desde otro hilo, sin cota de latencia; causa del congelamiento `l`.
  Arreglo de clase en runtime genérico: sampler suspend-based de Windows ahora
  **opt-in** (`PSX_HOST_SAMPLER_SUSPEND=1`), apagado por defecto; watchdog intacto.
  Nuevos `runtime/tests/test_host_sampler_policy.c`, registro en CMakeLists y
  `tools/tests/test_host_sampler_policy.py`. Sesiones con `max_suspend_us=0`.
- **R1 (remates aéreos):** causa del no-inject observada (el Circle final del
  gesto25 arrancaba el normal `6A` y `control+0` bit8, impidiendo armar `0x20`).
  Mejora real: `followup_lift()` sustituye solo los argumentos de entrada nativos
  para que el motor original haga el despegue, y luego entrega `25` por
  `control+0x56`. Observado en partida ambos lados: `25→20→98→80→99` y `98→9A`;
  vs CPU 32/26, ambos humanos 18/18. Contadores de motivo añadidos. Pendiente:
  `cmd29/ID6→200→9B`.
- **R2/R3 (movimiento/clips):** geometría decodificada (18 registros, 425 piezas,
  14.755 polígonos), cadena modelo→parte→jerarquía y `Rx·Ry·Rz` contra `RotMatrix`;
  anatomía observada solo registro 0. Transición propia de pose slot2→1 (6 ticks,
  smoothstep, 3984 bytes) en `src/mods/dbfb_rig_bridge.h`; herramientas
  `combat_rigclip.py`/`combat_rig_preview.py`. No integrada/renderizada aún.
- **R4 (cámara):** propiedad del contexto `0x800A9FA0`→`0x800A9D0C` y rama general
  `0x80054EC4` mapeadas; sonda de solo lectura `src/mods/dbfb_camera.h` +
  `tools/combat_camera.py`. Sin encuadre implementado.
- **Verificación:** `python -B -m unittest discover -s tools/tests -p "test_*.py"`
  → **86/86 OK** (35 grupos C); build normal+PGXP PASS; `verify_offline.py` PASS
  (`cg18_1b6950cb_gc58692d0b_f0`, 1157 DLLs); `combat_camera.py --check` PASS;
  partida `dbfb-final-20261019` (420 s): 4 combates, pausa, save/load, locomoción,
  salida 0, `max_suspend_us=0`; `git diff --check` exit 0.
- Detalle completo en `ROADMAP_RELEVO_COMBATE.md` §7. Sin commit/push.

## 2026-10-18: relevo persistente y continuación de R1

- Usuario pidió seguir el roadmap y dejar un relevo para otro modelo antes de
  continuar. Creado `ROADMAP_RELEVO_COMBATE.md`, enlazado en AGENTS/HANDOFF:
  tareasR0–R7, criterios, comandos, estado y prompt transferible. No delegación
  efectiva ni agentes lanzados.
- Continuación real: cmd25/fila32/607A0 conecta flags20/40→98/AA, con delay
  slot; cmd28/29/2B/2C completan accesos por ID. Productores80 en
  62FF4/63030/63228 y200 en60AAC; consumidor576BC→9B/99/9A, limpia flags y
  publica candidato sp+48 en57F94. IDs nativos no equivalen a índices BTCHARA.
- Nuevo `combat_map.py routes` genera metadatos con hash/base USA exigidos;
  código de lectura, sin hooks/parches nuevos. Opcode61 corregido a
  `audio_channel_event` en `combat_moves.py`: no produce banderas del luchador.
- Nuevos `tools/tests/test_combat_routes.py` y caso en `test_combat_moves.py`.
  `python -B -m unittest discover -s tools/tests -p "test_*.py"`: **69/69PASS**,
  34gruposC,matriz942/432técnicas siguen verdes. `combat_map.py routes` ejecutado.
- Docs ampliadas: MAPA§9, REDISENO§13, EVIDENCIA y este resumen. No se inició
  partida nueva; n sigue siendo evidencia anterior. Próximo experimentoR1:
  wtrace control+4/+8 en ambos lados, gesto nativo dentro de flags20/40,
  correlación de PCs/seq, sin inyectar RAM. Instrucciones exactas en relevo§6.
- R0(l/c) sigue sin causa; no declarar rediseño/remates nuevos terminados.

## 2026-10-18: locomoción propia observada; m/n PASS; bloqueo l sin causa

- NUEVO `src/mods/dbfb_locomotion.h`: callback0x80067A68/mult s0,v0 cambia
  delta propio de raíz antes de proyección/separación; objetivo5/4, aceleración40
  y frenado64 porVBlank, ambas direcciones/lados. No usa script+c ni posiciones.
  Registro añadido en responsive, reset encombat_reset y sitio en game.toml.
- `test_responsive.py`/harness ahora22bloques privados,34gruposC, incluye
  cadencia, frenado, límites, pausa/KO/restore/online sin escrituras de RAM.
  `test_combat_matrix_harness.c` acepta22bloques. Suite **65/65PASS**.
- `combat_smoke.py`: `--movement`/`--summary`, contadores en cada captura
  conservados ante crash, movimiento observado obligatorio cuando solicitado.
  Test adicional del veredicto. Sesión **n PASS**420s/4382:cuatro combates,
  pausa,save/load y salida0;5321locomotion,34465framesalúltimosondeo,
  144técnicas,91transiciones,25ráfagas,200/200hit-stop. Evidencia privada n.
- `host_sampler.[ch]` mide intervalo suspend/context de Windows, sin alterar
  watchdog/timing. `debug_server.c` expone `host_profile.max_suspend_us`;
  `crash_trace.c` serializa `host_sampler_max_suspend_us`. mPASS4combates antes
  de locomoción:123400µs; n:173844µs. **No resuelve l**, que no reapareció.
- Ghidra/JDK existentes localizados por registro de otro cliente. ProbeMCPREA
  207tools/binary_sessionOK vía entorno local; sin instalaciones ni cambios de
  configuración. Archivo temporal `dbfb_rea_probe.py`; no sesión de binario abierta.
- Ambos builds PASS. `compile_overlays.py` con vault182capturas: primera
  llamada timeout600s; continuación8workers terminó con624built/250skipped/
  **8rechazos**audit/memo enkernelregiones1000/2000. No se debilitóauditoría.
  Namespace nuevo `cg18_1b6950cb_gc58692d0b_f0`,1157DLLsconranges;
  verify_offline PASS, config15663bytes. No afirmar todosshardsPASS.
- Comandos finales:
  `python -B -m unittest discover -s tools/tests -p "test_*.py"` PASS65;
  `cmake --build build-release --target psx-runtime psx-runtime-pgxp -j 4` PASS;
  `python -B tools/combat_smoke.py --launch --port 4382 --seconds 420 --kos 3 --savestate --movement --summary --out <temp>/dbfb-rework-smoke-20261018n` PASS.
- Docs §12 y evidencia actualizadas. Pendientes verdaderos: bloqueo l,
  rutas/remates aéreos, clips totalmente nuevos/anatomía, giro, encuadre general,
  balance humano. No declarar rediseño terminado.

## 2026-10-18 (último resultado): l FAIL, corregida la falsa movilidad125%

**No declarar acabado ni estable:** tras el cambio final, 64 tests y builds
normal/PGXP PASS, pero smoke **l FAIL** en segundo combate frame11887,
retorno2 por watchdog (12.414.350µs). Pausa y estados rápidos save/load PASS,
un combate completo. k sigue siendo evidencia anterior, no del binario actual.

- `script+0x0C` no demuestra locomoción: opcode24 lo produce, consumidor
  `0x8006639C` toma s2=lado y s4=contrario (`0x800663BC`), mueve objeto de s4.
  El estándar ya usa `SPEED_ORIGINAL` para ese campo. Test estándar exige
  100/−100; laboratorio conserva prueba125/−125. Manifiesto deja de anunciar
  movilidad125%; el ritmo de ataques/poses sigue por su reloj compartido.
- Locomoción propia localizada: `0x800678D0` extrae delta de raíz, lo gira y
  aplica separación antes de control+2C/+34. Ninguna acción0..23 contiene op24
  en18registros. Falta mapear entrada/bucles/traslación. Cámara general tiene
  otra rama (`0x800AA194==1`); conversión relativa en `0x800506C8` con matriz
  de nodo y truncado signed16. Ver §11 del rediseño.
- Evidencia nueva `%TEMP%/opencode/dbfb-rework-smoke-20261018l/`: reporte,
  ring, heartbeat, dos dumps automáticos previos y tarjetas temporales intactos.
  Ring gap12.414.691µs, distinto de c266µs. 63 muestras mantienen frame11887,
  ciclos6707853641, dirty_insns11602342; luego avanzan47.458ciclos/117insns.
  Compatible con pausa del hilo host o trabajo nativo sin ciclo, no prueba un
  bucle MIPS. Finalstore80041AC8=SWC2, next=LWC2; native stack incluye
  psx_gte_stall/psx_cyc_lwc2_read/devices_service/watchdog/exit. Stack es barrido,
  no unwind fiable. current_func no es PC instantáneo.
- Host sampler Windows compilado usa SuspendThread/GetThreadContext/ResumeThread
  cada1ms; candidato para investigar, **sin causalidad demostrada**. WPR/WPA
  instalados; próximo experimento decisivo: traza CPU/planificación de la
  reproducción para separar suspensión/espera de cómputo nativo. No se lanzó
  captura global del host, no se tocó core ni se silenció/amplió watchdog.
- Últimos comandos: suite64PASS, ninja normal y PGXP PASS;
  smoke `--port 4380 --seconds 420 --kos 3 --savestate --out <temp>/dbfb-rework-smoke-20261018l`
  FAIL. Archivos añadidos a los cambios de §siguiente: `dbfb_responsive.c`,
  manifiesto, test estándar y docs §11. Verificador offline y diff-check son
  independientes de este fallo en ejecución y no lo cierran.

## 2026-10-18 (cierre actual): guardia correcta, dificultad, técnicas y cuatro combates

- **64/64 PASS**, 33 grupos C, matriz 942 variantes, 432 scripts de técnicas
  comprobados. Ambos exe normal/PGXP compilados. Sin commit/push.
- **Bug de defensa corregido:** `0x80066DC8 = lui v0,0x4000`; máscara del divisor
  dos = `0x40000000`, NO `0x4000`. Corregidos helper y flag de rotura en
  `dbfb_combat.h`; tests de disco y casos bit14/bit30/signo actualizados.
- **Dificultad probada estáticamente:** opción byte `0x8003BC74`, menú cursor−2
  (índices 0..2); copia por lado `0x80072960 + lado*0x24`, forzada a 2 en modos
  0x43/44/45. Stores `0x80053DE4/53EFC`, consumo IA `0x800509BC/50D40`.
  `0x80034FD4` es flags, no dificultad.
- **IA corregida:** ownership CPU = `control & 1` (`0x800549C8`), no presencia
  de un mando digital. Solo CPU J2 frente a humano J1. Cadencia extra de diseño
  150/120/90 VBlanks por índice; pausa e hit-stop la preservan. No reemplaza
  comando original, botones de `sp+10/14`, outputs almacenados, temporizador,
  decisiones C8/C9, guardias ni respuestas ante amenaza. Los comandos 0/1 son
  técnicas especiales, no golpes básicos. 1 inyección observada en sesión k.
- **Técnicas `78..83`:** scripts privados con coste positivo del op84 a 4/5;
  tiempos, poses, daño y sincronía nativos. Familias directas 78..7A/7E..80;
  coordinadas 7B..7D/81..83 (selector `0x8005F2C4` altera también al rival).
  Contador nuevo `technique_variants`. No reciben cancelación ni daño de clips
  retimados. `combat_moves --cards` muestra handler, familia y coste; op60 es
  `audio_bank_event`, no un salto de acción.
- **Prueba larga k PASS** (420s, puerto4379): 4 combates vida→KO→menú, pausa
  0→1→0, save/load completados (generaciones1/2, last_ok1), salida normal0.
  38.818 frames, 144 variantes de técnicas (incluye rebuild tras load), 96
  transiciones, 48 ráfagas, 289/289 script/pose detenidos, 4 cancelaciones,
  12 guardias, 1 just/1 perfect. 23.488.190 despachos nativos/1.839.401 interp.
- **Corrección del instrumento:** `combat_smoke.py` usa duración completa,
  exige KO + vida→cero→menú, pausa, salida0 sin terminate y, con `--savestate`,
  completitud real. Perder ACK de quit no significa que haya que matar el proceso;
  espera su salida. h: cuatro KO pero FAIL del cierre; i: FAIL por screenshot
  con display desactivado (ahora se anota como omitida); j: 3KO/save/load/salida0;
  k: PASS completo con binario actual. Evidencia privada h/i/j/k intacta.
- Estados rápidos en tarjetas temporales **no** prueban el guardado nativo en
  tarjeta. No reapareció watchdog, pero la causa histórica de c sigue sin
  demostrar. Siguen pendientes clips completamente nuevos/anatomía, rutas y
  remates aéreos, locomoción propia, encuadre general/relativo, nombres/medidas
  nominales y balance humano. §10 de COMBATE_REDISENO.md detalla límites.
- Archivos cambiados en este tramo: `src/mods/dbfb_combat.h`, `dbfb_motion.h`,
  `tools/combat_moves.py`, `combat_smoke.py`, tests `test_responsive.py`,
  `test_responsive_harness.c`, `test_combat_matrix_harness.c`,
  `test_motion_harness.c`, `test_combat_moves.py`, nuevo `test_combat_smoke.py`,
  manifiesto de dbfb.responsive y docs de estado.
- Comandos de verificación: `python -B -m unittest discover -s tools/tests -p "test_*.py"`;
  `ninja -C build-release DBFinalBout_Recompiled.exe` y target PGXP por separado;
  `python -B tools/combat_smoke.py --launch --port 4379 --seconds 420 --kos 3 --savestate --out <temp nuevo>`.

## 2026-10-18 (cont.): transiciones de pose nativas, watchdog y pausa real

**Último resultado real:** 58/58 tests PASS, builds normal/PGXP PASS y
`verify_offline.py` PASS. Sesiones headless nuevas: **e** y **g** completaron
boot → menú → combate → KO → regreso a menú sin reincidir el watchdog (f quedó
en combate tras su sonda de pausa).

- **Transiciones de pose nativas** (`src/mods/dbfb_pose.h`): el análisis de los 18
  registros probó que los clips ya traen una muestra por tick y que casi todos los
  ángulos son incrementos relativos; insertar huecos era inviable. La vía
  respaldada por los datos es **reperfilar una muestra interior existente** entre
  dos anclas de recuperación con correcciones angulares relativas compensadas
  (`+c`/`−c`, cabecera `0x03310000|parte`), que se cancelan al ancla siguiente
  para cualquier pose de entrada. Conserva tiempos, eventos, traslación, escala,
  geometría, jerarquía y poses de extremo. Contador renombrado
  `dbfb.responsive.pose_inbetweens` → `pose_transitions` (17 en la sesión g).
- **Watchdog:** el dump de c mostraba un heartbeat de **266 µs** al escribir la
  cabecera, compatible con un refresco concurrente que dejó evidencia obsoleta.
  `starvation_watchdog_check` ahora hace doble lectura
  (`starvation_watchdog_confirmed_stale`) y solo aborta si ambas lecturas están
  vencidas; no se silencia ni amplía. Arnés **26/26 PASS**.
- **Pausa real verificada en partida** (sesión g): `tools/combat_smoke.py` sondea
  `0x800A868C`; START la alterna 0→1→0 y el perfil suspende/reanuda escrituras
  solo. Sesión g: 17 transiciones, 24 frames de cámara de KO, 1 cancelación,
  3 comandos de IA, 10.472 frames.
- Evidencia privada en `%TEMP%/opencode/dbfb-rework-smoke-20261018{e,f,g}/`. El
  fallo intermitente c **sigue abierto** como bloqueo de entrega: las repeticiones
  no lo reproducen, pero tampoco demuestran su causa.

## 2026-10-18: reloj corregido, ráfagas, KO, matriz y desbloqueo real

**Último resultado real:** 58/58 tests, ambos builds y verificación offline PASS,
pero sesión **c FAIL** en menú, frame 3.303, retorno 2 por `starvation_watchdog`
(>10 s sin heartbeat). Espera alrededor de `0x8001BD34/68` y OpenBIOS
`0x1FC060E4`, `I_STAT=0`, sin mid-block ni unknown dispatch. Causa no demostrada.
La repetición **d**, mismo binario, sí completó combate/KO/regreso al menú en
14.818 frames: 10 nacimientos de ki, 280 ajustes de velocidad, 35/35 llamadas de
eventos/pose detenidas, 24 frames de KO y 10.019.954/817.311 despachos
nativos/interpretados. Esto NO cierra el fallo intermitente c. Evidencia intacta
en `%TEMP%/opencode/dbfb-rework-smoke-20261018{c,d}/`. Priorizar ese bloqueo antes
de declarar entrega final; no se cambió ni silenció el watchdog.

- **Correcciones críticas de la entrega anterior:** `script+4` es cuenta atrás
  por evento (no tiempo acumulado). Hit-stop pasa a filtros de `0x8004E530` y
  `0x80042240`, únicamente para los dos luchadores. La cancelación usa puntero
  privado, cierre final de ataque, cola visual y confirmación por daño sin
  bloqueo; descarta confirmaciones al repetir acción. La reducción de daño solo
  empieza tras publicar la variante completa. Pausa conserva temporizadores.
- `dbfb_projectiles.h` nuevo: eventos de nacimiento reales (`0x8004F5A0`),
  velocidad 256→320 antes de integrar (`0x800592A8/0x800592FC`), 64 VBlanks de
  duración y choques barridos 3D para ráfagas básicas `0x72..77`. Retirada por los
  flags nativos, sin dejar el bit de propietario atascado. Paso de objetos
  observado en vivo **21** (no asumir 36 fijo); admitido 17..36.
- Coste positivo de ki de esas variantes a 3/4 como su daño; conservar sentinelas
  y otros operandos. Cámara propia de KO: acercamiento máximo 8%, 24 VBlanks,
  restauración y cesión inmediata al motor si emite un plano nuevo (solo directo).
- **Unlock corregido y verificado en pantalla:** `lui 0x8004; sw -0x433c` da
  `0x8003BCC4`, no `0x8004BCC4`. START del protocolo debug es `0x0008`. La sesión
  `dbfb-rework-smoke-20261018b` muestra 17 retratos en `004-menu.png` y word
  `0x1FFFF`, una activación del contador. Las conclusiones de dirección de la
  sesión anterior eran erróneas; leer `DESBLOQUEO.md` actualizado.
- Pruebas: **58/58 PASS**, **33 grupos C**, matriz integrada de **942 variantes**
  en 18 registros/ambos lados (716 recuperaciones, 226 sin cancelación añadida),
  y ráfagas en los 17 registros con variantes básicas. Fichas estáticas/costes
  disponibles con `python tools/combat_moves.py --cards`; no inventan nombres ni
  frames de ventaja.
- Overlays: **1.158 DLLs** en `cg18_1b6950cb_gc2c269e7c_f0`; siguen los ocho
  rechazos conservadores de IRQ/BIOS (la herramienta informa fallos, no pase
  completo). Ambos runtimes normal/PGXP reconstruidos.
- Sesión real b: 9.572 frames muestreados; 6.135.743 despachos nativos/501.584
  interpretados. 8 nacimientos de ráfaga, 290 ajustes de velocidad, 2 expiraciones,
  31 llamadas de eventos y 31 de pose detenidas, 1 cancelación y 24 frames de KO.
  Los choques entre ráfagas solo se verificaron sintéticamente. Cierre mediante
  debug devuelve 1; no confundirlo con salida normal del usuario ni playtest.
- Evidencia privada: `%TEMP%/opencode/dbfb-rework-smoke-20261018{a,b}/`.
  Herramienta reproducible nueva `tools/combat_smoke.py` (tarjetas temporales,
  sin editar RAM/selección de mods y limpieza del proceso al terminar).
- **No cerrado al 100%:** siguen pendientes poses/animaciones nuevas y huesos,
  medidas/nombres por golpe, rutas aéreas/remates, IA por dificultad, cámaras
  relativas/encuadre general, técnicas especiales, balance humano y tres
  combates/guardados. `COMBATE_REDISENO.md` §9 es el estado vigente.
- Archivos de esta tanda: `src/mods/dbfb_{responsive.c,motion.h,combat.h,projectiles.h}`,
  `game.toml`, manifiesto responsive, `tools/combat_{moves.py,smoke.py}`,
  `tools/tests/test_{responsive.py,responsive_harness.c,motion_harness.c,combat_moves.py,combat_matrix.py,combat_matrix_harness.c}`
  y documentación de combate/desbloqueo/memoria. Sin commit ni publicación.
- Comandos de comprobación: `python -m unittest discover -s tools/tests -p
  'test_*.py' -v`; `cmake --build build-release --target psx-runtime -j 4`;
  `cmake --build build-release --target psx-runtime-pgxp -j 4`;
  `python tools/verify_offline.py`; `git diff --check`.

## 2026-10-17b: defensa, impacto, cancelación, IA y cámara sobre costuras verificadas

- Nuevo punto de enganche `0x80054A60` (`lh a0,+0x2856(at)`, `0x84242856`),
  antes de que la puerta lea el comando, añadido a `mod_instruction_sites`.
  Overlays recompilados en el namespace nuevo `cg18_1b6950cb_gc41ea2caf_f0` con
  **1.158 DLLs** (`ok=1158 failed=8 skipped=330`; los 8 siguen siendo IRQ/BIOS).
- `src/mods/dbfb_combat.h` (nuevo) implementa, siempre tras `standard_code()`:
  defensa reproduciendo la prueba de bloqueo nativa (acción `0x21/0x22/0x23` y
  máscara del word `+0x2900` del atacante) con medidor de guardia, rotura,
  just-guard (cuarto + ki) y perfect-guard; hit-stop que resta un tick a ambos
  relojes de script; empuje vectorial en las dos copias de posición con tope
  ±7000; sacudida de cámara acotada sobre `0x800A8664/0x800A8668` solo con
  `0x800A8680 == 0`; cancelación en recuperación tardía con impacto confirmado
  (`+0x2800` bit `0x10`); IA que inyecta un comando real (`0x00/0x01`) en
  `+0x2856` del lado 2 antes de la puerta, con cooldown, rango y desactivación si
  hay segundo mando; y prorrateo de combo.
- `dbfb_motion.h` guarda la línea de tiempo retimada por acción
  (`motion_total_ticks`) y expone `motion_clip_live`; el daño y la cancelación
  solo actúan si la tabla privada está publicada y la acción tiene clip retimado.
- Pruebas: **54/54 PASS**, **31 grupos C**; `cmake --build build-release --target
  psx-runtime psx-runtime-pgxp` PASS; `verify_offline.py` PASS con 1.158 DLLs.
- **Sesión real headless** (sin mandos humanos): `fatal=no`, sin volcados de
  freeze nuevos, 91% de despacho nativo. Contadores nuevos observados en combate:
  7.204 sondeos de combate, 216 variantes de movimiento, 40 empujes, 40 daños,
  108 frames de hit-stop, 346 sacudidas de cámara, 27 comandos de IA, 6 entradas
  de guardia, 2 bloqueos y 3 golpes prorrateados. No mide sensación humana.
- Siguen abiertos: fichas nominales por golpe, animaciones nuevas, velocidad/vida
  de proyectiles, cámara de KO propia y balance fino.

## 2026-10-17 (cierre): caché regenerada, primera partida real del estándar y daño coherente

- **Caché de overlays regenerada** con los puntos de integración nuevos
  (`mod_instruction_sites`): **351 shards construidos**, 214 omitidos por
  caché/datos y **8 rechazos de auditoría** en regiones IRQ/BIOS
  (`0x80001000`, `0x80002000`, interiores `0x80001F6C/27AC/27F8/2818`) por
  instrucciones no soportadas. Esos fragmentos siguen interpretados; el STEP40
  de combate sí compiló. Una DLL temporal incompleta de una ejecución
  interrumpida se movió a `build-release/backup/overlay-interrupted-20261017/`
  (no se borró nada).
- **Verificador corregido:** `tools/verify_offline.py` exigía una única carpeta
  `cg18_…` y fallaba al coexistir la caché anterior y la nueva. Ahora pregunta
  al serializador canónico del framework (`cache_tag`) qué namespace cargará el
  runtime y verifica solo ese. Resultado: **1.157 DLLs con `.ranges`**.
- **Primera sesión real del perfil estándar (headless, automatizada):**
  arranque → menús → combates, **132.905 frames**, cierre `tcp_quit`/`atexit`,
  `fatal=no`, `unknown_dispatch_total=0`, `midblock_count=0`,
  `empty_irq_callback_returns=0`, sin volcados de freeze nuevos.
  `dispatch_native=37.565.732` frente a `3.698.052` interpretadas (**91% nativo**).
  Contadores del estándar activos: 594 variantes de movimiento, 11 parches de
  ventana, 2.864 ganancias de ki, 514 ajustes de velocidad y 47 daños ajustados.
  No es una prueba de sensación humana: los mandos fueron sintéticos.
- **Corrección de coherencia (daño ↔ animación):** el daño se reducía por el
  reloj acortado aunque la variante de animación no se hubiera podido instalar
  (movimiento ausente/alias, o tabla privada aún no publicada). `dbfb_motion.h`
  registra qué acciones seleccionadas no se recompusieron y
  `standard_damage` solo escala cuando la tabla privada está publicada y la
  acción sí tiene clip retimado; si el compilador nunca actuó, el daño sigue
  siendo el original. Cubierto por el arnés de movimiento con datos reales.
- Comprobaciones: **54/54 tests PASS** (28 grupos C del plugin y el arnés de
  movimiento de los 18 registros), builds normal y PGXP enlazados,
  `verify_offline.py` PASS. La caché validada es
  `cg18_1b6950cb_gcb5146b81_f0` con 1.157 DLLs.
- Límites sin cambios: defensa/guardia, IA, cámara, proyectiles avanzados y
  animaciones nuevas siguen abiertos; el estándar no se declara definitivo.

## 2026-10-17: directriz activar y jugar, perfil estándar y estudio de animaciones

- El usuario precisó el objetivo: estándar muy bueno sin configuración y
  rediseño mecánico potente, incluidas animaciones. Nueva referencia rectora:
  `COMBATE_REDISENO.md`; directriz recogida también en `AGENTS.md`.
- Catálogo público: una sola feature `standard` (**Combate renovado**) sin
  opciones. Traza separada en desarrollo. Manifiesto previo conservado en
  `mods/development/dbfb.responsive-legacy.toml`; no se borran selecciones del
  usuario. Se retiran del catálogo los interruptores individuales del laboratorio.
- Plugin estándar independiente: buffer de 2 VBlanks, velocidad nominal 125%,
  +1 ki/4 sondeos válidos y umbral de aceptación 9→12 en `0x80054AC0`.
  No usa el parche incondicional de Open. Guardas de identidad de todas las
  partes, supresión de reglas duplicadas en el mismo VBlank y restauración
  de estado auxiliar al cargar un guardado.
- Pausa nativa mapeada en `0x800A868C`: inicialización `0x800540FC`, toggles
  `0x8006A178/180` y `0x8006A220/22C`, consumidor `0x8006A2F8/300`.
  El estándar deja de escribir al pausar, vacía entradas pendientes y vuelve a
  funcionar cuando el juego confirma que se ha reanudado; no exige reactivar.
- Traza: dos registros mecánicos adicionales kind=4 por sondeo, con acción,
  flags2, script, reloj/opcode, HP/ki y velocidad/contador de puerta; solo lectura
  de luchadores y escrituras en el ring diagnóstico.
- Estudio real de B3 HD, solo lectura: `src/combate.cpp`,
  `docs/03_formatos/ACM_FORMAT.md`, `docs/14_frentes/combate.md`,
  `studies/tools/frame_data.py` e instrucciones/índice del proyecto. Es el port
  Xbox 360/ReXGlue, no solo PS2. Se adopta la separación curvas → eventos →
  reacciones y medición de arranque/recuperación/guardia/whiff. No se han copiado
  activos ni cambiado el proyecto de B3.
- Herramientas: `tools/combat_map.py` añade inventario ISO e inmediatos;
  `tools/combat_assets.py` reproduce de forma acotada el descompresor Psdp
  leído del STEP40, sin extraer archivos. BTCHARA: 2.650 bloques / 12.868.520
  bytes descomprimidos; CHARSEL: 72 / 2.095.968. No se halló una tabla de acciones
  con el filtro estructural actual; no se confunde ese resultado con ausencia
  de animaciones. Falta resolver contenedores/enlace a los scripts en RAM.
- Corrección del mapa: tabla en `0x8003E78C`; opcode animación/acción 0x20,
  spawn 0x23, velocidad 0x24 y registro de golpe 0x25. Las etiquetas anteriores
  estaban desplazadas; las direcciones de campos de las reglas no cambian.
- Comprobaciones ejecutadas:
  - `python -m unittest discover -s tools/tests -p test_*.py -v`: **46/46 PASS**,
    con **26 grupos C** y 6 tests del lector de recursos.
  - `cmake --build build-release --target psx-runtime psx-runtime-pgxp -j 4`:
    **PASS**, ambos ejecutables y catálogo actualizado/verificado.
  - `python tools/verify_offline.py`: **PASS**, configuración idéntica y caché
    de **1.117 DLLs** conservada. No se modifica `game.toml` ni el codegen.
- No se lanzó el juego ni se añadieron animaciones; estándar inicial integrado
  no equivale a estándar definitivo ni cierra el rediseño. Los criterios y el
  siguiente bloqueo están explícitos en `COMBATE_REDISENO.md`.

## 2026-10-17: integración pendiente de las tres reglas de combate cerrada

- Se completó la implementación interrumpida en `src/mods/dbfb_responsive.c`:
  `ki-economy`, `speed-scale` y `chain-window`, con opciones en el manifiesto de
  `mods/preloaded/packages/dbfb.responsive/0.1.0/manifest.toml`. Default OFF y
  modo inicial Original; callbacks independientes, offline, con contexto de
  combate y comprobación de instrucciones verificadas.
- Se corrigieron el reescalado al cambiar porcentajes, la restauración del valor
  bruto al volver a Original, la aplicación diferida del parche hasta un sondeo
  válido y su reconciliación al cargar un guardado de Open estando en Original.
  Pausa suspende nuevas escrituras de reglas; ver límites en `COMBATE_MAPA.md`.
- Se terminó el arnés de cinco plugins en `tools/tests/test_responsive_harness.c`
  y se amplió `tools/tests/test_responsive.py` con cinco grupos funcionales de
  reglas y comprobaciones de manifiesto. Los bytes de identidad adicionales
  proceden de capturas privadas existentes pasadas por stdin; no se distribuyen.
- Comandos ejecutados y resultado:
  - `python -m unittest discover -s tools/tests -p test_*.py -v`: **40/40 PASS**,
    incluidos **22 grupos C** del plugin real con `-Wall -Wextra -Werror`.
  - `cmake --build build-release --target psx-runtime psx-runtime-pgxp -j 4`:
    **PASS**, normal y PGXP enlazados y catálogo actualizado/verificado.
  - `python tools/verify_offline.py`: **PASS**, fuente/desplegado idénticos,
    caché vigente **1.117 DLLs**. No se modificó `game.toml` ni los overlays.
- Documentación actualizada: `COMBATE_MAPA.md`, `COMBATE_EVIDENCIA.md` y este
  resumen. No se abrió el juego; no equivale a validar combos ni mejor sensación.
  Daño, IA, frame-data, ráfagas y modo alternativo siguen abiertos.
- Cambios locales sin commit nuevo. La carpeta ajena `github/` sigue sin tocar.

## 2026-10-03: release v0.1.1 actualizada in situ y handoff a Claude

- Se reconstruyó el paquete setup-host `dbfb-0.1.1-setup-host-win64.zip` con el
  árbol actual (runtimes `0.1.1`, recuperación del callback IRQ y contador
  `empty_irq_callback_returns`) y se **reemplazó el asset del release existente
  `v0.1.1`** con `gh release upload --clobber`, sin crear tag ni borrador. Las
  notas se actualizaron con `gh release edit --notes-file`.
- Asset único resultante: 33.060.246 bytes, SHA-256
  `5c74dbaff2744ace0396ba1be38b4a00982cb803f1d0824b6a6b24d625d23f53`,
  0 descargas. `verify_offline.py` y la prueba de integridad del ZIP pasan; no
  contiene imagen de disco ni dump retail de BIOS.
- El wrapper de empaquetado ahora incluye `baserom.md` y `mods/` (dejó de listar
  `launcher_assets`, que estaba vacío). `mods/bundled` es necesario para el
  catálogo de mods.
- Entorno: el packager bash necesita `zip`/`rsync`/`python3`, ausentes en el Git
  Bash del equipo. Se documentó la alternativa (7-Zip/Compress-Archive y
  `C:\Python314\python.exe`) y `PSXRECOMP_RUNTIME_BIN_DIR` para las DLLs
  `libc++.dll`/`libunwind.dll`.
- Documentación de la entrega creada/actualizada: `MEMORY.md` (memoria durable),
  `HANDOFF_CLAUDE.md` (misión Fases A/B), `AGENTS.md` §7/§11/§13/§14 (estado y
  referencias). El handoff pide a Claude dejar todo funcional de extremo a
  extremo y construir un mod de combate renovado tomando
  `guimaraf/plusalpha-recomp` como referencia conductual, documentando el
  trabajo en `INFORME_CLAUDE.md`. Commit/push los haremos nosotros.
- Sigue pendiente la sesión nueva instrumentada que confirme
  `empty_irq_callback_returns`; y la cobertura nativa completa del combate.

## 2026-09-26: playtest Piccolo estable y diagnóstico de recuperación

- El usuario completó **Piccolo vs Goku** y confirmó que la transición al
  segundo combate **Piccolo vs Little Goku Super Saiyan** avanzó sin colgarse.
- Artefactos locales de la ejecución cerrada normalmente: `psx_last_run_report.json`
  (frame 5438, `reason=atexit`, `exit_origin=sdl_window_close`, `fatal=null`) y
  `psx_freeze_heartbeat.json` (frame 5437, `fatal=null`, cero dumps automáticos
  fallidos, `in_exception=0`, `dirty_ram_insns=321715503`). El reporte trae
  `unknown_dispatch_tail.total=0`, `interp_unsupported.midblock_count=0` y
  `dispatch_depth=1` al cierre. El dump fatal de frame 2214 es de la prueba
  anterior, no de la sesión estable.
- El historial de overlay conserva 69 snapshots/78 regiones de la sesión, con
  actividad de combate STEP40 en `0x80060000..0x8006E000`. El reporte indica
  `disp_native=0`, `disp_interp=1618550`: la ruta de combate observada aún fue
  interpretada, no cambió por nuevos DLL nativos.
- El éxito concuerda con el fallback estrecho añadido para la ranura vacía del
  walker de IRQ, pero los artefactos previos no traen un contador específico y
  por sí solos no demuestran causalidad.
- Refuerzo diagnóstico: contador `g_dirty_ram_empty_irq_callback_returns`,
  exportado como `empty_irq_callback_returns` en heartbeat e informe final;
  `tools/analyze_latest_session.py` lo muestra en la próxima ejecución. Esto
  permitirá verificar que el callback fue descartado y a la vez que no hubo
  unsupported opcode ni dispatch desconocido.
- Los snapshots capturados tienen bytes del disco del usuario; son artefactos
  locales y no deben publicarse. No se usaron como raíces para recompilar.

## 2026-09-26: Piccolo repro y seguimiento del fix RI

- El usuario probó `INICIAR_FINAL_BOUT_NATIVO.bat` con Little Goku vs Piccolo y
  el juego volvió a colgarse. El dump nuevo es
  `build-release/psx_freeze_dump_psx-runtime_1790440947_0.json` (frame 2214).
- El fix RI anterior sí vectorizó desde `0x2030` a `0x80000080`, pero el manejador
  volvió al walker, que llamó otra vez la ranura borrada `0x1F6C`. La secuencia
  `0x1F6C -> 0x80000080 -> 0x27AC -> 0x2818` se repitió hasta que la guarda de
  recursión detuvo el juego (`exception_reentry_blocks=902`).
- Seguimiento en `psxrecomp/runtime/src/dirty_ram_interp.c`: una ejecución que
  empieza en RAM baja `0x1000..0xFFFF`, contiene solo NOPs y produce RI, con `$ra`
  igual al retorno de `jalr` del walker (`0x293C` o `0x2950`), se trata como
  callback vacío; devuelve `v0=0` y retoma el walker. Las demás RI conservan el
  comportamiento de excepción.
- Runtimes normal y PGXP reconstruidos. `python tools\\verify_offline.py` pasa;
  el juego no se lanzó desde el agente. La nueva prueba manual de Little Goku vs
  Piccolo aún está pendiente.

## 2026-09-26: frameworks actualizados y documentación de estado

- `psxrecomp`: merge upstream master en `rework-master`, commit `7d70880d`
  (base upstream `d62f4b44`), publicado en `novapowers0/psxrecomp`. El fix RI y
  diagnóstico están preservados en `d76c5c39`.
- `recomp-ui`: fast-forward a `01bff947`.
- `psxrecomp/lib/recomp-net`: pin anidado `c2338c63`.
- Build Release verificada: Ninja/clang enlazó
  `DBFinalBout_Recompiled.exe` correctamente el 2026-09-26. Aún falta probar en
  juego la transición Little Goku vs Piccolo; compilación correcta no equivale a
  validación funcional.
- `VERSION` del proyecto subió de `0.1.0` a `0.1.1`; se preparó el paquete
  `dbfb-0.1.1-setup-host-win64.zip` para la release correspondiente.
- La actualización del framework incorpora, entre otros cambios, el rediseño
  SIO/IRQ upstream. En `gpu.c` se adoptó el scene latch upstream; se preservó
  `sio_no_tx_gate` y se sustituyó el shim temporal de chat filter por la API real
  de `recomp-net`.
- Rebuild de release con `PSX_GAME_VERSION=0.1.1`: variantes normal y PGXP
  enlazadas. Packager setup-host oficial ejecutado; los controles verificaron
  ZIP íntegro, pins nuevos, VERSION/stamp `0.1.1` y ausencia de disc/BIOS retail.
  Publicado como GitHub Release `v0.1.1`:
  `https://github.com/novapowers0/DB-Final-Bout-Recomp/releases/tag/v0.1.1`.
  Asset `dbfb-0.1.1-setup-host-win64.zip` (33,058,485 bytes), SHA-256
  `edfa917b4faac1377050326ab954b14adf648a50a94e85431257f2786f8cae83`.
  La transición Little Goku vs Piccolo aún requiere prueba manual in-game.

## 2026-09-12: H1 refutada; el fallo no es la compuerta ni la instrumentación

- `INICIAR_FINAL_BOUT_NATIVO.bat` (sin capturador) **también crasheó** →
  descartada la hipótesis de perturbación por el cliente de diagnóstico.
- `INICIAR_FINAL_BOUT_SEGURO.bat` (`PSX_FAIL_FAST_UNKNOWN_DISPATCH=0`) **no
  crasheó**. Patrón del usuario: crashes con **Piccolo** de rival, sin crash
  contra Goku adulto (posible palanca de reproducción, no confirmado).
- El `psx_crash.txt` con el diagnóstico ampliado dice:
  `dirty=1 overlay_region=0 in_text=0 kbless=0 in_exception=1
  interp_unsupported=SPECIAL funct`.
  - `dirty=1` descarta la compuerta de página limpia.
  - El intérprete cubre todo el set SPECIAL R3000A → el motivo implica
    datos-como-código o un `psx_unknown_dispatch` que no pasó por el intérprete.
  - Sin entrada nueva en `dirty_block` tras `0x1F6C` → el fallo evita
    `dirty_ram_dispatch_inner`. Vía candidata: preámbulo de overlays nativos y
    stubs de `OpenBIOS_full.c`.
- Diagnóstico ampliado con `interp detail: last_unsupported_pc/insn/block_entry/
  entry_ra/midblock/aborts`; build `DBFinalBout_Recompiled.exe` reconstruida.
- **Causa raíz definitiva (reproducida, frame 2356):** el recorredor de IRQ del
  kernel salta a la ranura `0x1F6C` de la tabla de handlers del juego, que en ese
  mismo frame el overlay `0x8003F000` (`pc=0x80042CBC`) está **limpiando a ceros**
  (`[0x1F00,0x1FE0)`). El intérprete ejecuta la ranura a ceros (49 NOPs) y en
  `0x2030` encuentra `0x000900FF` (funct 0x3F), no válida → `abort_unsupported`
  → `cpu->pc=0` → `psx_unknown_dispatch(0x2934)` → fail-fast. En hardware habría
  **Reserved Instruction exception**; el intérprete aborta. **Fix aplicado:**
  `interp_exception(cpu, 10, 0, g_unsupported_pc)` en el caso mid-block
  (`dirty_ram_interp.c:3126`; mismo mecanismo ya usado para address errors).
  Build reconstruida 12/09 02:29. Reversión: `%TEMP%\opencode\dirty_ram_interp.c.bak_pre_ri`
  + `DBFinalBout_Recompiled.exe.bak_pre_diag`. Es foundation compartida: validar
  con oráculo. Ver `PLAN_SOLUCION_CRASH_Y_COMBATE.md` §3.2 y `ANALISIS_CRASHES.md` §9.3.
- Ver `PLAN_SOLUCION_CRASH_Y_COMBATE.md` §3.1 y `ANALISIS_CRASHES.md` §9.2.

## 2026-09-11 (tarde): RE del crash, build de diagnóstico y plan de combate (H1 histórica; refutada el 09-12)

Ver `PLAN_SOLUCION_CRASH_Y_COMBATE.md` para el detalle completo.

- **`0x2934` NO es hueco de cobertura**: en el run del crash (frame 5750) se
  interpretó **40.740 veces**, la última justo antes del fallo. El rechazo es
  dependiente de estado.
- Desensamblado verificado de `0x291C..0x295C`: es el **recorredor de la cadena
  de handlers de IRQ del kernel** (`lw`/`beq`/`jalr s1`/`jalr s0`/loop). No es
  una función del juego: no se siembra.
- Compuerta del rechazo: `dirty_ram_interp.c:2845` exige página dirty o región
  de overlay o game-text; la ventana del kernel `[0,0x10000)` está excluida a
  propósito. Para `0x2934` solo quedan `dirty` o `psx_kernel_bless_dispatchable`.
- **Hipótesis inicial H1 (luego refutada)**: la instrumentación (capturador con `history`/
  `gpu_state` cada 5 s + rings de 100.000 entradas) desplaza el timing en la
  transición a combate (carga de STEP40 + escritura de overlay_cache). El usuario
  reporta que el `.exe` nativo funcionaba sin diagnósticos.
- **Build de diagnóstico aplicada (solo observación)**: `runtime/src/traps.c`
  añade a `psx_crash.txt` la línea `refusal context: dirty=… overlay_region=…
  in_text=… kbless=… in_exception=… interp_unsupported=…`. `DBFinalBout_Recompiled.exe`
  reconstruido (Ninja/clang). Backups: `DBFinalBout_Recompiled.exe.bak_pre_diag`
  y `%TEMP%\opencode\traps.c.bak_pre_diag`.
- **Lanzadores nuevos**: `INICIAR_FINAL_BOUT_NATIVO.bat` (control, sin TCP),
  `INICIAR_FINAL_BOUT_SEGURO.bat` (`PSX_FAIL_FAST_UNKNOWN_DISPATCH=0`),
  `INICIAR_FINAL_BOUT_OBSERVAR_LIGERO.bat` (captura `--light`).
- **Capturador**: flags nuevos `--light` (solo contadores baratos) y `--rings`
  (volcado pesado, ahora opt-in). El JSON registra `light`/`rings`.
- **Sin cambios de comportamiento de gameplay.** El combate sigue sin mod Responsive.

## 2026-09-11: crash de transición y captura resiliente

- Una prueba manual falló al iniciar un combate en el frame `5992` con
  `FAIL-FAST unknown dispatch` en `0x00002934`, `ra=0x0000293C`.
- La repetición falló de nuevo en el frame `5750` con la firma idéntica:
  `0x00002934`, `ra=0x0000293C`, `epc=0x80041E78` y `SPECIAL funct` en
  `0x00002030`. El renderer de `settings.toml` era Vulkan.
- La captura parcial `build-release/captures/final_bout_manual_play_24456.json.partial`
  sí quedó guardada hasta la desconexión del debug server. Los errores WinError
  10053 posteriores solo indican que el proceso del juego ya había terminado.
- El informe también registra una instrucción `SPECIAL funct` no soportada en
  `0x00002030`; queda pendiente verificar la ruta antes de añadir seeds o
  modificar código.
- No había mod de gameplay activo: el fallo pertenece a cobertura/dispatch del
  runtime o del recompiler, no al diseño Responsive.
- La primera captura no llegó a producir JSON porque el proceso se cerró antes
  de su escritura final. El capturador fue corregido para guardar checkpoints
  atómicos `.json.partial` después de cada muestra.
- Se añadió `INICIAR_FINAL_BOUT_OPENGL_CON_CAPTURA.bat` para realizar una prueba
  A/B con OpenGL y restaurar automáticamente el renderer original.

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

## 2026-10-04: sesión autónoma Fase A/B (Claude)

Ver `INFORME_CLAUDE.md`. Causa de `disp_native=0` (desajuste de hash de caché cg10/cg13), cobertura STEP40 baja y callbacks por evidencia `jal/jalr`, recuperación IRQ generalizada (sin verificar), plugin `dbfb.responsive` (trace + input-buffer experimental), `verify_offline.py` corregido.

## 2026-10-18 (cont.): R1 — retención del remate aéreo, implementada y observada

Estado vigente en `ROADMAP_RELEVO_COMBATE.md`, `COMBATE_MAPA.md` §9.1,
`COMBATE_REDISENO.md` §14 y `COMBATE_EVIDENCIA.md`. R1 sigue **abierto**.

- Se releyeron los bytes: el consumidor `0x80057608` acepta `0x98` y `0xAA`; el
  handler `0x800607A0` escribe `control+8`; la puerta consume `control+0x56` en
  `0x800570F8`→`0x800570FC` (`0x80056E54`), por lo que el hook `0x80054AE8` llega
  en el mismo frame.
- **Mejora implementada (una):** `standard_command` retiene un `cmd25`/`cmd29`
  reconocido mientras `control+4` no tenga `0x20`/`0x40` y lo reinyecta por
  `control+0x56` (máx. 16 frames) al aparecer la bandera aérea. Solo escribe
  `control+0x56`. Contadores `followup_wait`/`followup_inject`.
- **Pruebas:** 69/69 PASS, **35 grupos C** (nuevo escenario de retención). Builds
  normal y PGXP PASS. `verify_offline.py` PASS, namespace
  `cg18_1b6950cb_gc58692d0b_f0` (1157 DLLs, sin cambios). `git diff --check` OK.
- **Partida privada** (`wtrace` exclusivo sobre `control+4`/`control+8`): retención
  64×/16×; `followup_inject`=0; el consumidor no se ejecutó (faltan sus stores de
  limpieza y los productores de `0x80`). No se ha mapeado qué entrada arma
  `control+4` `0x20`/`0x40`. R1 abierto con ese bloqueo y experimento siguiente.
