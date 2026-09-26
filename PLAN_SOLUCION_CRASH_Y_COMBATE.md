# Final Bout — Solución del crash de transición y hoja de ruta de combate

> Estado: actualizado 2026-09-26. El fix RI está aplicado en `psxrecomp` y la
> build Release recompila correctamente con los frameworks actualizados. La
> transición Little Goku vs Piccolo y la comparación con Beetle aún requieren
> validación; hasta entonces el resultado funcional permanece pendiente.

---

## 0. Resumen ejecutivo

1. **El fallo investigado no era de Vulkan ni del mod Responsive.** Era una
   instrucción inválida encontrada mientras el kernel recorría handlers durante
   la reconstrucción de la tabla del juego.
2. **`0x2934` no es un hueco de cobertura estática**: en el mismo run del crash se
   interpretó **40.740 veces**, la última justo antes del fallo
   (`dirty_block` seq 2595200, frame 5750). El fallo es **dependiente de estado**.
3. La hipótesis inicial de que la instrumentación alteraba el timing (**H1**)
   quedó **refutada**: el lanzador nativo sin capturador también reprodujo el
   fallo (ver §3.1).
4. Los lanzadores **nativo**, **seguro** (`PSX_FAIL_FAST_UNKNOWN_DISPATCH=0`) y
   **observación ligera** siguen disponibles. La causa se identificó como una
   RI en una ranura de handler que se estaba reconstruyendo; el fix está aplicado
   y compilado, a la espera de validación manual.

---

## 1. Qué es `0x2934` (desensamblado verificado)

La ventana `0x291C..0x295C` está en RAM del kernel (física, `< 0x10000`). Bytes
reales tomados del freeze dump (`ram_peeks.ra`, `addr=0x291C`, 64 bytes):

```
0x2924  lw   s1, 8(s6)     ; s1 = node->handler      (0x8ED10008)
0x2928  lw   s0, 4(s6)     ; s0 = node->next_handler (0x8ED00004)
0x292C  beq  s1, 0, +9                             ; (0x12200009)
0x2930  nop
0x2934  jalr s1            ; <-- address del crash    (0x0220F809)
0x2938  nop
0x293C  beq  v0, 0, +5     ; ra = 0x293C             (0x10400005)
0x2940  nop
0x2944  beq  s0, 0, +3                              ; (0x12000003)
0x2948  or   v1, v0, zero                          ; (0x00402025)
0x294C  jalr s0                                    ; (0x0200F809)
0x2950  nop
0x2954  lw   s6, 0(s6)     ; s6 = s6->next           (0x8ED60000)
0x291C  beq  s6, ra, +17   ; loop hasta el centinela (0x12C00011)
```

Es el **recorredor de la cadena de handlers de interrupción del kernel PSX**
(equivalente a `SysEnqIntRP` / el dispatcher de `InterruptCallback`):

- recorre nodos enlazados desde `s6`;
- llama al handler del nodo (`s1`) vía `jalr`;
- si el handler devuelve 0, salta al siguiente nodo;
- si devuelve distinto de 0, llama además al "next handler" (`s0`).

En el crash: `gpr[17] (s1) = 0x00001F6C` (handler instalado por el juego),
`gpr[31] (ra) = 0x0000293C` (retorno del `jalr`), `sp = 0x8548`. Todo coherente.

**Conclusión:** `0x2934` es el *call site* del despachador del kernel, no una
función del juego. No debe sembrarse como función; no se toca.

---

## 2. Por qué el dispatcher lo rechaza (compuerta exacta)

La primera hipótesis fue que `psx_dispatch` rechazaba la dirección por la
compuerta de página limpia de `dirty_ram_interp.c`. El diagnóstico posterior
descartó esa ruta: `dirty=1`, y la ejecución falló dentro del intérprete al
encontrar una instrucción inválida a mitad de bloque.

```c
if (!dirty_ram_is_dirty(phys) && !clean_game_text_miss) {
    if (phys < 2MB && phys_is_overlay_region(phys) &&
        dirty_ram_word_looks_decodable(fetch_word(phys))) {
        dirty_ram_mark_executable_range(phys, 4u);
    } else {
        return 0;            /* -> psx_unknown_dispatch -> fail-fast */
    }
}
```

Contexto registrado para el dispatch fallido en `0x2934`:

| Condición | Valor | Por qué |
|---|---|---|
| `dirty_ram_is_dirty(0x2934)` | `1` | La página estaba dirty; la compuerta de página limpia no lo explica |
| `overlay_region` | `0` | La dirección cae en la RAM baja del kernel |
| `in_text` | `0` | Fuera del texto del EXE |
| `kbless` | `0` | El kernel-bless no declaró ese cuerpo como dispatchable |
| `interp_unsupported` | `SPECIAL funct` | La instrucción inválida estaba en `0x2030` (`0x000900FF`) |

El header `dirty_ram_interp.h:79-83` confirma que la **ventana del kernel
(`[0, 0x10000)`) se mantiene deliberadamente per-bloque** y **fuera** de la
heurística "admitir palabra decodificable" que sí aplica a la región de overlays.

El dump adicional mostró que `block_entry=0x1F6C`: el walker de IRQ saltó a una
ranura de handler que el overlay estaba limpiando y reconstruyendo. El defecto
relevante fue abortar ante la RI mid-block en vez de levantar ExcCode 10; ver §3.2.

---

## 3. Hipótesis histórica: H1 (refutada; la instrumentación altera el timing)

**Observación inicial:** se sospechó que el cliente de captura añadía carga al
hilo de diagnóstico durante la transición a combate.

**H1:** el cliente de captura anterior pedía, cada 5 s, comandos que serializan
payloads grandes en el hilo de diagnóstico del emulador (`history`,
`gpu_state`, `overlay`), y al final volcaba rings de **100.000 entradas**
(`wtrace_dump`, `mmio`, `fntrace_dump`). En la transición a combate (carga de
`STEP40` por CD, `overlay_cache` escribiendo JSON), esa carga extra desplaza el
timing lo suficiente para que una re-entrada del manejador de excepciones llegue
a `0x2934` **antes** de que la página esté marcada dirty, o con el bit ya
limpiado. Resultado: fail-fast.

**Evidencia que motivó comprobar H1 (no suficiente para confirmarla):**
- `exception_entries = 28911` en frame 5750 (actividad de excepción anómala);
- `restore_trace` muestra un patrón `restore_escape`→`restore_resume`→`rfe_resume`
  repitiéndose cada frame en `0x8001BFD0` (BIOS `store_pc=0xBFC205FC`);
- `i_stat = 0x04` (IRQ de CD-ROM pendiente) e `i_mask = 0x0D`;
- `0x2934` se interpretó 40.740 veces: el fallo es puntual, no estructural;
- el usuario reporta estabilidad sin diagnósticos.

**Prueba de refutación:** ejecutar `INICIAR_FINAL_BOUT_NATIVO.bat` sin el
capturador. El mismo fallo también ocurrió en esa ruta; por tanto H1 se descarta.

### 3.1 Resultado de las pruebas del usuario (2026-09-12) — H1 REFUTADA

- `INICIAR_FINAL_BOUT_NATIVO.bat` **también crasheó**: el fallo no depende del
  capturador ni del cliente TCP. **H1 descartada.**
- `INICIAR_FINAL_BOUT_SEGURO.bat` (`PSX_FAIL_FAST_UNKNOWN_DISPATCH=0`) **no
  crasheó** y permitió jugar; el dispatch no resuelto se absorbe.
- Patrón reportado: elegir **Little Goku** y toparse con **Piccolo** coincidía
  con los crashes; la vez que no crasheó fue contra **Goku adulto**. Puede ser
  casualidad, pero encaja con una ruta por emparejamiento de personajes y sirve
  como palanca de reproducción.

El `psx_crash.txt` del crash NATIVO (build con diagnóstico ampliado) trae:

```
refusal context: dirty=1 overlay_region=0 in_text=0 kbless=0 in_exception=1 interp_unsupported=SPECIAL funct
```

Lectura:

- **`dirty=1`**: la página SÍ está sucia. **No fue la compuerta de página limpia**
  (`dirty_ram_interp.c:2845`). Esa vía queda descartada.
- `overlay_region=0`, `in_text=0`, `kbless=0`, `in_exception=1`.
- **`interp_unsupported=SPECIAL funct`**, pero el switch SPECIAL del intérprete
  **cubre todo el set válido del R3000A** (0x00–0x2B). "SPECIAL funct no
  soportado" solo puede significar **datos ejecutados como código**
  (`0x000900FF`, funct 0x3F, no es instrucción real) o un `psx_unknown_dispatch`
  invocado **sin pasar por el intérprete**.
