# Combate renovado — producto estándar y rediseño mecánico

Fecha: 2026-10-17. Directriz del usuario: **activar y jugar**. El estándar final
debe estar bien ajustado; la investigación, el balance y la selección de opciones
son trabajo del desarrollo, no una tarea que deba resolver cada jugador.

**Estado más reciente (2026-10-19): `R0_ESTABILIDAD.md` y roadmap §10/§11.**
Espera bloqueante del núcleo corregida y publicada en v0.2.1, con reproducción
antes/después;121tests, builds/offline y matriz del ZIP3/3 PASS (10combates).
No se ha demostrado que explique los tres watchdog históricos: R0-C sigue
abierto. v0.2.1 es una pre-release experimental, no una garantía universal.

**Historial de entrega: roadmap §9.** Transición nueva integrada
y revisada visualmente por el agente; cámara ON/OFF inspeccionada, un par con
estado equivalente. R7 cerrado para entrega experimental 0.2.0; 112 tests,
builds normal/PGXP y offline PASS. El modo original del ZIP tuvo dos watchdog
con sampler=0: **R0 general reabierto**, sin causa asignada. El vuelo conserva
recortes de cámara nativos; no se promete balance competitivo exhaustivo ni
animaciones nuevas para todos. La revisión visual ya no es una tarea para el
usuario. El historial inferior no sustituye la matriz real del roadmap §9.

## 1. Contrato del producto

- Una sola entrada pública: **Combate renovado**. Activarla selecciona un perfil
  completo y fijo, sin tener que activar por separado entradas, velocidad o ki.
- El perfil estándar es el producto principal. Un futuro panel avanzado será
  opcional; nunca requisito para que el estándar funcione bien.
- La versión final abarca reglas de ataque/defensa, transiciones, movilidad,
  recursos, impactos, IA y animaciones. **No se cierra con un buffer de botones
  ni con acelerar el combate original.**
- Las animaciones son parte del alcance: inventariar lo existente, corregir el
  uso de movimientos/transiciones y producir o adaptar las secuencias que falten.
  Una lista de acciones no es un recuento de animaciones únicas.
- La instalación final debe ser autosuficiente respecto a B3 HD: usarlo como
  referencia de desarrollo no puede convertirse en un requisito para el jugador.
- El interruptor del mod sigue apagado de serie para conservar el juego original.
  **Una vez activado, todos los ajustes del estándar actúan automáticamente.**

## 2. Implementado ahora, sin confundirlo con la versión definitiva

`mods/preloaded/packages/dbfb.responsive/0.1.0/manifest.toml` ofrece `standard`:
no tiene opciones de ajuste. La traza queda en el canal de desarrollo. El
manifiesto anterior con interruptores aislados se ha conservado en
`mods/development/dbfb.responsive-legacy.toml`, fuera del catálogo que se despliega.
Los identificadores anteriores ya no activan reglas independientes en este
catálogo; no se edita ni se borra el archivo de selección del usuario.

Perfil inicial integrado en `src/mods/dbfb_responsive.c`:

| Parte | Valor inicial implementado | Límite real |
|---|---|---|
| Captura de toques | Una entrega por toque perdido entre sondeos; vida de 2 VBlanks | Todavía no espera a la recuperación de una acción |
| Movilidad | Aceleración y frenado sobre el delta de raíz propio antes de giro/colisiones (§12) | No modifica clips de locomoción ni añade giro propio |
| Ki | +1 a cada luchador cada 4 sondeos válidos (8 frames a la cadencia observada), máximo 196 | No modifica el coste de técnicas ni representa aún un balance final |
| Encadenado | Umbral de la puerta original 9 → 12 ticks del intérprete | Conserva cierre de ventana y demás restricciones; no garantiza combos nuevos |
| Pausa | Lee la bandera nativa; suspende escrituras y descarta entradas pendientes | Confirmada 0→1→0 en sesiones reales, incluida n |

La ventana estándar **no usa** el parche de laboratorio que elimina sin límite
el rechazo del comando. Se cambia `sltiu v0,v0,9` por `sltiu v0,v0,12` en
`0x80054AC0`, conservando `0x80054AD8` intacta. Si no coinciden todos los sitios
conocidos, el perfil no escribe parcialmente sobre un contexto desconocido.
Los callbacks pertenecen al plan del mod; no hay una bandera global de activación
que pueda mantenerlo encendido al arrancar otro plan.

La etiqueta sigue siendo experimental: la ausencia de ajustes obligatorios ya
está implementada; **la calidad definitiva de la jugabilidad aún no está medida**.

### Pausa: evidencia que desbloquea la reanudación automática

Sobre STEP40 SHA-256
`001adcdc2e129d3bd715c29b64e393fa8c2901a7ef39c2347874b321aae6b9dd`:

- `0x800540FC`: inicializa `0x800A868C` a cero.
- `0x80069FE0..0x8006A020`: reconoce START en los flancos del mando.
- `0x8006A178/180` y `0x8006A220/22C`: alternan la bandera con XOR 1.
- `0x8006A2F8/300`: comprueban bandera == 1 para el dibujo del menú pausado.
- Los tres sitios usados como identidad por el perfil se cotejan con capturas
  locales también al construir el arnés C. No se deduce la pausa de soltar START.

## 3. Estudio concreto de B3 HD

Proyecto consultado, solo lectura:
`../DBZ Budokai 3 HD Collection/`.
Es el port de **Xbox 360** sobre ReXGlue; las referencias PS2 están en otro
subdirectorio. La descripción anterior que lo trataba solo como proyecto PS2 era
incompleta. No se han modificado sus archivos ni copiado sus activos al juego.

| Fuente local de B3 HD | Evidencia/enseñanza aplicable |
|---|---|
| `docs/03_formatos/ACM_FORMAT.md`, §2–4 | Distingue curvas de animación `#ACM`, eventos/ventanas de impacto `#CSK` y reacciones HR. Un golpe combina esas capas, no solo un código de acción |
| Mismo documento, §3 | Documenta un pool de Krillin con 99 animaciones y tablas de 50 huesos. Es un ejemplo concreto de B3; no una cifra aplicable a Final Bout |
| Mismo documento, §4 | Daño, aturdimiento y empuje varían por golpe normal, contraataque, juggle, suelo o guardia; cada evento abre/cierra una ventana |
| `docs/14_frentes/combate.md`, §11–12 y WL-12 | El proyecto mide arranque, recuperación, ventaja, guardia y whiff; separa datos del fichero de lo observado en partida |
| `src/combate.cpp`, `kAct`, `kHitFrame`, `kAnimFrame` y `SondaLado` | Observa acción, reloj de animación, impacto, recursos y mando juntos; permite atribuir qué parte limita el movimiento |
| `studies/tools/frame_data.py`, `ventanas`, `ficha`, `medir` | Resuelve el ataque hasta sus ventanas y reacciones y contrasta contra medidas. El lector distingue alias de recursos únicos |

Aplicación al rediseño: cada ataque de Final Bout debe tener una ficha coherente
de **entrada → arranque → ventana activa → impacto/guardia/whiff → recuperación →
transiciones permitidas**, enlazada con su secuencia visual. No se importan los
offsets, las fórmulas ni el balance de B3 sin adaptación.

