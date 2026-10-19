# Roadmap y relevo del combate — actualización 2026-10-19

**Estado vigente: §11, §10 y `R0_ESTABILIDAD.md`.** R0-B corregido y publicado
en **v0.2.1**: el hilo del juego ya no espera a trabajadores aún vivos tras
`DONE`. Reproducción antes/después, 121tests OK y matriz del ZIP 3/3 PASS,
10combates. R0-C conserva tres cierres sin atribución definitiva; R0 global
sigue abierto. R7 permanece cerrado como entrega experimental; v0.2.1 es una
pre-release de mantenimiento. El historial inferior conserva sus resultados
originales.

Documento operativo para **cualquier modelo** que continúe. Complementa las
reglas de `AGENTS.md` y `psxrecomp/CLAUDE.md`; sustituye el estado histórico del
handoff del 3 de octubre. El usuario pide seguir trabajando, no solo preparar
un plan. No hace falta volver a preguntarle qué priorizar.

## 1. Encargo y punto de partida

Un único interruptor público «Combate renovado», activar y jugar. Completar
movilidad, golpes y fichas, rutas/remates, animaciones y transiciones, defensa,
ki/especiales, IA por dificultad, cámara y balance. Estética PS1; el usuario
autoriza crear activos nuevos. No confundir autorización con implementación.

Repo real: `C:\Users\javie\Desktop\PROYECTOS IA\DBFinalBoutRecomp`.
La carpeta inicial `DB Final Bout` es distinta. Hay cambios sin commit de
sesiones anteriores y un submódulo `psxrecomp` modificado: conservarlos.
`github/` es trabajo ajeno. No borrar datos, instalar terceros, publicar ni
hacer commit/push sin autorización específica. Si hay que retirar artefactos,
conservar respaldo. No editar `generated/` ni la configuración desplegada.

### Confirmado antes de esta continuación

- 65/65 tests, 34 grupos del arnés C; matriz 942 variantes y 432 scripts de
  técnicas. Builds normal/PGXP y verificación offline PASS.
- Locomoción propia en `src/mods/dbfb_locomotion.h`: sitio `0x80067A68`,
  original `0x02020018`, delta de raíz antes de giro y separación nativos;
  aceleración/frenado por VBlank. `script+0x0C` NO es locomoción propia:
  desplaza al contrario en la ruta demostrada. No reintroducir esa confusión.
- Hit-stop script/pose, cancelación tardía con impacto confirmado, defensa,
  ráfagas, coste de técnicas, IA respetuosa con defensa y cámara directa de KO.
  No equivalen a clips completamente nuevos ni cámara general terminada.
- Sesión n: 420s, cuatro combates completos, pausa, save/load, salida0;
  5.321 intervenciones de locomoción. m también pasó cuatro combates.
- Namespace actual `cg18_1b6950cb_gc58692d0b_f0`, 1.157 DLLs con ranges.
  Ocho rechazos de auditoría de fragmentos kernel durante la reconstrucción:
  quedaron excluidos, no se debilitó la auditoría. No decir «todo compiló».
- `unlock-all`: 17 retratos observados; tabla correcta `0x8003BCC4`.

### Abierto: no se puede declarar acabado

| ID | Entregable | Trabajo y condición de cierre |
|---|---|---|
| R0 | Bloqueo intermitente | Reproducir la sesión l, separar espera/suspensión host de ejecución MIPS, demostrar causa y arreglo de clase. No silenciar ni ampliar watchdog. Repetir la misma reproducción tras corregirlo. |
| R1 | Rutas y remates aéreos | Reconstruir productores/consumidores y comandos de 98/AA→99/9B/9A. Elegir una mejora concreta, pasar por la maquinaria nativa y comprobar coste, interrupciones, pausa/restore, ambos lados y CPU/humano. Verla ejecutarse en partida antes de cerrarla. |
| R2 | Giro y locomoción visual | Aceleración/frenado existen; falta giro propio y correspondencia entre desplazamiento, bucles y pies. Mapear antes de modificar; no llamar «animación nueva» a retiming. |
| R3 | Clips nuevos | Vincular paquetes/partes con geometría y jerarquía, demostrar anatomía; crear un clip compatible, probar decodificación y render, después ampliar movimientos/personajes. No inventar nombres de huesos ni importar activos de B3. |
| R4 | Cámara general | Mapear rama 800AA194==1 y contexto *(800A9D0C), propietario/orden de escritura y restauración. Mantener a ambos luchadores visibles, vuelo y bordes, sin pisar cinematográficas. La cámara de KO directa ya existe. |
| R5 | Fichas por golpe | Nombres/personaje/comando respaldados por tablas; medir inicio, contacto, recuperación, daño, ki y alcance en ejecución. `--cards` actual son tiempos estáticos, no frame advantage medido. |
| R6 | Dificultad y balance | Probar índices 0/1/2 en partidas; más emparejamientos, ambos lados, CPU y segundo humano. Ráfagas que chocan solo están verificadas sintéticamente. Balance humano sigue sin verificar. |
| R7 | Cierre integrado | Repetir tests, builds, offline y matriz de partidas; reconciliar catálogo/docs con lo observado y entregar pendientes explícitos. Ningún PASS aislado cierra R0–R6. |

Orden de ejecución: continuar R1 ahora; R0 se investiga en paralelo **solo con
herramientas/procesos propios**, sin lanzar agentes salvo permiso aplicable.
Después R2/R3, R4, R5/R6 y R7. Si surge fallo de fidelidad del núcleo, R0 tiene
prioridad sobre el enhancement: corregir recompilador/runtime y regenerar.

## 2. Cómo continuar cada investigación

1. Leer código y evidencia; anotar hipótesis como hipótesis.
2. Desensamblar bytes verificados y seguir llamada/registro/estructura. Un
   `ori 0x80` no prueba nada sin seguir **dónde se guarda**: control+0,
   control+4 y variables globales son campos diferentes.
3. Establecer productor, consumidor, duración y limpieza. Confirmar quién es
   atacante/defensor, signo de inmediatos y si un reloj sube o baja.
4. Observar por debug server/rings existentes. Si falta visibilidad, añadir
   información estructurada; no printf ni logs ad-hoc. Capturar en temporal
   privado; no introducir bytes retail en documentación o commits.
5. Especificar diseño fijo y guardas (offline, pausa, KO, restore, recarga,
   código original, ambos lados). Implementar solo con la ruta demostrada.
6. Pruebas de comportamiento y regresión con datos del disco, build y partida.
   No fabricar una prueba que solo replique la implementación.
7. Registrar observación, comando, resultado real y siguiente incógnita aquí.

### R0: evidencia que no debe perderse

Privado: `C:\Users\javie\AppData\Local\Temp\opencode\dbfb-rework-smoke-20261018l`.
Fallo tras cargar estado, combate2, frame11887; watchdog12.414.350µs, salida2;
current_func `0x1FC085D8`, last_store_pc `0x80041AC8`, sin fatal/in_exception.
Los ciclos/insns apenas avanzaban durante la parada: no demuestra bucle MIPS.
También existe sesión c. m/n no lo reprodujeron: eso **no prueba arreglo**.

El muestreador Windows suspende brevemente el hilo para leer contexto. Nuevo
`host_sampler_max_suspend_us()` se publica en reporte y TCP
`host_profile.max_suspend_us`: m123400µs/n173844µs. Hipótesis aún sin causalidad.
Si reaparece, conservar ese campo, frame/ciclos/insns y planificación/pilas
Windows (WPR/WPA existentes), distinguir hilo parado de hilo ejecutando. No
deducir el culpable de un barrido de pila que no es unwind.

#### R0 — estado 2026-10-18 (esta continuación): mecanismo medido, cierre abierto

Se añadió instrumentación estructurada (sin printf) en el runtime para separar
suspensión host de ejecución MIPS:

- `host_sampler.c/.h`: además de `max_suspend_us` (total), publica
  `max_suspend_wait_us` (lo que bloqueó `SuspendThread`), `max_suspend_hold_us`
  (hilo objetivo realmente suspendido), `worst_hold_target_cpu_us`
  (`GetThreadTimes`: CPU kernel+user consumida por el objetivo durante ese
  hold) y `suspend_age_us` (hold vivo). El hold se mide antes de
  `ResumeThread`; las máximas se publican como antes.
- `crash_trace.c` (reporte), `freeze_heartbeat.c` (`psx_freeze_heartbeat.json`)
  y `debug_server.c` (`host_profile`) exponen esos campos.

Medición real (misma reproducción `--seconds 420 --kos 3 --savestate
--movement`, puerto 4385, carpetas privadas nuevas `-q`..`-aa`; todas PASS,
salida 0, 4–5 combates):

| sesión | max_suspend µg | wait µg | hold µg | CPU objetivo en el hold | resultado |
|---|---:|---:|---:|---:|---|
| m | 123400 | — | — | — | PASS |
| n | 173844 | — | — | — | PASS |
| q | 394562 | — | — | — | PASS |
| r | 136568 | — | — | — | PASS |
| s | **1783293** | — | — | — | PASS |
| t | 1944235 | 425 | **1944234** | — (sin discriminador) | PASS |
| u | 130002 | 291 | 130000 | — | PASS |
| v | 132670 | 207 | 132665 | **0** | PASS |
| w | 207902 | 345 | 207893 | **0** | PASS |
| x | 81767 | 295 | 81765 | **0** | PASS |
| y | 119588 | 384 | 119587 | **0** | PASS |
| z | 141250 | 212 | 141248 | **0** | PASS |
| aa | 161388 | 251 | 161384 | **0** | PASS |

Hechos demostrados:

1. El sampler externo puede mantener suspendido el hilo de emulación entre
   82 ms y 1,944 s en una sesión normal; `wait` es ~0,23–0,43 ms y casi todo el
   intervalo es `hold`. Con `GetThreadTimes`, en los holds de 82–208 ms el
   objetivo consumió **0 µs** de CPU: no estaba dentro de una operación kernel
   (loader/I/O); estaba suspendido.
2. Mientras dura el hold, `psx_cycle_count`, `frame_count` y `dirty_ram_insns`
   quedan congelados. El ring de `l` lo muestra exacto: 63 ticks consecutivos
   con el mismo `cyc` (≈6,3 s de los 12,414350 s) y luego +47.458 ciclos /
   +117 insns justo antes del aborto.
3. El heartbeat de starvation lo sella el hilo de emulación
   (`debug_server_poll`/present). No puede avanzar mientras ese hilo está
   suspendido, y el chequeo del watchdog también corre en ese hilo: no dispara
   durante el hold. Al reanudar, el primer chequeo ve el heartbeat más viejo
   que el hold; si el hold supera `PSX_STARVATION_TIMEOUT_US` (4 s), aborta con
   salida 2. Por eso `l` (12,414350 s) es una **suspensión host**, no un bucle
   MIPS: los ciclos/insns congelados lo descartan.

Lo que NO se cerró: no se capturó un hold ≥4 s con la build instrumentada
(máximo real 1,944 s en `t`; 1,783 s en `s`). La cola es pesada (2 de 11
sesiones llegaron a ~1,8–1,9 s), así que el caso `l` es plausible pero raro.
R0 sigue **abierto**: falta reproducir el disparo del watchdog con la causa
adjunta y verificar el arreglo de clase.

Siguiente experimento concreto:

1. Repetir sesiones de 420 s con el binario instrumentado (misma orden) hasta
   que una reporte `host_sampler_max_suspend_hold_us >= 4000000` y salida 2.
   Ese JSON será la reproducción de `l` con causa adjunta; conservarlo privado.
2. Arreglo de clase (runtime genérico, no parche de juego): el sampler no debe
   suspender el hilo de emulación desde otro hilo. Opción inmediata: sampler
   suspend-based **opt-in** (variable de entorno, por defecto off) para que la
   ruta normal no se perturbe; opción de fondo: muestreo cooperativo desde el
   propio hilo de emulación en un punto seguro de alta frecuencia. No tocar el
   umbral ni la lógica del watchdog.
3. Repetir la misma reproducción tras el arreglo: exigir 0 salidas por
   watchdog y holds acotados. Sin esa repetición no declarar R0 cerrado.


### R1: punto exacto de arranque

- Consumidor de continuación: `0x80057608..0x80057790`, acciones98/AA y
  control+4 bits80/200. Falta comprobar completamente sus productores y
  comandos; no escribir esos bits solo para hacer que el efecto aparezca.
- Productor candidato ya visto: `0x80060A70..0x80060ABC` lee control+4,
  exige bits20/40, OR200, guarda control+4 y acción98. Seguir su tabla de
  salto y las entradas reales antes de atribuir un botón o nombre al movimiento.
- No confundir `0x8005DB10`/`0x8005DC54`: escriben bits80/200 en **control+0**.
- Revisar etiqueta histórica opcode61 `fighter_flags`: el nombre no es prueba
  de que produzca los bits anteriores. Confirmar su handler antes de usarla.

## 3. Archivos que tocar según el trabajo

- Plugin: `src/mods/dbfb_responsive.c`, módulos `dbfb_combat.h`,
  `dbfb_motion.h`, `dbfb_pose.h`, `dbfb_projectiles.h`, `dbfb_locomotion.h`.
- RE/metadata: `tools/combat_map.py`, `combat_moves.py`, `combat_assets.py`.
- Partidas: `tools/combat_smoke.py`, `tools/combat_live.py`.
- Tests: `tools/tests/test_responsive*`, `test_motion*`, `test_combat_matrix*`,
  `test_combat_moves.py`, `test_combat_smoke.py`.
- Sitios nuevos: `game.toml` → invalida namespace de overlays. Reconstruir
  ambos ejecutables, recompilar overlays y verificar **el namespace en uso**.
- Núcleo: leer las reglas de `psxrecomp` y su plan antes de editar. No parche
  específico del juego para fingir fidelidad. Las mejoras deliberadas del mod
  pertenecen al plugin, no al núcleo genérico.
- Docs finales: este relevo, `COMBATE_REDISENO.md`, `COMBATE_EVIDENCIA.md`,
  `summary.md`; memoria/AGENTS si cambia un hecho duradero.

## 4. Comandos reproducibles (PowerShell 5.1)

Ejecutar en la raíz real del repo. No hay `&&` en este shell. Ajustar PATH en
el proceso, sin cambiar la configuración global:

```powershell
$env:PATH='C:\Users\javie\.local\share\retcomm\toolchains\cmake-clang-v1\1.0.14\bin;C:\msys64\mingw64\bin;'+$env:PATH
python -B -m unittest discover -s tools/tests -p "test_*.py"
cmake --build build-release --target psx-runtime psx-runtime-pgxp -j 4
python -B tools/verify_offline.py
git diff --check
```

Partida nueva: elegir puerto libre y carpeta **nueva**, no sobrescribir l/m/n.
El instrumento tiene que cerrar únicamente su proceso, sin terminate para PASS.

```powershell
python -B tools/combat_smoke.py --launch --port 4383 --seconds 420 --kos 3 --savestate --movement --summary --out "C:\Users\javie\AppData\Local\Temp\opencode\dbfb-rework-smoke-20261018o"
```

Herramienta de mapa: `disasm` recibe **inicio y fin**, no `--size`:

```powershell
python -B tools/combat_map.py disasm 0x80057608 0x80057794
python -B tools/combat_map.py disasm 0x80060980 0x80060B10
```

Si cambia configuración de hooks/generador, compilar desde captura durable
`build-release/vault/overlay_captures.json` (182), no desde la captura vieja de
la raíz del build. Puede tardar >10min; guardar/reanudar resultados sin borrar:

