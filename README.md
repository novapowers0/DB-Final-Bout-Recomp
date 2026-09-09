# Dragon Ball GT: Final Bout Recompiled

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
| **Version** | v0.1.0 |

Copyright (c) 2026 **NovaPowers**. Licencia MIT (ver `LICENSE`).

---

## Aviso legal

El juego y sus datos **no se distribuyen**. Para jugar debes aportar los archivos
de tu **copia legal** de *Dragon Ball GT: Final Bout*.

- El proyecto espera la version USA `SLUS-00493`.
- Consulta `baserom.md` para el tamano, serial, volumen y checksums esperados.
- Las imagenes de disco, el BIOS retail y el codigo generado no se incluyen.
- El codigo recompilado se genera localmente a partir de tus propios archivos.

Proyecto no oficial, sin animo de lucro, de investigacion y preservacion. No esta
afiliado ni avalado por Bandai, Shueisha, Toei Animation ni ningun titular de los
derechos de Dragon Ball.

---

## Para jugar

1. Descarga `dbfb-0.1.0-setup-host-win64.zip` desde
   [Releases](https://github.com/novapowers0/DB-Final-Bout-Recomp/releases/latest).
2. Descomprime el paquete en una carpeta de Windows.
3. Aporta tu copia legal siguiendo la identidad descrita en `baserom.md`.
4. Ejecuta `DBFinalBout_Recompiled.exe` o abre el launcher incluido.
5. Deja el widescreen desactivado para una presentacion 4:3 fiel, o activa
   `psx.enhancement.widescreen` para 16:9/adaptive.

El paquete setup-host puede solicitar los datos del juego durante la primera
configuracion. No descargues BIOS ni imagenes de disco desde este repositorio.

### Configuracion recomendada

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

## Estructura del repositorio

```text
DB-Final-Bout-Recomp/
├── psxrecomp/       # Recompiler y runtime como submodulo
├── recomp-ui/       # Launcher y UI como submodulo
├── mods/             # Configuracion y manifiestos de mods
├── seeds/            # Seeds del ejecutable de Final Bout
├── ghidra_proj/      # Herramientas de analisis e ingenieria inversa
├── tools/            # Scripts de build, diagnostico y validacion
├── generated/        # NO incluido: codigo generado localmente
├── disc/             # NO incluido: tu imagen legal del juego
├── game.toml         # Configuracion del runtime
└── CMakeLists.txt    # Build del proyecto
```

---

## Compilar desde el codigo

Requisitos principales:

- Windows x64.
- Git con submodulos.
- CMake 3.20 o posterior.
- Ninja o un generador CMake equivalente.
- Python 3.
- Toolchain compatible con PSXRecomp.
- Una copia legal del disco indicada en `baserom.md`.

```bash
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

El codigo de `generated/` se deriva de tu disco y nunca debe subirse al
repositorio. Los artefactos de build y las imagenes del juego estan ignorados
por Git.

---

## Documentacion y diagnostico

- `baserom.md`: identidad del disco y checksums.
- `AGENTS.md`: reglas de trabajo y estado tecnico del proyecto.
- `ANALISIS_CRASHES.md`: investigacion de freezes y overlays.
- `SESSION_ANALYSIS.md`: flujo para capturar y analizar una sesion.
- `summary.md`: historial detallado de decisiones y validaciones.
- `tools/verify_offline.py`: comprobacion reproducible sin lanzar el juego.

---

## Historial de versiones

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
