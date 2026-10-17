# QoL — evidencia y entrega para integración

Fecha: **2026-10-17**. Proyecto: `DBFinalBoutRecomp`.
Encargo acotado: launcher, arquitectura multirregión, sombras y netplay.

## 1. Resultado principal

- **Netplay sintético:** reconstruido exclusivamente `build-net-tests` con dependencias
  instaladas. CTest termina **28/28 aprobados**, en 44,77 s. Uno de esos ejecutables,
  `rb_driver_test`, sale correctamente **sin ejercitar sus casos en Windows**;
  no contarlo como validación de rollback entre procesos.
- **Multirregión:** comparados los tres discos locales sin extraer archivos. Se
  confirman los 52 bytes distintos entre los boot EXE de EU y España, pero **cinco
  de seis overlays también difieren**, incluido STEP40. No está demostrada la
  equivalencia de código ni funciona PAL en el ejecutable USA por este trabajo.
- **Launcher:** implementado un preparador de comandos con validación de revisión,
  configuración, rutas y opciones guardadas. Produce planes launcher/offline/host/
  guest, sin ejecutarlos. El flujo gráfico real permanece sin verificar.
- **Sombras:** investigados parámetros y rutas del renderer; preparado un colector
  TCP y una matriz reproducible. No hay comparación nueva con Beetle ni corrección
  visual demostrada. La atribución histórica a «proyección Z» sigue siendo hipótesis.
- **Verificación offline del proyecto:** aprobada, con 1117 DLL y codegen `1b6950cb`.

No se abrió juego ni oráculo. Las ediciones de fuentes se limitan a herramientas
nuevas y este informe. La única reconstrucción fue el build aislado de netplay.

## 2. Revisión inicial del trabajo existente

Se leyeron `MEMORY.md`, `AGENTS.md`, `HANDOFF_CLAUDE.md`, `ROADMAP.md`, el plan
de crash/combate, las notas relevantes de `summary.md` y las reglas del framework.
Antes de editar se ejecutaron `git status --short`, `git diff --stat` y después
el estado del submódulo. El árbol ya contenía trabajo previo:

- Modificados: `AGENTS.md`, `CMakeLists.txt`, `PLAN_SOLUCION_CRASH_Y_COMBATE.md`,
  `README.md`, `README_ES.md`, `RELEASE_NOTES_v0.1.1.md`, `game.toml`,
  `scripts/package_setup_release.sh`, `summary.md`, `tools/analyze_latest_session.py`,
  `tools/verify_offline.py` y el estado sucio de `psxrecomp`.
- Sin seguimiento: `COMBATE_EVIDENCIA.md`, `ESTABILIDAD_EVIDENCIA.md`,
  `HANDOFF_CLAUDE.md`, `INFORME_CLAUDE.md`, `MEMORY.md`, `ROADMAP.md`, los tres
  launchers locales de captura/observación/OpenGL, `github/`, `src/`, el paquete
  `dbfb.responsive`, `tools/_dump_*.py`, `tools/step40_coverage_step.py` y las
  pruebas de Responsive en `tools/tests/`.
- En `psxrecomp`: `runtime/src/dirty_ram_interp.c` modificado y las dos pruebas
  `runtime/tests/test_irq_callback_recovery.{c,py}` sin seguimiento.

Esos cambios son heredados; no son entregables de esta tarea. No se modificaron
runtime, plugins, `game.toml`, `CMakeLists.txt` ni los documentos compartidos.
`ROADMAP.md` queda para integración por el responsable; las actualizaciones
concretas propuestas están en §9.

## 3. Matriz de verificación

