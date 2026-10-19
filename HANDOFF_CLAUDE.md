# HANDOFF_CLAUDE.md — Misión para la siguiente sesión (Claude)

**Actualización 2026-10-19:** este encargo conserva el contexto histórico.
El relevo operativo actual, válido para cualquier modelo, está en
`ROADMAP_RELEVO_COMBATE.md` §10/§11 y `R0_ESTABILIDAD.md`: leerlos antes de
usar los estados/comandos antiguos. R0-B corregido, probado y publicado en
v0.2.1; R0-C sin atribución causal definitiva.121tests y matriz del ZIP3/3 PASS.
No afirmar cierre global de R0.

> **Destinatario:** la instancia de Claude que retoma este proyecto para
> iteraciones de pulido/mejora.
> **Objetivo doble:** (A) dejar el juego funcional **de extremo a extremo** y
> (B) construir un **mod de combate renovado** (el combate original de Final
> Bout es muy criticado), usando ingeniería inversa sobre el propio disco y
> tomando `guimaraf/plusalpha-recomp` (Street Fighter EX Plus Alpha) como
> **referencia conductual**, nunca como transplante de motor.
> **Entregable final de Claude:** un `.md` de informe (`INFORME_CLAUDE.md`) con
> todo lo hecho, evidencia y límites. **No hagas commit ni push**; de eso nos
> encargamos nosotros.

Antes de tocar nada, lee en este orden: `MEMORY.md`, `AGENTS.md`,
`PLAN_SOLUCION_CRASH_Y_COMBATE.md`, `summary.md`, y el `CLAUDE.md` del
framework (`psxrecomp/CLAUDE.md`). Este documento **no reemplaza** las reglas
del framework; las hereda.

---

## 0. Reglas de trabajo (obligatorias)

1. **Precisión > recall.** Nunca declares una frontera de función sin prólogo
   real (`addiu sp,X,-N`) presente en `executed_pcs`. Una función mal compilada
   es fatal.
2. **No editar código generado** (`generated/`). El fix va en el recompilador.
3. **No `fprintf`/logs ad-hoc.** Inspecciona por el debug server TCP (4370) o por
   el heartbeat/reporte existentes. Regla absoluta del framework.
4. **No adivinar direcciones ni offsets.** Sin evidencia reproducible (captura,
   traza, oracle) no hay hook.
5. **El `game.toml` fuente es la verdad.** No edites a mano
   `build-release/game.toml`.
6. **No dejes instancias del juego vivas** (contienden por el puerto 4370 y los
   JSON de captura → crashes fantasma).
7. **No publiques** ROMs, BIOS retail ni snapshots de overlay (llevan bytes del
   disco).
8. **Regla -1 del framework:** el core fiel primero; los shims por juego son
   legítimos solo en la fase de enhancement, no para fingir fidelidad.
9. **No hagas commit/push.** Entrega cambios y el informe; nosotros commiteamos.

---

## 1. Estado de partida (verificado 2026-10-03)

- Release `v0.1.1` publicada y actualizada in situ (asset
  `dbfb-0.1.1-setup-host-win64.zip`, SHA-256
  `5c74dbaff2744ace0396ba1be38b4a00982cb803f1d0824b6a6b24d625d23f53`).
- La secuencia **Piccolo vs Goku → Piccolo vs Little Goku Super Saiyan** pasó
  una prueba manual sin cuelgue (2026-09-26). Es la única secuencia confirmada;
  **no** es garantía universal.
- El playtest estable seguía casi todo **interpretado**
  (`disp_native=0`, `disp_interp=1.618.550`): el resultado no vino de DLLs
  nativos nuevos.
- La recuperación del callback IRQ vacío está compilada y hay contador
  (`empty_irq_callback_returns`, hoy `not-recorded`) en heartbeat/reporte.
- `python tools\verify_offline.py` pasa. `psxrecomp` está en `7d70880d`
  (`rework-master`, ahead 5, 4 archivos modificados sin commit).

**Pendientes abiertos:** causalidad del fix sin confirmar; cobertura nativa del
combate; retrato del rival/pantalla negra en el 2º combate; sombras 3D; multi-
región; higiene de git.

---

## 2. Entorno y comandos

- **Jugar/capturar:** `play_session.cmd` o `INICIAR_FINAL_BOUT_NATIVO.bat`
  (fail-fast activo). Fallback: `INICIAR_FINAL_BOUT_SEGURO.bat`
  (`PSX_FAIL_FAST_UNKNOWN_DISPATCH=0`).
