# AGENTS.md — DBFinalBout Recomp

**Continuación vigente (2026-10-19):** leer `R0_ESTABILIDAD.md` y
`ROADMAP_RELEVO_COMBATE.md` §10 para
el roadmap pendiente, estado más reciente y encargo transferible a otro modelo.
Las secciones históricas de este archivo no sustituyen ese registro operativo.

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

Estado del proyecto (2026-09-26): los submódulos se actualizaron y la build
Release volvió a compilar correctamente. Tras reproducir el bucle de excepción
anterior se añadió una recuperación estrecha para la ranura vacía del callback
IRQ. El usuario confirmó un combate Piccolo vs Goku y el paso al segundo combate
Piccolo vs Little Goku Super Saiyan. La sesión cerró normalmente sin fatal,
unknown dispatch ni RI mid-block. El contador `empty_irq_callback_returns` queda
ahora en heartbeat/reporte para confirmar el uso de esa ruta en futuras sesiones.
No prometer estabilidad universal; continuar observando al ampliar el juego.

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
  `C:\Users\javie\.local\share\retcomm\toolchains\cmake-clang-v1\1.0.14`. Sus
  binarios `x86_64-w64-mingw32\bin` aportan `libc++.dll` y `libunwind.dll` que
  el packager necesita copiar junto a `psxrecomp-game.exe`.
- **Python:** se invoca `python` directamente en PowerShell; en el **Git Bash**
  hay que usar la ruta real `C:\Python314\python.exe` (el alias de Windows Store
  resuelve `python3` en PowerShell pero no dentro de Git Bash, y el empaquetador
  llama `python3`). Para scripts bash del packager, define antes
  `python3(){ /c/Python314/python.exe "$@"; }`.
- **Empaquetado de release (setup-host):**
  `scripts/package_setup_release.sh build-release setup-host-win64 build-recompiler`
  → escribe `dist/dbfb-<VERSION>-<tag>.zip`. El shell del packager necesita
  `zip`, `rsync` y `python3`, pero el Git Bash de este equipo **no trae `zip` ni
  `rsync`**. Alternativas para la compresión: `C:\Program Files\7-Zip\7z.exe` o
  `Compress-Archive` de PowerShell. Si el packager falla con
  `required DLL missing for psxrecomp-game.exe: libc++.dll`, fija
  `PSXRECOMP_RUNTIME_BIN_DIR` al bin de mingw del toolchain clang
  (`.../1.0.14/x86_64-w64-mingw32/bin`).
- **Submódulos fijados (2026-09-26):** `psxrecomp` `7d70880d` (fork
  `rework-master`, con upstream master integrado), `recomp-ui` `01bff947` y el
  submódulo anidado `psxrecomp/lib/recomp-net` `c2338c63`.
- **Validación de build del seguimiento RI (2026-09-26):**
  `ninja -C build-release DBFinalBout_Recompiled.exe` compiló y enlazó con
  Ninja/clang; el target `ninja -C build-release` también enlazó la variante
  PGXP. `python tools\\verify_offline.py` pasa. La prueba manual de transición
  Little Goku vs Piccolo sigue pendiente; compilación correcta no equivale a
  validación in-game.
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

### Release v0.1.1 actualizado (2026-10-03)
- La release existente `v0.1.1` (tag `bc69be7`, 0 descargas) se actualizó **in
  situ**: se reemplazó el asset con `gh release upload --clobber` y las notas con
  `gh release edit --notes-file`. No se creó un tag nuevo ni un borrador.
- Asset único: `dbfb-0.1.1-setup-host-win64.zip`, 33.060.246 bytes, SHA-256
  `5c74dbaff2744ace0396ba1be38b4a00982cb803f1d0824b6a6b24d625d23f53`. Contiene
  los runtimes normal/PGXP `0.1.1`, la recuperación del callback IRQ, el contador
  `empty_irq_callback_returns` y `mods/bundled`; **sin** imagen de disco ni dump
  retail de BIOS. `verify_offline.py` y la prueba de integridad del ZIP pasan.
- El paquete ahora incluye `baserom.md` y `mods/` (el script dejó de listar
  `launcher_assets`, que estaba vacío). Cambio inocuo; `mods/bundled` es
  necesario para el catálogo de mods.
- La secuencia confirmada (Piccolo vs Goku → Piccolo vs Little Goku SS) sigue
  siendo la evidencia; falta una sesión nueva con el contador para saber si la
  ruta de recuperación se ejecutó.

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