| Caso | Estado de esta entrega | Evidencia / límite |
|---|---|---|
| Identificación USA/EU/España por contenido | **Verificado offline** | `tools/qol_disc_final_evidence.json`; SYSTEM.CNF, cabecera EXE, hashes de pista/boot/overlays |
| USA vs PAL: boot diferente | **Verificado** | 116167 bytes distintos en cada comparación USA/PAL |
| EU vs España: 52 bytes del boot | **Verificado** | offsets de archivo 116008..116094 |
| EU/España: mismo código ejecutable completo | **No verificado** | boot/payload mezclan código y datos; cinco overlays distintos |
| Multirregión funcional | **No verificado / no implementado** | el detector/comparador no cambia el dispatcher ni aporta builds PAL |
| Plan launcher con disco USA y rutas con espacios | **Verificado offline** | JSON final, pruebas y análisis sintáctico PowerShell sin ejecutarlo |
| Rechazo del disco España por el preparador USA | **Verificado** | CLI devuelve error esperado; prueba de revisión incompatible |
| Abrir/cancelar/reabrir GUI y pulsar Play | **No verificado** | matriz preparada; ningún juego iniciado |
| Opciones realmente guardadas en disco | **Verificado como archivo** | `settings.toml`: Vulkan, bilinear, AA=true; no implica ejecución de ese perfil |
| Corrección de sombras / igualdad con Beetle | **No verificado** | investigación de fuentes y antecedentes, sin nuevas imágenes comparables |
| Netplay biblioteca: handshake, inputs, transferencia de estado | **Verificado sintético** | CTest y `session_state_test`, peers localhost |
| Lobby/rematch/control multipeer sintéticos | **Verificado sintético** | `lan_rematch_test`, `lan_lobby_test`, `rb_ctrl_multipeer_test`, etc. |
| Suite actual Windows | **28/28 CTest** | 27 ejecutables con pruebas efectivas + `rb_driver_test` que omite sus casos en Windows |
| Rollback driver de dos procesos | **No ejercitado** | `rb_driver_test.c:41-46`; requiere POSIX/fork |
| ICE/STUN/TURN reales por Internet | **No verificado** | `RNET_ENABLE_ICE=OFF`; aprobar `stun_test` no prueba conectividad pública |
| Host/guest en dos equipos jugando Final Bout | **No verificado** | planes generados; no se conectó a las IP de ejemplo |
| Netplay entre regiones / determinismo del mod | **No verificado** | la biblioteca no demuestra estado determinista del juego/plugin |
| `verify_offline.py` | **Aprobado** | config idéntica, codegen `1b6950cb`, 1117 DLL con ranges |
| Pruebas de herramientas QoL | **11/11 aprobadas** | ISO sintético, rechazo PAL/config divergente, protección de evidencia, TCP local |

## 4. Multirregión: evidencia y arquitectura propuesta

### Identidades medidas

Todos los boot EXE miden 190464 bytes, cargan en `0x80010000` y entran por
`0x80010B98`. Compartir direcciones **no demuestra** compartir el programa.

| Perfil | Serial leído | Tamaño del BIN | SHA-256 del boot EXE |
|---|---|---:|---|
| USA | SLUS-00493 | 158811744 | `507f132cdcbb635bbbf7a75e15c62a9d0d51e22ce4432828da784ec03b67cbcc` |
| Europa | SLES-03735 | 162137472 | `9ed186dd13132eb76ae87cbc70de37ee2ef99642b41a36440277385ea8f9b5da` |
| España | SLES-03685 | 162137472 | `82959075cf67ee5a0927a2487a50c2826e4ee5403b327b3cd115afc52eb613d0` |

Los CUE USA y España disponibles describen una pista; Europa se auditó desde BIN
porque no hay CUE local. La herramienta no valida el TOC completo ni certifica
un dump Redump (`toc_verified=false`). Los hashes completos están en el JSON.

### Hallazgo adicional: overlays PAL

Comparación **posicional de bytes**, no distancia semántica ni desensamblado:

| Archivo EU / España | Tamaño EU | Tamaño España | Bytes diferentes, incluida diferencia de longitud |
|---|---:|---:|---:|
| STEP00 | 7964 | 7964 | 75 |
| STEP01 | 227472 | 228112 | 998 |
| STEP02 | 107212 | 107212 | 77 |
| STEP03 | 164870 | 165634 | 3939 |
| STEP40 | 442596 | 443068 | 490 |
| STEP999 | 52064 | 52064 | 0 |

No se ha demostrado que los 52 bytes del boot sean exclusivamente una tabla de
idioma ni que los cambios de overlay no afecten código/direcciones. El texto
histórico «EU+Spain code-identical, trivial» es insuficiente para integrar soporte.

### Decisión técnica para integrar

**Un punto de entrada/launcher común con perfiles de revisión y productos
recompilados separados** es la primera implementación recomendada:

1. Identificar por serial **y hashes** de pista, boot y overlays, no por nombre.
2. Mantener inicialmente perfiles USA, EU y España independientes, cada uno con
   su configuración, seeds, código generado, build y caché. Consolidar PAL solo
   después de comparar los miembros ejecutables reales de todos los overlays.