- **Resumen de la última sesión (sin lanzar):**
  `python tools\analyze_latest_session.py`.
- **Nativo vs intérprete en vivo:** `psxrecomp\tools\stall_report.py --port 4370 snap`.
- **Recompilar overlays:** `recompile_overlays.cmd` (equivale a
  `python psxrecomp\tools\compile_overlays.py --captures ... --game-toml
  game.toml --recompiler build-recompiler\psxrecomp-game.exe ... --gcc
  C:\msys64\mingw64\bin\gcc.exe`).
- **Rebuild del exe:** `cmake --build build-release --target psx-runtime`.
- **Verificación offline:** `python tools\verify_offline.py`.
- **Empaquetar:** `scripts/package_setup_release.sh build-release
  setup-host-win64 build-recompiler` (Git Bash no trae `zip`/`rsync`; ver
  `MEMORY.md` §6).
- **Compilador de shards:** `C:\msys64\mingw64\bin\gcc.exe`. Toolchain final:
  `...\retcomm\toolchains\cmake-clang-v1\1.0.14`.

---

## 3. FASE A — Juego funcional de extremo a extremo

Cada tarea debe producir **evidencia** (artefactos, snapshots de debug server,
salida de `verify_offline.py`) y un resultado reproducible.

### A1. Línea base instrumentada
- Sesión nueva con `INICIAR_FINAL_BOUT_NATIVO.bat`; jugar boot → menús → varios
  combates → salir normal.
- Al cerrar: `analyze_latest_session.py` y registrar
  `empty_irq_callback_returns`, `unknown_dispatch_tail`, `interp_unsupported`,
  `automatic_freeze_dumps`, `fatal`, `disp_native/disp_interp`.
- **Criterio:** sin `psx_freeze_dump_*.json` nuevo, `fatal=null`,
  `midblock_count=0`, y el contador reportado (aunque sea 0).
- **Motivo:** cerrar la causalidad del fix y saber cuánto combate corre nativo.

### A2. Cobertura nativa real del combate
- Captura fresca del STEP40 y recompilación de overlays **con el archivo completo
  del disco** (no capturas truncadas; ver `MEMORY.md` §4).
- Confirmar con `stall_report.py` que el combate corre mayormente nativo
  (`dispatch_native` alto).
- **Criterio:** un combate completo con `disp_native` dominante y sin freezes.

### A3. Segundo combate
- Objetivo: retrato del rival visible y sin pantalla negra.
- Pista histórica: overlays de stage-2/menú-VS (`0x8006B000`, `0x80040000`,
  `0x80047000`, etc.) corriendo interpretados. Escanear prólogos válidos,
  declarar `[[overlays]]` y recompilar; nunca desde capturas truncadas.
- **Criterio:** 2º combate renderiza y es jugable de principio a fin.

### A4. Sombras 3D "como en la lejanía"
- Diagnóstico previo: problema de proyección de profundidad/Z del **port base**
  (aparece con widescreen OFF y PGXP off).
- Investigar parámetro/sitio en `psxrecomp` (PGXP, `ws_far_threshold`,
  `geometry_correction`) con el oráculo **Beetle** (`find_first_divergence`,
  `emu_read_ram`). Si no hay fix fiel, documentarlo como limitación con la
  comparación que lo demuestra.

### A5. Matriz de humo extremo a extremo
Probar y registrar: boot, launcher, menús, character select, ≥3 combates,
pausa, especiales, vuelo, rematch y cierre. Cada caso con su artefacto.
- **Criterio:** ningún caso cuelga ni crashea; los fallos visuales conocidos
  (si quedan) están documentados y acotados.

### A6. Mantener verde lo de release
- `verify_offline.py` pasa; el empaquetado sigue funcionando; el ZIP no incluye
  disco/BIOS retail. No rompas el flujo de release.

### A7. Multi-región (decisión, no necesariamente implementación)
- Hallazgo: EU+Spain son **code-identical** (52 bytes, tabla de idioma); USA es
  build distinta. Documenta la arquitectura elegida (1 exe con selección de ROM
  vs builds separadas) antes de implementar.

---

## 4. FASE B — Mod de combate renovado

### 4.1 Encuadre (leer antes de escribir código)