```powershell
python psxrecomp/tools/compile_overlays.py --captures build-release/vault/overlay_captures.json --game-toml game.toml --recompiler build-recompiler/psxrecomp-game.exe --runtime-include psxrecomp/runtime/include --project-root psxrecomp --out-dir build-release/cache --gcc C:\msys64\mingw64\bin\gcc.exe --jobs 8
```

STEP40 base verificada8003DFA0, SHA256
`001adcdc2e129d3bd715c29b64e393fa8c2901a7ef39c2347874b321aae6b9dd`.
Control80072800/stride7C, script800728F8/stride30; script+4 cuenta **abajo**.
Dificultad efectiva80072960+lado*24; CPU=control+0 bit0. Pausa800A868C.
START debug0008. Guardia divisor40000000, no4000.

REA6.7.0/Ghidra12.1.2/JDK25 ya instalados. Ghidra en el proyecto vecino
`Shin Budokai 2\ghidra_12.1.2_PUBLIC`; JAVA_HOME
`C:\Program Files\Eclipse Adoptium\jdk-25.0.4.7-hotspot`.
Probe MCP local `...\Temp\opencode\dbfb_rea_probe.py`:207tools y
binary_session disponibles en la sesión anterior. Disponibilidad no significa
que se haya importado/descompilado STEP40. No instalar ni editar OpenCode como
atajo; respetar las reglas de análisis/oráculo si se toca el núcleo.

## 5. Texto de encargo para otro modelo

> Continúa el proyecto DBFinalBoutRecomp. Lee MEMORY.md, AGENTS.md y
> ROADMAP_RELEVO_COMBATE.md; distingue estado actual de notas históricas.
> El usuario pide terminar el combate renovado, sin parámetros que deba ajustar,
> y autoriza activos nuevos compatibles con estética PS1. No hagas commit/push,
> publicaciones ni instalaciones; conserva los cambios y evidencias existentes.
> Empieza por la tarea marcada activa abajo, no rehagas lo ya validado. Verifica
> productores/consumidores nativos antes de hooks, usa el debug server, conserva
> resultados reales. No silencies el watchdog ni inventes anatomía o frame data.
> Implementa y comprueba, no entregues solo otro plan. Al terminar o bloquearte,
> actualiza este relevo con archivos modificados, comandos ejecutados/resultados,
> qué falta exactamente y el siguiente experimento concreto. Separa tests,
> builds y partidas: ninguno demuestra por sí solo el cierre completo.

## 6. Registro de esta continuación

- Guía de relevo creada **antes** de continuar, a petición del usuario.
- **R1, avance de esta continuación:** herramienta `combat_map.py routes`
  implementada. Comprueba hash/base y reconstruye cinco rutas de comandos
  25/28/29/2B/2C, casos por ID nativo, productores de confirmación y desenlaces.
  Emite metadatos, no activos ni parches. Documentación completa en
  `COMBATE_MAPA.md` §9 y `COMBATE_REDISENO.md` §13.
- La vía general que faltaba es **cmd25**, fila32, `800607A0`: pasos internos
  2000→4000→0020. Con flags20 elige98; sin20 y con40 eligeAA. El delay slot de
  80060800 es decisivo: no tratar ambas salidas como una misma acción.
- **Productor80 resuelto estáticamente:** colisión de98/AA, atacante s3=a0,
  rival s5=(s3==0); stores62FF4/63030/63228 sobre control+4. Los casos de IDs
  coinciden con los14 del consumidor. No equivalen a confirmación universal de
  daño para todas las acciones. Productor200:60AAC, cmd29, casoID6, flags20/40.
- **Precaución nueva:** 576BC decide sobre el candidato en `sp+48`, no sobre
  una transición necesariamente visible entre dos sondeos. Resultado almacenado
  en control+8 por **57F94**. Una secuencia de fotos puede perder esa transición;
  usar wtrace con PC/seq para demostrarla, no atribuir causalidad a proximidad.
- Corregida etiqueta falsa opcode61 en `combat_moves.py`: ahora
  `audio_channel_event`. Handler4EAFC llama5015C, tabla de6canales6F79C y máscaras
  18..23; no produce los flags de luchador. Se añadió regresión específica.
- Nuevos tests de rutas contra disco/captura privados: decisiones98/AA y delay
  slot, identidad de campos/lados, consumidor/limpieza y rechazo de otro binario.
  Suite ejecutada: **69/69 PASS**,34gruposC,matriz942 y432técnicas siguen verdes.
- Archivos modificados en esta continuación:
  `ROADMAP_RELEVO_COMBATE.md` (nuevo), `AGENTS.md`, `HANDOFF_CLAUDE.md`,
  `tools/combat_map.py`, `tools/combat_moves.py`,
  `tools/tests/test_combat_routes.py` (nuevo), `tools/tests/test_combat_moves.py`,
  `COMBATE_MAPA.md`, `COMBATE_REDISENO.md`, `COMBATE_EVIDENCIA.md`, `summary.md`.
  Los demás cambios de git son de los tramos anteriores: conservarlos.
- **No se ha implementado un remate nuevo ni se ha vuelto a ejecutar una
  partida en este tramo.** n es evidencia anterior. R0 continúa sin causa.

### Siguiente experimento concreto (R1 activo)

Observar una ejecución nativa sin forzar RAM/acciones. No hace falta añadir
hooks ni regenerar overlays para capturarla: el servidor ya ofrece wtrace.

1. Arrancar sesión propia y privada, identificar ID en control−4 y esperar
   combate real con HP válidos. Elegir comando válido del informe `routes`.
2. Consultar `wtrace_ranges`; añadir con `wtrace_add` rangos exclusivos
   `lo=0x80072804,hi=0x8007280C` y `lo=0x80072880,hi=0x80072888` (hi exclusivo).
   Guardar slots; no usar `wtrace_range`, que borra rangos ajenos, ni resetear
   evidencia anterior. Confirmar que hay sitio en los8slots.
3. Comprobar generación real de flags20/40 (un productor ya localizado en
   5D900/5D910, acción1D); falta completar la relación botón/estado y el40.
   Probar entradas nativas, no escribir banderas para saltarse esa incógnita.
4. Ejecutar cmd25 con los flancos internos2000→4000→0020 dentro de las ventanas
   nativas. Las palabras debug son activas-bajas y byte-swapped:
   `FFDF→FFBF→DFFF`; temporizar por frames del juego, no suponer60FPS host.
   Hay que cumplir las guardas nativas; emitir el gesto en neutral no basta.
5. `wtrace_dump` con `addr_lo/addr_hi`, `frame_lo`, `count<=2048`, `newest=1`.
   Las direcciones devueltas son físicas. Buscar writer6071C (98/AA), los
   productores80 y store57F94 (99/9B/9A); ordenar por seq, no por el orden de
   newest. Consultar también stores de200/limpieza y las precondiciones693CC.
6. Conservar el JSON privado, distinguir fallo/guardia/impacto y ambos lados.
   Retirar solo slots propios en orden descendente (`wtrace_del` compacta).
   Si faltan eventos, comprobar cobertura del ring antes de afirmar ausencia.
7. Solo después elegir una mejora concreta (p. ej. accesibilidad/ventana o
   continuación visual sincronizada), especificar diseño y probarla. No retimar
    a ciegas una ruta que coordina al otro luchador. R1 sigue abierto hasta verla.

### Registro R0 — 2026-10-18 (esta continuación)

- **Archivos modificados:** `psxrecomp/runtime/include/host_sampler.h`,
  `psxrecomp/runtime/src/host_sampler.c`,
  `psxrecomp/runtime/src/crash_trace.c`,
  `psxrecomp/runtime/src/freeze_heartbeat.c`,
  `psxrecomp/runtime/src/debug_server.c`, este roadmap y
  `psxrecomp/docs/internal/FAITHFUL_TIMING_PLAN.md`. No se tocó el watchdog ni
  el código generado. Se conservaron los cambios previos del submódulo.