3. Resolver el producto compatible antes de Play. Disco/revisión desconocido:
   mostrar incompatibilidad, no reenviar al dispatcher USA.
4. Separar también settings, saves, mods y caché por perfil. La clave de caché
   debe seguir incluyendo identidad del juego, codegen y configuración.
5. Para netplay, exigir misma revisión/contenido y contrato de mods; no ofrecer
   partidas cruzadas USA/PAL por haber detectado ambos discos.

**Un solo ejecutable nativo con tres dispatchers** queda diferido: requiere
namespaces/descriptores de backend, selección de text/entry por revisión y pruebas
PAL de cadencia y overlays. No se obtiene añadiendo hashes PAL a `prepare_disc`.

Evidencia de la ligadura actual: `CMakeLists.txt:50-51` fija
`generated/SLUS_004.93_dispatch.c` y su glob; `codegen_setup.c:14-19` fija
config, marcador, build y nombre del producto USA; `game.toml:4-27` fija serial,
EXE, dirección y hashes USA. No se han cambiado esos puntos.

## 5. Launcher y opciones: adaptación concreta

`tools/qol_launcher.py` produce JSON y el campo `powershell` con el comando
para ejecutar manualmente más adelante. La herramienta **no tiene arranque
automático**. Así se puede revisar el smoke sin abrir procesos ni instalar nada.

- Valida boot, serial, tamaño, MD5 y SHA-1 contra el perfil USA local y exige
  `game.toml` fuente/desplegado idénticos.
- Modos: `launcher` fuerza `--launcher`; `offline` omite GUI; `host/guest`
  preparan UDP directo con slots 0/1 y dispositivo local 0 en ambos equipos.
- Valida IPv4 y puertos; rechaza localhost para el plan de dos equipos.
- En el comando propuesto fija LAN/delay, dos plazas y fail-fast activo. Retira
  `PSX_NO_LAUNCHER` y desactiva headless/ventana oculta. No modifica el entorno
  de la sesión que genera el plan.
- Propone carpetas de memory cards separadas por modo y un guard que rechaza
  juego/oráculo ya abierto; no mata procesos. El guard es preventivo, no un
  bloqueo global atómico contra sesiones ajenas.
- Registra hashes de EXE/config/settings y las opciones de vídeo guardadas.
- **settings sigue compartido junto al EXE**. `--memcard-dir` no aísla las
  preferencias gráficas. El GUI puede guardarlas si luego se ejecuta el plan.

Rutas observadas en fuente: flags `main.cpp:17158-17248`, prioridad y lectura
de settings `main.cpp:17997-18014`, forzado de launcher `main.cpp:18600-18632`.
La prioridad del renderer CLI no restablece automáticamente el resto del perfil.

Estado guardado encontrado en `build-release/settings.toml`:
`renderer="vulkan"`, `texture_filtering="bilinear"`, `antialiasing=true`,
escala 1, aspecto 4:3, corrección geométrica/perspectiva desactivadas y
`bios_hle=true`. El plan final solicita software, pero **no debe llamarse
vanilla completo** sin comprobar las demás opciones y el estado de mods.

## 6. Sombras: qué demuestra la investigación

- `summary.md:282-296` conserva una observación histórica con widescreen/PGXP
  apagados. Es antecedente útil, no una comparación nueva reproducida aquí.
- `debug_server.c:9453-9467`: `ws_far_threshold` separa el fondo lejano para
  deshacer el squash X; no es un ajuste general de sombras/profundidad.
- `gte.cpp:1151-1189`: la aplicación del umbral está condicionada por squash/
  suppress o por expansión de dome. Cambiar ese umbral en la línea base sin
  esas rutas no demuestra una corrección de la sombra.
- `debug_server.c:5344-5410`: activar geometry/perspective tampoco demuestra
  cobertura; deben medirse hits, misses y proveniencia PGXP.
- `gpu_gl_renderer.c:4352-4392`: el depth buffer PGXP exige proveniencia 3D y
  excluye primitivas semitransparentes del test/escritura de profundidad. No hay
  evidencia de que la sombra concreta entre en esa ruta.
- `CMakeLists.txt:34-40` documenta que la variante PGXP instrumenta la
  propagación completa; no asumir equivalencia activando un mod en el EXE base.

