#!/usr/bin/env python3
"""Auditoría de solo lectura: identidad, boot EXE y overlays; nunca extrae ROMs.

Python 3.11+, biblioteca estándar. No determina identidad de código MIPS a
partir de la semejanza del EXE: el payload también contiene datos.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import struct

SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
MAX_FILE = 8 * 1024 * 1024


def save_report(path: Path, report: dict) -> None:
    """Creación exclusiva: nunca reemplazar evidencia previa ni crear carpetas."""
    if not path.parent.is_dir():
        raise ValueError(f"No existe la carpeta de salida: {path.parent}")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=True)
        stream.write("\n")


def data_track(path: Path) -> tuple[Path, int, str | None, int | None]:
    """BIN/ISO o TRACK 01 de CUE; INDEX 01 se mide dentro de su FILE."""
    path = path.resolve(strict=True)
    if path.suffix.lower() in (".bin", ".iso"):
        return path, 0, None, None
    if path.suffix.lower() != ".cue":
        raise ValueError("Se admite .cue, .bin o .iso; CHD no se modifica ni convierte")
    current_file = None
    track = None
    tracks = 0
    result = None
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        file_match = re.fullmatch(r'FILE\s+"([^"]+)"\s+BINARY', line, re.I)
        if line.upper().startswith("FILE "):
            current_file = None
        if file_match:
            current_file = (path.parent / file_match[1]).resolve()
        match = re.fullmatch(r"TRACK\s+(\d+)\s+(\S+)", line, re.I)
        if match:
            track = int(match[1])
            tracks += 1
            if track == 1:
                if current_file is None:
                    raise ValueError("TRACK 01 sin FILE BINARY entre comillas")
                result = [current_file, None, match[2].upper()]
        match = re.fullmatch(r"INDEX\s+01\s+(\d+):(\d+):(\d+)", line, re.I)
        if match and track == 1 and result:
            mm, ss, ff = map(int, match.groups())
            if ss >= 60 or ff >= 75:
                raise ValueError("INDEX 01 inválido")
            result[1] = (mm * 60 + ss) * 75 + ff
    if not result or result[1] is None:
        raise ValueError("Falta TRACK 01 / INDEX 01")
    if result[2] not in ("MODE2/2352", "MODE1/2352", "MODE1/2048"):
        raise ValueError(f"Formato de pista no admitido: {result[2]}")
    if not result[0].is_file():
        raise ValueError(f"No existe la pista: {result[0]}")
    return result[0], result[1], result[2], tracks


class IsoReader:
    """Lectura acotada ISO9660, sectores cooked y crudos Mode 1/2 Form 1."""

    def __init__(self, path: Path, start: int = 0, mode: str | None = None):
        self.path, self.start = path, start
        self.size = path.stat().st_size
        self.stride = 2048 if mode == "MODE1/2048" else 2352
        with path.open("rb") as stream:
            stream.seek(start * self.stride)
            first = stream.read(24)
        if first[:12] == SYNC:
            if first[15] not in (1, 2):
                raise ValueError("Sector crudo sin Mode 1/2")
            self.user_offset = 16 if first[15] == 1 else 24
            expected_mode = "MODE1/2352" if first[15] == 1 else "MODE2/2352"
            if mode and mode != expected_mode:
                raise ValueError("El CUE no coincide con el formato real")
        elif mode in (None, "MODE1/2048"):
            self.stride, self.user_offset = 2048, 0
        else:
            raise ValueError("Sin cabecera de sector crudo")
        pvd = self.read(16, 2048)
        if pvd[:7] != b"\x01CD001\x01":
            raise ValueError("No hay descriptor ISO9660 primario válido en LBA 16")
        self.volume = pvd[40:72].decode("ascii", "replace").strip()
        self.root = (struct.unpack_from("<I", pvd, 158)[0],
                     struct.unpack_from("<I", pvd, 166)[0])

    def read(self, extent: int, size: int) -> bytes:
        if size < 0 or size > MAX_FILE or extent < 0:
            raise ValueError("Archivo ISO fuera del límite de lectura (8 MiB)")
        result = bytearray()
        with self.path.open("rb") as stream:
            for offset in range(0, size, 2048):
                position = (self.start + extent + offset // 2048) * self.stride
                take = min(2048, size - offset)
                if position + self.user_offset + take > self.size:
                    raise ValueError("Extensión ISO fuera de la imagen")
                stream.seek(position)
                sector = stream.read(self.stride)
                if self.user_offset:
                    expected = 1 if self.user_offset == 16 else 2
                    if sector[:12] != SYNC or sector[15] != expected:
                        raise ValueError("Sector de archivo no coincide con el formato")
                    if expected == 2 and sector[18] & 0x20:
                        raise ValueError("Archivo ISO en sector Mode 2 Form 2")
                result.extend(sector[self.user_offset:self.user_offset + take])
        return bytes(result)

    def entries(self, location: tuple[int, int]) -> dict[str, tuple[int, int, bool]]:
        data = self.read(*location)
        entries = {}
        pos = 0
        while pos < len(data):
            length = data[pos]
            if not length:
                pos = (pos // 2048 + 1) * 2048
                continue
            if length < 34 or pos + length > len(data):
                raise ValueError("Registro de directorio ISO truncado")
            record = data[pos:pos + length]
            name_length = record[32]
            if 33 + name_length > length or record[25] & 0x80:
                raise ValueError("Registro ISO inválido o multi-extent no admitido")
            name = record[33:33 + name_length]
            if name not in (b"\x00", b"\x01"):
                key = name.decode("ascii").split(";")[0].upper()
                entries[key] = (struct.unpack_from("<I", record, 2)[0],
                                struct.unpack_from("<I", record, 10)[0],
                                bool(record[25] & 2))
            pos += length
        return entries

    def file(self, name: str) -> bytes:
        entries = self.entries(self.root)
        parts = name.replace("\\", "/").strip("/").upper().split("/")
        for index, part in enumerate(parts):
            extent, size, directory = entries[part.split(";")[0]]
            if index == len(parts) - 1:
                if directory:
                    raise ValueError("Se esperaba archivo ISO")
                return self.read(extent, size)
            if not directory:
                raise ValueError("Se esperaba directorio ISO")
            entries = self.entries((extent, size))
        raise ValueError("Ruta ISO vacía")


def digest(data: bytes) -> dict:
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def inspect_disc(path: Path) -> tuple[dict, bytes, dict[str, bytes]]:
    image, start, mode, tracks = data_track(path)
    iso = IsoReader(image, start, mode)
    cnf = iso.file("SYSTEM.CNF").decode("ascii")
    match = re.search(r"BOOT\s*=\s*cdrom:\\?([^;\s]+)", cnf, re.I)
    if not match:
        raise ValueError("SYSTEM.CNF sin BOOT cdrom")
    boot_path = match[1].replace("\\", "/").lstrip("/")
    exe = iso.file(boot_path)
    if exe[:8] != b"PS-X EXE" or len(exe) < 2048:
        raise ValueError("Boot no es un PS-X EXE")
    pc, load, size = (struct.unpack_from("<I", exe, n)[0] for n in (16, 24, 28))
    if size > len(exe) - 2048:
        raise ValueError("Payload del EXE truncado")
    serial_raw = re.sub(r"[^A-Z0-9]", "", boot_path.split("/")[-1].upper())
    serial = serial_raw[:4] + "-" + serial_raw[4:]
    hashes = {name: hashlib.new(name) for name in ("md5", "sha1", "sha256")}
    with image.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            for h in hashes.values():
                h.update(chunk)
    overlays = {}
    root = iso.entries(iso.root)
    for folder, location in [("", (*iso.root, True))] + [
        (key + "/", value) for key, value in root.items()
        if value[2] and key == "MENU"
    ]:
        for name, (extent, length, directory) in iso.entries(location[:2]).items():
            if not directory and re.fullmatch(r"STEP\d+\.BIN", name):
                overlays[folder + name] = iso.read(extent, length)
    report = {
        "source": str(path.resolve()), "data_file": str(image),
        "data_file_size": image.stat().st_size,
        "data_file_hashes": {name: h.hexdigest() for name, h in hashes.items()},
        "track_count": tracks, "toc_verified": False,
        "index01_frames": start, "sector_stride": iso.stride,
        "volume": iso.volume, "serial": serial,
        "region_hint": "NTSC-U" if serial.startswith("SLUS-") else
                       "PAL" if serial.startswith("SLES-") else "unknown",
        "boot_path": boot_path, "boot": digest(exe),
        "entry_pc": f"0x{pc:08X}", "load_address": f"0x{load:08X}",
        "payload_size": size,
        "payload_sha256": hashlib.sha256(exe[2048:2048 + size]).hexdigest(),
        "overlays": {name: digest(data) for name, data in sorted(overlays.items())},
        "runtime_compatibility": "NOT_VERIFIED",
    }
    return report, exe, overlays


def compare_bytes(a: bytes, b: bytes) -> dict:
    changed = [index for index, (x, y) in enumerate(zip(a, b)) if x != y]
    # Solo offsets y cantidades, nunca palabras/bytes del disco.
    tail_size = abs(len(a) - len(b))
    first = changed[:16]
    if tail_size:
        first += list(range(min(len(a), len(b)), min(max(len(a), len(b)),
                                                    min(len(a), len(b)) + 16 - len(first))))
    return {"identical": a == b, "different_bytes": len(changed) + abs(len(a) - len(b)),
            "first_changed_offsets": first,
            "last_changed_offset": max(len(a), len(b)) - 1 if tail_size else
                                   changed[-1] if changed else None,
            "size_delta": len(b) - len(a)}


def audit(paths: list[Path]) -> dict:
    discs = [inspect_disc(path) for path in paths]
    comparisons = []
    for (a, ax, ao), (b, bx, bo) in itertools.combinations(discs, 2):
        comparisons.append({
            "a": a["serial"], "b": b["serial"],
            "boot": compare_bytes(ax, bx),
            "overlays": {name: compare_bytes(ao[name], bo[name])
                         for name in sorted(ao.keys() & bo.keys())},
            "overlays_only_a": sorted(ao.keys() - bo.keys()),
            "overlays_only_b": sorted(bo.keys() - ao.keys()),
            "code_identity": "NOT_PROVEN: EXE/overlay payloads mix code and data",
        })
    return {"schema": 1, "read_only": True, "discs": [d[0] for d in discs],
            "comparisons": comparisons,
            "multiregion_functional": False,
            "scope": "Identity/comparison only; no game, extraction or build"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("discs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, help="JSON nuevo, sin sobrescribir")
    args = parser.parse_args()
    try:
        report = audit(args.discs)
        if args.output:
            save_report(args.output, report)
        print(json.dumps(report, indent=2, ensure_ascii=True))
        return 0
    except (OSError, ValueError, KeyError, struct.error) as error:
        parser.exit(2, f"Auditoría rechazada: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
