# ROADMAP — Dragon Ball GT: Final Bout (Recompilado)

Actualizado: 2026-10-17 (sesión de equipo). Prioridad: **P1 = inmediato**,
**P2 = QoL / pulido**, **P3 = fondo**. El *rework de combate* es el objetivo mayor
(sección 4).

Leyenda de estado: ✅ hecho y validado · 🟡 hecho, falta validación en juego ·
⛔ bloqueado · ⬜ pendiente.

---

## 0. Base e integración de esta sesión

- Framework sincronizado: `psxrecomp` (`rework-master`, codegen `cg18_1b6950cb`) y
  `recomp-ui` (`0546fbc`); punteros en el commit `c78c5a1` del padre.
- **Build integrada reconstruida** (fix IRQ + plugin nuevo): `psx-runtime` y
  `psx-runtime-pgxp` enlazan sin error (solo avisos `-Wtautological-compare` del
  código generado del juego, preexistentes).
- **Suite de aceptación (esta sesión):**
  - `tools/verify_offline.py` → **PASA** (config fuente/desplegada idénticas 14917 B,
    codegen `1b6950cb`, 1117 DLL, runtimes normal+PGXP).
  - IRQ: `test_irq_callback_recovery.py` → **PASA** `-O0`/`-O2`.
  - Combate: `tools/tests/test_responsive.py` (2) y `test_responsive_evidence.py --inspect` → **OK**.
  - Sesión: `tools/tests/test_session_analysis.py` → **27 OK**.
  - QoL: `tools/tests/test_qol_tools.py` → **11 OK**.
  - Netplay: `ctest build-net-tests` → **28/28** (la inestabilidad de
    `rb_ctrl_multipeer_test` se corrigió; ver §2 y §5).
  - OpenBIOS regenerada (huella nueva, no stale) y cachés `cg10/cg13` archivadas.
- Informes de evidencia: `ESTABILIDAD_EVIDENCIA.md`, `COMBATE_EVIDENCIA.md`,
  `QOL_EVIDENCIA.md`, `REGENERACION_EVIDENCIA.md`.

---

## 1. Inmediato (P1) — estabilidad y regresiones

1. 🟡 **`FAIL-FAST unknown dispatch 0x2934` (frame 8418).**
   - Mecanismo del runtime **reproducido sin plugin** y **dos defectos corregidos** en
     `dirty_ram_interp.c`: (a) el indicador de error se propagaba al llamador válido,
     (b) una carga diferida pisaba `s0` restaurado. El dump del incidente tiene
     `empty_irq_callback_returns=1` → la mitigación sí se ejecutó (contradice la nota
     antigua “nunca salió de 0”).
   - Falta: reproducir la secuencia histórica completa con/sin `trace` y comparar con
     Beetle; no exonerado el plugin.
2. ⬜ **Cobertura nativa cae desde el 2.º combate.** Tabla histórica afinada:
   **95,8 % → 53,9 % → 6,6 %** (el ~7 % aparece desde el **3.er** combate; fracción de
   *despachos*, no de tiempo). **Causa no demostrada**: sin muestras de
   `overlay_loader_status`/`overlay_candidates` por combate no se toca el cargador.
   Acción: muestrear CRC/generación/segmento por pelea antes de corregir nada.
3. 🟡 **Recuperación del callback IRQ.** Ruta ahora **cubierta por pruebas automáticas**
   (13 escenarios, ambas continuaciones `0x293C`/`0x2950`, restauración de `s0-s7/gp/sp/fp`).
   Falta validación en juego y causa raíz de la IRQ original.
4. ✅ **Regenerar `generated/OpenBIOS_*.c`.** Hecho: el bloqueo era el guardián de
   tests sin registrar; se registró `irq_callback_recovery_test` y se regeneró
   (`EMIT OK`, 651 funciones, 3990 dispatch, huella nueva). Runtimes reconstruidos y
   `verify_offline` PASA. SCPH1001 y su respaldo intactos.
5. ✅ **Regenerar el C del juego con el recompilador nuevo.** Hecho (salida 0):
   `SLUS_004.93_full_00..09.c` + cabecera + dispatch; 2982 funciones, 10 fragmentos,
   748 entradas de dispatch; 35 avisos de rama fuera de función conservados en el log.
   Respaldo íntegro verificado en `build-recompiler/respaldo_regeneracion_20261017/`.
6. ✅ **Higiene de cachés.** `cg10_*` y `cg13_*` movidas (no borradas) a
   `build-release/_obsolete_cache_backup_20261017/`; solo queda `cg18`. El vault
   (`build-release/vault/`, 6,3 MB) se conserva hasta cerrar P1.2.