**Conclusión:** causa exacta, paridad con Beetle y corrección de sombras **no
confirmadas**. No se propone un parche de `geometry_correction` o
`ws_far_threshold` como solución demostrada.

El colector `tools/qol_smoke.py` consulta solamente `ping`, `netplay_status`,
`geom_correction`, `gpu_state`, `overlay_loader_status` y `mod_counters` a un
proceso que ya exista, en localhost. Dos muestras, 3 s máximo por consulta,
1 MiB máximo de respuesta; conexión nueva por comando. Admite el ping rápido
documentado con id=0 (`debug_server.c:16926`). No pide RAM ni bytes de overlays,
no pausa ni cambia parámetros. `queries_ok` solo certifica respuestas válidas.

## 7. Netplay: comandos ejecutados y resultados

### Antes de reconstruir

- `build-net-tests/session_state_test.exe`: aprobado; pipeline estricto y
  transferencia/resincronización de 100000 bytes.
- CTest sobre los binarios existentes: **10/11**. Falló
  `rollback_episode_test` con las cuatro expectativas históricas:
  `peer rows not complete yet`, `invalid rows do not complete seal`,
  `slot 2 incomplete (no rows)`, `extend clears peer completeness for new offsets`.
- `ctest` no estaba en PATH y el ctest indicado por el cache del toolchain
  tampoco existía. Se usó el ya instalado `C:\msys64\mingw64\bin\ctest.exe`.

### Reconstrucción aislada

Primero se reconfiguró el mismo build con ICE OFF/tests ON. Falló el enlace de
`session_state_multipeer_test` y `rb_ctrl_multipeer_test`: **nanosleep64 sin
resolver**. Las pruebas usan nanosleep y necesitaban la biblioteca pthread.
Se resolvió únicamente mediante la configuración del build de tests:

```powershell
$env:PATH="C:\Users\javie\.local\share\retcomm\toolchains\cmake-clang-v1\1.0.14\bin;C:\msys64\mingw64\bin;$env:PATH"
& "C:\msys64\mingw64\bin\cmake.exe" -S psxrecomp/lib/recomp-net -B build-net-tests -DRNET_ENABLE_ICE=OFF -DRNET_BUILD_TESTS=ON -DCMAKE_EXE_LINKER_FLAGS=-pthread
& "C:\msys64\mingw64\bin\cmake.exe" --build build-net-tests --parallel 4
& "C:\msys64\mingw64\bin\ctest.exe" --test-dir build-net-tests --output-on-failure --timeout 90 -j 1
```

Resultado: **build aprobado; CTest 28/28, 44,77 s, salida 0**.
Fuente recomp-net: `e53059306824edf4f0aec4aae5ae65151b18535f`.
Registro bruto: `build-net-tests/Testing/Temporary/LastTest.log` (14:16–14:17).

Los 28 nombres registrados:

```text
auth_startup_test, api_link_test, chat_filter_test, ring_admit_test,
wire_map_test, hostport_test, host_relay_test, lan_chat_test,
lan_rematch_test, lan_lobby_test, lan_beacon_test, udp_port_test,
address_test, stun_test, session_state_test, session_state_multipeer_test,
rb_ctrl_multipeer_test, state_replay_test, input_contract_test, rb_driver_test,
rollback_episode_test, session_observer_test, rb_wire_test, hash_confirm_test,
rb_quorum_test, input_hist_test, rb_post_test, sched_smoke_test
```

Límites relevantes del registro:

- `rb_driver_test` es un **skip interno en Windows con salida 0**; no cubre
  ninguna de sus dos partes en este sistema (`rb_driver_test.c:41-46`).
- `session_state_test` sí ejercita dos a cuatro peers, broadcasts con pérdida
  simulada, subidas MEMCARD, barreras y sala dispersa; son estados sintéticos.
- `rb_ctrl_multipeer_test` prueba control de cuatro peers con latencia/jitter/
  pérdida simulada; no ejecuta el motor de Final Bout.
- `lan_rematch_test` prueba el protocolo de revancha, no el rematch del juego.
- No se ejecutó `host_relay_e2e` contra un servidor público ni se instaló ICE.
- Aviso de compilación: `session_ice_reset_transport` no usado al desactivar ICE.
  La primera configuración dejó `FETCHCONTENT_FULLY_DISCONNECTED=ON`; CMake
  avisó que no se utilizaba en este proyecto con ICE OFF. No contar esa variable
  como prueba de aislamiento de red; la ruta FetchContent de libjuice no se activa.