- **Instrumentación (estructurada, sin printf):** split
  wait/hold de la suspensión del sampler, CPU del objetivo durante el hold,
  edad viva del hold; publicada en `psx_last_run_report.json`,
  `psx_freeze_heartbeat.json` y `host_profile`.
- **Comandos ejecutados y resultado real:**
  - `python -B -m unittest discover -s tools/tests -p "test_*.py"` → **69/69 OK**
    (34 grupos C incluidos).
  - `cmake --build build-release --target psx-runtime psx-runtime-pgxp -j 4`
    → enlazados ambos. El primer intento falló con *Permission denied* porque
    otra sesión ajena (`--debug-port 4386`, carpeta privada
    `dbfb-r1-probe2-20261018`) tenía el exe abierto; se esperó a que terminara
    y el reintento enlazó. No se mató ningún proceso ajeno.
  - `python -B tools/verify_offline.py` → **OFFLINE VERIFICATION PASSED**
    (1157 DLLs, namespace `cg18_1b6950cb_gc58692d0b_f0`).
  - `git diff --check` → limpio (solo avisos CRLF/LF de Git).
  - `test_starvation_watchdog.c` con gcc C11 `-Wall -Wextra -Werror -pedantic`
    → **26/26 ok, exit 0**.
  - `python -B tools/combat_smoke.py --launch --port 4385 --seconds 420
    --kos 3 --savestate --movement --summary --out <q..aa>` → q,r,s,t,u,v,w,x,y,z,aa
    **PASS**, salida 0, 4–5 combates. t/u con el split; v–aa con el
    discriminador `GetThreadTimes`.
- **Qué queda:** R0 abierto. El mecanismo está medido y separado (suspensión
  host, no MIPS), pero no se reprodujo un hold ≥4 s que dispare el watchdog. No
  se declara arreglo ni cierre. `l` y `c` siguen intactas; las carpetas privadas
  `q..aa` se conservan.


### Registro 2026-10-18 (continuación R1): mejora implementada y observación real

- **Hecho estático nuevo:** el consumidor `0x80057608` acepta el candidato `0x98`
  **y** `0xAA` (delay slot `0x80057610`); el handler `0x800607A0` escribe
  `control+8`; la puerta consume `control+0x56` en `0x800570F8`→`0x800570FC`
  (dentro de `0x80056E54`), luego el hook `0x80054AE8` llega en el mismo frame.
  Detalle en `COMBATE_MAPA.md` §9.1.
- **Mejora implementada (una):** `standard_command` retiene un `cmd25`/`cmd29`
  reconocido mientras `control+4` no tiene `0x20`/`0x40` y lo reinyecta por
  `control+0x56` (máx. **16** frames de invitado) al armarse la bandera aérea.
  Solo escribe `control+0x56`; no toca `control+4`/`control+8`. Contadores
  `dbfb.responsive.followup_wait`/`followup_inject`.
- **Archivos:** `src/mods/dbfb_responsive.c`,
  `tools/tests/test_responsive_harness.c` (nuevo escenario),
  `tools/tests/test_responsive.py` (35 grupos C),
  `mods/preloaded/packages/dbfb.responsive/0.1.0/manifest.toml`,
  `COMBATE_MAPA.md` §9.1, `COMBATE_REDISENO.md` §14, `COMBATE_EVIDENCIA.md`,
  `ROADMAP_RELEVO_COMBATE.md`, `summary.md`.
- **Comandos y resultados reales:** `python -B -m unittest discover -s tools/tests
  -p "test_*.py"` → **69/69 PASS**, **35 grupos C**; `cmake --build build-release
  --target psx-runtime psx-runtime-pgxp -j 4` → **PASS** (hubo que esperar a que
  terminara la sesión de otro agente que bloqueaba el exe; no se mató nada);
  `python tools/verify_offline.py` → **PASS** (namespace sin cambios,
  `cg18_1b6950cb_gc58692d0b_f0`, 1157 DLLs); `git diff --check` → exit 0 (solo
  avisos CRLF preexistentes).
- **Partidas privadas** (headless, puertos 4384/4386, carpetas propias;
  `dbfb-r1-probe-20261018` y `-probe2/-probe3`): `wtrace_add` exclusivo sobre
  `control+4`/`control+8`. Retención observada **64×** (life 8) y **16×** (life 16);
  `followup_inject` **0**. `0x98`/`0x99` sí se escriben en `control+8`
  (`0x8004EEAC`/`0x80057F94`), pero **no** aparecen los stores de limpieza del
  consumidor ni los productores de `0x80`: el consumidor **no** se ejecutó.
- **R1 sigue ABIERTO.** Bloqueo exacto: falta mapear qué entrada/acción arma
  `control+4` `0x20`/`0x40` (productor `0x1D` `0x8005D900`; el de `0x40` sin
  localizar). Sin esa ventana el gesto sintético no entra y no se puede ver la
  entrega ni el consumidor. **Siguiente experimento:** saltar con cada botón
  candidato registrando `control+8`/`control+4` por wtrace para hallar el que arma
  `0x20`/`0x40`; con esa ventana, repetir `cmd25` y observar `followup_inject`,
  `0x8006081C` y `0x800576F8/0x80057734/0x80057764`.

## 7. Cierre de esta tanda — 2026-10-19

Resumen del estado real tras esta continuación (verificado con tests, build,
verificación offline y partidas). Se separan hechos demostrados de pendientes.

### R0 — bloqueo intermitente: causa corregida de clase (cerrado como defecto)

- **Causa (ya medida):** el muestreador de host suspendía el hilo de emulación
  desde otro hilo (`SuspendThread`), sin cota de latencia; si el propio hilo
  muestreador se retrasaba, el juego quedaba congelado (ciclos/frames/insns
  quietos, 0 µs de CPU del objetivo). No era un bucle MIPS.
- **Arreglo de clase (runtime genérico, no parche de juego):** el sampler
  suspend-based de Windows ahora es **opt-in explícito**
  (`PSX_HOST_SAMPLER_SUSPEND=1`); por defecto no crea el hilo que suspende. El
  watchdog de starvation **no se tocó** (ni umbral ni lógica).
  Archivos: `psxrecomp/runtime/src/host_sampler.c`,
  `psxrecomp/runtime/include/host_sampler.h`,
  `psxrecomp/runtime/tests/test_host_sampler_policy.c` (nuevo),
  `psxrecomp/runtime/CMakeLists.txt` (registro), `psxrecomp/tools/host_profile.py`
  (nota de uso).
- **Verificación:** nueva prueba `test_host_sampler_policy` (default/invalid no
  suspenden ni muestrean; `enabled` sí) y `tools/tests/test_host_sampler_policy.py`;
  sesiones de 420 s con `host_sampler_max_suspend_us=0` y
  `host_sampler_max_suspend_hold_us=0`, salida 0 y 4 combates (p. ej.
  `dbfb-r0-fixed-20261019a`). El caso `l`/`c` (suspensión host ≥4 s) queda
  explicado por la misma causa; ya no puede producirse con el sampler por defecto.

### R1 — remates aéreos: cmd25 entregado y observado en partida (abierto solo en cmd29)

- **Causa del no-inject (observada):** el Circle final del gesto25 arrancaba el
  normal terrestre `6A` y activaba `control+0` bit8, que impide que arriba arme
  `0x20` durante LIFE16. No era latencia ni vida insuficiente.
- **Mejora implementada:** al retener un `cmd25` en el suelo, `followup_lift()`
  sustituye **solo** los argumentos de entrada nativos (`sp+0x10/0x14`) del gesto
  por la entrada de arriba; el motor original produce `1D` y `0x20`, y después se
  entrega `25` por `control+0x56`. No escribe flags ni acciones; conserva LIFE16,
  coste y guardas nativas. Contadores de motivo: `followup_wait`,
  `followup_lift`, `followup_inject`, `followup_expired`, `followup_interrupted`,
  `followup_native`, `followup_superseded`.
  Archivos: `src/mods/dbfb_responsive.c`, `tools/tests/test_responsive_harness.c`,
  `tools/tests/test_responsive.py`.
