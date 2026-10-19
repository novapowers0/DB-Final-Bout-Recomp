# Preloaded mods

## Final Bout: activar el combate renovado

En el lanzador, abre **Mods** y activa **Combate renovado**. No hace falta
configurar entradas, velocidad, ki o encadenado por separado: el perfil estándar
los integra. Desactivarlo conserva el juego original en el siguiente arranque.

El perfil es experimental: incluye una transición nueva de recuperación del
brazo para el registro 0 verificado y mejoras de movilidad, defensa e IA; no
sustituye todas las animaciones ni implica balance exhaustivo. Su alcance se documenta en
`COMBATE_REDISENO.md`. Las opciones antiguas de laboratorio se conservan para
desarrollo en `mods/development/`, fuera del catálogo del jugador.

Ship reviewed, default-disabled packages here:

```text
packages/<package-id>/<version>/
  manifest.toml
  ...
```

Build wiring copies `mods/preloaded` next to the game executable as `mods/`.
Install player `.psxmod` archives through the launcher Mods manager instead of
committing them here. See `psxrecomp/docs/MOD_PACKAGES.md`.