- El `dirty_block` del crash termina en `0x2924 → 0x2934 → 0x1F6C` y **no hay
  entrada nueva tras `0x1F6C`**: el fallo **no entró por
  `dirty_ram_dispatch_inner`** (que habría registrado la entrada). Hay una vía
  que llama a `psx_unknown_dispatch` sin pasar por el intérprete: el preámbulo
  de overlays nativos
  (`psxrecomp/runtime/include/overlay_dispatch_preamble.c.inc:76`) reenvía
  `psx_unknown_dispatch` al runtime, y `OpenBIOS_full.c` también contiene stubs.

**Build de diagnóstico (2ª ampliación, ya reconstruida):** `psx_crash.txt` añade
`interp detail: last_unsupported_pc=0x… insn=0x… block_entry=0x… entry_ra=0x…
midblock=N aborts=N`, que decide entre datos-como-código (con dirección y palabra
exactas) y un bypass con global pegado.

**Resultado del test T2:** el informe ya registró `dirty=1`,
`overlay_region=0`, `in_text=0`, `kbless=0`, `in_exception=1` y
`interp_unsupported=SPECIAL funct`. El dump de intérprete localizó además la
instrucción `0x000900FF` en `0x2030`, dentro del bloque iniciado en `0x1F6C`.
Estos datos establecieron la causa descrita en §3.2; ya no está pendiente decidir
entre las ramas de compuerta o añadir cobertura.

### 3.2 Causa raíz definitiva (reproducida contra Piccolo, frame 2356)

El diagnóstico ampliado la fija sin ambigüedad:

```
interp detail: last_unsupported_pc=0x00002030 insn=0x000900FF
               block_entry=0x00001F6C entry_ra=0x0000293C midblock=1 aborts=1
```

Secuencia:

1. El recorredor de IRQ del kernel (`0x291C..0x2954`) hace `jalr s1` y salta al
   handler apuntado por la cadena, `0x1F6C` (`block_entry`).
2. La ranura `0x1F6C` está **a ceros**: en el mismo frame 2356, código de overlay
   en `0x80042CBC` (`ra=0x80042328`, overlay de VS/transición `0x8003F000`)
   escribe `0x00000000` sobre `[0x1F00, 0x1FE0)` y luego pointers en `0x1FE4+`.
   Es una tabla de handlers/eventos que el juego **limpia y reconstruye**.
3. El intérprete ejecuta la ranura a ceros como código (49 NOPs) y en `0x2030`
   encuentra `0x000900FF` (funct `0x3F`), que **no es una instrucción R3000A**.
4. `abort_unsupported(pc, insn, "SPECIAL funct")` marca `g_unsupported_seen`; el
   intérprete, por ser mid-block (`insns_executed > 0`), pone `cpu->pc = 0` y
   devuelve 1. El dispatch acaba en `psx_unknown_dispatch(0x2934)` → fail-fast.

**En hardware real**, el paso 3 levanta la **Reserved Instruction exception**
(ExcCode 10) y vectoriza a `0x80000080`, donde corre el manejador del juego. El
intérprete, en cambio, **aborta y mata el proceso**. Ese es el defecto: la
ejecución de datos como código es el síntoma, pero el fallo fatal lo produce el
`abort_unsupported` en lugar de la excepción fiel.

**Fix aplicado (class-level, fiel):** en
`dirty_ram_interp.c`, para el caso **mid-block** de opcode no soportado, levantar
la excepción RI con el mecanismo que ya existe (`interp_exception`, usado para
Load/StoreAddressError en las líneas 1638/1649/2211/2227/2250/2273/2296):

```c
/* antes (línea ~3115): */
cpu->pc = 0;
/* después: */
interp_exception(cpu, 10, 0, g_unsupported_pc);   /* Reserved Instruction */
```

El caso de **primera instrucción** (`insns_executed == 0`) se deja devolviendo 0,
para no romper la resolución de trampolines de `psx_unknown_dispatch`.

**Estado:** aplicado en commit `d76c5c39`, integrado en merge `7d70880d` y
compilado de nuevo el 2026-09-26 con el framework actualizado. Ramas de
seguridad locales: `backup/pre-update-20260926` en `psxrecomp` y el padre.
La validación funcional y la comparación con el oráculo Beetle siguen pendientes.