Una animación de B3 no es una secuencia ya reproducible en Final Bout: hay que
verificar la representación de pose del motor PS1, su jerarquía de partes/huesos,
ejes, escalas, root motion y eventos. El inventario de Final Bout todavía no
permite asegurar esa correspondencia. La vía de adaptación queda abierta; no se
da por imposible ni por resuelta sin demostrar el formato de destino.

## 4. Investigación nueva de recursos de Final Bout

`tools/combat_assets.py` es un lector offline, sin extracción de archivos ni
escritura en el disco del juego:

1. Usa el lector ISO existente para inventariar `BTCHARA.DAT`, `BTWINV.DAT`,
   `CHARSEL.BIN` y `STEP40.BIN`.
2. Reproduce de forma acotada el descompresor Psdp leído en
   `0x80042D50..0x80042D98` y `0x80042E30..0x80042F14`:
   flags LSB, literal o referencia, distancia `token >> 5`, longitud
   `(token & 31) + 3`, ceros para referencias anteriores al inicio.
3. Busca candidatos estructurales de tablas como las que consume
   `0x8004E5B4..0x8004E644`. Los etiqueta como candidatos, nunca como movimientos
   jugables ni animaciones verificadas.

Resultados reproducidos:

| Archivo | Tamaño | Bloques Psdp leídos | Bytes descomprimidos en memoria | Tablas candidatas con el filtro actual |
|---|---:|---:|---:|---:|
| `TITLE/BTCHARA.DAT` | 9.142.272 | 2.650 | 12.868.520 | 0 |
| `TITLE/CHARSEL.BIN` | 3.469.312 | 72 | 2.095.968 | 0 |
| `BATTLE/BTWINV.DAT` | 1.951.744 | 0 | 0 | 0 |
| `MENU/STEP40.BIN` | 442.876 | 0 | 0 | 0 |

Esto **no prueba que no haya animaciones**. El filtro busca una forma concreta de
tabla con 64–512 entradas, y no reconstruye todavía todos los contenedores ni la
reubicación de los recursos. El enlace entre esos bloques, los pools de poses y
los punteros del intérprete en RAM sigue pendiente. La cantidad de animaciones
útiles de Final Bout no está establecida; no se afirma aún que sea la causa del
problema de combate.

Corrección importante del mapa: contando desde `0x8003E78C`, el evento de
animación/acción está en opcode **0x20**, el spawn en **0x23**, la velocidad en
**0x24**, y el registro de golpe en **0x25**. El mapa anterior de 0x21/24/25/26
tenía un desplazamiento. No cambian las direcciones de los campos ya probadas.

La traza ahora añade dos registros `kind=4` por sondeo (bit 8 indica J2), con
acción, flags, puntero al script, contador/opcode, vida/ki y velocidad/contador de
puerta. Conserva el formato de ring de 8 words y los registros de entrada; no
escribe estado de los luchadores ni atribuye nombres de animación sin evidencia.

## 5. Secuencia de implementación mecánica que falta para la versión final

Estas son partes obligatorias del estándar final, no interruptores que se
delegarán al jugador. Son objetivos de diseño, no funciones ya implementadas.

1. **Movimientos y transiciones:** enlazar pools reales con códigos y eventos;
   inventariar animaciones únicas, alias y secuencias inaccesibles por personaje.
   Obtener curvas/poses y documentar el formato PS1 antes de convertir material.
2. **Ataque:** cadenas cortas con progresión clara, rutas distintas de remate,
   transición cuerpo a cuerpo → ki y persecución. Las cancelaciones se conceden
   por estado y ventana; no deben sacar al luchador del KO o de una reacción de
   golpe, ni anular toda recuperación al fallar.
3. **Defensa:** guardia, retroceso, recuperación y respuestas consistentes. Separar
   golpe, guardia y whiff; medir cuánto dura cada compromiso para ambos lados.
4. **Movilidad:** aceleración/frenado, aproximación y separación controlables;
   sincronizar los cambios con locomoción, giro y transiciones visuales. No basta
   con multiplicar la velocidad de desplazamiento.
5. **Impactos y proyectiles:** correspondencia de contacto con pose y reacción,
   empuje legible, vuelos/derribos y ráfagas que enlacen con recuperaciones reales.
   No ampliar el alcance de todos los golpes para fingir que conectan mejor.
6. **Animación adicional:** donde falten poses o enlaces, producir secuencias
   propias o adaptar curvas mediante una correspondencia demostrada. Incluir sus
   eventos y probarlas con ambos lados, tamaños de personaje, suelo/aire y cámara.
   Interpolación visual y root motion no pueden desincronizar el impacto.
7. **Ki/daño/IA:** balancear el ciclo presión → gasto → defensa → recuperación,
   acotar repetición de golpes/cancelaciones y enseñar a la IA las mismas reglas,
   ventanas y costes. Evitar ventaja oculta de reacción o recursos para un lado.
8. **Cierre del estándar:** fijar una versión del perfil y automatizar la matriz
   de movimientos, guardia, whiff, KO, pausa, técnicas, revancha, tres peleas,
   guardados y ambos lados; revisar la sensación jugando. Los ajustes avanzados
   podrán añadirse después sin sustituir este estándar.

Próximo bloqueo técnico concreto: resolver el enlace de los recursos con la
tabla de scripts cargada, para disponer de las fichas de ataque y animación.
Cambiar recuperación o sustituir animaciones antes de resolver ese enlace sería
modificar tiempos/eventos sin conocer lo que se está reproduciendo.

## 6. Verificación de esta entrega

- `python -m unittest discover -s tools/tests -p test_*.py -v`: **54/54 PASS**,
  incluidos **28 grupos C** del plugin de producción, 6 tests sintéticos del lector
  de recursos y el arnés de movimiento sobre los 18 registros (54 variantes por
  lado, idempotencia, recarga, restauración y límites de daño).
- `cmake --build build-release --target psx-runtime psx-runtime-pgxp -j 4`:
  **PASS**, los dos ejecutables y el catálogo actualizado.
- `python tools/verify_offline.py`: **PASS**, configuración fuente/desplegada
  idéntica y caché vigente `cg18_1b6950cb_gcb5146b81_f0` con **1.157 DLLs**.
  El verificador ahora resuelve el namespace con el serializador canónico del
  framework, no con una única carpeta asumida.
- **Sesión real headless** (mandos sintéticos): 132.905 frames, 91% de despacho
  nativo, `fatal=no`, cero `unknown_dispatch`/`midblock`, sin volcados nuevos.
  Demuestra que el perfil actúa en combate, no que la sensación esté ajustada.
- Coherencia corregida: el daño solo se reduce si la tabla privada está publicada
  y la acción tiene clip retimado; una variante no instalada conserva daño y
  tiempo originales.
- No se han añadido animaciones al juego. El perfil inicial no se presenta como
  el rediseño definitivo.

## 7. Evaluación sincera del alcance restante (2026-10-17)

