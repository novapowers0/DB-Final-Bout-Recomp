# AGENTS.md — DBFinalBout Recomp

Guía para cualquier sesión (agente o humano) que retome este proyecto. Léela entera
antes de tocar nada: contiene el modelo mental, el estado real del trabajo, y los
comandos correctos. Complementa (no reemplaza) a `summary.md`, `ANALISIS_CRASHES.md`
y `SESSION_ANALYSIS.md`.

---

## 1. Qué es esto

Puerto nativo para PC de **Dragon Ball GT: Final Bout** (SLUS-00493, USA) usando
`mstan/psxrecomp`. Objetivo: estabilizar el recompilador (eliminar los "freezes" de
combate) y, después, soporte multi-región (USA/EU/Spain en un único `.exe`
plug-and-play, sin "Generate & build").

**El problema histórico:** el juego entraba en combate y se quedaba "congelado".
Esos congelamientos **no eran crashes nativos** sino **freezes del intérprete**
(`wedge_kind: spin_freeze/fatal`, `dispatch_count=0`, `dirty_ram_insns` 7-13M,
`in_exception=1`). La causa: todo el gameplay vive en **overlays STEP\*.BIN**
cargados en runtime, y sin cache nativo ese código corría 100% interpretado.

Estado actual del objetivo principal: **el combate ya se juega completo** (un
combate de inicio a fin, sin freeze). Quedan bugs visuales en combate (ver §8).

---

## 2. Principio rector (crítico)

> **Precisión > recall.**

En psxrecomp, una función **omitida** es segura (cae al intérprete, correcto pero
lento). Una función **mal compilada** es fatal (corrompe estado y congela). Al
declarar fronteras de overlay, usa **solo** prólogos reales de función
(`addiu sp,sp,-N`) que además aparezcan en `executed_pcs`. No "adivines" seeds.

---

## 3. Entorno / toolchain

- **Sistema:** Windows (PowerShell 5.1). Shell por defecto del agente.
- **MSYS2 gcc:** `C:\msys64\mingw64\bin\gcc.exe` (compila los shards DLL de overlays
  y el recompilador). Añadir `C:\msys64\mingw64\bin` al PATH si algo falla en silencio.
- **Toolchain pack (clang/llvm_mingw)** usado para el build final del exe:
  `C:\Users\javie\.local\share\retcomm\toolchains\cmake-clang-v1\1.0.14`.
- **Python:** se invoca `python` directamente (scripts de `psxrecomp/tools/`).
- **Dependencia local de libchdr** (offline): `deps/libchdr`. Persistida en
  `build-release\CMakeCache.txt` vía `FETCHCONTENT_SOURCE_DIR_PSX_LIBCHDR` — **no
  perder** ese override o el "Generate & rebuild" intentará fetch de red.

---

## 4. Arquitectura del juego y del recompilador (modelo mental)

### 4.1 El juego
- El **EXE base** (`disc/SLUS_004.93`, 190464 bytes, text `0x2E000`) contiene solo
  el boot/menú inicial. Se recompila AOT (seeds en `seeds/ghidra_funcs.txt`).
- **Todo el gameplay** (menús, VS, combate) vive en **overlays** `STEP*.BIN`
  (`STEP00/01/02/03/40/999`) que el juego DMA a RAM en runtime.
- El overlay de combate es **STEP40** (~442 KB, un archivo con varios miembros de
  código). El miembro de combate (file offset `0x22060`, size `0x12354`) se DMA a
  RAM en base **`0x80060000`** y abarca ~60 KB (hasta `0x80072000+`). El runtime
  ancla el capture en `0x80060000` o `0x80068000` según qué páginas dirty vea
  primero, por eso hay DLLs para AMBAS bases (ver §6).

### 4.2 Cómo se recompilan los overlays (pipeline)
1. **Captura en runtime:** con `[runtime] overlay_cache = true`, el runtime registra
   cada overlay DMA'd a RAM en `build-release/overlay_captures.json` (load_addr,
   bytes, crc32, `executed_pcs`). El addendum histórico va a
   `overlay_captures.addendum.jsonl`.