El fallo histórico de rollback queda superado por reconstrucción desde las
fuentes actuales, **sin cambios del protocolo ni de sus tests**.

## 8. Herramientas, artefactos y cómo reproducir

### Archivos nuevos de esta entrega

| Archivo | Función |
|---|---|
| `tools/qol_disc_audit.py` | ISO9660 acotado, sectores 2048 y 2352 Mode1/2 Form1, CUE/INDEX01, hashes y comparación boot/STEP |
| `tools/qol_launcher.py` | Preparador launcher/offline/host/guest y detección de opciones persistidas |
| `tools/qol_smoke.py` | Matriz `--plan` y recogida TCP acotada, solo consulta |
| `tools/tests/test_qol_tools.py` | 11 pruebas con discos sintéticos y servidor TCP local; no juego |
| `tools/qol_disc_final_evidence.json` | Auditoría definitiva de tres discos; no contiene sus bytes |
| `tools/qol_launcher_final_evidence.json` | Plan GUI definitivo, software solicitado, fingerprints y settings guardados |
| `tools/qol_host_evidence.json` | Plan host con IP **de ejemplo** 192.168.1.20 |
| `tools/qol_guest_evidence.json` | Plan guest con IP **de ejemplo** 192.168.1.10 |
| `tools/qol_disc_evidence.json`, `tools/qol_launcher_evidence.json` | Primeras salidas conservadas; usar los archivos `*_final_evidence.json` como referencia actual |
| `QOL_EVIDENCIA.md` | Este informe y propuestas para integración |

Las primeras salidas anteceden a dos mejoras: incluir bytes de cola en el último
offset de diferencia y registrar settings/fingerprints en el plan. Se conservan
sin reemplazar como evidencia de iteración, no son el resultado definitivo.

Los JSON nuevos se crean en modo exclusivo: si existen se rechaza la escritura.
Al repetir comandos con `--output`, elegir un nombre nuevo. No se crean carpetas
implícitamente. Python 3.11+ y biblioteca estándar; no hay dependencias nuevas.

Desde la raíz del proyecto:

```powershell
python -B -m unittest discover -s tools/tests -p test_qol_tools.py -v
python -B tools/verify_offline.py
python -B tools/qol_disc_audit.py "..\DB Final Bout\Dragon Ball GT - Final Bout (USA).cue" "..\DB Final Bout\Dragon Ball - Final Bout (E) [SLES-03735].bin" "..\DB Final Bout\Dragon Ball - Final Bout (Spain).cue"
python -B tools/qol_launcher.py --disc "..\DB Final Bout\Dragon Ball GT - Final Bout (USA).cue" --mode launcher --renderer software
python -B tools/qol_launcher.py --disc "..\DB Final Bout\Dragon Ball - Final Bout (Spain).cue" --mode launcher
python -B tools/qol_smoke.py --plan
```

Resultados ejecutados: **11/11 pruebas**, verificación offline aprobada,
auditoría de tres discos aprobada, plan USA aprobado; el comando España
**rechazado con salida 2, esperado**. La suite verifica lectura equivalente
cooked/Mode1/Mode2, INDEX01 con pregap, extents truncados, revisión PAL y config
divergente, ausencia de sobrescritura, mensajes fragmentados/IDs/errores TCP,
ping rápido, límite de tamaño y timeout. Los fixtures sintéticos se conservan
en `%TEMP%\opencode\dbfb-qol-tests-*`; no se borran al finalizar.

`git diff --check` también pasó. Sus avisos CRLF/LF afectan archivos heredados;
no hubo error de espacios en el diff existente.

### Smoke manual preparado, NO ejecutado

1. Cerrar cualquier juego/oráculo antes de iniciar otra sesión. Generar el plan
   local de launcher, revisar sus opciones y ejecutar manualmente el campo
   `powershell` únicamente cuando se vaya a realizar el playtest.
2. Comprobar GUI, cancelar, reabrir, vídeo/controles/mods, Play, boot y cierre.
   No usar Generate & rebuild para esta prueba: podría descargar/instalar
   toolchains y modificar otros builds.