**Prueba pendiente con el fix actualizado:** `INICIAR_FINAL_BOUT_NATIVO.bat`
(fail-fast activo), Little Goku vs Piccolo. Registrar si la transición sigue, si
aparece un `psx_crash.txt` nuevo o si el juego se cuelga. No asumir de antemano
que el manejador atiende la RI correctamente. Si se cuelga, usar temporalmente
`INICIAR_FINAL_BOUT_SEGURO.bat` y conservar el informe para análisis.

**Riesgos pendientes de validar:**
- El fallo ocurre con `in_exception = 1`: levantar otra excepción anida en el
  manejador. En hardware eso también pasa (RI dentro del handler re-vectoriza);
  hay que comprobar que el juego lo atiende y no entra en bucle.
- Es un cambio de foundation en `psxrecomp` (afecta a todos los títulos): debe
  validarse contra el oráculo Beetle antes de darlo por definitivo.
- Alternativa de fondo: el disparo real es que se entrega/interrumpe **durante**
  la reconstrucción de la tabla de handlers. El fix correcto de largo plazo es el
  timing fiel de entrega de IRQ (eje de ciclos), no la excepción.

**Fallback:** `INICIAR_FINAL_BOUT_SEGURO.bat`
(`PSX_FAIL_FAST_UNKNOWN_DISPATCH=0`) sigue disponible si el modo nativo se cuelga.
Ese modo permite continuar sesiones, pero absorbe el dispatch sin ejecutar el
handler y no demuestra que el fix RI funcione.

---

## 4. Resultado del diagnóstico y estado de validación

El diagnóstico T2 ya se obtuvo: `dirty=1`, `kbless=0`,
`interp_unsupported=SPECIAL funct`, con `last_unsupported_pc=0x2030`,
`insn=0x000900FF` y `block_entry=0x1F6C`. Por tanto, no era un miss por página
limpia ni un hueco de seeds. Era una instrucción inválida ejecutada desde una
ranura de handler que el overlay estaba reconstruyendo. El fix de intérprete
fiel al Reserved Instruction se aplicó y compiló; su comportamiento in-game
sigue pendiente de prueba. Véase §3.2 y `ANALISIS_CRASHES.md` §9.3-9.4.

---

## 5. Entregables de esta sesión

### Lanzadores (raíz de `DBFinalBoutRecomp\`)

Los lanzadores NATIVO y SEGURO son scripts portables del proyecto. Los
lanzadores de captura/OpenGL dependen del capturador instalado en el workspace
local y se mantienen como utilidades de desarrollo, no como descargas del repo.

| Archivo | Qué hace | Cuándo usarlo |
|---|---|---|
| `INICIAR_FINAL_BOUT_NATIVO.bat` | Abre el juego sin capturador ni TCP; fail-fast activo. | Validación pendiente del fix RI |
| `INICIAR_FINAL_BOUT_SEGURO.bat` | Igual, con `PSX_FAIL_FAST_UNKNOWN_DISPATCH=0`. | Fallback si un miss aborte el proceso |

Los lanzadores locales de captura/OpenGL (`INICIAR_FINAL_BOUT_OBSERVAR_LIGERO`,
`_CON_CAPTURA` y `_OPENGL_CON_CAPTURA`) necesitan el capturador externo del
workspace y no se incluyen en el repositorio.

### Capturador (`DB Final Bout\tools\psxrecomp\tools\capture_final_bout_session.py`)

- Nuevo flag `--light`: omite `gpu_state`, `overlay`, `history` y los volcados de
  ring; solo consulta `ping`, `wtrace_stats`, `fn_stats`, `dirty_ram_stats`.
- Nuevo flag `--rings` (opt-in): vuelca `wtrace_dump`/`mmio`/`fntrace_dump`.
  **Por defecto ya no se vuelcan** (antes se hacía siempre).
- El JSON registra `light` y `rings` para trazabilidad.
- Validado con `python -m py_compile`.

### Runtime (diagnóstico, fix RI y build actualizada)

`psxrecomp/runtime/src/traps.c` — diagnóstico. En el
`psx_unknown_dispatch` fail-fast se añade una segunda línea con el estado de la compuerta:
`dirty`, `overlay_region`, `in_text`, `kbless`, `in_exception`,
`interp_unsupported`.