> El plan operativo detallado —incluida la fase de mod de combate— vive en
> `HANDOFF_CLAUDE.md`. Aquí solo el orden de alto nivel.

1. **Sesión nueva instrumentada** con `INICIAR_FINAL_BOUT_NATIVO.bat` (la
   secuencia de transición ya se confirmó sin cuelgue el 2026-09-26). Al cerrar,
   `python tools\analyze_latest_session.py` y comprobar
   `empty_irq_callback_returns` (hoy `not-recorded`), `unknown_dispatch_tail=0`,
   `interp_unsupported.midblock_count=0` y ausencia de `psx_freeze_dump_*`
   nuevos. Conservar los artefactos si algo falla. Ver
   `PLAN_SOLUCION_CRASH_Y_COMBATE.md` §3.2.
2. **Cobertura nativa real del combate:** el playtest estable seguía con
   `disp_native=0` / `disp_interp=1.618.550`. Recompilar el STEP40 completo con
   captura fresca y confirmar con `stall_report.py --port 4370 snap` que el
   combate corre nativo antes de tocar el combate.
3. **Sombras 3D defectuosas:** es del port base (proyección Z). Investigar a fondo
   si hay parámetro/sitio en `psxrecomp` (PGXP, `ws_far_threshold`,
   `geometry_correction`) que lo corrija — o documentar como limitación del port.
4. **Multi-región:** decidir arquitectura de "1 exe, 3 regiones" (USA separada;
   EU+Spain code-identical). Ver `ANALISIS_CRASHES.md §9` y las notas de Buu's
   Fury / Bloody Roar 2 como referencia.
5. **Cobertura nativa restante:** aplicar el mismo escaneo de prólogos a otras
   regiones de menú que aún se saltan (`0x80023000`, `0x8002A000`, `0x8004C000`,
   `0x80050000`, `0x8005F000`) si causan problemas.
6. **Widescreen real:** ya configurado stretch-only + offer 16:9/adaptive
   (21/08). El cull `auto_screen_x` (0x200/0x1E0) ahora aplica en combate (STEP40
   nativo). Testear: 16:9 en combate, menús (pillarbox), y decidir si `squash=true`
   (FOV real) es viable pese al riesgo SXY — NO recomendado.

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

---

## 13. Documentos de esta entrega (leer en este orden)

1. `MEMORY.md` — memoria durable y destilada: identidad del proyecto, lecciones
   que costaron sesiones, pins, comandos y prohibiciones. **Leer primero.**
2. `AGENTS.md` (este documento) — guía de arquitectura, pipeline y estado.
3. `HANDOFF_CLAUDE.md` — misión de la siguiente fase: (A) dejar el juego
   funcional de extremo a extremo y (B) construir un **mod de combate renovado**
   inspirado en `guimaraf/plusalpha-recomp` (Street Fighter EX Plus Alpha),
   usando el disco/EXE/STEP40 como referencia de ingeniería inversa.
4. `PLAN_SOLUCION_CRASH_Y_COMBATE.md` — diagnóstico del crash de transición y
   hoja de ruta del combate "Responsive Edition" (Tiers 0–4).
5. `summary.md` — registro cronológico de sesiones.

## 14. Material de referencia del combate

### Directriz vigente del producto (2026-10-19)

**Actualización posterior a release (§10):** R0-B corregido localmente en
`autocompile_poll_main`: sondeo de terminación de ambos trabajadores con espera
cero; `DONE` no implica hilo terminado. Test controlado fallaba antes/pasa después,
conservación de recursos y finalización única. 121tests OK; build normal/PGXP y
offline PASS; matriz final original600s/5combates, estándar300s/3, PGXP300s/2,
3/3 PASS. R0-C aún abierto: nuevo fallo instrumentado frame7236 con5,24s pared,
1,05s CPU, sampler0, antes de medir secciones. Ver `R0_ESTABILIDAD.md`; no atribuir
todos los cierres a R0-B. Secciones/CPU/ciclos en reporte; watchdog intacto.
`tools/combat_stability.py` aísla cada modo y valida el runtime, con `--build`
opcional para el candidato local. La v0.2.0 publicada NO contiene esta revisión.
Fuentes del submódulo modificadas sobre835f1902; no representar el pin limpio
como si incluyera los cambios locales. No tocar `github/` ajeno.