- **Observado en partida (420 s, ambos lados humanos y contra CPU):** 32 arranques
  /26 inyecciones (vs CPU) y 18/18 (ambos humanos); cadena completa
  `54A24(25)→5D910(20)→6081C(98)→62FF4(80)→57734/57F94(99)`, reconocimiento y
  productor en el mismo frame, entrega 2 frames después. También `98→9A` sin
  confirmación, interrupción real por golpe, dos pausas `0→1→0` y save+2 loads.
  Evidencia privada: `dbfb-r1-*-20261019`.
- **Pendiente mínimo:** capturar `cmd29/ID6→200→9B` (sin ampliar el mapeo a otros
  IDs a ciegas). La pausa/restore dentro de la ventana pendiente de 2 frames está
  cubierta por el arnés, no capturada en partida.

### R2/R3 — movimiento/clips: geometría y anatomía parciales, transición propia (abierto)

- **Demostrado offline:** 18 registros, 425 piezas, 14.755 polígonos; límites de
  vértices == límites almacenados. Cadena modelo→geometría→parte→jerarquía:
  EXE `80011C10..80011D64`, STEP40 `8004201C` (etiqueta), `800401B4` (pieza),
  `80042568` (padre). Ejes locales y orden `Rx·Ry·Rz` (4096/vuelta) contra
  `RotMatrix` EXE `8002059C..80020824`. Anatomía observada **solo registro 0**:
  parte8→9 (brazo), 18→19→20 (pierna/pie).
- **Transición propia:** `src/mods/dbfb_rig_bridge.h` genera una transición de
  pose local slot2→1 (6 ticks, smoothstep, 28 partes, 3984 bytes, incluye el
  paquete final nativo `0x01090000`); **no es retiming**. Es parcial (no full-body
  ni root motion). Generador idéntico byte a byte al de referencia en 18 registros.
  Herramientas: `tools/combat_rigclip.py`, `tools/combat_rig_preview.py`, tests
  `tools/tests/test_combat_rigclip.py`, `tools/tests/test_rig_bridge_harness.c`.
- **No integrado al runtime ni renderizado en partida.** Falta propietario que
  lea la pose real, preserve la trayectoria de los carriers protegidos y entregue
  el destino sin duplicar deltas relativos (pausa/restore/online/KO). No sustituir
  una acción completa ni anteponer 6 ticks a golpes.

### R4 — cámara general: propiedad mapeada, sin encuadre implementado (abierto)

- **Demostrado:** contexto `0x800A9FA0`, publicado en `0x800A9D0C` por `0x80047FA4`;
  rama general `0x80054EC4` (modo==1), con `context+0` como puerta de supresión y
  `context+8` seleccionando tomas internas; `context+0x50/+0x70/+0x90/+0xB0` son
  actual/anterior/destino/delta (6 palabras); matriz vía
  `80054F90→44824→24850`. `0x800A8680==0` NO selecciona la cámara general.
- **Sonda de solo lectura:** `src/mods/dbfb_camera.h` + `tools/combat_camera.py`
  (18 guardas, 9 ventanas con hash, 3 sitios de ejecución), test
  `tools/tests/test_combat_camera.py`. **No escribe RAM.** No implementa encuadre:
  falta demostrar `80024850`/proyección/recorte y límites visibles de ambos modelos.

### Verificación de esta tanda

- `python -B -m unittest discover -s tools/tests -p "test_*.py"` → **86/86 OK**
  (35 grupos C, matriz 942 variantes incluidas).
- `cmake --build build-release --target psx-runtime psx-runtime-pgxp -j 4` → **PASS**
  (ambos enlazados, exit 0).
- `python -B tools/verify_offline.py` → **OFFLINE VERIFICATION PASSED**
  (1157 DLLs, namespace `cg18_1b6950cb_gc58692d0b_f0`).
- `python -B tools/combat_camera.py --check` → PASS; `combat_rigclip.py --record 0`
  → metadatos correctos.
- Partida integrada `dbfb-final-20261019` (420 s, puerto 4389): **4 combates**,
  pausa, save/load, locomoción propia, salida 0, `fatal` ausente,
  `host_sampler_max_suspend_us=0`; contadores `motion_variants=324`,
  `technique_variants=144`, `pose_transitions=105`, `locomotion=6109`,
  `followup_wait=23`.
- `git diff --check` → exit 0 (solo avisos CRLF preexistentes).

### Pendientes explícitos (no cerrados)

- R1: rama `cmd29/ID6→200→9B`; ventana pendiente bajo pausa/restore en partida.
- R2/R3: integración al runtime + render y calidad visual; anatomía de los otros
  17 registros; giro propio y correspondencia pies/desplazamiento.
- R4: proyección/recorte y encuadre general; límites visibles de ambos modelos.
- R5: fichas por golpe medidas (frame advantage real), no estáticas.
- R6: dificultad 0/1/2 en partidas y balance humano.
- R7: matriz de partidas más amplia y reconciliación catálogo/docs.
- No hay commit/push/publicación; cambios sin commit conservados a propósito.

## 8. Cierre 2026-10-19 (segunda tanda) — esta sección sustituye los pendientes de §7

Se ejecutó con subagentes en paralelo (R1, R3, R4, R5, R6) más verificación del
coordinador. Todo lo de abajo está ejecutado y comprobado salvo lo marcado.

### R3 — transición de clip integrada (settle nativo) y probada en partida

- **Integración real elegida** (más conservadora que el clip puente completo):
  `src/mods/dbfb_pose_settle.h` (nuevo) con `motion_settle_build()`, llamado
  desde `motion_build()` en `src/mods/dbfb_motion.h` (línea 403). Solo actúa
  sobre el archivo de 218 slots (registro 0): verifica por FNV las pistas
  nativas 0/1/2 y 105 y el patrón de la acción 6
  (`0x01200002 / 0x00200069 / 0`), clona la pista 105 con DOS paquetes
  relativos nuevos por grupo (partes 8/9, `pose_packet` relativo) que telescopan
  a cero en la muestra 5, conserva byte a byte todos los paquetes originales,
  raíz/carriers y el paquete final nativo, y publica un slot nuevo apuntado por
  la acción 6. Otros usuarios de la pista 105 no se tocan. Sin hooks nuevos, sin
  reloj de host: el dueño sigue siendo el playback nativo (`context+8`).
- **Pruebas:** `tools/tests/test_pose_settle.py` (oráculo de transformación
  nativa: handoff exacto módulo-16 para poses de entrada arbitrarias -32760/0/
  32760, paquetes originales intactos en orden, timing nativo de la acción 6);
  `tools/tests/test_pose_settle_harness.c`; `tools/tests/test_combat_assets.py`.
- **Prueba en partida (coordinador):** sonda de solo lectura durante sesiones
  `dbfb-r3-verify{,2,3,4}-20261019`. Con `slots=218` el puntero de arena es
  `0x9F000000` (`scripts=arena+16`, `animations=arena+712`, validado por el
  propio mod) y la acción 6 apunta a un **slot creado (245)**, no al nativo 105
  (`word0=0x01200002`, `word1=0x002000F5`). La acción 6 no está en el conjunto
  de retiming (`motion_selected` = 0x64..0x77/0xA0..0xA5/0x8C), así que el único
  escritor posible de esa entrada es el settle. Sesiones con 2-4 combates,
  salida 0.
- **Límites:** no hay comprobación visual humana del resultado del settle (solo
  datos de invitado + oráculo offline); anatomía de los otros 17 registros sin
  tocar; la rama de 6 ticks solo se aplica a la acción 6 del registro 0.