2. **Recompilación offline:** `compile_overlays.py` clasifica cada región capturada.
   Si una región tiene roots (seeds) válidos la compila a un **DLL** en
   `build-release/cache/SLUS-00493/gcc/win-x64/cg<codegen>_.../`.
3. **Carga en runtime (clave):** el exe **no se reconstruye** para los overlays.
   En runtime, el `overlay_loader.c` **escanea el cache y registra cada DLL como
   "candidate"** (con su `load_addr`, `crc_code` de los bytes de código y su
   `.ranges`). Cuando el juego recarga un overlay, si el CRC del código RAM coincide
   con el de un candidate → ejecuta **nativo** (LoadLibrary); si no → **intérprete**.
   Por eso: **cambiar/regenerar un DLL del cache NO requiere recompilar el exe**.

### 4.3 El clasificador y las regiones "data-only"
`compile_overlays.py` rechaza como "data-only" las regiones cuyo `function_entry_pcs`
(vía `game.toml` `[[overlays]]`) está vacío o cuyos dispatch seeds no son inicios de
función. Eso deja ese overlay interpretado. La solución ya usada: **escanear los
bytes capturados buscando prólogos de función en `executed_pcs`** y declararlos en
`game.toml` bajo `[[overlays]]` con `load_addr` + `function_entry_pcs` (sin
`bytes_crc` para robustez ante direcciones variables).

---

## 5. Estructura de directorios (solo lo relevante)

```
DBFinalBoutRecomp/
├─ game.toml              # FUENTE de la config (overlays, widescreen, runtime)
├─ build-release/         # Árbol de build DESPLEGADO (lo que corre el usuario)
│  ├─ DBFinalBout_Recompiled.exe      # exe base (estable)
│  ├─ DBFinalBout_Recompiled_pgxp.exe # variante PGXP (precisión de vértices)
│  ├─ game.toml           # config desplegada (debe sincronizarse con el fuente)
│  ├─ disc.cfg            # apunta a la ROM USA (ruta absoluta)
│  ├─ overlay_captures.json          # capturas de overlays de la última sesión
│  ├─ overlay_captures.addendum.jsonl
│  └─ cache/SLUS-00493/gcc/win-x64/cg10_<codegen>_<config>_f0/
│     # DLLs nativos de overlays + sus .ranges; cambia al cambiar el código
├─ build-recompiler/      # psxrecomp-game.exe / psxrecomp-bios.exe (el recompilador)
├─ psxrecomp/             # el framework (submódulo): recompiler/, runtime/, tools/
│  └─ tools/compile_overlays.py      # la herramienta de recompilación de overlays
├─ seeds/ghidra_funcs.txt # seeds del EXE base
├─ disc/                  # ROM + boot EXE (USA); también hay un SFEX+ ajeno, ignorar
├─ summary.md             # registro cronológico de sesiones (LEER)
├─ ANALISIS_CRASHES.md    # diagnóstico completo de los crashes + fix (§7) (LEER)
└─ SESSION_ANALYSIS.md    # análisis de sesión
```

**Nota:** en `disc/` hay además un `Street Fighter EX Plus Alpha (USA).bin` — es
basura ajena al proyecto, **ignorar**.

---

## 6. Los bugs y fixes ya aplicados (historia esencial)

- **Crash 0xC00000FF (arranque):** junction NTFS rota a un archivo + lanzador
  `filesystem_error`. Fix: hard link a la ROM real. (17/08) — resuelto.
- **Bug A — miscompilación nativa `0xD7FFFFAC`:** fallo de *load-delay*
  cross-fragment en `code_generator.cpp` (defer_load declara `psx_ldd_<addr>` en el
  scope del bloque) + `full_function_emitter.cpp` (flush solo del mismo fragmento).
  Verificado: todos comparten hash codegen `0x5ddbd2c4`. (18-19/08) — resuelto.
- **Bug B — config desincronizado:** `build-release/game.toml` tenía
  `overlay_cache=false`. Fix: sincronizar desde el fuente. (19/08) — resuelto.
