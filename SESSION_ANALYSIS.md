# DBFinalBout — Registro y análisis de sesión

Flujo preparado para que **jugando una partida** se genere un registro completo
analizable: qué overlays se cargaron, dónde, qué PCs se ejecutaron, y si hubo
crashes. Todo listo para que el agente / el desarrollador lo inspeccione offline.

---

## 1. Jugar (genera el registro)

Doble clic en **`play_session.cmd`** (o ejecutarlo desde terminal).

Qué pasa:
- Se abre la ventana de la consola con instrucciones
- Se lanza `build-release\DBFinalBout_Recompiled.exe --game game.toml --debug-port 4370`
  **en primer plano** (la ventana de la consola espera hasta que cierres el juego)
- Se abre el **launcher** del juego: pulsa **Play** para entrar al juego
- El script espera a que cierres el juego y luego muestra qué artefactos quedaron

> **Widescreen: déjalo APAGADO (default) en esta sesión.** Queremos una línea
> base limpia (vanilla) para capturar overlays y medir estabilidad. El
> widescreen se probará en el paso 4, tras recompilar los overlays.

**Qué jugar para máxima cobertura:**
1. Menús (título, select de personaje, opciones) → captura overlays de menú (STEP00-03/999)
2. Al menos **una pelea completa** → captura el overlay de batalla **STEP40**
   (el que contiene el render funnel con los culls `0x200`/`0x1E0`)
3. Si se congela: perfecto, eso queda registrado en el freeze dump
4. Cerrar el juego cuando termine

> El script espera a que el juego se cierre y luego muestra qué artefactos
> quedaron.

---

## 2. Analizar el registro

Tras jugar:

```bat
python tools\analyze_session.py
```

Genera un digest con:
- Overlays capturados (dirección, CRC, nº de PCs ejecutados)
- Qué overlay es el funnel de pelea (firma widescreen `0x200`/`0x1E0`)
- Freeze dumps presentes (signatura de crash: wedge_kind, current_func,
  last_store_pc, in_exception)
- El comando `compile_overlays.py` recomendado

**Análisis en vivo adicional** (con el juego corriendo, debug server 4370):

```bat
python ghidra_proj\probe_ram.py --port 4370 ...   REM lecturas puntuales
python ghidra_proj\ram_dump.py    --port 4370 ...   REM volcado de RAM
python psxrecomp\tools\stall_report.py --port 4370 snap
python psxrecomp\tools\stall_report.py --port 4370 run --secs 60
```

---

## 3. Recompilar overlays (estabilidad + widescreen)

Cuando `overlay_captures.json` exista:

```bat
recompile_overlays.cmd
```

- Compila cada overlay capturado a DLL nativa (gcc) en
  `build-release\cache\<game-id>\gcc\win-x64\cg<N>_<hash>\*.dll`
- El runtime carga esos DLLs automáticamente en la siguiente ejecución
  (sin intérprete dirty-RAM → menos crashes, más velocidad)
- Los culls de widescreen (`screen_w_imms=["0x200"]`,
  `screen_h_imms=["0x1E0"]` en `game.toml`) se hornean en el código nativo
  de los overlays en esta compilación

Si el recompilador está desactualizado (staleness guard):

```bat
cmake --build build-recompiler --target psxrecomp-game
```

---

## 4. Verificar

Vuelve a lanzar `play_session.cmd` y comprueba:

1. **Estabilidad**: sin freeze dumps nuevos en menús/combate
2. **Widescreen** (tras el paso 3): activa el mod widescreen (16:9) en el
   launcher y mira si la pelea revela más mundo horizontal (culls ensanchados)
3. **Interpretación**: `stall_report.py snap` muestra `dispatch_native` alto /
   `dispatch_interp_fallback` bajo

---

## Resumen de archivos preparados

| Archivo | Qué hace |
|---|---|
| `play_session.cmd` | Lanza el juego con registro de sesión y espera a que cierres |
| `tools/analyze_session.py` | Analiza los artefactos de la sesión (offline) |
| `recompile_overlays.cmd` | Recompila los overlays capturados a código nativo |
| `game.toml [runtime]` | `overlay_cache`, `overlay_capture_history`, `overlay_capture_persist_dir`, `debug_port=4370` |
| `game.toml [widescreen.cull]` | `screen_w_imms=["0x200"]`, `screen_h_imms=["0x1E0"]`, `precise_nclip=true` |
| `psxrecomp/docs/COMPILING_OVERLAYS.md` | Documentación del pipeline de overlays |

---

## Notas

- `overlay_captures.json` contiene instantáneas del código del juego (de TU
  disco legal). **No se sube a GitHub** — está en `build-release/` (gitignored).
- Los overlays son MODE2 scatter-load: solo se capturan correctamente en
  tiempo de DMA (jugando), no extrayendo el disco. Por eso este flujo existe.
- Referencia: `Bloody Roar 2\WIDESCREEN.md` — mismo pipeline, mismo funnel de
  culling `0x200/0x1E0` (BR2 lo validó con `squash=true`; Final Bout usa
  `squash=false` porque su lógica lee SXY).