**Historial de publicación §9:** revisión visual del agente completada (transición real
2896–2907, cámara ON/OFF con un par de estado equivalente y 26 imágenes
revisadas). R7 cerrado para entrega **experimental v0.2.0**; R0 general
**reabierto**: dos watchdog en paquetes extraídos/modo original con sampler=0,
sin causa demostrada. No confundir con el mecanismo del sampler ya eliminado.
112 tests/36 grupos C, build normal+PGXP y offline PASS; pruebas del ZIP
estándar/PGXP PASS, original con fallos explícitos en la matriz. No decir que
todo pasó. Publicación autorizada por el usuario. Empaquetar con
`python -B tools/package_release.py`, que valida Python portable completo,
TinyCC, catálogo público apagado y hashes del ZIP; preservar stages anteriores.
Pins actuales en `framework_pins.txt` (núcleo `835f1902`). La inspección visual
no requiere delegación al usuario; el recorte en vuelo y balance exhaustivo
siguen siendo límites documentados del producto.
ZIP final: 3/3 sesiones PASS (original 2 combates; estándar y PGXP 1 cada uno),
autocompile correcto, sampler=0. No borrar por ello los fallos previos de R0.

**Tanda histórica §8 de `ROADMAP_RELEVO_COMBATE.md`:** R3 settle integrado y probado
en partida (acción 6 → slot creado); R4 encuadre general implementado en el seam
nuevo `0x80054F88` (opt-out `DBFB_CAMERA_FRAMING=0`, overlays recompilados,
namespace `cg18_1b6950cb_gc164a1e9a_f0`, 1158 DLLs); R5 fichas medidas
(`tools/combat_cards.py`); R6 dificultad 0/1/2 verificada en partida; R1
cmd29/200→9B capturado. **111 tests OK** (36 grupos C), build exit 0,
`verify_offline` PASS. Pendientes: visual del settle, A/B visual de cámara,
aéreos/bloqueo en fichas, n mayor por dificultad, balance humano, R7.

**Tanda §7 anterior:** R0 corregido de clase (sampler
de host opt-in `PSX_HOST_SAMPLER_SUSPEND=1`, watchdog intacto); R1 cmd25 entregado
y observado en partida (`followup_lift`, pendiente cmd29/200→9B); R2/R3 geometría y
transición propia sin integrar; R4 cámara mapeada con sonda de solo lectura.
86tests/35gruposC, builds normal/PGXP PASS, `verify_offline` PASS y partida
`dbfb-final-20261019` (4 combates, salida0, `max_suspend_us=0`). Restan giro propio,
clips nuevos renderizados, cámara general, fichas nominales y balance humano.

**Tramo §12 anterior:** NUEVO `dbfb_locomotion.h`, hook80067A68/02020018: delta
de raíz propio con aceleración/frenado antes de proyección/colisiones nativas.
65tests/34gruposC y buildsPASS. Sesiónn420s/4382:4combates,pausa,save/load,
salida0,5321intervenciones de locomoción. Namespace
**cg18_1b6950cb_gc58692d0b_f0**,1157DLLsconranges; ocho rechazos de auditoría
kernel durante reconstrucción, no ocultarlos. m/n no reprodujeron l; nuevo
samplermaxsuspendTCP/reporte123400/173844µs. Bloqueo l aún abierto. No se han
terminado rutas aéreas, clips nuevos, giro propio, cámara general ni balance humano.

**Resultado final del tramo:** §11 corrige la falsa movilidad125%: script+c
mueve al rival en la ruta verificada, por eso el estándar conserva su valor
nativo. Ataques/poses siguen retimados juntos. Suite64 y builds PASS, pero
**sesión l FAIL** en combate2 frame11887, retorno2/watchdog12,4s. Pausa/save/load
sí completos. kPASS descrito debajo es una revisión anterior. Diagnósticos
privados l intactos, causa pendiente; hace falta observar la parada del hilo
host (ciclos/insns quietos9s), no inventar un parche al juego ni silenciar watchdog.

**Última comprobación 2026-10-18:** §10 de `COMBATE_REDISENO.md` sustituye
guardia/IA/cierre anteriores. Máscara de divisor dos `0x40000000`, no `0x4000`.
Dificultad efectiva `0x80072960+lado*0x24`, CPU=control bit0; preservar defensa
nativa. Técnicas78..83 coste4/5 con tiempos/poses originales. **64 tests PASS**,
ambos builds; sesión k: cuatro combates completos, pausa, estados rápidos
save/load y salida0 sin terminate. Estados en carpeta temporal no prueban
guardado nativo. Los cierres1 anteriores no demostraban salida normal: el
instrumento mataba al perder respuesta de quit. Causa de starvation c aún abierta.
Clips nuevos, rutas aéreas, locomoción y encuadre general siguen pendientes.

