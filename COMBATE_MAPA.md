# Final Bout — Mapa del sistema de combate y plan de modificación

Fecha: 2026-10-17. Alcance: recompilación USA (SLUS-00493), overlay STEP40.
Fuente: desensamblado estático read-only con `tools/combat_map.py` (STEP40 cocido
SHA256 `001adcdc…b9dd`, base verificada `8003DFA0`, 33.393 PCs ejecutados).
Nada de este documento se ha validado todavía en partida real.

**Dirección vigente del producto:** `COMBATE_REDISENO.md`. El catálogo público
ahora ofrece únicamente **Combate renovado** (`standard`), sin ajustes necesarios.
Las tres reglas separadas de §3 son antecedentes de desarrollo, conservados en
`mods/development/dbfb.responsive-legacy.toml`, no tres interruptores que deba
configurar el jugador. La traza de desarrollo sigue disponible por separado.

Convención: las direcciones se dan con el inmediato ya extendido con signo.
El desensamblador muestra `addiu`/`ori` en sin signo; `lui 0x800b` + `lw …, -0x795c`
es `0x800A86A4`, no `0x800B86A4`.

## 1. Cadena completa: mando → golpe → reacción

| Etapa | Dirección | Qué hace | Conf. |
|---|---|---|---|
| Lectura de mando | `0x80010F40` `PadRead` | Devuelve pad con bytes intercambiados. Ventana `0x10C` FNV `C4EF2A99` | alta |
| Sondeo | `0x8003FCF0` | En combate se llama **cada 2 frames**. Escribe flancos en `0x800A9CE8` (pulsado), `0x800AA198` (soltado), `0x800A9F30` (unión); guarda el pad previo en `0x1F800004` | alta |
| Remapeo | `0x8003FE68` | Reescribe el word de pad según modo (`0x8003BC70/72`) y swap `0x8003BC7E` | alta |
| Reconocedor | `0x8005FEA4` | Recorre la tabla de 34 comandos; cada paso es una pulsación exigida; el `wait_field` (12/15) es la **ventana** que sobrevive el paso; espeja ←/→ para J2. Devuelve el id de comando | alta |
| Tabla de comandos | `0x8006EDC8`, 34 × `0x24` | `+0`/`+2` cursor por jugador, `+4`/`+5` espera, `+6` id de salida, `+8..` pasos (`(ventana<<16)|botones`) | alta |
| Puerta de aceptación | `0x80054A60`–`0x80054AE8` | Rechaza el comando (`cmd = -1`) si el luchador está ocupado: `+0x2804` bits `0x20`/`0x40`, contador `+0x291A` ≥ 9, salvo comandos `0x25`/`0x29` o ki negativo | alta |
| Despacho comando→acción | `0x80061120` | `handler = *(0x8006ED04 + idx*4)`; llama al handler y fija la **acción** en `+0x2808`; enciende bit `0x08` de `+0x2800`. Llamado desde `0x800570FC`, `0x8005821C`, `0x80058C04`, `0x80058F60` | alta |
| Intérprete de acción | `0x8004E530` | Ejecuta el script de la acción. Tabla de opcodes en `0x8003E78C` (0x85 entradas; activas `0x00`, `0x20`–`0x26`, `0x40`/`0x41`, `0x60`–`0x62`, `0x80`–`0x82` y `0x84`). Corrección: los índices `0x21`–`0x27` de la versión anterior estaban desplazados una entrada | alta |
| Movimiento | `0x8006639C` | `delta = (velocidad/2)·sen(ángulo)>>12`; aplica a X/Z. Sitios de lectura de velocidad: `0x800666EC`, `0x8006672C` | alta |
| Autocercamiento | `0x8005C768` | Acerca a los luchadores cuando la distancia XZ cae por debajo del umbral de `0x800A8864/68` | media |
| Test de impacto | `0x80058540` | Solo para la acción `0x53`: distancia 3D entre posición previa y actual; si < `0x708` (1800) pone al defensor en acción `0x54` y enciende `+0x2800` bit `0x10` | alta |
| Daño | `0x80066C80`–`0x80066EA4` | Suma términos y aplica `hp = max(0, hp − daño)` en `0x80066E84`/`0x80066E90`; acumula sufrido en `+0x2846` | alta |
| Muerte / KO | `0x80055E3C`, `0x800658D8` | Comparan `+0x2840` contra 0 | media |

### 1.1 Los datos del luchador

Dos arrays independientes, con pasos distintos — no confundirlos:

**A. Estado de control** — base `0x80072800`, paso **`0x7C`** (J1 `0x80072800`, J2 `0x8007287C`):