- **Fix del combate STEP40 (19/08, lo importante):** los dispatch seeds del capture
  NO eran inicios de función (interiores). Escaneados prólogos `addiu sp,sp,-N` en
  `executed_pcs` → **35 fronteras** declaradas en `game.toml` para `0x80068000` →
  `00068000_05DDBCB5.dll` (330 KB, 26 funciones). El combate ya compila nativo y se
  juega completo. Ver `ANALISIS_CRASHES.md §7`.
- **Combate 100% nativo (21/08, cobertura completa):** el capture 18/08 solo cubría
  una ventana de 28 KB. Uniendo las páginas capturadas el 19/08
  (0x80060000..0x8006F003) y el propio STEP40.BIN (miembro file `0x22060` → RAM
  base `0x80060000`, size `0x12354`, bytes verificados idénticos 1:1 al capture)
  se escanearon los prólogos REALES del miembro completo. Resultado:
  `[[overlays]]` `0x80060000` con **89 fronteras** (35 conocidas + 56 laxas
  `addiu sp,X,-N` en executed_pcs) → `00060000_21D7E1FC.dll` (943 KB, **101
  funciones**) y variante `0x80068000` (77 funciones) → `00068000_CB735076.dll`.
  El walk de compile_overlays descubrió además jal-targets adicionales.
- **Menú/VS nativo (19/08, último cambio):** regiones `0x8003F000` (18 prólogos) y
  `0x80047000` (4 prólogos) se saltaban como "data-only" → el VS/transición corría
  interpretado. Añadidas a `game.toml` y compiladas al cache
  (`0003F000_5339951C.dll`, `00047000_DCD22276.dll`, `00056000_61856E3F.dll`).
- **Perfil visual seguro (09/09):** renderer software, 4:3, nearest, 1x y sin
  correcciones PGXP/geométricas. La oferta/adaptación widescreen y el culling
  automático están desactivados hasta confirmar la línea base visual.

---

## 7. Estado actual (verificado)

### Confirmado históricamente
- Boot, launcher, menús, audio y un combate completo funcionaron en una sesión
  anterior con el pipeline de overlays activo.
- El overlay de combate llegó a compilarse con 101 funciones en la variante
  `0x80060000` y 77 en `0x80068000`. Los nombres/hash de esas sesiones son
  históricos; el cache actual debe identificarse siempre con
  `python tools/verify_offline.py`.

### Confirmación funcional más reciente
- El usuario completó cuatro combates con la generación anterior de esta build.
  El heartbeat de esa sesión registra 10.518 frames, `fatal=null`, cero dumps
  automáticos y ejecución hasta `0x8006B5F8`.
- La sesión actual de código posterior a ese playtest fue recompilada offline
  con Vulkan/netplay; debe repetirse el smoke test antes de considerar esas
  capacidades funcionalmente confirmadas.

### Bugs visuales pendientes en combate (reporte del usuario, 19/08)
1. **Sombras 3D defectuosas** ("como en la lejanía") — diagnosticado como problema
   de **proyección de profundidad/Z del PORT BASE** (no del widescreen). Aparece con
   widescreen OFF y PGXP off. Ver `summary.md` sesión 18/08.
2. **En el 2º combate no aparece el retrato del rival** + **carga en negro** (al
   pasar al 2º combate, el personaje seleccionado por el usuario no se mostraba,
   solo el rival). *Hipótesis en curso:* la pantalla VS/transición (regiones
   `0x8003F000`/`0x80047000`) corría interpretada; **ya se compiló nativa** — falta
   re-testear.
3. **Widescreen:** ahora ofrece 16:9/adaptive como presentación. Sigue sin
   activar `squash`, `auto_screen_x`, `auto_backdrop` ni `precise_nclip`; el
   FOV/culling real queda pendiente de un test separado.

---

## 8. Multi-región (USA/EU/Spain en 1 exe) — hallazgo clave

Se analizaron los boot EXEs de las 3 ROMs (parseo ISO9660 de `DB Final Bout\*.bin`):

