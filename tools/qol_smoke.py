#!/usr/bin/env python3
"""Recoge evidencia TCP local de UN juego ya abierto; nunca inicia un proceso.

Solo consultas acotadas, sin escrituras de RAM/config, screenshot remoto ni
volcados de overlays. Un OK significa consultas correctas, no smoke visual pasado.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import time

from qol_disc_audit import save_report

COMMANDS = ("ping", "netplay_status", "geom_correction", "gpu_state",
            "overlay_loader_status", "mod_counters")
LIMIT = 1024 * 1024
CHECKPOINTS = ["launcher-opciones-cancelar-reabrir", "boot-menu-seleccion",
               "combate-1-sombras", "pausa-especiales-vuelo", "combate-2-retrato",
               "combate-3-transicion", "rematch", "cierre-normal"]


def query(port: int, command: str, request_id: int, timeout: float = 3.0) -> dict:
    if command not in COMMANDS:
        raise ValueError("Comando fuera de la lista de solo consulta")
    deadline = time.monotonic() + timeout
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as connection:
        request = {"id": request_id, "cmd": command}
        connection.sendall(json.dumps(request).encode("ascii") + b"\n")
        buffer = bytearray()
        while b"\n" not in buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Respuesta TCP fuera del plazo")
            connection.settimeout(remaining)
            chunk = connection.recv(min(65536, LIMIT + 1 - len(buffer)))
            if not chunk:
                raise ValueError("Respuesta TCP incompleta")
            buffer.extend(chunk)
            if len(buffer) > LIMIT:
                raise ValueError("Respuesta TCP supera 1 MiB")
        response = json.loads(buffer.split(b"\n", 1)[0])
        # El hilo I/O responde ping con id=0 sin pasar por la cola del guest.
        # Es la única excepción documentada al eco del identificador.
        fast_ping = (isinstance(response, dict) and command == "ping" and
                     response.get("id") == 0 and response.get("pong") is True and
                     response.get("io_thread") is True)
        if not isinstance(response, dict) or (response.get("id") != request_id and not fast_ping):
            raise ValueError("Respuesta TCP sin id coincidente")
        if response.get("ok") is not True:
            raise ValueError(f"Consulta rechazada: {response}")
        return response


def collect(port: int, label: str, interval: float) -> dict:
    samples = []
    errors = []
    for sample in range(2):
        if sample:
            time.sleep(interval)
        responses = {}
        for command in COMMANDS:
            try:
                responses[command] = query(port, command, sample * len(COMMANDS) + len(responses) + 1)
            except (OSError, ValueError) as error:
                errors.append({"sample": sample, "command": command, "error": str(error)})
        samples.append({"utc": datetime.now(timezone.utc).isoformat(), "responses": responses})
    return {"schema": 1, "port": port, "label": label, "samples": samples,
            "errors": errors, "queries_ok": not errors,
            "visual_result": "NOT_VERIFIED", "gameplay_result": "NOT_VERIFIED",
            "netplay_determinism": "NOT_VERIFIED",
            "note": "Muestras secuenciales; no son un frame atómico ni comparación con Beetle"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="Mostrar checkpoints, sin conectar")
    parser.add_argument("--port", type=int, default=4370)
    parser.add_argument("--label", default="manual")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.plan:
        print(json.dumps({"checkpoints": CHECKPOINTS, "status": "ALL_NOT_VERIFIED",
                          "instructions": "Una sesión cada vez; captura PNG manual y anota personaje/escenario/cámara",
                          "shadow_baseline": {"renderer": "software", "aspect": "4:3",
                                              "scale": 1, "filter": "nearest", "PGXP": False,
                                              "oracle": "Beetle en otra sesión, mismo caso visual"},
                          "launcher_cases": ["abrir GUI forzado", "cancelar sin Play", "reabrir",
                                             "ver opciones", "Play -> boot", "cierre normal"],
                          "netplay_two_computers": {
                              "common": "Mismo disco/build/mods off/delay/session; UDP directo, no ICE",
                              "host": "active=1, host=1, players=2",
                              "guest": "active=1, host=0, players=2",
                              "during_fight": "tick y resolved_through avanzan en ambos; desync=0",
                              "manual_cases": ["handshake", "input local/remoto", "tres combates",
                                               "pausa", "rematch", "desconexión", "cierre"],
                              "limit": "desync=0 en muestras breves no demuestra determinismo universal"}},
                         indent=2, ensure_ascii=True))
        return 0
    if not 1 <= args.port <= 65535 or not 0 <= args.interval <= 30:
        parser.error("Puerto o intervalo fuera de rango")
    if args.output and (args.output.exists() or not args.output.parent.is_dir()):
        parser.error("Salida debe ser un archivo nuevo en carpeta existente")
    report = collect(args.port, args.label, args.interval)
    try:
        if args.output:
            save_report(args.output, report)
    except (OSError, ValueError) as error:
        parser.exit(2, f"No se pudo guardar: {error}\n")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report["queries_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