| Off | Contenido | Evidencia |
|---|---|---|
| `+0x00` | Flags (bits vistos `0x01`, `0x02`, `0x04`, `0x08`=cambió acción, `0x10`=golpe conectado, `0x0800`, `0x2000`, `0x04000000`) | `0x80061198`+, `0x80066DB0` |
| `+0x04` | Flags de estado (bits `0x20`, `0x40` = ocupado; `0x01`) | `0x80054A98`, `0x80057060` |
| `+0x08` | **Acción actual** (byte bajo del word) | `0x8006118C`, handlers |
| `+0x1C/+0x20/+0x24` | Posición **previa** X/Y/Z | `0x80063A94` |
| `+0x2C/+0x30/+0x34` | Posición actual (copia del objeto) | `0x80053F5C` |
| `+0x3E` | **Vida máxima** | `0x80053CF4`, divisor HUD `0x80050974` |
| `+0x40` | **Vida actual** | `0x80066E6C`, HUD `0x80050968` |
| `+0x42` | **Ki** (0…196, 4 barras a 50/100/150) | init `0x80053D60`, recarga `0x8006D1D4`, coste `0x8004F204`, HUD `0x8005098C` |
| `+0x46` | Daño acumulado (halfword, con signo) | `0x80066EC0` |
| `+0x4C` | Fase del balanceo vertical | `0x80058014` |
| `+0x56` | Último comando reconocido (−1 = ninguno) | `0x80054A60` |

**B. Estado del script de acción** — base `0x800728F8 + n*0x30` (J1 `0x800728F8`, J2 `0x80072928`):

| Off | Contenido | Evidencia |
|---|---|---|
| `+0x00` (`0x28F8`) | Puntero al script en curso | `0x8004E584` |
| `+0x04` (`0x28FC`) | Contador de frames del script | `0x8004E590` |
| `+0x06` (`0x28FE`) | Byte de paso | `0x8004E59C` |
| `+0x0C` (`0x2904`) | **Velocidad** (halfword con signo) | opcode `0x24` `0x8004E7B8`; lectura `0x800666EC` |
| `+0x22` (`0x291A`) | Contador de la puerta de aceptación | `0x80054AB8` |
| `+0x02` (`0x2902`/`0x2904` zona) | Parámetros de golpe (`0x2908`, `0x290A`, `0x290E`) | `0x80066C84`, `0x8004F210` |

Tabla de scripts por luchador: `*(0x8006F794 + n*4)` = `0x80117800` / `0x80190000`
(punteros fijos baked en el overlay). **Los scripts viven en RAM cargada en
caliente** — no están en STEP40; ver §4.

**C. Objeto 3D** — J1 `0x80078C9C`, J2 `0x80078CC4` (paso `0x28`), punteros en
`0x800A86A4`/`0x800A86A8`:

| Off | Contenido |
|---|---|
| `+0x12` | **Ángulo/facing** (`0x1000` = 360°) |
| `+0x18` | **X** (word con signo, ±7000) |
| `+0x1C` | **Y** (word con signo) |
| `+0x20` | **Z** (word con signo, ±7000) |
| `+0x24` | Sin uso confirmado |

## 2. Qué está mal y dónde se arregla

| Queja | Causa medida | Punto a tocar | Mecanismo |
|---|---|---|---|
| Respuesta lenta | El sondeo es cada 2 frames (30 Hz) y el reconocedor exige flancos exactos | Ya mitigado por `input-buffer`; siguiente palanca: puerta de aceptación | hook existente |
| No encadenar / cancelar | La puerta rechaza (`cmd=-1`) mientras el luchador está ocupado | `0x80054AD8` (`addiu v0,zero,-1`) | parche de 1 instrucción |
| Movimiento rígido | La velocidad sale del script y se integra en un solo punto | `0x80072904`/`0x80072934` (velocidad) | escalado por tick |
| Daño | `hp = max(0, hp − daño)`; el único `/2` (`0x80066E04`) es de la rama con flag `0x0800` | `0x80066D20`/`0x80066E84` (común) | **necesita 2 instrucciones** → ruta de `mod_instruction_sites` |
| Ki | Recarga lenta, coste fijo por especial | `+0x2842`, tope `0xC4` | añadir por tick / parche de constantes |
| Golpes/ráfagas toscos | Impacto con umbral fijo 1800 y reacción fija `0x54` | `0x80058540` | fase posterior |
| IA | Sin mapear | — | fase posterior |

## 3. Features implementadas en esta fase (todas por defecto OFF)

En `src/mods/dbfb_responsive.c`, paquete `dbfb.responsive`, canal `experimental`,
solo offline (rechazan netplay/resimulado), sin efectos si están apagadas.