- El combate original es el problema central percibido por el usuario. La
  solución **recomendada y ya diseñada** es un **mod híbrido nativo**, no un
  motor nuevo desde cero: el juego sigue siendo dueño de render, animación,
  cámara, audio, colisión, IA y estado; el plugin observa y modifica solo en
  puntos de entrada verificados. Ver
  `FINAL_BOUT_RESPONSIVE_ARCHITECTURE.md` (copia en
  `..\DB Final Bout\tools\psxrecomp\docs\`).
- **`guimaraf/plusalpha-recomp`** es una referencia **conductual**, no un
  transplante: es un juego de lucha 2D (SLUS-00548) sobre el mismo framework.
  Sirve para estudiar **input buffering corto, confirmación de golpe legible,
  hit-stop contenido, encuadre de cámara predecible y reglas de
  ataque/recuperación**. Su modelo completo **no** se copia en el motor 3D de
  Final Bout sin activos, estados y datos de colisión equivalentes. Su framework
  es `guimaraf/psxrecomp-plusalpha` (PolyForm Noncommercial); respeta su
  licencia.
- **Disco de referencia del propio juego:** `disc/SLUS_004.93` y los overlays
  `STEP*.BIN` (el de combate es `STEP40.BIN`). Las fronteras verificadas del
  STEP40 ya están en `game.toml`. En `disc/` hay además
  `Street Fighter EX Plus Alpha (USA).bin` (material ajeno: oráculo conductual,
  nunca parte del build).

### 4.2 Tiers (no saltar pasos)

- **Tier 0 — Original:** features off, cero escrituras de gameplay. Caso de
  control de cada experimento.
- **Tier 1 — Instrumentación nativa (PRIMER ENTREGABLE):** solo lectura. Hooks en
  las fronteras verificadas del STEP40, pad muestreado y transiciones de flanco,
  y mapa de estructura de luchador. Sin logs ad-hoc: usar los rings/TCP
  existentes. Campos mínimos: frame y PC de entrada; pad y flancos; candidato a
  estructura de luchador con fuente/confianza; estado, animación y timer; posición,
  vida, ki; flags de ataque/impacto; inicio de ataque, hit, hit-stop y recuperación.
- **Tier 2 — Correcciones selectivas reversibles:** input buffer acotado;
  consumo más temprano del input ya muestreado (si la traza lo justifica); timers
  de recuperación/pausa usando los timers del propio juego; suavizado de cámara y
  márgenes de encuadre. Cada corrección es una feature independiente y
  desactivable.
- **Tier 3 — Reemplazo de reglas por costuras:** el plugin toma una regla
  concreta (reconocimiento de comandos, duración de hit-stop, selección de
  recuperación) y el resto sigue siendo del juego. Opera sobre las estructuras
  reales del guest o **falla cerrado**.
- **Tier 4 — Modo de combate alternativo (opcional, diferido):** solo si las
  trazas demuestran que el estado original no puede expresar lo deseado. Es un
  **modo separado**, nunca una mejora silenciosa. Requiere contrato
  determinista y serialización para netplay/save states. Aquí sí se puede tomar
  inspiración estructural de SFEX, adaptada a los activos/estados reales de
  Final Bout.

### 4.3 Integración técnica (concreta)

1. **Plugin confiable** (código nativo enlazado en el target de Final Bout, no
   cargado desde un `.psxmod`). Registro por constructor:
   ```c
   #include "mod_plugins.h"

   static void dbfb_responsive_vblank(void) {
       if (psx_mod_game_started()) { /* observación/escritura verificada */ }
   }
   static void dbfb_on_step40_entry(CPUState* cpu, uint32_t addr) {
       /* leer pad/estructura de luchador, emitir a rings/TCP */
   }
   PSX_MOD_CONSTRUCTOR(dbfb_register_responsive) {
       (void)psx_mod_register_vblank_plugin("dbfb.responsive", dbfb_responsive_vblank);
       (void)psx_mod_register_function_entry_plugin(
           "dbfb.responsive", 0x8006xxxxu, dbfb_on_step40_entry);
   }
   ```
2. **Hooks de entrada de función:** añade las direcciones verificadas del STEP40 a
   `[recompiler] mod_function_entry_funcs` en `game.toml`. El recompilador emite
   `psx_mod_function_entry(cpu, addr)` en esos inicios; el intérprete dirty-RAM y
   el preámbulo de overlays también lo disparan, así que el hook funciona tanto
   en ruta nativa como interpretada.
3. **Manifest del mod:** crea
   `mods/preloaded/packages/dbfb.responsive/<version>/manifest.toml`
   (formato v6) con features independientes, `default_enabled = false`, y la
   selección del plugin por id (`[[plugin]] feature = "..." id = "dbfb.responsive"`).
   Revisa `psxrecomp/docs/MOD_PACKAGES.md` y usa
   `PRELOADED_MODS_DIR` en `psxrecomp_add_game_runtime(...)` si aún no está.
4. **Fuente del plugin en el build:** añade el `.c` del plugin a las fuentes del
   target (mecanismo `EXTRAS_SOURCES`/`CODEGEN_SETUP_SOURCES` de
   `psxrecomp_add_game_runtime`, forwardado a `psxrecomp_add_runtime_target`).
   Sigue el ejemplo real de TombaRecomp (su `CMakeLists.txt` y `src/mods/`);
   el README del framework (§ "Trusted game code") lo documenta.
5. **Comprimir toda escritura de gameplay** en features independientes,
   documentando dirección, dueño, ancho y restauración. `Original` no escribe.

### 4.4 Catálogo de features propuesto

| Feature | Dueño | Puerta |
|---|---|---|
| `responsive-input` | Plugin nativo | Existe traza input→estado |
| `input-buffer` | Plugin nativo | Ventana de lectura de comando medida |
| `recovery-tuning` | Plugin nativo | Mapa de timers de animación verificado |
| `impact-readability` | Plugin/datos | Flags de hit-stop/impacto mapeados |
| `camera-framing` | Plugin nativo | Función de cámara y límites mapeados |
| `combat-rules-experimental` | Sub-sistema de reglas | Una regla aislada y reproducible |
| `alternate-combat-mode` | Sub-sistema nuevo | Existe contrato de estado determinista |

El paquete por defecto con **todo desactivado**. Un preset `Responsive` activa el
subconjunto validado; `Original` no selecciona ningún plugin de gameplay.

### 4.5 Criterios de aceptación del mod

- `Original` no produce escrituras de gameplay.
- Cada escritura de `Responsive` tiene dirección, dueño, ancho y restauración
  documentados.
- Una revisión equivocada de exe/overlay rechaza la activación.
- Un hook fallido o desconocido desactiva **solo su feature** y reporta por la
  vía de diagnóstico existente.
- Entrada idéntica repetida produce traza y estado idénticos.
- La matriz de humo (todos los modos, parejas, vuelo, especiales, pausa)
  sobrevive.
- El netplay sigue siendo determinista o la feature se marca **offline-only**.

---

## 5. Entregable obligatorio de Claude: `INFORME_CLAUDE.md`

Al terminar (o al cerrar cada iteración), crea/actualiza en la raíz del proyecto
`INFORME_CLAUDE.md` con:

1. **Resumen ejecutivo:** qué se logró y qué no, en 5–10 líneas.
2. **Estado de partida vs estado final** (comandos + salidas).
3. **Cambios por archivo:** ruta, qué y por qué (no pegues diffs gigantes).
4. **Evidencia:** artefactos, métricas (`empty_irq_callback_returns`,
   `disp_native`, `unknown_dispatch_tail`, etc.), capturas y comparaciones con
   Beetle.
5. **Mod de combate:** features implementadas, direcciones/offsets verificados,
   restauración, y qué tiers quedaron completos.
6. **Cómo verificar** paso a paso (comandos exactos).
7. **Incógnitas y límites:** lo que **no** se pudo probar y por qué. Nada de
   "probablemente"; escribe "no confirmado".
8. **Recomendaciones de siguientes pasos.**
9. **Lista de archivos sin commitear** para que nosotros preparemos el commit.

No commitees ni hagas push. Deja el árbol listo y el informe escrito.

---

## 6. Prohibiciones explícitas

- No transplantar el motor 2D de SFEX en Final Bout.
- No editar `generated/`.
- No usar `fprintf`/logs ad-hoc.
- No compilar overlays desde capturas truncadas.
- No editar a mano `build-release/game.toml`.
- No prometer estabilidad universal: evidencia por secuencia probada.
- No publicar assets con bytes de disco/BIOS.
- No commitear ni publicar release por tu cuenta.

---

## 7. Definición de "hecho" (global)

El trabajo no está terminado hasta que:

1. El juego se juega de principio a fin en la matriz de humo (Fase A) con
   evidencia y sin cuelgues nuevos.
2. El combate corre mayormente nativo y el 2º combate renderiza completo.
3. Existe el mod de combate con al menos **Tier 1 (instrumentación)** completo y
   una primera feature de Tier 2 validada y desactivable.
4. `verify_offline.py` pasa y el flujo de release sigue sano.
5. `INFORME_CLAUDE.md` está escrito con evidencia y límites.

Cualquier desviación de este plan debe justificarse con evidencia en el informe,
no con conveniencia.