### R4 — encuadre general implementado en el punto de entrega nativo

- **Hallazgo que lo desbloquea:** una escritura en `0x80054F34` (seam antiguo)
  se pierde porque `0x800442A8`/`0x8004778C` reescriben `+0x50` después. El
  punto correcto es **`0x80054F88`** (`lui a0,0x800b`; palabra original
  `0x3C04800B`), justo antes de `jal 0x80044824` con `a0+0x50` en el delay slot
  - el mismo frame lo consume `0x80024850` (ojo `+0x50/+54/+58`, objetivo
  `+0x5C/+60/+64`, 8 palabras).
- **Implementación:** `src/mods/dbfb_camera_frame.h` (nuevo): plugin de sitio de
  instrucción registrado en `src/mods/dbfb_responsive.c`. Escala SOLO el vector
  ojo→objetivo nativo (17/16, ~6,25 % de zoom-out); no toca objetivo, lock,
  flags de toma ni delta de transición. Guardas que rechazan antes de escribir:
  apagado (`DBFB_CAMERA_FRAMING=0` para A/B), fuera de alcance, pausa
  (`0x800A868C`), KO (`s_ko_frames`), modo != 1, contexto != `0x800A9FA0`, lock
  `context+0 != 0`, transición (`+0xB0..+0xC4` no cero) y coordenadas fuera de
  rango. Contador `dbfb.responsive.camera_framing`.
- **Config:** `game.toml` `mod_instruction_sites` += `0x80054F88` → hash de
  configuración nuevo. **Overlays recompilados** con el pipeline documentado:
  **1158 OK, 330 skipped, 8 rechazos** (3 audit + 5 fragment, regiones kernel
  0x1000/0x2000; no se debilitó la auditoría). `verify_offline.py` **PASSED**:
  namespace nuevo **`cg18_1b6950cb_gc164a1e9a_f0`**, 1158 DLLs, config 15677
  bytes. Build normal+PGXP exit 0.
- **Pruebas:** grupo C 36 en `tools/tests/test_responsive_harness.c`
  (`camera framing: native delivery seam, offset-only scale, target intact,
  mode/lock/transition/KO/pause/online/out-of-bounds reject`), con la lista de
  escrituras permitidas ampliada solo a las 3 palabras del ojo. Suite **111
  tests OK**.
- **Partidas:** `dbfb-r4-verify-20261019` (encuadre ON): PASS, salida 0, 2
  combates, `camera_framing=435`, `camera_shake=422`, `ko_camera=48`.
  `dbfb-r4-verify-off-20261019` (`DBFB_CAMERA_FRAMING=0`): PASS, salida 0,
  contador ausente (=0) → el opt-out funciona y no hay escrituras.
  `dbfb-r4-shots-20261019`: 3 capturas en combate real (stride 21, HP 346/392 y
  256/392) con render correcto (Goku vs L. Goku, ambos luchadores en cuadro).
- **Límites:** el A/B visual exacto del 6,25 % no está demostrado (poses
  distintas entre sesiones); no se excluyeron formalmente las tomas internas
  (`context+8`); no se verificó que ambos luchadores "quepan" en todos los
  planos.

### R1 — rama cmd29/ID6→200→9B y ventana pausa/restore observadas en partida

- Sesión `dbfb-r1-cmd29-20261019` (puerto 4393, PID 34008, salida 0 tras quit;
  ID6=Gohan vs ID7=Cell, ambos humanos). Cadena completa capturada:
  `32034 seq241261 0x8005D910` (control+4 0x1000→0x1020), `32048 seq241406
  0x80054A24` (+0x56 → 0x29), `32048 seq241408 **0x80060AAC 0x1020→0x1220**`
  (añade 0x200), `seq241409 0x80060ABC` (control+8 → 0x98), `32074 seq241686
  0x80062FF4` (0x1200→0x1280, confirma contacto), `32086 seq241826 0x800576F8`
  (limpia 0x200), `seq241827 0x80057734` (limpia 0x80), `seq241829 0x80057F94`
  (**control+8 → 0x9B**). El decisor 0x800576BC es rama, visible por su efecto.
- **Pausa/restore en la ventana pendiente:** 3 ensayos cmd29 en suelo
  (reconocimientos f41760/41860/41960) y 1 cmd25 con lift (f45286): la pausa cae
  dentro de los 2 frames reconocimiento→entrega, el frame queda quieto, y al
  reanudar `0x80054994` limpia `+0x56` **sin despacho ni entrega**; sin
  corrupción ni inyección indebida. Contadores {wait 11,lift 0,inject 0,expired
  7} → {12,1,0,7} tras la pausa.
- **Límite:** el instante exacto del inject a +2 frames no es visible en traza
  pausada (evidencia previa); cmd29 en suelo nunca inyecta (7 expiraciones); el
  lift del mod solo sustituye entradas de cmd25.

### R5 — fichas por golpe medidas (herramienta nueva)

- `tools/combat_cards.py` (nuevo; modos `--launch`/`--combine`) mide en
  VBlanks del juego: startup = frame de impacto (store de HP, escritor nativo
  `0x80066E90`) − frame de presión; recuperación = primer frame estable con
  acción ≤ 0x23; ventaja = recuperación del defensor − la del atacante; hit-stop
  = delta del contador del plugin con tick-hold medido.
- **Tabla combinada** (4 sesiones, 131 intentos, `combined-cards.json`):
  cuadrado 0x1000 → acciones 0x72/0x73, n=3, startup 17/18/20 VB, ventaja hit
  2/38/40, bloqueo 0 y 12 (n=2), whiff 32/36/42, hit-stop 4 VB (n=6);
  triángulo 0x8000 → 0x64/0x65, n=2, startup 14/18.5/23, whiff 32, hit-stop
  2 VB (n=3); círculo/cruz → 0 muestras válidas; aéreos → 0 muestras (bandera
  0x20 no activa al iniciar). Tick-hold 17-23 VB en los impactos.
- **Pruebas:** `tools/tests/test_combat_cards.py` (20 casos con trazas
  sintéticas, sin exe). Evidencia privada `dbfb-r5-cards-{b,c2,d,e}-20261019`,
  `dbfb-r5-combined-b-20261019`.
- **Límites:** n pequeño (3-6), ventaja varía 2..40 según estado del rival; sin
  bloqueo controlado; `no_action` frecuente (10-13 de ~17 por golpe) sin causa
  identificada.

### R6 — dificultad 0/1/2 verificada en partidas reales

- 3 sesiones (`dbfb-r6-diff{0,1,2}-20261019`, puertos 4394-4396, 330 s,
  salida 0). Dificultad fijada con `write_ram` en `0x8003BC74` + readback;
  wtrace capturó los stores nativos `0x80053DE4` (J1) y `0x80053EFC` (J2) con
  el valor pedido; en combate `0x8003BC74`/`0x80072960`/`0x80072984` = 0/1/2 en
  el 100 % de 1,3-1,5 k muestras por lado; modo 0x40 en todas las peleas.
- **Acciones del CPU por minuto emulado** (mediana): 28,0 / 37,4 / 42,7 (dif 0/
  1/2); comandos nativos `+0x56` 20,8/20,8/25,2; `ai_command` 0/0/1. La cadencia
  extra del mod (150/120/90 VBlanks) **no es distinguible** en partida porque el
  gate de inyección casi siempre está cerrado.
- **Límites:** n=1 sesión por nivel, emparejamientos y turbo distintos → la
  subida de acciones es observación, no atribución causal; dif0 vs dif1 no se
  separan. Balance humano no automatizable (harían falta jugadores reales).

### Verificación de la segunda tanda

- `python -B -m unittest discover -s tools/tests -p "test_*.py"` → **111 tests
  OK**, **36 grupos C**.