El perfil estándar actual es una **base funcional**, no el rediseño completo. De
las ocho fases obligatorias de §5, **ninguna está cerrada**: cinco están
parcialmente cubiertas y tres no han empezado.

| Área | Estado | Qué existe hoy | Qué falta para cerrarla |
|---|---|---|---|
| Entrada y respuesta | Cubierta | buffer de 2 VBlanks, recuperación de comando, pausa nativa | Validación humana; no requiere más diseño |
| Movilidad | Ampliada (§12) | Aceleración/frenado propios sobre delta de raíz, antes de giro y separación nativos; escala de script+c retirada (§11) | Giro propio, clips de locomoción y ajuste visual/humano |
| Ataque y cadenas | Esencial cubierto | puerta 9→12, cancelación de recuperación tras impacto confirmado, daño 4/5 y 3/4 | Ficha nominal por golpe, rutas/remates, combate aéreo |
| Defensa | Esencial cubierto | guardia nativa reproducida, medidor, rotura, just-guard, perfect-guard, recompensa de ki | Chip explícito y ventana fina de just-defense |
| Impacto y proyectiles | Ampliado 2026-10-18 | hit-stop por filtros de eventos/pose; ráfagas básicas al 125%, vida 64 VBlanks e intercambios barridos en 3D | Rayos/técnicas especiales e intercambios en partida humana |
| Animaciones | Parcial | Retiming de 27 clips existentes; hit-stop congela la pose; **transiciones de pose relativas compensadas** (§9) | Clips nuevos con jerarquía de huesos, root motion y nombres anatómicos |
| IA | Ampliada (§10) | Dificultad efectiva por lado, cadencia en VBlanks, asignación CPU/mando nativa; prioridad de defensa y decisiones originales | Ajuste humano y estrategias nuevas; prueba real de los tres índices |
| Cámara y transiciones | Parcial | Sacudida en golpe y acercamiento propio de KO, 8%/24 VBlanks, solo en cámara directa y cediendo a nuevos planos | Encuadre general, cámaras relativas y transiciones |
| Balance | Parcial | Daño/ki de ráfagas a 3/4; ki de técnicas 78..83 a 4/5; defensa precisa alivia presión; combos se reinician al recuperar el defensor | Ajuste fino con la IA y validación humana |
| Verificación | Ampliada (§10) | 64 tests, 33 grupos C, matriz de 942 variantes; sesión k: cuatro combates con KO/menú, pausa, guardar/cargar y cierre normal | Playtest humano, guardado nativo en tarjeta, 2P real y más emparejamientos |

**Bloqueos técnicos que siguen abiertos**

1. Las fichas nominales por golpe (arranque, activa, recuperación, guardia y
   whiff) requieren poner nombre a las 27 acciones retimadas. El enlace de datos
   con los 18 registros ya existe; falta la correspondencia con nombres.
2. Las animaciones nuevas necesitan demostrar el formato de pose/huesos de PS1 y
   su enlace con los scripts; hoy se retimó material existente, se congela la pose
   con el hit-stop y se añadieron transiciones de pose relativas compensadas
   (§9), pero no hay clips nuevos ni nombres anatómicos de partes.
3. Las ráfagas básicas ya tienen velocidad, vida e intercambios (§9). Los rayos,
   cinemáticas y técnicas especiales conservan su comportamiento nativo.
4. El KO propio existe para cámara directa (§9). El encuadre general y las
   cámaras relativas a nodos siguen pendientes.
5. No hay validación humana: la sesión headless demuestra ejecución y ausencia de
   fallos, no sensación de juego.

**Orden recomendado para terminar**

1. Fichas de movimiento por personaje y nombres de acción.
2. Ataque: rutas, remates y combate aéreo sobre la cancelación ya existente.
3. Proyectiles: ampliar la cobertura de ráfagas básicas a técnicas especiales.
4. Cámara: encuadre general y cámaras relativas.
5. IA por dificultad y reacciones defensivas.
6. Animaciones nuevas o adaptadas.
7. Matriz automática y playtest humano.

Declarar hoy «rework completo» sigue siendo falso: las animaciones nuevas, las
rutas aéreas/remates, las técnicas especiales, el encuadre general y el balance
fino siguen abiertos. §9 sustituye las conclusiones de reloj/cancelación de §8.

## 8. Ampliación 2026-10-17b: defensa, impacto, cancelación, IA y cámara

Todo se apoya en costuras ya verificadas de STEP40 y en un único punto de
enganche nuevo. Cada módulo comprueba `standard_code()` antes de escribir y no
toca memoria del invitado si el código no coincide.

- **Punto de enganche nuevo:** `0x80054A60` (`lh a0,+0x2856(at)`, palabra
  `0x84242856`), justo antes de que la puerta lea el comando. Registrado en
  `mod_instruction_sites`; obligó a recompilar overlays (namespace nuevo
  `cg18_1b6950cb_gc41ea2caf_f0`, **1.158 DLLs**).
- **Defensa:** se reproduce la propia prueba de bloqueo del motor (acción del
  defensor `0x21/0x22/0x23` + máscara `0x05000000`/`0x00400000` en el word
  `+0x2900` del atacante) y se ajusta el daño antes de que el cuerpo nativo
  aplique su mitad/cuarto/cero. Medidor de guardia que rompe por presión
  sostenida, just-guard por entrada observada de la acción (cuarto de daño y +2
  de ki) y perfect-guard (divisor nativo cero).
- **Impacto:** el hit-stop resta un tick a ambos contadores de script
  (`+0x28FC`/`+0x292C`) durante unos VBlanks; el empuje desplaza al defensor a lo
  largo del vector de golpe en las dos copias de posición (`+0x1C/0x24/0x2C/0x34`
  y objeto `+0x18/0x20`), con tope ±7000 y enfriamiento.
- **Cámara:** sacudida acotada sobre el origen de cámara verificado
  (`0x800A8664/0x800A8668`) solo cuando el modo directo `0x800A8680 == 0`;
  abandona sin escribir si el juego emite un comando de cámara nuevo.
- **Ataque:** ventana de cancelación en recuperación tardía (≥ 75 % de la línea
  de tiempo retimada) y solo con impacto confirmado (`+0x2800` bit `0x10`), baja
  el contador de la puerta `+0x291A`; no actúa si la tabla privada no está
  publicada.
- **IA:** el lado 2 recibe un comando real (`0x00`/`0x01`) en su propio slot
  `+0x2856` antes de la puerta, con cooldown y alcance; la puerta, el coste y el
  handler nativos siguen decidiendo. Se salta si hay un segundo mando conectado.
- **Balance:** prorrateo de combo (−5 % por golpe tras el primero, suelo 60 %) y
  la rotura de guardia como castigo de la presión.

**Verificación de esta ampliación**

- `python -m unittest discover -s tools/tests -p test_*.py -v`: **54/54 PASS**,
  con **31 grupos C** del plugin de producción (incluye defensa, hit-stop,
  cámara, empuje, cancelación e IA).
- `cmake --build build-release --target psx-runtime psx-runtime-pgxp -j 4`:
  **PASS**.