1. **`ki-economy`** — por tick de combate añade ki a ambos luchadores (1 punto
   cada N ticks, recortado al tope `0xC4` que aplica el propio juego). No toca
   nada más. Opciones: `mode` (original / flow), `period` (1–8 ticks).
2. **`speed-scale`** — escala la **velocidad** almacenada (`0x2904`/`0x2934`)
   con sombra propia: toma una muestra inicial y escala cambios observados en
   los siguientes sondeos. No reescala valores que permanecen iguales. Al cambiar
   porcentaje usa el último valor bruto observado; Original lo restaura en el
   siguiente sondeo verificado. No mueve posiciones ni toca colisiones. Opciones:
   `mode` (original / 75% / 125% / 150%).
3. **`chain-window`** — parchea **una** instrucción verificada (`0x80054AD8`,
   `addiu v0,zero,0xffff` → `addu v0,a0,zero`) para que la puerta no descarte el
   comando. El parche se aplica en caliente solo si la palabra original coincide
   y sus instrucciones vecinas coinciden (identidad de código). Se revierte al
   seleccionar Original; también reconcilia una partida guardada con código
   parcheado si la opción actual es Original. Opciones: `mode` (original / open).
   Esto relaja una puerta concreta; no demuestra que el motor acepte todos los
   encadenados o cancelaciones deseados.

La cuarta (daño) y la quinta (velocidad agresiva/alcance de golpe) quedan
especificadas y **no implementadas** porque exigen más de una instrucción o un
punto de enganche nuevo (ver §4). No se envía nada a medias.

## 4. Lo que falta y por qué

1. **Frame-data por ataque.** Los scripts de acción están en RAM cargada al
   empezar el combate (`0x80117800` / `0x80190000`). Para leerlos y ajustar
   arranque/recuperación por golpe hace falta **una captura de RAM en vivo**
   durante una pelea (`ghidra_proj/ram_dump.py 0x80117800 <n>`).
2. **Escalado de daño.** El camino común no tiene una sola instrucción
   escalable; requiere `[recompiler] mod_instruction_sites` en `game.toml` y
   recompilar overlays (invalida la caché validada).
3. **Puntos de enganche nuevos.** Cualquier hook fuera de `0x8003FCF0`/
   `0x8003FE68` exige añadirlo a `function_entry_pcs` y **recompilar overlays**
   (el hash de configuración invalida la caché). No se hace aquí para no romper
   la build ya validada.
4. **IA y cámara**: sin mapear.

## 5. Riesgos

- Los parches de código son **globales mientras están aplicados**; se revierten
  al seleccionar Original. Deshabilitar la feature completa retira sus callbacks:
  antes hay que seleccionar Original, o reiniciar el juego/recargar el overlay.
- El parche de la puerta permite encadenar acciones: puede producir estados
  raros de animación (es el objetivo, pero hay que probarlo).
- El escalado de velocidad usa una sombra: si el script vuelve a escribir el
  mismo valor escalado, el paso se salta una vez (error acotado, no acumulativo).
- Ninguna de estas features está validada en partida; todas están apagadas.

## 6. Integración y verificación cerradas (2026-10-17)

Esta sección conserva los resultados de la entrega de tres experimentos. La
ampliación de una sola activación y la investigación de animaciones se documentan
en `COMBATE_REDISENO.md` y en la entrada más reciente de `summary.md`.

- Las tres features están implementadas, declaradas en el manifiesto y enlazadas
  en los ejecutables normal y PGXP. El build ha desplegado el catálogo actualizado.
- Los cinco plugins (incluidos entrada y traza) tienen callbacks independientes.
  Con todas las reglas en su valor inicial Original, sus sondeos no leen ni
  escriben memoria ni mandos. No se activan automáticamente.
- Ki y velocidad verifican además las instrucciones que acceden a sus campos.
  Encadenado verifica el salto anterior y el almacenamiento posterior al parche.
- START/SELECT suspende nuevas escrituras de cada regla hasta una activación
  nueva o un cambio de contexto de código detectado. Soltar pausa no la rearma.
  Este comportamiento conservador es un límite del experimento actual.
- El estado auxiliar se reinicia al cargar una partida guardada. Velocidad toma
  una nueva referencia: no conoce el valor bruto histórico de un guardado que
  ya contiene velocidades modificadas. No es un ajuste exacto por script.
- `python -m unittest discover -s tools/tests -p test_*.py -v`: **40/40 PASS**;
  dentro de ellos, el C de producción supera **22 grupos de escenarios**, incluidos
  límites de ki, conservación de HP vecino, signos/saturación, cambios de velocidad,
  restauración del parche, recarga, guardados, pausa y rechazo online/resimulado.