7. ✅ **Comentarios desincronizados de `game.toml`.** Corregido: la nota del render
   `0x80054684` (sí declarado) y la aclaración de que `mod_function_entry_funcs` son
   direcciones de **overlay** (no-op en el EXE, activas con el STEP40).

---

## 2. QoL (P2)

- ✅/🟡 **Launcher:** preparador offline (`tools/qol_launcher.py`) con validación de
  revisión/rutas/opciones; **el flujo gráfico real (GUI) sigue sin verificar**.
- ⬜ **Pausa / especiales / rematch / vuelo:** matriz de humo preparada
  (`tools/qol_smoke.py`), sin ejecutar contra juego vivo.
- ⬜ **Sombras 3D:** investigadas rutas (`ws_far_threshold`, depth PGXP); “proyección Z”
  sigue siendo **hipótesis**, sin comparación nueva con Beetle ni fix demostrado.
- 🟡 **Multi-región (A7):** premisa **corregida**: EU y España **no** son code-identical
  (5 de 6 overlays difieren, incluido STEP40). Arquitectura recomendada = **un launcher
  común con builds por perfil**, no 1 exe con 3 dispatchers.
- 🟡 **`dbfb.responsive` entrada:** reescrito a **`buffer`** (recupera una pulsación
  perdida entre sondeos, entrega única), **`hold`** separado y **`original`** sin
  accesos/escrituras; offline-only, default-off; probado con el C real.
- ✅ **`trace`:** canal `developer`, off por defecto.
- ✅/🟡 **Netplay:** suite sintética **28/28 estable**. La inestabilidad de
  `rb_ctrl_multipeer_test` tenía causa demostrada (base de puerto > 65535) y está
  corregida. Falta host/guest reales, ICE/WAN y determinismo del juego.

---

## 3. Fondo (P3)

- 🟡 **Mapa de estructura del luchador** (vida/ki/hit-stop/animación).
  `tools/combat_map.py` **verificado** (comandos inventory/disasm/xrefs/calls/pointers/
  words/fieldrefs/commands, salida 0): mapa de STEP40 en el disco, anclas por captura y,
  clave para el Tier 3, la **tabla de comandos** (34 filas: ID de salida, handler, pasos).
  Sigue **sin** mapa de estado de luchador (vida/ki): pendiente de análisis de control-flow.
- ⬜ **Cobertura STEP40 ampliada** como ciclo repetible (`tools/step40_coverage_step.py`).
- ⬜ **Tiers 3 y 4** del rework: no iniciados.

---

## 4. Rework del sistema de combate

Meta: modernizar el combate sin romper el original, sobre el plugin confiable
`dbfb.responsive` y datos verificados del invitado.

1. 🟡 **Instrumentar.** Traza de pad y flancos reales (`0x800A9CE8` pulsación,
   `0x800AA198` liberación, `0x800A9F30` unión; escrituras en `0x8003FE34..50`).
   Falta leer estado (vida/ki/hit-stop) — depende de §3.
2. ✅ **Capa de entrada.** `buffer`/`hold`/`original` implementados, con puertas por
   ruta de combate verificada, bloqueo online/resimulado, caducidad y reinicios;
   probado byte a byte en el C real.
3. ⬜ **Ajustes de combate** (balance/hit-stop/ventanas) como features opt-in.
4. ⬜ **Compatibilidad:** paridad byte-idéntica en Original (probada sintéticamente en C).
5. ⬜ **Netplay:** contrato determinista si el rework toca la simulación (hoy offline-only).

Criterio de cierre: paridad Original verificada en juego + features opt-in documentadas
(dirección/dueño/ancho/restauración) + sin regresiones.

---

## 5. Decisiones pendientes / riesgos abiertos

- Causa del freeze de transición (temporización de IRQ): no demostrada.
- Degradación de cobertura nativa: sin muestras por combate; no tocar el cargador aún.
- Multi-región: los overlays PAL difieren; PAL no está soportado por el exe USA.
- `lib/recomp-net` (submódulo anidado) queda modificado localmente por el fix del test;
  conviene proponerlo upstream al actualizar.
- **Validación en juego parcial:** un smoke acotado confirma que la build integrada
  (fix IRQ + plugin + BIOS regenerada) **arranca y expone el servidor de depuración**
  (`ping` OK con `--hidden-window`; sin procesos residuales, sin crash nuevo, el
  `psx_crash.txt` presente es del 04/10/2026). Un playtest interactivo real
  (combate, transición 0x2934, cobertura nativa) sigue pendiente de sesión humana.
- Publicación: **no** subir ROMs/BIOS/snapshots ni `build-release/overlay_captures*` /
  `psx_freeze_dump_*`.