- `python tools/verify_offline.py`: **OFFLINE VERIFICATION PASSED**, codegen
  `1b6950cb`, **1.158 DLLs** en `cg18_1b6950cb_gc41ea2caf_f0`.
- **Sesión real headless** (arranque → menús → combate, sin mandos humanos):
  `fatal=no`, sin volcados de freeze nuevos, 91 % de despacho nativo. Contadores
  nuevos activos en el combate: 7.204 sondeos de combate, 216 variantes de
  movimiento, 40 empujes, 40 daños ajustados, 108 frames de hit-stop, 346
  sacudidas de cámara, 27 comandos de IA, 6 entradas de guardia, 2 bloqueos y 3
  golpes prorrateados. No es una prueba de sensación.

## 9. Corrección y ampliación 2026-10-18

### Relojes, confirmación y coherencia

El contador `script+4` **es una cuenta atrás del evento actual**, no un reloj
acumulado: `0x8004E66C` carga la duración y `0x8004EE84` la decrementa. Por tanto,
restarlo para producir hit-stop aceleraba eventos y compararlo con el 75% del
total no detectaba la recuperación. Las conclusiones anteriores de §8 quedan
corregidas:

- Hit-stop mediante filtros de las funciones verificadas `0x8004E530`
  (intérprete, argumento lado 0/1) y `0x80042240` (pose, solo contextos
  `0x800A8624/0x800A8644`). No se repiten paquetes de transformación relativa ni
  se editan relojes. El reproductor devuelve 0 («no terminada») mientras se omite.
- La recuperación se resuelve contra el **puntero exacto del script privado**,
  el contador restante y la cola visual del clip correcto. Requiere haber pasado
  el último `clear_attack_flag` y al menos el 75% del tiempo compuesto; las
  variantes sin cierre verificable no reciben cancelación.
- Confirmación desde el punto de daño real, solo sin guardia. El bit `0x10`
  observado en la embestida no se generaliza a todos los golpes. Un cambio de
  acción, rebobinado del puntero o KO descarta la confirmación. Whiff y bloqueo
  no abren la recuperación.
- El daño conserva el valor original hasta publicar una variante completa. Una
  compilación fallida invalida sus metadatos. La pausa no consume los temporizadores
  de combate. Revancha tras KO reinicia medidores/confirmaciones/proyectiles.
- La defensa precisa alivia el medidor en lugar de romper la guardia precisamente
  en el golpe defendido a tiempo. Recuperar un estado neutral/guardia termina el
  prorrateo del combo anterior.

### Ráfagas básicas: velocidad, duración e intercambios

`src/mods/dbfb_projectiles.h` añade reglas para `0x72..0x77`, con variantes
publicadas, sin alterar rayos ni cinemáticas:

| Evidencia STEP40 | Uso |
|---|---|
| `0x8004F5A0`, `sh v0,-0x1c(v1)` | Nacimiento exacto en la lista `0x800A870C + lado*12`; tipos 14/15/16 |
| `0x80071CC0`: 14,15,16 | Correspondencia con registros de objeto |
| `0x80072A02` | Paso dinámico entre lados; observado 21 en Goku/Pan, acotado 17..36 |
| `0x8007B8BC + índice*40` | Objeto; posición XYZ en `+0x18/+0x1C/+0x20` |
| `0x800592A8/0x800592FC`, `sll v0,v0,8` | Integración de velocidad nominal 256; escalar el resultado trigonométrico antes de integrar produce 320 (125%) conservando dirección |
| `0x800593DC..404` | Retirada nativa: bit alto del registro `0x8007C3FC + índice*20`, lista a cero y flag de propietario `0x100` |
| `0x8006E4F4` | Salida de límites nativa; sigue vigente |

La duración máxima del estándar es 64 VBlanks de combate desde el nacimiento,
incluyendo reutilizaciones del mismo slot. La retirada conserva otros flags y
solo limpia el propietario cuando no quedan disparos activos en sus seis slots.
Los intercambios comparan la distancia barrida relativa en **tres dimensiones**
entre sondeos, radio de diseño 128; cada bola se retira una vez. Cambios de código,
partidas guardadas y disparos no registrados mantienen el comportamiento original.
Los intercambios están comprobados sintéticamente; no aparecieron en las dos
sesiones reales de esta entrega.

El coste nativo procede del byte alto con signo del operando de `0x84`
(`0x8004ED50/74` → `0x8004F210/224`). Para estas ráfagas, el coste positivo pasa
a 3/4, mínimo 1, igual que su daño; cero y valores negativos se conservan. Las
técnicas especiales no reciben esta modificación. Las fichas `--cards` muestran
coste original/estándar, eventos y alias, **no** frames de ventaja ni nombres
de luchador/movimiento todavía sin demostrar.

### Cámara de KO

El modo directo consume seis coordenadas (ojo XYZ + objetivo XYZ) en
`0x800A8664..0x800A8678`; opcode `0x22` las escribe y `0x8004DEFC` utiliza su
diferencia. Un KO confirmado acerca el ojo un máximo del 8% hacia ese objetivo y
regresa al plano original en 24 VBlanks. Se descarta si el juego cambia cualquier
coordenada o pasa a cámara relativa. No sustituye las cinemáticas nativas.

### Verificación y límites de cierre

- Suite: `python -m unittest discover -s tools/tests -p 'test_*.py' -v`.
  **58/58 PASS**, incluidos **33 grupos C** y la matriz integrada de **942
  variantes** (18 registros del archivo, ambos lados; 716 recuperaciones
  confirmadas y 226 variantes sin cancelación añadida). No equivale a 942
  emparejamientos jugados.
- Matriz de ráfagas sobre los 17 registros con ráfagas retimadas: signos de
  velocidad, ambos lados, tres slots, expiración exacta, reciclado, colisión
  barrida, separación vertical, online y restauración. El arnés de movimiento
  comprueba también los costes y la conservación de los operandos vecinos.
- Compilaciones normal y PGXP correctas; caché `cg18_1b6950cb_gc2c269e7c_f0`,
  **1.158 DLLs**, con los mismos ocho rechazos conservadores IRQ/BIOS de antes.
  La herramienta de shards **no** da un pase completo: informa esos ocho fallos;
  las regiones correspondientes conservan el intérprete.
- Sesión real `dbfb-rework-smoke-20261018b`: 9.572 frames al último muestreo,
  6.135.743 despachos nativos/501.584 interpretados (~92,4%). Contadores: 8
  nacimientos de ráfaga, 290 ajustes de velocidad, 2 expiraciones, 31 llamadas
  de script y 31 de pose detenidas, 1 cancelación, 24 frames de cámara de KO.
  Cierre por orden del cliente de debug (proceso devuelve 1); no se etiqueta como
  salida normal del jugador ni como validación humana de estabilidad.