- `cmake --build build-release -j 4` → **exit 0** (normal + PGXP).
- `python -B tools/verify_offline.py` → **PASSED** (namespace
  `cg18_1b6950cb_gc164a1e9a_f0`, 1158 DLLs, config 15677 bytes).
- `python -B tools/combat_camera.py --check` → PASS (18 guardas, 9 ventanas, 16
  palabras del seam, 30 del EXE).
- Partidas de verificación: R3 (3 sesiones con sonda de arena), R4 (2 sesiones
  A/B + 1 de capturas), R1 (1 sesión con wtrace), R5 (4 sesiones), R6 (3
  sesiones). Todas con salida 0.
- `git diff --check` → exit 0 (solo avisos CRLF).

### Pendientes tras la segunda tanda

- R2/R3: calidad visual del settle no comprobada a ojo; anatomía de los otros 17
  registros; giro propio y correspondencia pies/desplazamiento; clip puente
  completo (`dbfb_rig_bridge.h`) sigue sin dueño de runtime.
- R4: A/B visual exacto; exclusión formal de tomas internas (`context+8`);
  demostrar que ambos luchadores caben en todos los planos.
- R5: aéreos y bloqueo controlado sin medir; n mayor.
- R6: n≥3 por dificultad y turbo comparable; cadencia del mod con P2 humano.
- R7: matriz ampliada y reconciliación catálogo/docs.
- Sin commit/push; cambios sin commit conservados a propósito.

## 9. Revisión visual del agente y cierre de R7 — v0.2.0 experimental

Encargo: revisión visual sin delegarla al usuario, actualizar este roadmap,
cerrar R7 y publicar commit + push + release. La autorización de publicación
es explícita en esta continuación. No se requiere una revisión humana para
dar por realizada la inspección descrita aquí.

### Inspección visual realizada (píxeles del render nativo)

1. `tools/combat_bridge_live.py --seconds 120 --port 4401 --lifecycle` con
   salida privada `dbfb-release-visual-settle-20261019`: Goku/registro 0 frente
   a Boo/ID8; 71 capturas del historial del render, 109.167 escrituras
   observadas, salida 0. Acción 6 enlazada al slot creado. Pausa dentro del
   clip propio, contexto quieto, guardar/restaurar exacto y ambas reanudaciones
   **true**. El agente abrió las capturas 2898/2901/2906 y el montaje ampliado
   2896–2907: retorno del brazo visible, manos/brazos unidos al cuerpo,
   silueta coherente y pose final estable; no se observó geometría rota ni
   salto de raíz en esa secuencia. Es una comprobación real del render del
   registro 0, no de las anatomías sin mapear ni de todos los personajes.
2. `tools/combat_visual_ab.py`: dos procesos aislados con el mismo estado
   pausado y ruta de entradas por frame, `DBFB_CAMERA_FRAMING=1/0`.
   `dbfb-release-camera-ab-20261019` falló al cargar antes de crear las arenas;
   la herramienta se corrigió para entrar en combate antes de cargar.
   `dbfb-release-camera-ab2-20261019`: dos salidas 0, 13 pares de imágenes.
   El par relativo **145** conserva idénticos los 124 bytes de control de
   **ambos** luchadores; la cámara difiere. El agente abrió ese par: misma
   postura, HUD intacto y encuadre activado visiblemente más abierto.
   Abrió además los 26 fotogramas en montaje: suelo, separación, vuelo,
   ataques y reacción. No se vio corrupción de render.
3. **Límite observado:** en vuelo se recorta al luchador superior tanto con
   cámara ON como OFF. No se afirma que el cambio mantenga a ambos siempre
   dentro del plano. Los otros 12 pares no conservan todo el estado idéntico;
   el veredicto determinista completo del instrumento es **false** y se
   conserva así. Solo el par 145 es A/B de estado equivalente; el resto es
   revisión observacional. La escala numérica 17/16 está probada por arnés,
   no medida como una proporción exacta de píxeles en esos planos.

### Matriz de integración ampliada y resultado completo

Evidencia privada en `%TEMP%/opencode/`; no publicar capturas, estados o RAM.

| Sesión | Alcance | Resultado real |
|---|---|---|
| `dbfb-final2-20261019` | Estándar, 300 s, 3 combates, pausa/estados/movilidad | PASS, salida 0; framing 3350, pose 87, unlock 1; sampler 0 |
| `dbfb-release-visual-settle-20261019` | Transición propia y ciclo pausa/estados | PASS funcional + inspección visual anterior; salida 0 |
| `dbfb-release-camera-ab2-20261019` | 13 pares, cámara ON/OFF | 2 salidas 0; 1 par equivalente; determinismo completo FAIL, revisión visual acotada |
| `dbfb-release-matrix-20261019/original` | Primer ZIP, mods apagados | FAIL, watchdog, frame 9781; Python auxiliar incompleto |
| `dbfb-release-matrix-20261019/standard` | Primer ZIP, 300 s | PASS, 3 combates; autocompile degradado por Python incompleto |
| `dbfb-release-matrix-20261019/pgxp` | Primer ZIP, 240 s | PASS, 1 combate; misma limitación de Python |
| `dbfb-release-matrix2-20261019/original` | ZIP con Python corregido, 240 s | FAIL tras 1 combate, watchdog frame 17850, sampler 0, autocompile no degradado |
| `dbfb-release-matrix2-20261019/standard` | ZIP corregido, 180 s | PASS, 1 combate, pausa/estados/movilidad, salida 0, autocompile correcto |
| `dbfb-release-matrix2-20261019/pgxp` | ZIP corregido, 180 s | PASS, 1 combate, pausa/estados/movilidad, salida 0, autocompile correcto |
| `dbfb-release-original-diag-20261019` | Original, 300 s, carpeta ya usada, diagnóstico de carga | PASS, 2 combates, pausa/estados, plugin inerte, salida 0; carga máxima 2204 µs |
| `dbfb-release-cold-diag-20261019/original` | Extracción nueva, original, 300 s | Cierre normal y pausa/estados PASS, 0 combates completos: smoke FAIL por cobertura; carga máxima 44191 µs |
| `dbfb-release-matrix-final-20261019/original` | ZIP final, extracción nueva, 300 s | PASS, 2 combates, pausa/estados, plugin inerte, salida 0; autocompile correcto |
| `dbfb-release-matrix-final-20261019/standard` | ZIP final, 180 s | PASS, 1 combate, pausa/estados/movilidad, salida 0; autocompile correcto |
| `dbfb-release-matrix-final-20261019/pgxp` | ZIP final, 180 s | PASS, 1 combate, pausa/estados/movilidad, salida 0; autocompile correcto |

**R0 reabierto en su alcance general:** desactivar la suspensión del sampler
elimina ese mecanismo, pero los dos watchdog con sampler=0 demuestran otra
incidencia sin causa atribuida. Las cargas medidas en sesiones sin fallo no
prueban que Windows/loader sea el culpable. Se añadieron al reporte final los
contadores de carga ya existentes (`overlay_load_total_us/max_us/last_us`).
No se subió el timeout ni se suprimió el watchdog. Una sesión PASS posterior
no borra esos fallos. Se publica **pre-release experimental**, no release estable.

### Catálogo, verificaciones y paquete

- Catálogo reconciliado: `standard` y `unlock-all`, ambos apagados por defecto;
  descripción fiel a transición nueva limitada al registro 0, cámara y límites.
  El empaquetador oficial filtra la traza developer sin eliminar el estándar.
  No se incluye el `mods/state.toml` local ni sus rutas de texturas.
- `python -B -m unittest discover -s tools/tests -p "test_*.py"`: **112 OK**,
  36 grupos C, matriz de 942 variantes. Se agregó una prueba para que el smoke
  original exija KO nativo y plugin inerte, no contadores del mod activado.
- `cmake -S . -B build-release '-DPSX_GAME_VERSION=0.2.0'` y
  `cmake --build build-release -j 4`: ambos ejecutables enlazados, versión 0.2.0.
  En PowerShell hay que entrecomillar el argumento de versión: sin comillas
  una primera invocación lo dividió como `0`/`.2.0`; se corrigió y reconstruyó.
