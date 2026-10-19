# DB Final Bout Recompiled v0.2.0 — Combate renovado (experimental)

## Para jugar

Descarga `dbfb-0.2.0-windows-x64.zip`, descomprime y abre
`DBFinalBout_Recompiled.exe`. Selecciona tu disco USA SLUS-00493. El paquete
incluye el juego compilado, la variante PGXP, bibliotecas nativas de overlays,
OpenBIOS y herramientas de recompilación de overlays. No requiere generar ni
compilar el juego antes de jugar.

## Novedades

- **Combate renovado**, un único interruptor opcional en Mods: entradas,
  retención de remates aéreos por las rutas nativas, ritmo de ataques/poses,
  aceleración/frenado, defensa, hit-stop, cancelación tras impacto, ki y ráfagas.
- Transición nueva de asentamiento del brazo en la recuperación de la acción 6,
  limitada al registro de animación 0 identificado y verificado.
- Cámara general ligeramente más abierta (6,25 %) y cámara de KO. Para comparar
  con el encuadre original: variable de entorno `DBFB_CAMERA_FRAMING=0`.
- **Todos los personajes**: desbloqueo opcional de los 17 luchadores.
- El muestreo diagnóstico que suspendía el hilo de emulación en Windows queda
  desactivado por defecto. La protección contra bloqueos sigue activa.
- Herramientas de análisis y medición de combate, comparación visual y pruebas
  reproducibles incluidas en el repositorio.

Los mods vienen **desactivados**. Activa los que quieras en el lanzador. El
combate renovado se limita al juego offline.

## Comprobaciones

- Suite del proyecto: 112 pruebas correctas, 36 grupos del arnés C y matriz
  integrada de 942 variantes.
- Compilación de ejecutables normal y PGXP; verificación offline.
- Revisión visual por el agente de una secuencia real de recuperación y de
  capturas de cámara activada/desactivada desde el mismo estado guardado.
- Pausa y guardar/cargar dentro de la transición nueva: conserva el contexto
  exacto y reanuda correctamente.
- Partidas automatizadas con combates completos, KO, pausa, guardar/cargar y
  locomoción. Detalle y alcance en `ROADMAP_RELEVO_COMBATE.md`, §9.

## Alcance de esta versión

**Incidencia abierta:** dos pruebas del modo original desde paquetes extraídos
terminaron por la protección contra bloqueos (watchdog), incluso sin muestreo
que suspenda el hilo. Otra prueba completó dos combates y cerró normalmente.
No se ha demostrado la causa de esta incidencia intermitente; se conserva en
R0 y esta publicación es una **pre-release experimental**, no una declaración
de estabilidad universal. La protección sigue activa. El paquete inicial que
tenía incompleto el Python auxiliar fue corregido y no se publica.

El perfil sigue siendo **experimental**. No sustituye todos los movimientos o
animaciones. El vuelo conserva planos nativos que pueden recortar a un
luchador. Las fichas de golpes tienen muestras pequeñas y no cubren todos los
aéreos/bloqueos; no se afirma balance competitivo exhaustivo. La comparación
de cámara tiene un par con estado de ambos luchadores idéntico; el resto es
observacional y no una reproducción determinista completa.

Se incluyen 1.158 bibliotecas nativas en la configuración verificada. Ocho
fragmentos kernel rechazados por la auditoría no se distribuyen como nativos;
la auditoría no se ha relajado. Software/4:3 es la referencia. Vulkan, PGXP y
netplay conservan su alcance experimental previo.

No se distribuyen discos, BIOS retail, capturas, estados ni volcados privados.
