# GUION YOUTUBE — "Dragon Ball Final Bout en PC: cómo instalarlo (y por qué existe)"

> Guion para dar a conocer el proyecto **DBFinalBout Recomp (PSXRecomp)**.
> Estilo NovaPowers / Hijos del Tiempo, pero con estructura de **tráiler +
> guía de instalación**. Duración objetivo: 12–16 minutos.
> Formato: bloques con timestamp, indicaciones visuales entre paréntesis.

---

## PARTE 0 — TRÁILER (0:00 – 1:30)

### TRÁILER — 0:00 – 0:50 (montaje rápido, sin voz o con voz en off épica)

*(Secuencia rápida de cortes, música épica en crescendo. CERO texto explicativo. Solo imágenes + una frase por corte.)*

- CORTE 1 *(negra, suena un "blip" de PS1)*: texto blanco sobre negro → **"1997. Dragon Ball Final Bout. El primer Dragon Ball en 3D."**
- CORTE 2 *(portada original de PS1, luego un combate en pantalla)*: **"Y el que todo el mundo quiso olvidar."**
- CORTE 3 *(gameplay original: personajes flotando, frames cayendo, input lag)*: **"Input lag. 20 frames. Movimiento de abuelo con lumbago."**
- CORTE 4 *(negro → aparece el logo de PSXRecomp brevemente)*: **"Un día, alguien decidió abrir el cadáver."**
- CORTE 5 *(el juego corriendo en Windows, launcher abierto)*: **"No es un emulador."**
- CORTE 6 *(combate real en ventana, 60 fps, widescreen)*: **"Es el juego, nativo, en tu PC. Funciona mucho mejor."**
- CORTE 7 *(ráfaga: Kamehameha a pantalla completa en 16:9)*: **"Y con widescreen."**
- CORTE 8 *(negra)*: **"Dragon Ball Final Bout Recomp."**
- CORTE 9 *(título del vídeo a pantalla completa, golpe de música)*: **"Cómo instalarlo. Y por qué existe."**

### POST-TRÁILER — 0:50 – 1:30 (primeras palabras a cámara)

*(Se acabó el tráiler. Te sientas, tono distendido, como quien baja la película para contarte algo.)*

"¡Listo! Eso es exactamente lo que instalaremos hoy, sin rodeos ni clickbait. Pero antes de pasar al tutorial técnico paso a paso, os cuento rápidamente la increíble historia detrás de este proyecto."

---

## PARTE 1 — LA HISTORIA (por qué existe)

## 1) PROMESA CLARA — De qué va ESTE vídeo (1:30 – 2:10)

*(Visual: gameplay real del proyecto corriendo en Windows con el launcher visible.)*

"El tutorial llega ya, pero antes de descargar nada, debéis entender qué es esto.

Es una recompilación estática: traducimos el código MIPS original para que el juego corra nativo en Windows, sin emuladores ni glitches. Es, literalmente, un programa de PC.

Lo mejor: respeta el copyright. No distribuye archivos del juego; tú aportas tu copia legal (disco o ISO) y el software hace el resto.

Os cuento la historia del proyecto, su potencial y, al final, os dejo la guía paso a paso."

## 2) CONTEXTO BREVE — El recuerdo compartido (2:10 – 3:30)

*(Visual: montaje rápido con Ultimate Battle 22, Legends, Hyper Dimension y la propia Final Bout en su versión original.)*

"Contexto rapidito, que sé que muchos ya lo sabéis. 1997: Dragon Ball GT terminaba en Japón, y para cerrar la franquicia llegó lo que parecía la gran promesa: **el primer Dragon Ball en 3D poligonal**.

El problema: el desarrollo fue un caos. El estudio cambió de manos, el motor se rehízo a mitad, y el resultado fue un juego que se movía como si los personajes flotaran en sopa de fideos. Input lag brutal, 20 frames por segundo, golpes que no conectaban. Era la vergüenza de la saga.

Y ahí quedó. Enterrado. Para siempre. Hasta que veinticinco años después, un chaval descubrió lo que la comunidad de recompilación hizo: **reescribir el código de PS1 para no necesitar consola ni emulador**."

## 3) PRIMER GIRO — La grieta (3:30 – 5:00)

*(Visual: captura del log de la herramienta de codegen, hex dumps, un error críptico en pantalla.)*