`psxrecomp/runtime/src/dirty_ram_interp.c` — fix RI: cuando una instrucción
SPECIAL no soportada aparece mid-block, el intérprete levanta Reserved
Instruction (ExcCode 10) en lugar de poner `cpu->pc = 0`. La ruta de primera
instrucción permanece sin cambios para resolver trampolines.

- `DBFinalBout_Recompiled.exe` se reconstruyó con Ninja/clang el 2026-09-11 y
  volvió a enlazarse el 2026-09-26 tras actualizar los submódulos.
- Copias de seguridad previas: `build-release\DBFinalBout_Recompiled.exe.bak_pre_diag`
  y `%TEMP%\opencode\traps.c.bak_pre_diag`.
- Las ramas `backup/pre-update-20260926` de `psxrecomp` y del padre conservan el
  estado previo a la actualización de frameworks.

### Documentación

- Este documento.
- `ANALISIS_CRASHES.md` §9 ampliado con el desensamblado y la compuerta.
- `summary.md` actualizado.

---

## 6. Hoja de ruta de combate (Responsive Edition)

Estado verificado y reutilizable:

- **STEP40 (combate) ya se compila nativo** (19/08). `game.toml` declara las
  fronteras de función del overlay y el shard cubre `0x80069228..0x8006E5FC`.
- **Overlays capturados**: cientos de `SLUS-00493_*.json` en `build-release\`,
  con base y CRC por sesión (p. ej. `0x80060000`, `0x80068000`, `0x8006A000`).
- **API de mods** (`mod_plugins.h`): callbacks de activación, VBlank y
  *function-entry*; lectura/escritura de byte/half/word; `psx_mod_write_code_word`
  para parchear código sin romper save states; opciones por manifest.
- **Tiers** definidos en `docs/FINAL_BOUT_RESPONSIVE_ARCHITECTURE.md`
  (0 Original, 1 instrumentación, 2 correcciones selectivas, 3 reglas, 4 modo
  alternativo). El trabajo válido siguiente es **Tier 1**.

Siguiente trabajo (en orden, sin saltarse pasos):

1. **Validar el build actualizado en una ejecución de combate estable.** Los
   diagnósticos T1/T2 ya identificaron la causa y el fix se compiló; falta la
   prueba manual descrita en §3.2. Sin ella no hay *ground truth* nuevo de input
   lag ni de tiempos de recuperación.
2. **Plugin de observación (Tier 1)** — solo lectura, sin escrituras de gameplay:
   - registrar `pad` muestreado y transiciones de flanco;
   - hooks `function_entry` en las fronteras verificadas de `STEP40`;
   - exponer los datos por la infraestructura de rings/TCP existente
     (CLAUDE.md §3: nada de `fprintf` ni logs ad-hoc);
   - campos mínimos: frame, PC de entrada, pad, puntero candidato a estructura
     de luchador, estado/animación/timer, posición/vida/ki, flags de ataque e
     impacto, inicio de ataque, hit, hit-stop, recuperación.
3. **Mapa de estructura de luchador** para un personaje y un jugador, con
   dirección verificada.
4. **Tier 2**: buffer de input acotado, consumo más temprano del input ya
   muestreado (si el trace lo justifica), ajuste de timers de recuperación,
   suavizado de cámara. Cada feature independiente y desactivable.
5. Solo después, Tier 3/4.

Principios que no se rompen:

- `Original` no escribe gameplay.
- Cada escritura de `Responsive` tiene dirección, dueño, ancho y restauración
  documentados.
- Ningún offset adivinado; sin evidencia reproducible no hay hook.
- El plugin vive solo en el target de Final Bout, no en el runtime genérico.

---

## 7. Referencias

- `psxrecomp/runtime/src/dirty_ram_interp.c` (compuerta `:2845`, dispatcher `:2738`)
- `psxrecomp/runtime/src/traps.c` (`psx_unknown_dispatch`, fail-fast `:1408`)
- `psxrecomp/runtime/src/memory.c` (`dirty_ram_is_dirty`, `psx_kernel_bless_dispatchable`)
- `psxrecomp/runtime/include/dirty_ram_interp.h` (ventanas y semántica de regiones)
- `psxrecomp/runtime/include/mod_plugins.h` (API de plugins nativos)
- `build-release/psx_freeze_dump_psx-runtime_1789144131_0.json` (run del crash, frame 5750)
- `ANALISIS_CRASHES.md`, `summary.md`