**Actualización 2026-10-18:** leer `COMBATE_REDISENO.md` §9 antes de usar §8 o
las notas del 17b. El contador de script es descendente. Hit-stop usa filtros
de eventos/pose; cancelaciones con confirmación por daño y recuperación real.
Ráfagas básicas: 125%, 64 VBlanks, choques 3D y coste/daño 3/4. Cámara de KO
directa 8%/24 VBlanks. Caché `cg18_1b6950cb_gc2c269e7c_f0` (1.158 DLLs), 58
tests/33 grupos C y matriz integrada de 942 variantes. **Unlock: `0x8003BCC4`**
(inmediato con signo), START debug **`0x0008`**. Ambos corregidos y 17 retratos
vistos en una sesión real. Sigue experimental; no hay animaciones/poses nuevas
ni balance humano. `tools/combat_smoke.py` hace una sesión temporal acotada y
cierra solo su propio proceso; `tools/combat_moves.py --cards` da fichas estáticas.

- Leer `COMBATE_REDISENO.md`: el usuario pide **un único mod activar y jugar**,
  cuyo estándar final sea bueno sin elegir ajustes. Las reglas aisladas son
  herramientas de desarrollo, no el producto. El catálogo público tiene
  `standard`; el manifiesto viejo se conserva en `mods/development/`.
- El rediseño incluye mecánicas, movimientos, transiciones y animaciones. No
  declarar acabado con inputs, velocidad y ki. B3 HD se estudia en
  `../DBZ Budokai 3 HD Collection/` (port Xbox 360/ReXGlue) como referencia real
  de curvas/eventos/reacciones, sin modificar ese proyecto.
- Perfil inicial implementado y probado sintéticamente: buffer 2 VBlanks,
  velocidad nominal 125%, +1 ki/4 sondeos y umbral acotado 9→12; no es el balance
  definitivo. Pausa real `0x800A868C`, probada contra código/capturas; reanudación
  automática, sin reactivar el mod tras pausar.
- Tabla de opcodes: la base es `0x8003E78C`; animación/acción 0x20, spawn 0x23,
  velocidad 0x24, golpe 0x25. Los números antiguos desplazados no deben reutilizarse.
- `tools/combat_assets.py` lee/descomprime Psdp sin extraer activos. Bloques no
  equivalen a animaciones; no hay inventario verificado de clips todavía.

- **Disco de Final Bout (referencia de RE):** `disc/` (EXE `SLUS_004.93` y
  overlays `STEP*.BIN`; el de combate es `STEP40.BIN`, miembro en offset
  `0x22060`, base RAM `0x80060000`). Las fronteras de función verificadas ya
  están en `game.toml`.
- **`guimaraf/plusalpha-recomp` (referencia conductual, NO de transplante):**
  port de *Street Fighter EX Plus Alpha* (SLUS-00548) sobre el mismo
  `psxrecomp`. Aporta un ejemplo real de juego de lucha funcionando (Software
  1x, 60 FPS, LLE SCPH-1001) y patrones de temporización de luchadores. Su
  framework es `guimaraf/psxrecomp-plusalpha`. Leer su README y sus docs; sirve
  para diseño de input/hit-stop/cámara, **no** para copiar su modelo 2D en el
  motor 3D de Final Bout (ver `FINAL_BOUT_RESPONSIVE_ARCHITECTURE.md`).
  - Hay una copia con documentación de Final Bout en
    `..\DB Final Bout\tools\psxrecomp\` (incluye
    `docs/FINAL_BOUT_RESPONSIVE_ARCHITECTURE.md`).
  - En `disc/` hay además `Street Fighter EX Plus Alpha (USA).bin` — material
    ajeno útil solo como referencia/oráculo; **ignorar** para el build.
- **Punto de integración del mod:** `psxrecomp/runtime/include/mod_plugins.h`
  (plugins confiables por id), `psxrecomp/docs/MOD_PACKAGES.md` (manifiestos v6)
  y `mods/preloaded/packages/<id>/<version>/manifest.toml`. El plugin nativo se
  enlaza en el target de Final Bout (`PSXRT_EXTRAS_SOURCES` vía
  `psxrecomp_add_game_runtime`, ya usado con `codegen_setup.c`), nunca en
  `runtime.cmake` genérico.