"Aquí vino la parte difícil, la que casi me hace tirar la toalla. Recompilar suena bien, pero implica coger el ejecutable original —el SLUS_004.93— y traducir sus instrucciones MIPS a x86 para PC. No es automático: hay que reconstruir funciones de cero, entender cómo renderiza los gráficos y cómo gestiona los archivos.

Existe una herramienta brutal llamada **PSXRecomp**, un recompilador de PlayStation que ya usaban otros proyectos de la comunidad. Así que pensé: 'perfecto, solo aplico esto a Final Bout'.

Jajaja.

Cada juego es un mundo. Y cuando lo abres, descubres que Final Bout por dentro tenía mucho más de lo que dejaba ver: modelos a medias, sistemas que nunca se activaron, código muerto. Había que descifrarlo todo a base de pruebas: semanas de hex dumps, de offsets, de pruebas que fallaban. Hubo un momento en el que el juego se caía al arrancar, con un error críptico que no decía nada —resultó ser una 'junction' rota de Windows, de las que ni te enteras de que existen—.

Pero tras tanto tiempo metido ahí, es imposible dejarlo a medias. Ver el juego arrancar estable en Windows es una sensación adictiva. Es como descifrar un jeroglífico que llevaba meses dándote dolores de cabeza."

---

## PARTE 2 — QUÉ PUEDE HACER

## 4) BLOQUE CENTRAL — Viaje personal traducido (5:00 – 8:00)

### 4.1 El puerto: lo que se ha logrado (5:00 – 6:30)

*(Visual: gameplay en widescreen 16:9 a 60 fps. Comparativa lado a lado con el original de PS1.)*

"Y no os engañéis: lo que se ha conseguido es una locura.

El juego corre a **30 frames nativos** pero son nativos. Los que lo jugasteis en 1997 sabéis que en PS1 se arrastraba entre 20 a 30 si es que llegaba.

El **input lag** —ese lag que hacía que los combos no salieran— está documentado y atacado desde la base, en los propios pads de la consola virtual. Ya no pegas a un personaje 'medio segundo después' de pulsar el botón.

Y el **widescreen**. Final Bout era un 4:3 puro. El puerto añade 16:9 sin estirar la imagen, sin deformar. Y con una regla de oro: todo lo que se toca se documenta, se marca como WIP, y si algo no está listo se dice claro, en este caso NO está 100% listo, os lo aviso, se está trabajando en ello para que sea más estable."

### 4.2 El launcher: tu nave espacial (6:30 – 8:00)

*(Visual: recorrido por el launcher: botón de Play, opciones de vídeo, la herramienta detectando el disco.)*

"Y todo se controla desde el launcher: elegir la resolución, ventana o pantalla completa, y un botón de Play que te lleva directo al combate. Pero lo importante está debajo del capó: cuando pulsas Play, el launcher verifica tu copia del disco —con sus checksums—, genera el código del juego y lo compila para tu máquina. En media hora tienes tu propio Final Bout nativo, hecho por ti, con tu copia legal.

Y ojo, hay más: se han añadido **mods** al proyecto. Un motor de combate personalizado y el widescreen, ambos marcados como WIP con total honestidad —el widescreen está, el combate personalizado todavía no está listo para uso. Esto es una obra en construcción, y se dice en la cara."

---

## PARTE 3 — LA VERDAD

## 5) MOMENTO INCÓMODO — La verdad que duele un poco (8:00 – 9:30)

*(Visual: pantalla en negro unos segundos. Luego una captura de un modelo en combate con las sombras "en la lejanía". Música que baja.)*

"Y toca el momento incómodo. Porque no todo es magia.

Primero, las **sombras**: hay un problema con los modelos. En ciertos ángulos, parecen que están a años de distancia, como si la profundidad se hubiera torcido. Investigamos, medimos, comparamos con el emulador de referencia…

*(Pausa.)*

Y resulta que ese defecto **ya estaba en el juego original**. Es la proyección de profundidad del motor de 1997. No lo arreglamos nosotros, no lo arregló nadie en 25 años, y ahora por fin está documentado con pelos y señales en el repositorio. Eso es la diferencia entre un trabajo serio y un vídeo de 'mira qué port chulo he hecho': publicamos también los fallos.

Y segundo, la honestidad en los WIP: el widescreen está en desarrollo, y el motor de combate personalizado no está recomendado para uso todavía. Os lo digo para que no penséis que ya se puede jugar de forma excelente, ahora pasó de un mediocre a un "ta bien"."

---

## PARTE 4 — LA GUÍA DE INSTALACIÓN (el plato fuerte)