- `cmake --build build-release --target psx-runtime psx-runtime-pgxp -j 4`:
  **PASS**, ambos ejecutables enlazados y catálogo desplegado/verificado.
- `python tools/verify_offline.py`: **PASS**, configuración fuente/desplegada
  idéntica y caché vigente con **1.117 DLLs**. No se cambió `game.toml` ni se
  recompilaron overlays para estas tres opciones.
- No se inició una pelea en esta tanda. Estas verificaciones no cierran el
  rediseño completo: daño, IA, frame-data, ráfagas y modo alternativo siguen abiertos.

## 7. Ampliacion 2026-10-17b: anclas usadas por los modulos nuevos

Verificado sobre STEP40 cocido SHA256 `001adcdc...b9dd` (base 8003DFA0) y
revalidado en vivo por `standard_code()`.

| Dato | Direccion | Evidencia |
|---|---|---|
| Comando antes de la puerta | `0x80054A60` `lh a0,+0x2856(at)` (`0x84242856`) | se lee justo antes del `sltiu`/rechazo; unico sitio nuevo |
| Accion del defensor (guardia) | `control+8` (`0x80072808`/`0x80072884`) | `0x80066D44` `lbu v1,+0x2808(at)` |
| Word de ataque del atacante | `script+0x08` (`0x80072900`) | `0x80066D18` `lw a1,+0x2900(at)`; máscaras `0x05000000`/`0x00400000` y bit **`0x40000000`** (`lui v0,0x4000` en `0x80066DC8`) |
| Contador de script | `script+0x04` (`0x800728FC`/`0x8007292C`) | `0x8004E590` `lhu s4,+0x28fc(at)` |
| Puerta de aceptacion | `script+0x22` (`0x8007291A`/`0x8007294A`) | `0x80054AB8` `lhu v0,+0x291a(at)` |
| Impacto confirmado | `control+0` bit `0x10` | `0x80058618` `ori v0,v0,0x0010` tras el test de accion 0x53 |
| Posiciones (prev/actual) | `control+0x1C/0x24/0x2C/0x34` y objeto `+0x18/0x20` | `0x80058568`.. y `0x8005C828`/`0x8005C848` |
| Origen de camara | `0x800A8664`/`0x800A8668`; modo directo `0x800A8680` | handler opcode 0x22 `0x8004EA38`/`0x8004EA48`/`0x8004EA24`; copia `0x80055070` |
| Ticks retimados por accion | `s_motion_ticks` (host) | calculado en `motion_build` al reescribir duraciones |

El unico punto de enganche nuevo es `0x80054A60`; el resto reutiliza los sitios
ya declarados (`0x80054AE8`, `0x80066D28`), el sondeo/remap y el compilador de
movimiento. Los overlays se recompilaron en `cg18_1b6950cb_gc41ea2caf_f0`
(1.158 DLLs).

## 8. Correcciones de 2026-10-18

El estado vigente es `COMBATE_REDISENO.md` §9. `script+4` **decrementa la duración
del evento** (`0x8004EE84`), no mide tiempo transcurrido de la acción. El hit-stop
anterior y la cancelación basada en ese supuesto se han sustituido por filtros
de eventos/pose y resolución del script privado. Confirmar impactos mediante el
punto de daño, no generalizando el bit de la embestida.

Ráfagas básicas: nacimiento `0x8004F5A0`, integración trigonométrica
`0x800592A8/0x800592FC`, objetos `0x8007B8BC + índice*40`, flags de render
`0x8007C3FC + índice*20`, lista por lado `0x800A870C + lado*12`, paso entre
lados `*(uint16_t*)0x80072A02` (**21 observado**). Coste en byte alto firmado
del operando de `0x84`, consumido por `0x8004F210`.

Desbloqueo: **`0x8003BCC4`**, porque `lui 0x8004 + -0x433c` requiere signo.
START del debug es **`0x0008`**. 17 retratos comprobados en pantalla tras corregir
ambos errores. Caché vigente `cg18_1b6950cb_gc2c269e7c_f0`.

## 9. Rutas de continuación: productores localizados (2026-10-18)

Continuación de §8; estado operativo en `ROADMAP_RELEVO_COMBATE.md`.
`python -B tools/combat_map.py routes` reproduce los enlaces siguientes desde
el STEP40 completo, fijado al hash/base verificados. Sus IDs son los del byte
`control−4`, **no** nombres de personaje ni índices del archivo BTCHARA.

