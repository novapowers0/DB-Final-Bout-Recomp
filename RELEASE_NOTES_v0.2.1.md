# DB Final Bout Recompiled v0.2.1 — estabilidad de mantenimiento (experimental)

## Para jugar

Descarga `dbfb-0.2.1-windows-x64.zip`, descomprime y abre
`DBFinalBout_Recompiled.exe`. Selecciona tu disco USA SLUS-00493. El paquete
incluye el juego compilado, la variante PGXP, bibliotecas nativas de overlays,
OpenBIOS y herramientas de recompilación de overlays. No requiere generar ni
compilar el juego antes de jugar.

## Novedades

- **Corrección de una espera bloqueante del núcleo.** El mantenimiento del
  compilador en VBlank esperaba sin límite a trabajadores auxiliares que ya
  habían anunciado su finalización lógica, pero cuyo hilo todavía podía seguir
  vivo. Ahora consulta su terminación sin detener el juego, conserva el estado
  y los recursos mientras hagan falta, y finaliza una sola vez. El cierre del
  programa sigue esperando la terminación real de esos hilos.
- **Regresión reproducible:** una prueba controlada que retiene esos
  trabajadores se bloqueaba antes del cambio y pasa después.
- **Diagnóstico pasivo del watchdog:** el reporte final incluye el mayor
  intervalo entre comprobaciones (pared, CPU, ciclos, función) y el tiempo de
  ocho secciones de mantenimiento del host. No se cambió el umbral, el
  heartbeat ni la decisión del watchdog.
- **Herramienta de matriz aislada** en el repositorio para probar original,
  combate renovado y PGXP desde un paquete verificado, con carpetas privadas
  por modo y comprobaciones del runtime.
- El contenido jugable es el mismo que en v0.2.0.

## Comprobaciones

- 121 pruebas correctas, 36 grupos del arnés C y matriz integrada de 942
  variantes.
- Compilación de ejecutables normal y PGXP; verificación offline PASS con
  1.158 bibliotecas nativas en `cg18_1b6950cb_gc164a1e9a_f0`.
- Matriz del paquete 0.2.1 extraído y verificado, sin sustituir binarios:
  original 600 s con 5 combates, combate renovado 300 s con 3 combates y PGXP
  300 s con 2 combates; 3/3 PASS con pausa, guardar/cargar, locomoción propia,
  cierre normal y sampler desactivado. Identidad del ejecutable:
  `nightly-1382-ga51c9aa7`.
- Los ocho fragmentos kernel rechazados por la auditoría siguen excluidos;
  no se afirma que todos los overlays compilen.

## Alcance de esta versión

**Incidencia abierta:** siguen existiendo cierres intermitentes por watchdog
en el modo original cuya causa no está demostrada. Esta versión corrige una
espera bloqueante real y medible, pero **no atribuye a esa corrección todos
los cierres históricos ni declara estabilidad universal**. Se conservan el
umbral del watchdog y todos sus detectores. El rescan síncrono del proveedor
mantiene costes medidos de aproximadamente 1,1–1,4 s en sesiones sanas.

El perfil de combate sigue siendo **experimental**. No sustituye todos los
movimientos o animaciones. El vuelo conserva planos nativos que pueden
recortar a un luchador. Las fichas de golpes tienen muestras pequeñas y no
cubren todos los aéreos/bloqueos; no se afirma balance competitivo exhaustivo.
La comparación de cámara tiene un par con estado de ambos luchadores idéntico;
el resto es observacional y no una reproducción determinista completa.

Software/4:3 es la referencia. Vulkan, PGXP y netplay conservan su alcance
experimental previo. No se distribuyen discos, BIOS retail, capturas, estados
ni volcados privados.

Los límites declarados de v0.2.0 sobre cámara en vuelo, fichas y balance se
mantienen; el detalle vive en `ROADMAP_RELEVO_COMBATE.md` y
`R0_ESTABILIDAD.md`.