## 6) GUÍA DE INSTALACIÓN — Paso a paso (9:30 – 14:00)

*(Visual: pantalla compartida con capturas reales de cada paso. Numeración en pantalla bien grande. Ritmo pausado: aquí la gente está siguiendo, no riéndose.)*

"Y ahora sí. Dejadme que os explique cómo instalar esto en vuestra casa. No es complicado, pero hay que hacerlo en orden. Vamos paso a paso.

### Paso 1 — Descargar el proyecto (9:30 – 10:00)

*(Visual: la página de GitHub del proyecto, pestaña Releases.)*

"Primero, entráis al repositorio del proyecto —lo dejo enlazado en la descripción—, id a la pestaña de **Releases**, y descargáis el ZIP de Windows: `dbfb-0.1.0-setup-host-win64.zip`. Lo descomprimís en una carpeta. Dentro viene el ejecutable `DBFinalBout_Recompiled.exe`, el recompilador, el SDK y un README que os explica todo.

*(Nota de honestidad en pantalla: "El ZIP NO incluye el juego.")*

### Paso 2 — Instalar Python (10:00 – 10:30)

*(Visual: captura de la web de Python, el instalador, y `python --version` en una terminal.)*

"El proyecto necesita **Python 3** para las herramientas de generación y compilación. Si no lo tenéis, lo instaláis desde python.org —marcando 'Add to PATH' en el instalador, que es lo que olvida todo el mundo. Comprobadlo con `python --version` en una terminal: si os responde la versión, listo."

### Paso 3 — Aportar tu copia legal del juego (10:30 – 11:45)

*(Visual: diagrama de dónde va cada cosa: la ISO/bin del juego y, opcionalmente, la BIOS SCPH-1001.)*

"Aquí viene lo importante, y por esto el proyecto es legal: **el ZIP no trae el juego**. Vosotros tenéis que aportar los archivos de vuestra copia legal. Es el mismo sistema que usan los proyectos de recompilación de la comunidad: tú pones el juego, ellos ponen el código.

Necesitáis **vuestra copia del disco** —el bin o la ISO de *Dragon Ball GT: Final Bout* versión USA (SLUS-00493)—. Si tenéis el disco físico, lo pasáis a bin con cualquier lector de PS1 y una herramienta de extracción de imágenes.

Y ojo, un detalle que gusta mucho a los puristas: en la documentación del proyecto —el archivo `baserom.md`— están los checksums exactos del disco, para que verifiquéis que vuestra copia es la correcta antes de empezar. Nada de roms de dudosa procedencia: copia legal, y el proyecto se encarga del resto."

### Paso 4 — Primer arranque y generación (11:45 – 13:00)

*(Visual: primer arranque real, launcher abierto. Marcar con círculos en pantalla cada opción. Luego el 'Generate & rebuild'.)*

"Ejecutáis `DBFinalBout_Recompiled.exe` y se abre el launcher. Aquí:

- Le indicáis dónde está **vuestra copia del disco** —el bin que habéis preparado.
- Pulsáis **Play** (o seguís el asistente de 'Generate & rebuild').

El launcher verifica el disco contra los checksums, genera el código del juego a partir de vuestro bin, y lo compila para vuestra máquina. La primera compilación descarga el compilador —`cmake-clang-v1`— automáticamente, así que tardará un rato. Las siguientes veces, todo va directo.

*(Nota en pantalla: "El código generado se queda en TU máquina. No se sube a ningún sitio.")*

Un detalle técnico: si tenéis una **BIOS de PlayStation original** (SCPH-1001) podéis usarla; si no, el proyecto genera una BIOS abierta localmente. Todo legal, todo en tu máquina."

### Paso 5 — Comprobar que todo funciona (13:00 – 14:00)

*(Visual: el juego arrancando, entrando a un combate en widescreen a 60 fps. Marcar en pantalla lo que se espera ver.)*

"Y listo. Si habéis hecho los pasos en orden, tenéis el **Dragon Ball Final Bout corriendo de forma nativa en Windows**, a 30 frames reales, en widescreen, generado por vuestro propio ordenador a partir de vuestra copia legal.

Y si algo va mal: el proyecto guarda logs en la carpeta de logs, y la documentación está en abierto. Esto es software libre hecho por fans: los bugs se reportan, se investigan y se arreglan."

---

## PARTE 5 — CIERRE

## 7) RESOLUCIÓN — Aceptar el cambio (14:00 – 15:00)

*(Visual: montaje de los logros: el juego corriendo, el launcher, el widescreen. Música nostálgica.)*