| Vía | Hecho demostrado |
|---|---|
| Comando25, fila32, handler607A0 | Reconocedor: pasos2000→4000→0020. Selector3EE54; IDs0,2,4,5,6,9,10,11,13,14,15. Requiere control+4 bits20/40. Con20 elige98; si solo40,AA. El delay slot60804 asigna98 y el60810 asignaAA; ignorarlo cambia la interpretación. |
| Comandos28/29/2B/2C | Otros accesos por ID, con desenlaces distintos; informe `routes` incluye tablas/casos. No son una única técnica universal. Cmd29/ID6 requiere20/40 y añade200 en control+4 (60AAC), solicita98. |
| Confirmación de98 | Dispatch3F004[(98−62)*4]→62F48; tabla3F24C por ID; productores62FF4/63030 añaden80 al control+4 del atacante. |
| Confirmación deAA | Mismo dispatch→631BC; tabla3F2DC; productor63228 añade80 al control+4 del atacante. |
| Identidad de lados | Función620FC:62104 fija s3=a0,62140 s5=(s3==0). Las escrituras de confirmación indexan s3, no s5. Las precondiciones de colisión693CC y contexto visual siguen aplicándose. |
| Consumidor576BC | Para IDs0,2,3,4,5,6,9,10,11,12,13,14,15,16 y candidato98/AA en sp+48:80+200→9B;80 sin200→99;sin80→9A.9B limpia200 y80;99 limpia80;9A limpia200. Se solicita cambio de acción por control+0 bit8. |
| Publicación final | 57F84 lee sp+48;57F94 guarda control+8. No confundir candidato en pila con una transición de acciones observada entre sondeos. |

Los14 IDs del consumidor coinciden con los de ambos productores de80. Existen
entradas directas a98 de IDs excluidos del consumidor; no generalizar la cadena
a todos los personajes porque el número de acción sea igual.

**Corrección de metadatos:** opcode61 no es `fighter_flags`:4EAFC carga operando,
4EB00 llama5015C con el lado. La función recorre6halfwords en6F79C, construye
máscaras de canales18..23, limpia esas entradas y llama1A078. Ahora se etiqueta
`audio_channel_event`; no se debe usar como productor de flags de combate.

**Alcance:** evidencia estática, con tests contra disco/captura y rechazo de
otro hash. Aún falta capturar la ruta completa en ejecución y comprobar el
gesto/estado que produce20/40. No se añadió un remate ni se cambió el timing.

### 9.1 Verificación de bytes y mejora implementada (2026-10-18)

Se releyeron los bytes y se implementó **una** mejora en el plugin; R1 sigue abierto.

- **Consumidor** `0x80057608`: el delay slot `0x80057610` carga `0xAA` y la segunda
  comparación `0x80057614` recibe `v1` = candidato; por eso candidatos `0x98` y `0xAA`
  llegan ambos a `0x8005761C`. `0x800576BC` decide `0x9B`/`0x99`/`0x9A` por
  `control+4` `0x80`/`0x200`, limpia la máscara y guarda en `sp+0x48`; `0x80057F94`
  publica en `control+8`.
- **Handler cmd25** `0x800607A0`: escribe `control+8` = `0x98` si `0x20`, `=0xAA` si
  `0x40`, y si no **no escribe acción**; el delay slot `0x80060804`/`0x80060810` es
  decisivo. `cmd29` `0x800609C0` añade `0x200` en `0x80060AAC`.
- **Consumo de `control+0x56`:** la puerta (`0x80054980`) llama `jal 0x80056E54`, y
  ahí `0x800570F8` (`lh a1,+0x2856`) alimenta el despacho `0x800570FC`. El hook del
  estándar en `0x80054AE8` corre **antes** en el mismo frame: su inyección llega.
- **Mejora:** `standard_command` retiene un `cmd25`/`cmd29` reconocido mientras
  `control+4` no tenga `0x20`/`0x40` y lo reinyecta por `control+0x56` (máx. 16 frames
  de invitado) al armarse la bandera aérea. Solo escribe `control+0x56`; no toca
  `control+4`/`control+8`. Contadores `followup_wait`/`followup_inject`.
- **Observación privada:** con `wtrace` sobre `control+4`/`control+8`, la retención se
  ejecutó 64× y 16× en dos sesiones; la entrega (`followup_inject`) quedó en 0 y el
  consumidor no se reprodujo (faltan los stores `0x800576F8`/`0x80057734`/`0x80057764`
  y los productores `0x80` `0x80062FF4`…). Falta mapear qué entrada/acción arma
  `control+4` `0x20`/`0x40` (productor `0x1D`, `0x8005D900`).