- `python -B tools/verify_offline.py`: PASS, config 15677 bytes y 1158 DLLs en
  `cg18_1b6950cb_gc164a1e9a_f0`; se conservan los ocho rechazos kernel previos.
- Test independiente del watchdog: GCC C11 `-Wall -Wextra -Werror -pedantic`,
  **26 comprobaciones correctas**. Tests de política del sampler incluidos en
  la suite. `git diff --check` sin errores de espacios.
- `python -B tools/package_release.py`: usa el stager oficial para el catálogo,
  caché, licencias y manifiestos de ejecución. Añade PGXP y reutiliza TinyCC
  instalado; genera Python portable desde la instalación local funcional con
  su biblioteca estándar y licencia. Ejecuta imports, `compile_overlays --help`
  y `tcc -v`; valida CRC y SHA256 de todos los archivos del ZIP. Sin descargas
  ni instalaciones nuevas. Los paquetes descartados se respaldan en `dist/`.
- Paquete: `dbfb-0.2.0-windows-x64.zip` y checksum; sin disco, BIOS retail,
  capturas, estados, volcados ni fuentes generados. OpenBIOS MIT sí se incluye.
  Fuentes del núcleo fijadas en `835f190226b40abc3ecde1e27b882aca7b3d56ca`,
  ya publicadas en el fork `novapowers0/psxrecomp`, rama `rework-master`.
- ZIP final validado: **83.480.650 bytes**, **2749 archivos**, SHA256
  `c1e17b089f3d5868c1970575b50344b74a576060b73022466b6bb1f2aabcfb6d`.
  Se extrajo de nuevo, se comprobaron todos sus hashes y se ejecutó la matriz
  final anterior: 3/3 sesiones PASS. Núcleo sin marca dirty `835f1902`;
  sampler=0 y autocompile no degradado en las tres. Cargas máximas
  65067/1805/2382 µs (original/estándar/PGXP). Estos PASS no resuelven por sí
  solos los dos watchdog anteriores. **Publicada** como pre-release en
  `https://github.com/novapowers0/DB-Final-Bout-Recomp/releases/tag/v0.2.0`.
  Commit/tag `285cb7f4003f347af9d06a3830b3688d2c5125d3`, push a `master`
  confirmado; GitHub confirmó ambos assets `uploaded` y el SHA256 remoto
  coincide con el ZIP local. `v0.1.1` se conserva como última estable.

### Cierre y seguimiento

**R7 cerrado como ciclo de verificación, reconciliación y entrega experimental**:
matriz ejecutada con éxitos y fallos explícitos, visual inspeccionado por el
agente, catálogo y documentación coherentes, versión y paquete comprobados.
No equivale a cerrar R0–R6 globalmente. Seguimiento de producto: R0 watchdog
intermitente sin causa; R2 giro/pies y anatomía de otros registros; R4 recorte
en vuelo y exclusión de todas las tomas internas; R5 muestras aéreas/bloqueo;
R6 balance cuantitativo más amplio. Estos son límites declarados de v0.2.0,
no comprobaciones pendientes que se encarguen al usuario antes de publicar.

## 10. Seguimiento R0 — espera bloqueante corregida y publicada en v0.2.1

**Estado vigente tras la publicación.** Encargo: investigar R0 y dejar el estado
pulido y bien establecido. Registro completo y comandos en
[`R0_ESTABILIDAD.md`](R0_ESTABILIDAD.md).

- **R0-A cerrado:** sampler de Windows opt-in, ya incluido en v0.2.0.
- **R0-B cerrado en su reproducción controlada:** el VBlank esperaba con
  `INFINITE` a trabajadores que publican `DONE` antes de terminar realmente.
  Se reprodujo el bloqueo antes del parche; ahora el sondeo espera cero,
  conserva recursos/estado y reintenta en el siguiente frame. El test retiene
  ambos trabajadores, confirma finalización única y sigue comprobando las 300
  publicaciones y el cierre del pipeline.
- **R0-C abierto:** además de los dos cierres de §9, se reprodujo uno con
  diagnóstico pasivo en `dbfb-r0-matrix-20261019/1-original`, frame7236,
  pared5.241.554µs/CPU1.046.875µs/69.625ciclos, sampler0 y carga máxima4744µs.
  No tenía aún atribución por sección; no adjudicarlo automáticamente a R0-B.
- Observabilidad nueva: `watchdog_max_check_gap` y `watchdog_host_sections` en
  el reporte final; ocho secciones host. Ni cambios de temporización invitada
  ni nuevos heartbeats ni umbrales. Las pruebas del watchdog real conservan la
  salida2 tras una espera4,5s y ante un bucle sin heartbeat.
- Herramienta nueva `tools/combat_stability.py`: valida ZIP, aísla **cada modo**,
  repeticiones/frío y tarjetas, registra hashes/identidad/errores del runtime.
  `--build` prueba explícitamente los binarios locales, no sustituye una prueba
  de la distribución publicada. `--modes original --rounds 3 --stop-on-failure`
  permite perseguir R0-C con un comando sin pedir pruebas al usuario.
- **Verificación final ejecutada:** 121tests OK, build normal/PGXP y offline
  PASS. Matriz `dbfb-r0-verified-final-20261019`: original600s/5combates,
  estándar300s/3, PGXP300s/2; **3/3 PASS**, pausa/estados, cierre0, autocompile
  correcto y sampler0. Núcleo `835f1902-dirty`, hashes en el documento de R0.
- Nueve sesiones originales600s **anteriores al parche** ya pasaban con48
  combates; por tanto esos PASS no sirven como prueba causal del parche.
- WPR general perdió eventos; no usarlo como prueba de causa. xperf CPU reducido
  sin avisos de pérdida, pero su sesión PASS no capturó el cierre.
- Seguimiento preciso: capturar R0-C con secciones/traza completas, atribuir la
  operación, reproducir y corregir. El rescan del proveedor conserva costes
  medidos de1,1–1,4s; no fue eliminado por la corrección de las esperas.

La revisión se publicó como **v0.2.1**; v0.2.0 permanece inmutable. R7
continúa cerrado como entrega experimental. R0 global no se marca cerrado por
haber corregido R0-B ni por una matriz sin fallos.

## 11. Publicación v0.2.1 — mantenimiento experimental

- **Núcleo:** `a51c9aa7` (`runtime: avoid blocking VBlank on finishing
  autocompile workers`), subido a `nova/rework-master`.
- **Repo principal:** `9b60a4d` (evidencia R0, herramienta y pin) y `7bfb3a1`
  (VERSION/notas/README). Tag anotado `v0.2.1`; master remoto `7bfb3a1`.
- **Build:** `nightly-1382-ga51c9aa7`, VERSION 0.2.1.
- **Paquete:** `dbfb-0.2.1-windows-x64.zip`, 2.749 archivos, 83.484.971 bytes,
  SHA256 `b9c67dea5092e5668930508fb88cab1de1ea1e6f856993b2850135f65054a20e`;
  `.sha256` adjunto. Assets `uploaded` y digest remoto = local.
- **Prueba del paquete:** matriz sin `--build` 3/3 PASS: original600s/5combates,
  renovado300s/3, PGXP300s/2; pausa/estados/locomoción/cierre0/autocompile/
  sampler0. Evidencia privada `dbfb-021-release-matrix-20261019`.
- **Publicación:** pre-release (no latest; v0.1.1 sigue estable):
  https://github.com/novapowers0/DB-Final-Bout-Recomp/releases/tag/v0.2.1
- **Límite:** R0-C no se cierra. La corrección es de clase y está probada en su
  reproducción controlada, pero no explica por sí sola los tres cierres
  históricos. Los costes de `provider_poll` (1,1–1,4 s) siguen documentados.