- Capturas y JSON privados en
  `C:\Users\javie\AppData\Local\Temp\opencode\dbfb-rework-smoke-20261018b\`.
  `004-menu.png` muestra los **17 retratos**, incluido SSJ4, con `0x8003BCC4 ==
  0x1FFFF` y el contador de desbloqueo activo. Se corrigió tanto la dirección
  firmada como START del protocolo de debug (`0x0008`, no `0x0800`).

**No está al 100%:** faltan animaciones/poses nuevas y su correspondencia de
huesos, nombres y medidas reales de cada golpe, nuevas rutas aéreas/remates,
IA por dificultad, encuadre general, técnicas especiales, balance humano y la
secuencia completa de revancha/tres peleas/guardados. El estándar sigue en canal
experimental; las pruebas verifican lo implementado, no cierran esas tareas.

### Última comprobación: bloqueo intermitente abierto

Tras el ajuste final de costes y limpieza del flag del propietario:

- **58/58 tests PASS**, builds normal/PGXP PASS y `verify_offline.py` PASS;
  configuración idéntica y 1.158 DLLs vigentes.
- Sesión **c: FAIL** antes de entrar en combate. Frame 3.303; retorno del proceso
  **2**, origen `starvation_watchdog`, más de 10 segundos sin heartbeat. El
  diagnóstico sitúa la espera alrededor de `0x8001BD34/0x8001BD68` y OpenBIOS
  `0x1FC060E4`, `I_STAT=0`, sin instrucciones no soportadas mid-block ni
  despachos desconocidos. No se ha establecido la causa ni que pertenezca al mod.
  Se conservaron `starvation_dump.jsonl`, heartbeat, reporte y capturas en
  `dbfb-rework-smoke-20261018c`; no se silenció ni amplió el watchdog.
- Repetición **d** con el mismo binario: llegó a combate, KO y regreso a menú,
  **14.818 frames** muestreados; 10 nacimientos de ki, 280 ajustes de velocidad,
  35 llamadas de eventos/35 de pose detenidas y 24 frames de cámara de KO.
  10.019.954 despachos nativos/817.311 interpretados. Cierre por debug, retorno 1.
  Que esta repetición avance **no resuelve ni invalida el fallo c**.

La estabilidad del flujo de menús es ahora un bloqueo explícito de entrega,
además de las mecánicas/animaciones pendientes. No etiquetar esta versión como
final ni usar los pases offline para ocultar el fallo en ejecución.

### Transiciones de pose nativas (2026-10-18)

El análisis de los 18 registros demostró que los clips de recuperación **ya traen
una muestra por tick**: no quedan huecos temporales donde insertar in-betweens, y
los ángulos son casi todos incrementos relativos (142.912 relativos frente a 6
absolutos en las variantes seleccionadas). Insertar huecos habría inventado
tiempo y no era viable; se descartó también ampliar `gap<=6` o forzar una pose
absoluta de entrada.

`src/mods/dbfb_pose.h` toma la vía respaldada por los datos: **dar forma a una
muestra interior existente** entre dos anclas de recuperación, con correcciones
angulares relativas compensadas (`+c` en el grupo intermedio, `−c` en el grupo de
salida). Como el almacenamiento nativo es aditivo módulo 16 bits, la pose final
coincide **exactamente** con la original para cualquier pose de entrada, sin
conocerla. Cabecera usada: relativa, solo ángulos, `0x03310000 | parte`.

- Conserva tiempos, eventos, traslación, escala, geometría, jerarquía y poses de
  extremo; no atraviesa finales, saltos, cámara ni cambios de jerarquía.
- Requiere grupos intermedio y de salida exclusivamente de transformación y
  desplazamiento angular acotado (±256 por eje, corrección ≤32 ≈ 2,8°).
- El árbol de raíces del clip de inicialización se amplía a los hijos directos
  reales (por jerarquía, sin nombres anatómicos), y nunca se corrige la raíz.
- Contador renombrado `dbfb.responsive.pose_inbetweens` → `pose_transitions`.
- El arnés C prueba tres poses de entrada (incluida envoltura) y verifica que la
  muestra interior cambia y el extremo final es idéntico bit a bit. En producción
  el arnés de movimiento cuenta transiciones por registro (p. ej. 32 en el
  registro 0). Es una **reperfilación declarada de la pose interior**, no un
  frame adicional.

### Corrección del watchdog y repeticiones e/f/g

El dump de la sesión c tenía un heartbeat de **266 µs** al escribir la cabecera:
compatible con que un refresco del hilo IO llegara entre la lectura del heartbeat
y la del reloj, dejando evidencia obsoleta. `starvation_watchdog_check` ahora
hace doble lectura (`starvation_watchdog_confirmed_stale`) y solo aborta si
**ambas** observaciones están vencidas; no se silenció ni amplió el watchdog y el
estallido real sigue detectándose. Arnés
`psxrecomp/runtime/tests/test_starvation_watchdog.c`: **26/26 PASS**.

Repeticiones del mismo linaje de binario (headless, mandos sintéticos):

| Sesión | Resultado | Observaciones |
|---|---|---|
| e | OK | combate + KO + regreso a menú; 17 transiciones de pose; 9.390 frames |
| f | OK | combate sin KO; sonda de pausa dejó el flag en 1 por una pulsación no registrada |
| g | OK | **pausa real**: `0x800A868C` 0→1→0 con START y reanudación automática; 17 transiciones, 24 frames de cámara de KO, 1 cancelación, 3 comandos de IA; 10.472 frames |

Ninguna repetición volvió a disparar el watchdog, pero eso **no demuestra** la
causa de c: el fallo sigue abierto como bloqueo de entrega. El parche reduce
falsos positivos, no confirma el origen.

## 10. Cierre de correcciones de defensa/IA/técnicas y prueba larga (2026-10-18)

Esta sección sustituye las afirmaciones anteriores sobre el divisor de guardia,
la propiedad del segundo luchador y la validación de cierre del proceso. No
declara completadas las ocho fases de §5.

### Defensa: corrección respaldada por el ejecutable

`0x80066DC8` contiene `lui v0,0x4000`: la máscara que determina el divisor dos
es **`0x40000000`**, no `0x4000`. `0x80066DE8` hace `and v0,a1,v0`; el salto
de parámetros negativos mantiene el divisor cuatro. Tanto el auxiliar como la
apertura de la rama nativa durante rotura de guardia usan ahora el bit correcto.
Los tests fijan esas instrucciones del disco y distinguen bit 14, bit 30 y signo;
la matriz integrada también utiliza el parámetro nativo correcto. Los pases
anteriores con `0x00404000` no demostraban la reducción nativa a la mitad.

### Dificultad y prioridad de la IA original

- Opción global: byte `0x8003BC74`. STEP01 `0x80044DD0..D8` guarda cursor−2;
  el menú permite índices 0, 1 y 2. Los nombres textuales de cada índice no se
  han demostrado.
- STEP40 copia a `0x80072960 + lado*0x24` (`sh` en `0x80053DE4/53EFC`).
  Los modos `0x43/44/45` fuerzan 2 mediante `0x8006C8A8`; leer la copia
  efectiva conserva esa excepción. La IA original consume la copia, entre otras
  direcciones, en `0x800509BC` y `0x80050D40`.
- La rama nativa `0x800549C8/CC` decide CPU con **control+0 bit 0**. La presencia
  física de un mando digital no era una prueba de quién controla al luchador.
  Solo se asiste a J2 CPU frente a J1 humano; 2P y CPU-vs-CPU quedan intactos.
- Cadencia adicional de diseño para índices 0/1/2: **150/120/90 VBlanks**.
  Ya no se reduce por llamadas repetidas al hook. Pausa e hit-stop no consumen
  la espera. Valores efectivos fuera de 0..2 no reciben inyección.
- La IA nativa corre antes del hook. Se conservan sus comandos, sus dos salidas
  actuales (`sp+0x10/14`), las almacenadas (`estado IA+8/+12`), su temporizador
  (`+16`), decisiones `0xC8/0xC9`, guardias `0x21..23` y bloqueo reconocido
  (`control+0 & 0x08000000`). No se fuerza un especial frente a un ataque o
  proyectil rival. No se escriben acciones ni botones para anular una defensa.
- Se mantienen costes, puertas y handlers originales. Los comandos 0 y 1 son
  **técnicas especiales**, no puños/patadas: handlers `0x8005FF9C/0x8006026C`.

### Técnicas especiales y fichas

`dbfb_motion.h` publica scripts privados para `0x78..0x83`, en ambos lados.
Solo cambia el coste positivo de ki del opcode `0x84` a **4/5**, mínimo 1:
80→64, 100→80; registro 17, 40→32 y 50→40. Conserva ceros y sentinelas con
signo. No añade aceleración, reducción de daño ni cancelación a estas acciones.

- Familias directas: `0x78..7A` (comando 1), `0x7E..80` (comando 0).
- Familias coordinadas: `0x7B..7D` y `0x81..83`, seleccionadas por
  `0x8005F2C4`. Esta rutina modifica también estado y posición del rival;
  sus tiempos, poses y sincronización se conservan.
- El arnés verifica **432 scripts** (12 × 18 registros × 2 lados), word a word:
  la única diferencia permitida es el byte del coste positivo. Verifica también
  que no adquieren reglas de daño/cancelación de clips retimados.
- Contador `dbfb.responsive.technique_variants`, separado de `motion_variants`.
- `combat_moves.py --cards` muestra estas familias, handler y coste estándar.
  El opcode `0x60` pasa de `control_event` a `audio_bank_event`: llama al banco
  de sonido (`0x8004EAEC → 0x8004FEB8`), no prueba un salto de acción.

### Pruebas y limitaciones del cierre

`combat_smoke.py` ahora usa toda la duración solicitada y exige KO, secuencia
vida positiva→cero→menú, pausa 0→1→0 y **salida 0 sin terminar el proceso a la
fuerza**. La pérdida de la respuesta TCP a `quit` debe ir seguida de una espera
de salida, no de un `terminate` inmediato. Las capturas durante un apagado de
pantalla nativo se anotan como omitidas; no se confunden con un crash.

| Sesión | Resultado observado |
|---|---|
| h, 420 s | 4 KO y regreso a menú; veredicto FAIL porque el script forzó el cierre tras perder la respuesta de quit |
| i | FAIL del instrumento: captura durante `display disabled`; proceso salió con 0 |
| j, 360 s | PASS: 3 KO, pausa y guardar/cargar completados; salida 0 |
| k, 420 s, binario actual | **PASS: cuatro combates completos** (vida→KO→menú), pausa, guardar/cargar y salida 0; 38.818 frames |

En k: 144 variantes de técnicas publicadas (incluye recompilación tras cargar),
96 transiciones, 48 ráfagas, 289 llamadas detenidas de script y otras 289 de pose,
4 cancelaciones, 1 comando añadido de IA, 12 entradas de guardia, 1 just-guard y
1 perfect-guard. Despachos: 23.488.190 nativos / 1.839.401 interpretados.
`savestate_status` confirma generación 1/save y 2/load, ambas `last_ok=1`;
se guarda en la carpeta de tarjetas **temporal nueva**, no en los datos personales.
Esto verifica estados rápidos, **no** el menú de guardado nativo en tarjeta.

- Suite: `python -B -m unittest discover -s tools/tests -p "test_*.py"`: **64/64 PASS**,
  33 grupos C, matriz integrada de 942 variantes y 432 scripts de técnicas.
- Ambos ejecutables normal y PGXP compilados. La sesión k usa el normal;
  compilar PGXP no equivale a jugar cuatro combates con PGXP.
- Evidencia privada: `%TEMP%/opencode/dbfb-rework-smoke-20261018{h,i,j,k}/`.
  No se reprodujo el watchdog, pero no demuestra la causa de c.
- Siguen abiertos: clips completamente nuevos y anatomía, rutas/remates aéreos,
  locomoción/aceleración propia, encuadre general/relativo, nombres y medidas por
  golpe, más emparejamientos y balance humano. La continuación nativa
  `0x98/0xAA → 0x99/0x9B/0x9A` está localizada en `0x80057608..57790`, pero el
  significado de sus flags `control+4 & 0x80/0x200` aún necesita demostrar sus
productores antes de cambiarla. No es una ruta nueva implementada.

## 11. Corrección de movilidad y frontera de cámara (2026-10-18)

**Validación del binario posterior a esta corrección: FAIL en ejecución.** Suite
64/64 y ambos builds PASS; sesión l, segundo combate frame11887, retorno2 por
watchdog tras12,4s sin heartbeat. Pausa/save/load completados, un combate completo.
Durante aprox.9s no avanzan frame/ciclos/insns; luego47.458ciclos/117insns antes
del watchdog. Compatible con suspensión o trabajo nativo del hilo host, causa
no demostrada. Evidencia privada l preservada; k era la revisión anterior.
Se requiere observar planificación/pila de hilos durante la parada antes de
atribuirla a una modificación del combate. No se silencia/amplía watchdog.

La revisión posterior de productores/consumidores impide mantener la afirmación
«movilidad al 125%». **El estándar conserva ahora `script+0x0C` original.** El
selector de laboratorio sigue disponible fuera del catálogo público, pero no es
una base demostrada de locomoción propia.

- Opcode `0x24`: `0x8004E7A8..7B8` guarda el halfword de velocidad; la acción
  nueva lo pone a cero (`0x8004E638`). Persiste hasta otra escritura, no hasta
  que se agote automáticamente la duración del evento.
- Consumidor `0x8006639C`: `s2=a0` (`0x800663A4`), **s4=lado contrario**
  (`sltiu s4,s2,1`, `0x800663BC`). Lee la velocidad del script de s2 y actualiza
  XZ del objeto de **s4** (`0x80066920..66A38`). Aumentarla no demuestra acelerar
  la marcha: puede modificar el desplazamiento del rival por contacto.
- Locomoción propia: `0x80054C80 → 0x800678D0` toma el delta del nodo raíz,
  lo gira, aplica comprobaciones de separación y acumula control+0x2C/+0x34
  (`0x80067E00..E2C`). `0x80054C88 → 0x80067148` actualiza referencias. En los
  18 registros, acciones0..23 no contienen opcode24. Falta enlazar entrada,
  bucle de locomoción y paquetes de traslación de raíz antes de reperfilarlos.
- Por ello se retiró la escala de velocidad del estándar, conservando su ritmo
  por el reloj conjunto de acción/pose ya probado. El test estándar exige ahora
  velocidades100/−100 intactas; el test independiente del laboratorio conserva
  su comprobación125/−125. El manifiesto deja de prometer locomoción al125%.

**Cámara:** `0x800A8680 != 0` se usa como referencia de nodo. La conversión
relativa está en `0x800506C8` tras `0x800242B8`, con matriz GTE y entradas
truncadas a halfword; `0x8004DEFC` consume el resultado después. La rama
`0x800AA194 == 1` (`0x80054EBC/C4`) utiliza otra cadena de cámara general y el
contexto `*(0x800A9D0C)`: modificar las seis coordenadas de cámara directa no
demuestra cambiar su encuadre. Faltan productores y frontera temporal segura de
esa rama. No se impone un ajuste de VBlank sin esos datos.

## 12. Locomoción propia y diagnóstico medido (2026-10-18)

### Delta propio antes de las colisiones

`src/mods/dbfb_locomotion.h` añade un callback en **0x80067A68**, instrucción
original `0x02020018` (`mult s0,v0`). Evidencia STEP40 SHA256 de §11:
`0x80067A54..5C` resta la traslación de raíz anterior; `0x80067A60/64` extiende
el delta de s0 a signed16. Las proyecciones seno/coseno usan ese mismo s0, y
después siguen separación y actualización de posiciones. La variante modifica
solo ese registro; no escribe posiciones ni `script+c`.

Diseño fijo del estándar, simétrico para humano y CPU: objetivo 5/4 del delta
nativo, aceleración máxima40 unidades/VBlank activo y frenado64. Para una
entrada100 y llamadas cada VBlank:40,80,120,125; neutral:61,0. Dos llamadas en
el mismo VBlank no acumulan aceleración. Solo familia nativa0..0x16 con vida/ki
válidos y delta−256..256. Otras acciones, KO, discontinuidades, hit-stop,
pausa, restauración, recarga y online conservan la ruta nativa y descartan la
velocidad guardada. No se ha añadido giro propio ni clips de locomoción.

El nuevo sitio figura en `game.toml` y está verificado contra la captura privada
y el disco en el arnés. Se reconstruyó el namespace
`cg18_1b6950cb_gc58692d0b_f0`: **1.157 DLLs con ranges**, configuración desplegada
15.663bytes idéntica. La reconstrucción completa no fue toda PASS: ocho
rechazos de auditoría/memo de fragmentos kernel en regiones1000/2000 quedaron
excluidos; no se relajó la auditoría. Primera invocación agotó600s; continuación
con8workers terminó (624construidos,250omitidos,8rechazados). El verificador
offline PASS y la prueba real posterior confirman el uso del nuevo namespace.

### Verificación actual

- **65/65 tests PASS**, 34grupos C; prueba nueva de aceleración/frenado con
  ambos signos/lados, cadencia, pausa, KO y restore. Matriz942 y432 scripts de
  técnicas siguen pasando. Hubo dos fallos iniciales de fixture: no simulaba
  el sondeo periódico y presentaba una resurrección de HP tras abrir el combate;
  se corrigió el escenario, no las guardas de producción.
- **Build normal y PGXP PASS.** Aviso preexistente de comentario en `pgxp.h`.
- **Sesión n PASS**,420s,puerto4382, `--kos 3 --savestate --movement --summary`:
  cuatro secuencias vida→KO→menú, pausa0→1→0, save/load generaciones1/2,
  salida0 sinterminate;34.465frames al último sondeo; **5.321 intervenciones de
  locomoción**,144variantes de técnicas,91transiciones,25ráfagas,200/200 filtros
  de hit-stop. Despachos21.910.246nativos/1.627.973interpretados. Evidencia privada
  `dbfb-rework-smoke-20261018n/`. El smoke conserva ahora los últimos contadores
  en cada captura si ocurre un fallo posterior y exige locomoción observada
  al usar `--movement`. No equivale a validación humana o de todos los escenarios.

### El bloqueo no se declara corregido

`host_sampler.c` registra la duración máxima de su intervalo Windows
SuspendThread/GetThreadContext antes de reanudar el hilo. Se expone por
`host_profile.max_suspend_us` y en el reporte final como
`host_sampler_max_suspend_us`. No cambia el watchdog ni la emulación. Sesión m
(antes de locomoción):4combates PASS, máximo123.400µs; n:4combates PASS,
máximo173.844µs. Ninguna reprodujo l. **No permite atribuir ni resolver los
12,4s de l**; la instrumentación sirve para distinguir esa hipótesis cuando
reaparezca. Las evidencias l/c permanecen intactas.

Disponibilidad recuperada sin instalación/configuración persistente: Ghidra12.1.2
y JDK25 ya existían, registrados para otro cliente. REA6.7.0 se probó por MCP
stdio (207tools, binary_session sin error) con entorno del proceso; no se editó
la configuración de OpenCode ni se instalaron componentes.

**Pendiente real:** causa del bloqueo, rutas/remates aéreos, clips totalmente
nuevos con correspondencia anatómica, giro propio, encuadre general y balance
humano. La aceleración/frenado ya no se enumera como función inexistente.

## 13. Continuación y relevo transferible (2026-10-18)

A petición del usuario se escribió primero `ROADMAP_RELEVO_COMBATE.md`: tareas
R0–R7, estado real, evidencias privadas, comandos, criterios de cierre y texto
de encargo para otro modelo. AGENTS/HANDOFF enlazan el documento para evitar
que un relevo repita estados antiguos como si fueran los actuales.

Después se continuó R1. **Productores y consumidores de80/200 localizados**,
con detalle reproducible en `COMBATE_MAPA.md` §9 y nuevo comando
`python -B tools/combat_map.py routes`. Incluye cinco accesos por comando,
condiciones por ID de luchador y ramas98/AA→99/9B/9A. La vía general cmd25
estaba sin enlazar: depende de20/40 y tiene un delay slot que distingue98 deAA.
Se corrigió la etiqueta errónea de opcode61, que controla canales de audio y
no banderas del luchador. Tres tests de rutas nativas y una regresión del
opcode elevan la suite a **69/69 PASS**; matriz942 y34gruposC se mantienen.

No se ha añadido todavía un movimiento aéreo nuevo. Falta observar por wtrace
los stores reales y completar la relación entrada→20/40 antes de diseñar el
cambio. El consumidor trabaja con candidato en pila sp+48 y publica en57F94;
no basta ver acciones en dos fotos para atribuir la transición. El relevo deja
el experimento con rangos, PCs, máscaras de entrada y limpieza segura de slots.
La sesión n pertenece al tramo anterior; no hubo nueva partida en esta tanda.

## 14. R1: retención del remate aéreo y observación en partida (2026-10-18)

Continuación de §13. Se volvió a verificar la cadena 98/AA→99/9B/9A leyendo los
bytes y se implementó **una** mejora concreta en el plugin. R1 sigue **abierto**:
la ruta completa no se reprodujo en una partida.

### Verificación estática (sin cambios de semántica)

- El consumidor `0x80057608` trata el candidato `0x98` y `0xAA`: el delay slot de
  `0x8005760C` (`addiu v0,zero,0xAA` en `0x80057610`) prepara la segunda comparación
  en `0x80057614`; ambas acciones llegan a `0x8005761C` (filtro de IDs), luego el
  selector `0x800576BC` lee `control+4` y elige `0x9B` (0x280), `0x99` (0x80 sin
  0x200) o `0x9A` (sin 0x80), limpia la máscara y guarda el candidato en `sp+0x48`.
  `0x80057F84` lo relee y `0x80057F94` lo publica en `control+8`.
- El handler de `cmd25`, `0x800607A0`, **escribe `control+8` directamente**:
  `0x20`→`0x98` (delay slot `0x80060804`), si no `0x40`→`0xAA` (`0x80060810`), si
  no no escribe acción. `cmd29` (`0x800609C0`) además arma `0x200` en `0x80060AAC`.
- Se confirmó dónde se **consume** `control+0x56`: la función de la puerta
  (`0x80054980`) lo llama con `jal 0x80056E54`, y dentro de esa función
  `0x800570F8` (`lh a1,+0x2856`) alimenta el despachador en `0x800570FC`. Por eso
  inyectar en `0x80054AE8` (hook del estándar) sí llega al mismo frame; no es una
  escritura inerte.

### Mejora implementada: retención del gesto de remate aéreo

`src/mods/dbfb_responsive.c`, dentro de `standard_command` (hook `0x80054AE8`):
cuando el reconocedor produce `0x25`/`0x29` y `control+4` **no** tiene `0x20`/`0x40`
(el handler nativo no escribiría acción), el comando se retiene y se **reinyecta
por el mismo slot nativo `control+0x56`** en cuanto aparece la bandera aérea, como
mucho **16 frames** de invitado. No se escribe nunca en `control+4` ni `control+8`:
la puerta, el handler, el coste de ki y el estado ocupado siguen decidiendo. Se
cancela con otro comando reconocido, una acción de continuación (98/AA/99/9A/9B),
pausa, online/resim, restauración o pérdida de contexto. Contadores nuevos
`dbfb.responsive.followup_wait` (retención) y `followup_inject` (entrega).

Es la palanca «accesibilidad/ventana» del roadmap aplicada a la ruta demostrada,
sin retimar ni coordinar al rival. No sustituye a la ruta nativa: solo evita perder
un gesto hecho en el arranque del salto.

### Observación en partida (privada)

- Instrumento: `wtrace_add` exclusivo sobre `control+4`/`control+8` de ambos lados,
  sesión headless con gestos sintéticos (puertos 4384/4386, carpetas propias).
- Con `FOLLOWUP_LIFE=8` la retención se ejecutó **64** veces en una sesión de 240 s;
  con `16` (medida final), **16** veces en otra. `followup_inject` quedó en **0**:
  el estado aéreo (`control+4` con `0x20`/`0x40`) apareció en ~7 % de muestras y no
  se alineó con el gesto, así que la entrega no se pudo observar sintéticamente.
- La ruta completa 98/AA→99/9B/9A **no** se reprodujo: en las capturas sí aparecen
  las acciones `0x98`/`0x99` escritas por `0x8004EEAC`/`0x80057F94`, pero **no** los
  stores de limpieza del consumidor (`0x800576F8`/`0x80057734`/`0x80057764`) ni los
  productores de `0x80` (`0x80062FF4`…), luego el consumidor no llegó a ejecutarse.

### Verificación

- `python -B -m unittest discover -s tools/tests -p "test_*.py"`: **69/69 PASS**,
  incluido el nuevo escenario C de retención (retención al estar en suelo, inyección
  única al armarse la ventana, cancelación por otro comando/continuación, cota,
  ambos lados, pausa/online/restore): **35 grupos C**.
- `cmake --build build-release --target psx-runtime psx-runtime-pgxp -j 4`: normal y
  PGXP enlazados con el cambio.
- `python tools/verify_offline.py`: **PASS**; namespace **`cg18_1b6950cb_gc58692d0b_f0`**
  sin cambios (1157 DLLs), no se tocó `game.toml` ni hooks.

### Por qué R1 sigue abierto

- La ruta del consumidor (98/AA→99/9B/9A) no se ejecutó en partida bajo input
  sintético y no se ha medido sensación ni ventaja.
- La **entrega** de la mejora no se observó; solo su retención.
- Falta mapear qué acción/entrada arma `control+4` `0x20`/`0x40` (productor `0x1D`
  en `0x8005D900`) y **quién** arma `0x40`, para dirigir el gesto a la ventana aérea
  y ver la entrega y la continuación.

Siguiente experimento concreto: identificar la entrada/acción que enciende
`control+4` `0x20` (y `0x40`) — instrumentar `control+8` y `control+4` durante un
salto dirigido — y, con esa ventana, repetir el gesto `cmd25` y observar
`followup_inject` y el consumidor `0x800576BC` con wtrace (PCs `0x8006081C`,
`0x800576F8`/`0x80057734`/`0x80057764`, `0x80062FF4`).

## 15. Cierre 2026-10-19: settle integrado, encuadre general, fichas medidas y dificultad

- R3: `src/mods/dbfb_pose_settle.h` (llamado desde `motion_build` en
  `dbfb_motion.h`) clona la accion 6 del registro 0 (pista 105) con dos paquetes
  relativos nuevos por grupo (partes 8/9) que telescopan a cero en la muestra 5;
  paquetes originales, raiz/carriers y final nativo intactos. Probado en partida:
  la accion 6 apunta a un slot creado (245), no al nativo 105. Sin dueño de host:
  el playback nativo (context+8) sigue mandando; pausa/hit-stop/interrupciones/
  save-load se comportan como el nativo.
- R4: el seam seguro es `0x80054F88` (tras `0x800442A8`/`0x8004778C`; en
  `0x80054F34` la escritura se pierde). `src/mods/dbfb_camera_frame.h` escala
  SOLO el vector ojo->objetivo nativo (17/16) en el punto que consume
  `0x80024850`; guardas de modo/lock/transicion/KO/pausa/online/rango; contador
  `dbfb.responsive.camera_framing`; opt-out `DBFB_CAMERA_FRAMING=0`. Requiere
  sitio nuevo en `game.toml` + overlays recompilados (1158 OK, 8 rechazos kernel
  conocidos), namespace `cg18_1b6950cb_gc164a1e9a_f0`.
- R5: `tools/combat_cards.py` mide en VBlanks del juego (startup, recuperacion,
  ventaja hit/bloqueo, hit-stop). Cuadrado 0x72/0x73 startup 17-20 VB, ventaja
  2-40 (n=3), hit-stop 4 VB; triangulo 0x64/0x65 startup 14-23. Limites: n
  pequeno, sin bloqueo controlado, aereos sin muestras.
- R6: dificultad 0/1/2 verificada en partida; acciones CPU/minE 28,0/37,4/42,7;
  cadencia extra del mod no distinguible con el gate cerrado.
- Detalle completo, archivos y comandos en `ROADMAP_RELEVO_COMBATE.md` §8.