- **EU vs Spain: solo 52 bytes difieren** (de 190464) — todos **valores numéricos de
  la tabla de idioma** (offsets 116008-116094). ⇒ **Son code-identical** (mismo
  código MIPS, cambia el idioma). Un solo build sirve para ambos, como Buu's Fury.
- **USA: 116167 bytes difieren** de EU/Spain ⇒ es una **build distinta** (región
  NTSC) y necesita su propia recompilación.

Implicación: el plan "1 exe, 3 regiones" es viable porque EU+Spain son triviales de
unificar; USA es el caso separado. **Requiere decisión del usuario sobre la
arquitectura** (no implementada aún).

---

## 9. Flujo de trabajo (comandos)

> Regla de oro: **el fuente `game.toml` es la verdad.** El `build-release/game.toml`
> desplegado se sincroniza con él (manualmente o reconstruyendo el exe, que lo copia
> vía POST_BUILD `copy_if_different`). **NO editar a mano el desplegado.**

### A. Jugar / capturar una sesión
```
play_session.cmd
```
Abre el exe con `--game game.toml --debug-port 4370`. Juega (menús + al menos un
combate). Al cerrar, deja `overlay_captures.json` actualizado.

### B. Recompilar overlays a nativo (después de jugar)
```
recompile_overlays.cmd
```
Equivale a:
```
python psxrecomp\tools\compile_overlays.py --captures build-release\overlay_captures.json \
  --game-toml game.toml --recompiler build-recompiler\psxrecomp-game.exe \
  --runtime-include psxrecomp\runtime\include --project-root psxrecomp \
  --out-dir build-release\cache --gcc C:\msys64\mingw64\bin\gcc.exe
```
El runtime lo recoge **automáticamente en el siguiente arranque** (sin recompilar el
exe). Para validar sin tocar el cache real usa `--check` (preflight a temp).

### C. Declarar fronteras de un overlay nuevo (método probado)
1. Captura con `play_session.cmd` (o ejecuta el exe y juega hasta tocar la zona).
2. Inspecciona `overlay_captures.json` (load_addr, executed_pcs).
3. Escanea los bytes capturados buscando prólogos `addiu sp,X,-N` (rt=29, inmed.
   negativo; X=sp o fp — el criterio del framework exige rs=rt=29, pero Final
   Bout usa prólogos `addiu sp,fp,-N`, así que usa el LAXO) que además estén en
   `executed_pcs` (mismo criterio del fix STEP40).
4. Añade un bloque `[[overlays]]` en `game.toml` con `load_addr` + `function_entry_pcs`.
5. Recompila esa región: `compile_overlays.py ... --only-region 0x<load> --force`.
6. Sincroniza `build-release/game.toml`.

### D. Reconstruir el exe (solo cuando cambias código C/C++ del runtime o config de código)
```
cmake --build build-release --target psx-runtime
```
(Esto además refresca `build-release/game.toml` desde el fuente.)

---

## 10. Diagnóstico cuando algo falla

- **Freeze/crash en runtime:** revisa `build-release/psx_freeze_dump_*.json`
  (`wedge_kind`, `dispatch_count`, `overlay_loader.active`, `in_exception`).
- **¿Una región corre interpretada?** En `compile_overlays.py --check` verás
  `SKIP: no walk-root seeds (data-only region)` para esa región → necesita
  fronteras declaradas (ver §9C).
- **¿El DLL nativo se está usando?** `stall_report.py --port 4370 snap`
  (`dispatch_native` alto / `dispatch_interp_fallback` bajo).
- **¿El exe no carga un DLL nuevo?** Confirma que el DLL está en el cache con el
  `crc32` que coincide con los bytes RAM del overlay (el loader empareja por CRC).

---

## 11. Siguientes pasos (priorizados)

1. **Re-testear una pelea** con el combate completo nativo: `stall_report.py --port
   4370 snap` debe mostrar `dispatch_native` alto y `dispatch_interp_fallback` bajo
   (antes ~78128 vs ~1043655). Confirmar también el 2º combate (retrato rival +
   sin pantalla negra) y el widescreen 16:9 (ahora ofertado en el launcher).
