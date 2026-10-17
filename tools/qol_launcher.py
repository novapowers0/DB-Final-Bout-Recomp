#!/usr/bin/env python3
"""Prepara comandos reproducibles para el launcher existente; no ejecuta el juego.

Comprueba disco USA exacto y configuración desplegada; no cambia TOML, saves,
entorno, runtime ni build. Devuelve JSON y un comando PowerShell autocontenido.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import tomllib

from qol_disc_audit import inspect_disc, save_report

ROOT = Path(__file__).resolve().parents[1]


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def peer_address(value: str) -> str:
    host, separator, port = value.rpartition(":")
    if not separator or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("Peer debe ser IPv4:puerto (1..65535)")
    address = ipaddress.IPv4Address(host)
    if address.is_unspecified or address.is_multicast or address.is_loopback:
        raise ValueError("Usa la IPv4 del OTRO equipo; localhost no es un smoke de dos equipos")
    return f"{address}:{int(port)}"


def make_plan(root: Path, disc: Path, mode: str, peer: str | None = None,
              port: int = 7777, session: int = 1, delay: int = 2,
              renderer: str | None = None) -> dict:
    root = root.resolve()
    config_path = root / "game.toml"
    config = tomllib.loads(config_path.read_text(encoding="utf-8-sig"))
    deployed = root / "build-release" / "game.toml"
    if deployed.read_bytes() != config_path.read_bytes():
        raise ValueError("game.toml fuente y desplegado difieren; debe integrarlo el dueño del build")
    exe_path = root / "build-release" / "DBFinalBout_Recompiled.exe"
    if not exe_path.is_file():
        raise ValueError(f"Falta el ejecutable: {exe_path}")
    if config["game"]["id"] != "SLUS-00493":
        raise ValueError("Este preparador está limitado al perfil USA SLUS-00493")
    identity, _, _ = inspect_disc(disc)
    prepare = config["prepare_disc"]
    reference = root / config["game"]["exe"]
    reference_sha = hashlib.sha256(reference.read_bytes()).hexdigest()
    if (identity["serial"] != config["game"]["id"] or
            identity["boot"]["sha256"] != reference_sha or
            identity["data_file_size"] not in prepare["known_sizes"] or
            identity["data_file_hashes"]["md5"] not in prepare["known_md5"] or
            identity["data_file_hashes"]["sha1"] not in prepare["known_sha1"]):
        raise ValueError("Disco/revisión no compatible con el perfil USA actual; no se prepara arranque PAL")
    if mode not in ("launcher", "offline", "host", "guest"):
        raise ValueError("Modo desconocido")
    if not 1 <= port <= 65535 or not 1 <= session <= 0xFFFFFFFF or not 0 <= delay <= 12:
        raise ValueError("Puerto/sesión/delay fuera de rango")
    if renderer not in (None, "software", "opengl", "vulkan"):
        raise ValueError("Renderer desconocido")
    if mode in ("host", "guest") and not peer:
        raise ValueError("Host y guest requieren --peer con la IPv4 del otro equipo")
    if mode not in ("host", "guest") and peer:
        raise ValueError("--peer solo se admite para host/guest")
    argv = [str(exe_path), "--game", str(config_path), "--disc", str(disc.resolve()),
            "--launcher" if mode == "launcher" else "--no-launcher"]
    if renderer:
        argv += ["--renderer", renderer]
    # Aislar memory cards del smoke. settings.toml sigue junto al ejecutable.
    # La herramienta NO crea estas
    # carpetas: el runtime lo hará únicamente si el usuario ejecuta el comando.
    cards = root / "build-release" / "qol-smoke-saves" / mode
    argv += ["--memcard-dir", str(cards), "--debug-port", "4370"]
    environment = {"PSX_NETPLAY": "0", "PSX_NET_TRANSPORT": "lan",
                   "PSX_NET_MODE": "delay", "PSX_NET_SLOTS": "2",
                   "PSX_NET_HOST_SPECTATES": "0", "PSX_NET_GUEST_MEMCARD": "0",
                   "PSX_NET_FORCE_TURN": "0", "PSX_NO_LAUNCHER": None,
                   "PSX_HEADLESS": "0", "PSX_HIDDEN_WINDOW": "0",
                   "PSX_FAIL_FAST_UNKNOWN_DISPATCH": "1"}
    if mode in ("host", "guest"):
        argv += ["--netplay", "--net-slot", "0" if mode == "host" else "1",
                 "--net-input-player", "0", "--net-bind", f"0.0.0.0:{port}",
                 "--net-peer", peer_address(peer), "--net-delay", str(delay),
                 "--net-session-id", str(session)]
    # Un proceso PowerShell hijo contiene los cambios de entorno y cwd. El
    # comando rechaza un juego/oráculo vivo, sin matar procesos del usuario.
    guard = ("if (Get-Process -Name DBFinalBout_Recompiled,DBFinalBout_Recompiled_pgxp,"
             "psx-runtime,psx-runtime-pgxp,psx-beetle -ErrorAction SilentlyContinue) "
             "{ throw 'Cierra el juego/oraculo antes de este smoke' }")
    setup = "; ".join(f"$env:{key}=" + ("$null" if value is None else ps_quote(value))
                      for key, value in environment.items())
    command = (guard + "; " + setup + "; Set-Location -LiteralPath " + ps_quote(str(root)) +
               "; & " + " ".join(ps_quote(arg) for arg in argv) + "; exit $LASTEXITCODE")
    # -Command recibe un único string entre comillas; escapar para PowerShell
    # externo con comillas simples evita expansión de $env y $LASTEXITCODE.
    powershell = "powershell.exe -NoProfile -Command " + ps_quote(command)
    settings_path = exe_path.parent / "settings.toml"
    settings_bytes = settings_path.read_bytes() if settings_path.exists() else b""
    settings = tomllib.loads(settings_bytes.decode("utf-8-sig"))
    return {"schema": 1, "executed": False, "mode": mode,
            "disc": identity, "argv": argv, "cwd": str(root),
            "environment": environment, "powershell": powershell,
            "memcard_dir": str(cards),
            "game_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            "exe_sha256": hashlib.sha256(exe_path.read_bytes()).hexdigest(),
            "settings_sha256": hashlib.sha256(settings_bytes).hexdigest() if settings_bytes else None,
            "saved_video_options": settings.get("video", {}),
            "requested_renderer": renderer,
            "verified": "Disco/config y preparación de argumentos solamente",
            "not_verified": ["launcher UI", "boot", "combate", "determinismo",
                             "WAN/ICE", "sombras", "multi-región"],
            "notes": ["Un equipo por peer; mismo disco, build, delay y session en ambos",
                      "Mods de gameplay desactivados para la línea base",
                      "settings.toml permanece compartido junto al exe; el GUI puede persistir cambios",
                      "El renderer y otras opciones guardadas prevalecen sobre game.toml salvo override CLI",
                      "Launcher: no pulsar Generate & rebuild durante este smoke; puede instalar toolchains",
                      "El guard de procesos no sustituye coordinación con otras sesiones"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--disc", type=Path, required=True)
    parser.add_argument("--mode", choices=("launcher", "offline", "host", "guest"), default="launcher")
    parser.add_argument("--peer")
    parser.add_argument("--port", type=int, default=7777)
    parser.add_argument("--session", type=int, default=1)
    parser.add_argument("--delay", type=int, default=2)
    parser.add_argument("--renderer", choices=("software", "opengl", "vulkan"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        plan = make_plan(args.root, args.disc, args.mode, args.peer, args.port,
                         args.session, args.delay, args.renderer)
        if args.output:
            save_report(args.output, plan)
        print(json.dumps(plan, indent=2, ensure_ascii=True))
        return 0
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"Preparación rechazada: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
