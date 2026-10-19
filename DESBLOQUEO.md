# Desbloqueo de personajes (Final Bout USA)

Mecanismo localizado en el código del juego y reimplementado como opción del mod
`dbfb.responsive` (feature `unlock-all`). Todo lo de este documento procede de
desensamblado del disco y de memoria viva; no hay offsets inventados.

## El truco original

En la pantalla de título (la del logo y «PRESS SELECT FOR SOUND MENU») el juego
lleva un **anillo de 18 entradas** con la última dirección pulsada:

| Dato | Dirección | Nota |
|---|---|---|
| Índice del anillo (0..17) | `0x80060B10` | se incrementa al cambiar de dirección |
| Anillo de direcciones | `0x80060B14 + i*4` | 18 palabras; envuelve en +0x48 |
| Dirección actual | `0x8005686C` | se ignora si es 0 o repite la anterior (`0x80056870`) |
| Tabla parte 1 (8 entradas) | `0x800562AC` | `Up, Down, Left, Right, Up, Down, Left, Right` |
| Tabla parte 2 (14 entradas) | `0x800562CC` | segunda secuencia |
| **Tabla de personajes** | **`0x8003BCC4`** | valor exacto comparado por la selección |

El reconocedor recorre el anillo hacia atrás y compara cada entrada con la tabla.
Como se lee del más reciente al más antiguo, el orden **que hay que teclear** es
el inverso de la tabla:

1. `Derecha, Izquierda, Abajo, Arriba` dos veces → suena un aviso y el juego
   escribe `0x0001BFFF` en `0x8003BCC4` (16 luchadores).
2. La segunda tabla (14 entradas) → escribe `0x0001FFFF` (los 17, incluido
   Goku SSJ4).

En el mapa de bits de la palabra: `0x7DF` es la plantilla inicial (10
luchadores), `0x1BFFF` son todos menos SSJ4 y `0x1FFFF` son todos. La selección
de personaje compara la palabra **exactamente** contra `0x1BFFF` y `0x1FFFF`
para decidir qué retratos enseña.

## Cómo lo implementa el mod

`src/mods/dbfb_responsive.c`, feature `unlock-all`:

- En cada VBlank, si la partida es offline y `0x8003BCC4` vale `0x7DF` o
  `0x1BFFF`, escribe `0x1FFFF`.
- Si vale cualquier otra cosa **no escribe nada**.

**Corrección 2026-10-18:** la dirección anterior `0x8004BCC4` era incorrecta.
STEP00 cocido, offsets `0x328/0x32C`: `lui at,0x8004` seguido de
`sw v0,-0x433c(at)`. Extendiendo el inmediato con signo resulta **`0x8003BCC4`**.
Las lecturas de STEP01 usan la misma combinación. La prueba automática compara
ahora la dirección con ese almacenamiento del disco, además de probar el plugin.

El valor escrito es exactamente el que el propio truco del juego escribe, así que
el comportamiento es idéntico al de teclear la combinación.

## Estado de verificación

- **Mecanismo: verificado.** Dirección, valores, tablas y código de comparación
  leídos del disco y confirmados en memoria viva durante una sesión headless.
- **Mod: verificado a nivel de unidad.** Compila con `-Wall -Wextra -Werror`,
  pasa la prueba de escenario del banco de pruebas (escribe el plantel completo
  desde los dos valores conocidos, deja intacto un valor de código y se niega en
  online/resim).
- **Extremo a extremo: verificado tras corregir la dirección.** La sesión
  `dbfb-rework-smoke-20261018b` registra `0x8003BCC4 == 0x1FFFF`, una activación
  del contador y **17 retratos visibles**, SSJ4 incluido (`004-menu.png`, privada
  en la carpeta temporal de la sesión). La navegación anterior también usaba START
  incorrecto: en debug es `0x0008` (activo-bajo `0xFFF7`), no `0x0800`.

## Cómo comprobarlo a mano

1. Activar `unlock-all` (y opcionalmente `standard`) en el launcher.
2. Entrar a la pantalla de título.
3. Ir a la selección de personaje y contar los retratos: deben aparecer los 17
   (Goku SSJ4 incluido) sin teclear nada.
4. Si se quiere el comportamiento original, desactivar `unlock-all`.
