# Dragon Ball GT: Final Bout Recompiled

[English](README.md) | [Español](README_ES.md)

[![Release](https://img.shields.io/github/v/release/novapowers0/DB-Final-Bout-Recomp?sort=semver&style=flat-square&color=orange&label=Release)](https://github.com/novapowers0/DB-Final-Bout-Recomp/releases/latest)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6?style=flat-square)](https://github.com/novapowers0/DB-Final-Bout-Recomp/releases/latest)
[![License](https://img.shields.io/github/license/novapowers0/DB-Final-Bout-Recomp?style=flat-square)](LICENSE)
[![Stars](https://img.shields.io/github/stars/novapowers0/DB-Final-Bout-Recomp?style=flat-square&color=yellow)](https://github.com/novapowers0/DB-Final-Bout-Recomp)
[![Built with](https://img.shields.io/badge/built%20with-PSXRecomp-8A2BE2?style=flat-square)](https://github.com/mstan/psxrecomp)

Recompilacion estatica para PC de *Dragon Ball GT: Final Bout* para PlayStation,
basada en [PSXRecomp](https://github.com/mstan/psxrecomp) y
[recomp-ui](https://github.com/mstan/recomp-ui).

El codigo MIPS original se recompila como codigo nativo para Windows y se integra
en un ejecutable independiente con launcher, soporte de mods y configuracion de
renderizado. No es un emulador tradicional.

| | |
|---|---|
| **Jugadores** | 1-2 |
| **Plataforma** | Windows x64 |
| **Region** | USA |
| **Serial** | SLUS-00493 |
| **Genero** | Lucha 3D |
| **Version** | v0.2.1 |

Copyright (c) 2026 **NovaPowers**. Licencia MIT (ver `LICENSE`).

---

## Aviso Legal

El juego y sus datos **no se distribuyen**. Para jugar debes aportar los archivos
de tu **copia legal** de *Dragon Ball GT: Final Bout*.

- El proyecto espera la version USA `SLUS-00493`.
- Consulta `baserom.md` para el tamano, serial, volumen y checksums esperados.
- No se incluyen imagenes de disco, BIOS retail ni fuentes C generados.
- La release incluye ejecutables y bibliotecas nativas; tu aportas el disco.

Proyecto no oficial, sin animo de lucro, de investigacion y preservacion. No esta
afiliado ni respaldado por Bandai, Shueisha, Toei Animation ni otros titulares
de derechos de Dragon Ball.

---

## Para Jugar

1. Descarga `dbfb-0.2.1-windows-x64.zip` desde
   [release experimental v0.2.1](https://github.com/novapowers0/DB-Final-Bout-Recomp/releases/tag/v0.2.1).
2. Descomprime el paquete en una carpeta de Windows.
3. Aporta tu copia legal siguiendo la identidad descrita en `baserom.md`.
4. Ejecuta `DBFinalBout_Recompiled.exe` o abre el launcher incluido.
5. Deja el widescreen desactivado para una presentacion 4:3 fiel, o activa
   `psx.enhancement.widescreen` para 16:9/adaptive.

El paquete ya esta compilado. Selecciona tu disco al abrirlo; no hace falta
compilar. Incluye OpenBIOS con su licencia MIT.

### Combate renovado (opcional, offline)

En **Mods**, activa **Combate renovado** para usar el perfil integrado.
**Todos los personajes** desbloquea los 17 luchadores de forma independiente.
Ambos vienen desactivados. El perfil mejora entradas, remates aereos nativos,
movilidad, defensa, hit-stop, ki y abre algo el encuadre. La transicion nueva
del brazo se limita al registro de animacion 0 verificado. Sigue siendo
experimental: en vuelo puede quedar un luchador fuera del plano original;
las fichas medidas y el balance por dificultad no son exhaustivos. Consulta
las notas de la version.
Las pruebas del modo original tambien detectaron un cierre intermitente por
watchdog. v0.2.1 corrige una espera del host sobre trabajadores de
autocompilacion ya finalizados, pero la causa de todos los cierres sigue
abierta. v0.2.1 es una pre-release experimental.

### Configuracion Recomendada

- **Renderer:** software, como ruta de referencia.
- **Widescreen:** stretch-only; 16:9/adaptive disponible.
- **Vulkan:** disponible como opcion experimental.
- **PGXP:** variante separada incluida para pruebas de precision.
- **Netplay:** LAN/direct-IP disponible; ICE/TURN online no esta activado.

---

## Funcionalidades

| Funcion | Estado |
|---|---|
| Recompilacion estatica del ejecutable PS1 | Funcional |
| Launcher Windows | Incluido |
| Overlay cache y recompilacion nativa | Incluido en la build validada |
| Widescreen 16:9/adaptive | Funcional en modo stretch-only |
| FOV/culling experimental | Desactivado por estabilidad |
| Renderer software | Ruta de referencia |
| Renderer Vulkan | Experimental |
| Runtime normal y PGXP | Incluidos |
| Netplay LAN/direct-IP | Compilado, pendiente de prueba manual completa |
| ICE/TURN online | No activado |

El widescreen conserva las coordenadas originales del juego. Algunos menus 2D
pueden mostrar una breve transicion de pillarbox 4:3 al cambiar de escena.

---

## Estructura del Repositorio

```text
DB-Final-Bout-Recomp/
├── psxrecomp/       # Recompiler y runtime como submodulo
├── recomp-ui/       # Launcher y UI como submodulo
├── mods/            # Configuracion y manifiestos de mods
├── seeds/           # Seeds del ejecutable de Final Bout
├── ghidra_proj/     # Herramientas de analisis e ingenieria inversa
├── tools/           # Scripts de build, diagnostico y validacion
├── generated/       # NO incluido: codigo generado localmente
├── disc/            # NO incluido: tu imagen legal del juego
├── game.toml        # Configuracion del runtime
└── CMakeLists.txt   # Definicion del build
```

---

## Compilar Desde el Codigo

Requisitos principales:

- Windows x64.
- Git con submodulos.
- CMake 3.20 o posterior.
- Ninja u otro generador compatible con CMake.
- Python 3.
- Toolchain compatible con PSXRecomp.
- Una copia legal del disco indicada en `baserom.md`.

```bash
git clone --recurse-submodules https://github.com/novapowers0/DB-Final-Bout-Recomp.git
cd DB-Final-Bout-Recomp

git submodule update --init --recursive
./psxrecomp/tools/ci/build_emitters.sh

python3 psxrecomp/psxrecomp_cli.py generate \
  --config game.toml \
  --project-root . \
  --disc "disc/<tu-disco>.cue"

cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --target psx-runtime
```

Para validar la instalacion sin iniciar el juego:

```bash
python tools/verify_offline.py
```

El contenido de `generated/` se deriva de tu disco y no debe subirse al
repositorio. Los artefactos de build y las imagenes del juego estan ignorados
por Git.

---

## Documentacion y Diagnostico

- `baserom.md`: identidad del disco y checksums.
- `AGENTS.md`: reglas de trabajo y estado tecnico del proyecto.
- `ANALISIS_CRASHES.md`: investigacion de freezes y overlays.
- `PLAN_SOLUCION_CRASH_Y_COMBATE.md`: estado actual y pasos de validacion del
  fix RI de la transicion a combate.
- `RELEASE_NOTES_v0.1.1.md`: cambios y estado de validacion de esta release.
- `SESSION_ANALYSIS.md`: flujo para capturar y analizar una sesion.
- `summary.md`: historial detallado de decisiones y validaciones.
- `tools/verify_offline.py`: comprobacion reproducible sin lanzar el juego.

---

## Historial de Versiones

### v0.2.1

Pre-release de mantenimiento: se corrigio una espera del hilo del juego en
VBlank sobre trabajadores de autocompilacion que habian publicado `DONE` sin
terminar, se anadio una regresion controlada de esa carrera y diagnosticos
pasivos del intervalo y las secciones del watchdog. Pasaron 121 pruebas, los
dos runtimes compilaron, la verificacion offline paso y una matriz aislada de
5/3/2 combates paso. La causa de los cierres intermitentes del modo original
sigue abierta; esta release no declara estabilidad universal.

Pins de frameworks: `psxrecomp` `a51c9aa7` (`rework-master`).

### v0.2.0

Release experimental de combate renovado: perfil opcional integrado,
transicion de recuperacion del brazo verificada, camara algo mas abierta,
desbloqueo de personajes, muestreo Windows opt-in y paquete Windows compilado.
Dos pruebas del paquete en modo original terminaron por watchdog; esa causa
intermitente siguio abierta.

Pins de frameworks: `psxrecomp` `835f1902` (`rework-master`), `recomp-ui`
`0546fbcb` y el submodulo anidado `recomp-net` `55269a62`.

### v0.1.1

Release de mantenimiento: se actualizaron los submodulos `psxrecomp` y
`recomp-ui`, se reconstruyo el paquete setup-host y se añadio una recuperacion
acotada para un callback IRQ vacio y obsoleto. Una sesion manual completo
Piccolo contra Goku y avanzo al combate contra Little Goku Super Saiyan sin
cuelgue. Los logs de esa sesion son anteriores al nuevo contador del callback,
asi que no prueban si se ejecuto esa recuperacion; el resultado solo cubre esa
secuencia probada y no garantiza que nunca haya cuelgues.

Pins de frameworks: `psxrecomp` `7d70880d` (`rework-master`), `recomp-ui`
`01bff947` y el submodulo anidado `recomp-net` `c2338c63`.

### v0.1.0

Primera release jugable y validada del proyecto, con runtime actualizado,
overlay cache, widescreen stretch-only, Vulkan experimental y soporte compilado
de netplay.

La publicacion original `v0.0.1` fue retirada: estaba en un estado demasiado
inestable, con crashes/freezes en transiciones de menus y combates y sin una
validacion suficiente para presentarla como release soportada.

---

## Creditos

- [PSXRecomp](https://github.com/mstan/psxrecomp): recompilador y runtime PS1.
- [recomp-ui](https://github.com/mstan/recomp-ui): launcher y componentes de UI.
- [recomp-net](https://github.com/TechnicallyComputers/recomp-net): transporte y
  soporte de netplay.
- **NovaPowers**: integracion de Final Bout, configuracion, mods y herramientas.