2. **Sombras 3D defectuosas:** es del port base (proyección Z). Investigar a fondo
   si hay parámetro/sitio en `psxrecomp` (PGXP, `ws_far_threshold`,
   `geometry_correction`) que lo corrija — o documentar como limitación del port.
3. **Multi-región:** decidir arquitectura de "1 exe, 3 regiones" (USA separada;
   EU+Spain code-identical). Ver `ANALISIS_CRASHES.md §9` y las notas de Buu's
   Fury / Bloody Roar 2 como referencia.
4. **Cobertura nativa restante:** aplicar el mismo escaneo de prólogos a otras
   regiones de menú que aún se saltan (`0x80023000`, `0x8002A000`, `0x8004C000`,
   `0x80050000`, `0x8005F000`) si causan problemas.
5. **Widescreen real:** ya configurado stretch-only + offer 16:9/adaptive
   (21/08). El cull `auto_screen_x` (0x200/0x1E0) ahora aplica en combate (STEP40
   nativo). Testear: 16:9 en combate, menús (pillarbox), y decidir si `squash=true`
   (FOV real) es viable pese al riesgo SXY — NO recomendado.
6. **Framework más nuevo (informativo, 21/08):** los recomps recientes
   (TechnicallyComputers/TwistedMetal4Recomp, /Street-Fighter-Alpha-3-Recomp,
   /MastersOfTerasKasiRecomp) usan `mstan/psxrecomp` `feat/rbengine` a9a61b4 (muy
   posterior a nuestro f2bb059). SF3/TerasKasi ponen TODO el gameplay en el text
   principal (sin overlays). TerasKasi ISSUES.md documenta fixes de runtime
   (interp→native handoffs, `native_handoffs` 15.8k). Una migración del submódulo
   a a9a61b4 es posible pero GRANDE y arriesgada (pierde los mods nova-mods,
   rehacer game.toml/overlays) — no hacerla salvo que el rendimiento lo exija.

### Verificación offline obligatoria

Antes de entregar o cambiar el cache de overlays, ejecutar:

```
python tools/verify_offline.py
```

Comprueba que ambos `game.toml` coinciden, que el perfil conserva software como
renderer por defecto, ofrece Vulkan y presentación 16:9/adaptativa sin activar
el culling experimental, que existen ambos runtimes y que el cache actual
contiene diez DLLs con sus `.ranges`. No inicia el juego.

Para resumir una sesión ya terminada sin lanzar nada:

```
python tools/analyze_latest_session.py
```

### Netplay sintético

El build aislado `build-net-tests` prueba LAN/direct-IP sin abrir el juego:

```
cmake -S psxrecomp/lib/recomp-net -B build-net-tests -G Ninja -DRNET_ENABLE_ICE=OFF -DRNET_BUILD_TESTS=ON
cmake --build build-net-tests
build-net-tests/session_state_test.exe
```

La prueba de estado crea dos peers UDP localhost y verifica handshake,
admisión y transferencia de estado. `rollback_episode_test` contiene cuatro
expectativas antiguas incompatibles con su propio host de filas válidas; no usar
ese fallo aislado como motivo para cambiar el protocolo.

---

## 12. Higiene / avisos

- **No editar** `build-release/game.toml` a mano (viene del fuente).
- **No perder** el override `FETCHCONTENT_SOURCE_DIR_PSX_LIBCHDR` del CMakeCache.
- **No crear junctions a archivos** con `mklink /J` (solo directorios); usa hard
  link (`mklink /H`) o copia. Eso fue la causa del crash 0xC00000FF.
- `disc/Street Fighter EX Plus Alpha (USA).bin` es basura ajena — ignorar.
- Si aparece `psx_freeze_dump_*.json` **nuevo**, es señal de que una región sigue
  interpretada o mal compilada; investigar antes de seguir.
- Al final de cada sesión, actualiza `summary.md` (y este AGENTS.md si cambian
  comandos/estado clave).
