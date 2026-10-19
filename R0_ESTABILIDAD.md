# R0 — estabilidad: estado y comprobación reproducible

**Estado vigente: 2026-10-19, después de publicar v0.2.1.**

Hay una corrección publicada y probada de una espera bloqueante del núcleo.
**No hay evidencia suficiente para atribuirle todos los cierres históricos ni
para cerrar R0 globalmente.** Este documento sustituye las referencias
imprecisas a «R0 pendiente». El registro de la release v0.2.0 está en el
roadmap §9; el mecanismo y su publicación están en §10 y §11.

## Qué está corregido y qué no

| Caso | Estado | Evidencia |
|---|---|---|
| R0-A: el muestreador suspendía el hilo del juego por defecto | Corregido en el núcleo publicado `835f1902` y en v0.2.0 | Opt-in exacto `PSX_HOST_SAMPLER_SUSPEND=1`; pruebas de política |
| R0-B: el mantenimiento del compilador esperaba a trabajadores aún vivos | **Corregido y publicado en v0.2.1** | Carrera reproducida con eventos; la prueba se bloqueaba antes del cambio y pasa después |
| R0-C: cierres por watchdog con sampler=0, frames 9781/17850/7236 | **Abierto en su atribución causal** | Tres fallos preservados; el último tiene medición de tiempo de pared y CPU; falta capturarlo con atribución por sección |

## R0-B: corrección de clase, sin cambiar el watchdog

En `psxrecomp/runtime/src/autocompile.c`, el preparador publica `AC_DONE`
**antes** de que termine su hilo de Windows. El hilo puede ser desprogramado en
esa frontera; tampoco se garantiza que el lector de salida ya haya terminado.
`autocompile_poll_main()`, llamado desde VBlank, esperaba ambos con
`WaitForSingleObject(..., INFINITE)`. Así, un trabajo auxiliar podía bloquear
el hilo del juego incluso después de anunciar su finalización lógica.

Ahora consulta ambos manejadores con espera **cero**, conserva `DONE`, sus
manejadores y sus recursos si alguno sigue vivo, y reintenta en el siguiente
frame. Solo después de terminar ambos cierra los manejadores y finaliza una vez.
El cierre del programa sigue siendo dueño de las esperas de terminación.

`runtime/tests/test_autocompile_publication.c` retiene deliberadamente al
preparador justo después de `DONE`, mediante eventos, y luego prueba también
un lector aún vivo. Comprueba que el sondeo regresa sin finalizar antes de
tiempo, conserva los recursos y hace exactamente un rescan al liberar ambos.
La misma prueba continúa comprobando 300 publicaciones, contrapresión de una
imagen, conservación de referencias y cierre durante trabajo pendiente.

- **Antes:** `test_autocompile_policy.py` agotó sus 12 s esperando el sondeo.
- **Después:** PASS, incluidos los dos trabajadores retenidos.
- No se ha elevado el umbral del watchdog ni añadido una excepción por juego.
- Los tests enlazados con el watchdog real siguen obteniendo salida 2 tras
  una espera de host de 4,5 s y ante un bucle de trabajo sin heartbeat.

## Qué se pudo medir del fallo real

Salida privada `dbfb-r0-matrix-20261019/1-original`:

- Cierre `starvation_watchdog`, salida 2, frame **7236**, pausa y estados correctos.
- Intervalo entre comprobaciones: **5.241.554 µs** de pared;
  **1.046.875 µs** de CPU kernel+usuario; **69.625 ciclos** de invitado.
- Sampler suspendido: **0**. Autocompilación no degradada. Sin instrucciones
  desconocidas ni despachos sin dueño registrados.
- Carga de DLL medida más larga: **4744 µs**. Ese contador no cubre toda la
  exploración de caché, el mantenimiento del proveedor o una orden de depuración;
  por tanto, no absuelve ni acusa por sí solo al subsistema de overlays.

La pausa real se reprodujo **antes** de añadir los cronómetros por sección.
Su coincidencia con una carrera posible de trabajadores no demuestra que esa
carrera provocase ese episodio. No convertirla en una atribución probada.

## Diagnóstico que queda instalado

El reporte final añade `watchdog_max_check_gap`: pared, CPU, ciclos, función
antes/después y disponibilidad de la medición CPU. `GetThreadTimes` observa el
hilo actual sin suspenderlo. Reinicio y restauración de estado no producen
restas sin signo desbordadas.

`watchdog_host_sections` atribuye llamadas, tiempo total y máximo a:
`debug_poll`, `frame_record`, `autocapture`, `provider_poll`, `audio`,
`mod_hooks`, `widescreen` e `image_capture`. Las observaciones no refrescan el
heartbeat ni alteran la decisión del watchdog. Sus máximos no tienen por qué
corresponder a un mismo instante: no sumarlos para explicar un fallo.

También se detectaron sondeos del proveedor de alrededor de **1,1–1,4 s** y
órdenes de depuración de hasta **1,5 s** en sesiones que terminaron bien. El
rescan síncrono de caché sigue siendo un coste medido, no un bloqueo eliminado
por el cambio de las esperas de trabajadores.