3. Sombras: software, 1x, 4:3, nearest, AA/correcciones/PGXP/widescreen/mods
   desactivados como control; registrar también BIOS/HLE. Comparar después con
   Beetle **en otra sesión**, mismo disco/personajes/escenario/cámara. Conservar
   PNG y descripción de la escena; no equiparar dos números de frame sin
   sincronización. Primero obtener el caso reproducible, luego variar una opción.
4. Durante una sesión ya abierta, recoger por checkpoint, por ejemplo:

   ```powershell
   python -B tools/qol_smoke.py --label combate-1-sombras --output tools/qol_smoke_combate1_nuevo.json
   ```

   Sin servidor devuelve fallo de consultas; nunca marca el juego como aprobado.
   El colector no se ejecutó contra un juego vivo en esta entrega.
5. Netplay manual: **dos equipos**, una instancia en cada uno. Preparar host con
   IP del guest y guest con IP del host. Igual disco/build/session/delay, mods de
   gameplay off; no usar las IP de ejemplo sin adaptarlas. `PSX_NET_MODE=delay`
   es la línea base; esto no prueba rollback.
6. En ambos equipos recoger muestras por separado. Esperar `active=1`, dos
   jugadores, host=1/0 respectivamente, `tick` y `resolved_through` avanzando,
   `desync=0`; jugar tres combates, pausa, especiales, vuelo, rematch,
   desconexión y cierre. Añadir `analyze_latest_session.py` al cierre. Unas
   muestras sin desync no certifican determinismo universal.

## 9. Integración que corresponde al responsable

### Cambios de configuración/build realizados

- **Solo `build-net-tests`:** regenerados cache/Ninja/binarios/registro CTest.
  Compilador existente Clang 22.1.8 (`latest/bin/cc.exe`), RelWithDebInfo,
  ICE OFF/tests ON; se añadió `CMAKE_EXE_LINKER_FLAGS=-pthread` para los nuevos
  tests con nanosleep. CMake/CTest ahora apuntan al MSYS2 instalado. El override
  de libchdr de `build-release` no se tocó.
- No hay parche de configuración de producción que copiar desde esta entrega.
  Si se desea hacer portable la reparación de tests, integrar el enlace a
  `Threads::Threads` en los dos targets multipeer de recomp-net; validar también
  MSVC/POSIX antes de hacerlo upstream. Aquí se dejó como flag del build permitido.

### Actualizaciones propuestas para ROADMAP (no aplicadas)

- Launcher: **preparación offline implementada; flujo GUI pendiente**. Registrar
  la precedencia de `settings.toml`; no inferir renderer efectivo del TOML base.
- A7: **arquitectura recomendada definida, auditoría realizada; PAL pendiente**.
  Retirar la premisa de que comparar solo el boot demuestra equivalencia total.
- A4: **investigación estática y smoke preparados; comparación Beetle y fix
  pendientes**. «Proyección Z» no es una causa demostrada en esta sesión.
- Netplay: **suite sintética actual reconstruida y aprobada**, con skip Windows
  de rb_driver explícito. Host/guest reales, ICE/WAN y determinismo del juego
  permanecen abiertos.

No marcar completa la sección QoL ni el ROADMAP global por estos resultados.
Los entregables permiten ejecutar y recoger esa validación sin confundir
detección de disco, compilación de biblioteca o consultas TCP con juego funcional.

## Actualización (sesión de cierre) — inestabilidad de `rb_ctrl_multipeer_test`

- **Síntoma:** en la suite completa falló 1 de 3 veces, a los 0,01 s, en el *setup*.
- **Causa raíz demostrada:** el test elige la base de puerto con
  `44000 + (pid % 4000) * 8`, que alcanza **75992** — por encima del máximo de 65535.
  Para ~1/3 de los PID el bind del hub falla. Reproducido correlacionando PID y
  resultado (`base=69504` → FAIL; el resto PASS con base ≤ 65535).
- **Arreglo:** rango que queda holgadamente por debajo de 65535
  (`20000 + (pid % 3000) * 8`, máximo 43999), en
  `psxrecomp/lib/recomp-net/tests/rb_ctrl_multipeer_test.c`. Recompilado `build-net-tests`.
- **Verificación:** 8/8 ejecuciones directas verdes y `ctest build-net-tests`
  **28/28**. Deja de ser inestable. (Cambio local en el submódulo anidado `lib/recomp-net`;
  conviene proponerlo upstream al actualizar.)