"Y con todo esto, ¿qué queda? Pues que hoy tenéis **el juego más odiado de Dragon Ball corriendo de forma nativa en Windows**, en nativo, con widescreen, con launcher, y con todo el trabajo de ingeniería inversa documentado en abierto, para que cualquiera pueda aprender y continuar.

No es perfecto. Tiene sus sombras raras —que ya estaban en el original—, sus WIP, sus cosas a medio hacer. Pero es **nuestro**. Y que algo así exista, en abierto, para que la gente pueda tocarlo, aprenderlo y mejorarlo… eso es lo que de verdad importa.

Final Bout no era mejor de lo que recordamos. Pero era el primer 3D. Era el puente. Y ahora, por fin, es el juego que se merecía a sí mismo."

## 8) CTA EMOCIONAL — Devuelve la pregunta (15:00 – 15:45)

*(Visual: el proyecto corriendo en pantalla completa, con el logo del canal al final.)*

"Y ahora os toca a vosotros, Hijos del Tiempo.

¿Habéis tenido alguna vez un juego que os dolía no poder jugar? Un juego atrapado en una consola muerta, en un formato olvidado, en una emulación rota. ¿Y si os dijeran que se puede resucitar… y que os explican cómo?

Si os ha molado esto de la preservación y la ingeniería inversa, y queréis ver qué juego resucito a continuación… dejadme en los comentarios cuál sería el vuestro. De verdad, me interesa. Porque estos proyectos nacen de ahí: de que alguien dijo 'esto no se puede perder'."

## 9) CIERRE + IDENTIDAD (15:45 – 16:30)

*(Visual: logo de 'Hijos del Tiempo', música de cierre del canal.)*

"Este canal no va solo de jugar. Va de recuerdos, de tiempo, de todo lo que se nos quedó por el camino… y de lo que se puede recuperar si alguien se empeña.

Si queréis seguir este proyecto —y los que vienen—, ya sabéis: suscribíos, compartid, y si queréis apoyar de verdad, los miembros del canal están ahí. Sin presión. Tendréis en pantalla y descripción los vídeos de los Budokai HD y Buu's Fury.

El código, las herramientas, la documentación y la guía de instalación completa… todo está en el repositorio del proyecto, enlazado en la descripción, para quien quiera meter las manos.

Nos vemos en el próximo vídeo. Y recordad: algunos juegos no mueren. Solo esperan a que alguien los resucite."

---

## NOTAS PARA PRODUCCIÓN

- **Estructura en dos mitades**: el tráiler (0:00–1:30) engancha; la historia (1:30–9:30) justifica; la guía de instalación (9:30–14:00) es el plato fuerte que la gente buscará y compartirá; el cierre (14:00–16:30) es el sello NovaPowers. Si alguien salta al minuto 9:30, se pierde la historia pero se lleva el tutorial.
- **La guía de instalación es el corazón del vídeo**: más capturas de pantalla reales y menos metáforas ahí. Numeración grande en pantalla, marcar con círculos rojos las opciones del launcher, y un diagrama de dónde va el bin del disco.
- **Términos técnicos a simplificar en voz alta**: recompilación = "traducir el juego de la consola a tu PC", MIPS = "el idioma de la PS1", bin = "la imagen de tu disco", checksum = "la huella digital del disco", WIP = "en desarrollo", junction = "un acceso directo raro de Windows".
- **Qué NO decir**: no prometer que el widescreen ni el motor de combate están acabados — decir "WIP" y "en desarrollo". No mencionar dónde conseguir la ISO — solo "copia legal", "tu disco", "baserom.md" con los checksums. Los checksums y nombres de archivo exactos están en `baserom.md`, no hace falta memorizarlos en el vídeo.
- **Si el vídeo se hace largo**: el bloque 4.1 (el puerto) y el 4.2 (el launcher) son los más recortables a 60-90s cada uno. El momento incómodo (bloque 5) y la guía (bloque 6) NO se recortan: son la identidad del canal y la utilidad del vídeo.
- **Título alternativo si se prefiere más guía que historia**: "Así resucito Dragon Ball Final Bout en PC (guía de instalación incluida)".
- **Enlaces para la descripción**:
  - Repo: https://github.com/novapowers0/DB-Final-Bout-Recomp
  - Release: https://github.com/novapowers0/DB-Final-Bout-Recomp/releases/tag/v0.1.0
  - Recompilador (fork con mods): https://github.com/novapowers0/psxrecomp