Dos capturas WPR generales perdieron eventos y **no se usan como prueba causal**.
La captura CPU reducida con xperf se completó sin avisos de pérdida, pero esa
sesión no reprodujo el cierre. Todo permanece privado en `%TEMP%/opencode/`.

## Verificación de v0.2.1

```powershell
# En PowerShell, conservar las comillas del argumento de versión.
cmake -S . -B build-release '-DPSX_GAME_VERSION=0.2.1'
cmake --build build-release -j 2
python -B -m unittest discover -s tools/tests -p "test_*.py"
python -B tools/verify_offline.py
python -B tools/combat_stability.py --archive "dist\dbfb-0.2.1-windows-x64.zip" --original-seconds 600 --seconds 300 --out "$env:TEMP\opencode\NUEVA-CARPETA"
```

Resultados ejecutados: **121 tests OK**, 36 grupos C de combate y matriz de
942 variantes; build normal y PGXP correctos; offline PASS, 1158 DLLs en
`cg18_1b6950cb_gc164a1e9a_f0`. Los ocho rechazos kernel históricos permanecen
excluidos; no se afirma que todos los overlays compilen.

Matriz ejecutada **desde el ZIP publicado**, sin `--build` ni sustituir
binarios (`dbfb-021-release-matrix-20261019`):

| Modo | Duración | Combates completos | Resultado |
|---|---:|---:|---|
| Original, mod inerte | 600 s | 5 | PASS |
| Combate renovado | 300 s | 3 | PASS |
| PGXP + combate renovado | 300 s | 2 | PASS |

Los tres confirmaron pausa/reanudación, guardar/cargar, locomoción propia,
autocompilación correcta, salida `tcp_quit`/0 y sampler=0. Identidad:
`nightly-1382-ga51c9aa7`. SHA256 de los ejecutables del paquete:

- Normal: `21feae7ce85ad4c6ce322b9a3d7b96a34e3b90ab5436b4e8defb24c8c7d067c8`.
- PGXP: `46f4825327b6d7a71b52f84e3988d069213b2c26b02d1b75bc6b7193eedda0d6`.

Paquete `dbfb-0.2.1-windows-x64.zip`: 2.749 archivos, 83.484.971 bytes,
SHA256 `b9c67dea5092e5668930508fb88cab1de1ea1e6f856993b2850135f65054a20e`.
La matriz previa `dbfb-r0-verified-final-20261019` también pasó con 5/3/2
combates y se conserva como evidencia de la revisión local.

Se conservan además las sesiones anteriores al cambio: nueve sesiones originales
de 600 s completaron **48 combates**, y hubo también el fallo instrumentado
anterior. El buen resultado de esas sesiones **sin la corrección** es precisamente
por lo que no debe deducirse una reparación global de R0 solo por repetir PASS.

## Cómo repetir sin contaminar la prueba

`tools/combat_stability.py` valida todos los hashes e inventario del ZIP, extrae
una carpeta nueva **por modo y repetición**, usa tarjetas privadas y establece
las opciones de cada modo en su propia copia. Con `--build` sustituye solo los
ejecutables y sus manifiestos de ejecución por los locales. La salida distingue
la identidad del binario y los resultados de sesión de los del runtime.

```powershell
# Para perseguir R0-C: tres arranques originales independientes, detenerse
# en el primer fallo, sin repetir por accidente el modo renovado.
python -B tools/combat_stability.py --build build-release --original-seconds 600 --rounds 3 --modes original --stop-on-failure --out "$env:TEMP\opencode\OTRA-CARPETA-NUEVA"
```

No reutilizar una copia de paquete cuyo `mods/state.toml` ya se habilitó en
otra prueba. Una sonda temprana de esta sesión se lanzó así por error: terminó
normalmente, pero `original_inert=false`; **no cuenta como prueba del original**.

## Criterio pendiente de cierre de R0-C

Capturar un fallo real con las secciones activas o una traza CPU/context-switch
sin pérdidas que cubra el intervalo. Atribuir la espera a una operación concreta,
construir su reproducción controlada, corregirla y exigir antes/después además
de la matriz de juego. Si aparece `provider_poll`, separar espera de trabajadores,
commit de imagen y rescan; no confundirlos. No aumentar tiempos ni desactivar
detectores para obtener PASS.

**Distribución:** R0-B está **publicado en v0.2.1** (pre-release). Núcleo
`a51c9aa7` en `nova/rework-master`, pin limpio, build `nightly-1382-ga51c9aa7`,
paquete probado sin sustituir binarios. Commit `7bfb3a1`, tag `v0.2.1`.
La release v0.2.0 no incluía la corrección y permanece inmutable.
https://github.com/novapowers0/DB-Final-Bout-Recomp/releases/tag/v0.2.1

R0-C sigue abierto: publicar R0-B no cierra la investigación de los cierres
intermitentes ni autoriza a declarar estabilidad universal.
