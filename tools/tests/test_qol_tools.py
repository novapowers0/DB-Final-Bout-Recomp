"""Pruebas offline con ISO sintético y servidor TCP local; no ejecutan el juego.

Fixtures conservados en TEMP/opencode (no se borran datos al terminar).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import qol_disc_audit as disc
import qol_launcher as launcher
import qol_smoke as smoke


def record(name: bytes, extent: int, size: int, directory=False) -> bytes:
    out = bytearray(33 + len(name) + (len(name) % 2 == 0))
    out[0] = len(out)
    struct.pack_into("<I", out, 2, extent)
    struct.pack_into(">I", out, 6, extent)
    struct.pack_into("<I", out, 10, size)
    struct.pack_into(">I", out, 14, size)
    out[25], out[28], out[31], out[32] = 2 if directory else 0, 1, 1, len(name)
    out[33:33 + len(name)] = name
    return bytes(out)


def synthetic_iso() -> tuple[bytes, bytes]:
    exe = bytearray(4096)
    exe[:8] = b"PS-X EXE"
    for off, value in ((16, 0x80010000), (24, 0x80010000), (28, 2048)):
        struct.pack_into("<I", exe, off, value)
    exe[2048:] = bytes(range(256)) * 8
    cnf = b"BOOT = cdrom:\\SLUS_004.93;1\r\n"
    image = bytearray(30 * 2048)
    pvd = bytearray(2048)
    pvd[:7] = b"\x01CD001\x01"
    pvd[40:72] = b"QOL_SYNTHETIC".ljust(32, b" ")
    pvd[156:190] = record(b"\x00", 20, 2048, True)
    image[16 * 2048:17 * 2048] = pvd
    root = (record(b"\x00", 20, 2048, True) + record(b"\x01", 20, 2048, True) +
            record(b"SYSTEM.CNF;1", 21, len(cnf)) + record(b"SLUS_004.93;1", 22, len(exe)) +
            record(b"MENU", 24, 2048, True))
    menu = record(b"STEP40.BIN;1", 25, 80)
    for extent, data in ((20, root), (21, cnf), (22, exe), (24, menu), (25, b"X" * 80)):
        image[extent * 2048:extent * 2048 + len(data)] = data
    return bytes(image), bytes(exe)


def raw_image(cooked: bytes, mode: int) -> bytes:
    output = bytearray()
    for offset in range(0, len(cooked), 2048):
        frame = bytearray(2352)
        frame[:12], frame[15] = disc.SYNC, mode
        user = 16 if mode == 1 else 24
        frame[user:user + 2048] = cooked[offset:offset + 2048]
        output.extend(frame)
    return bytes(output)


class DiscTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = Path(os.environ.get("TEMP", tempfile.gettempdir())) / "opencode"
        if not parent.is_dir():
            raise RuntimeError(f"Falta la carpeta temporal autorizada: {parent}")
        cls.folder = Path(tempfile.mkdtemp(prefix="dbfb-qol-tests-", dir=parent))
        cls.cooked, cls.exe = synthetic_iso()
        cls.paths = []
        for name, payload in (("cooked.iso", cls.cooked),
                              ("mode1.bin", raw_image(cls.cooked, 1)),
                              ("mode2.bin", raw_image(cls.cooked, 2))):
            path = cls.folder / name
            path.write_bytes(payload)
            cls.paths.append(path)

    def test_cooked_and_both_raw_formats_extract_identically(self):
        for path in self.paths:
            with self.subTest(path=path):
                report, exe, overlays = disc.inspect_disc(path)
                self.assertEqual(exe, self.exe)
                self.assertEqual(report["serial"], "SLUS-00493")
                self.assertEqual(overlays, {"MENU/STEP40.BIN": b"X" * 80})
                self.assertEqual(report["runtime_compatibility"], "NOT_VERIFIED")

    def test_cue_index01_with_pregap(self):
        image = self.folder / "pregap.bin"
        image.write_bytes(bytes(2352 * 2) + raw_image(self.cooked, 2))
        cue = self.folder / "pregap.cue"
        cue.write_text('FILE "pregap.bin" BINARY\n TRACK 01 MODE2/2352\n INDEX 01 00:00:02\n')
        report, exe, _ = disc.inspect_disc(cue)
        self.assertEqual(exe, self.exe)
        self.assertEqual(report["index01_frames"], 2)

    def test_truncated_iso_extent_rejected(self):
        reader = disc.IsoReader(self.paths[0])
        with self.assertRaisesRegex(ValueError, "fuera de la imagen"):
            reader.read(500, 20)
        with self.assertRaisesRegex(ValueError, "límite"):
            reader.read(0, disc.MAX_FILE + 1)

    def test_compare_counts_size_tail_without_exposing_bytes(self):
        result = disc.compare_bytes(b"abc", b"aXcd")
        self.assertEqual(result["different_bytes"], 2)
        self.assertEqual(result["first_changed_offsets"], [1, 3])
        self.assertEqual(result["last_changed_offset"], 3)
        self.assertNotIn("bytes", result)

    def test_report_is_exclusive(self):
        output = self.folder / "exclusive.json"
        disc.save_report(output, {"old": True})
        with self.assertRaises(FileExistsError):
            disc.save_report(output, {"old": False})
        self.assertEqual(json.loads(output.read_text()), {"old": True})

    def test_launcher_uses_verified_disc_and_rejects_pal(self):
        root = self.folder / "project with spaces"
        root.mkdir()
        (root / "build-release").mkdir()
        (root / "boot.exe").write_bytes(self.exe)
        (root / "build-release" / "DBFinalBout_Recompiled.exe").write_bytes(b"synthetic, never executed")
        image = self.paths[0].read_bytes()
        config = ('[game]\nid="SLUS-00493"\nexe="boot.exe"\n[prepare_disc]\n' +
                  f'known_sizes=[{len(image)}]\n' +
                  f'known_md5=["{hashlib.md5(image).hexdigest()}"]\n' +
                  f'known_sha1=["{hashlib.sha1(image).hexdigest()}"]\n')
        (root / "game.toml").write_text(config)
        (root / "build-release" / "game.toml").write_text(config)
        plan = launcher.make_plan(root, self.paths[0], "guest", "192.168.1.10:7777")
        self.assertFalse(plan["executed"])
        self.assertIn("--no-launcher", plan["argv"])
        slot = plan["argv"].index("--net-slot")
        self.assertEqual(plan["argv"][slot + 1], "1")
        self.assertEqual(plan["environment"]["PSX_NET_MODE"], "delay")
        self.assertIsNone(plan["environment"]["PSX_NO_LAUNCHER"])
        self.assertFalse(Path(plan["memcard_dir"]).exists())
        self.assertEqual((root / "game.toml").read_text(), config)
        if os.name == "nt":
            # Parsear el comando como texto, sin invocarlo ni abrir el juego.
            check = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 "$text=[Console]::In.ReadToEnd(); $tokens=$null; $errors=$null; "
                 "[void][System.Management.Automation.Language.Parser]::ParseInput("
                 "$text,[ref]$tokens,[ref]$errors); if ($errors.Count) { exit 1 }"],
                input=plan["powershell"], text=True, capture_output=True, timeout=15)
            self.assertEqual(check.returncode, 0, check.stderr)
        identity, exe, overlays = disc.inspect_disc(self.paths[0])
        identity["serial"] = "SLES-03685"
        with patch.object(launcher, "inspect_disc", return_value=(identity, exe, overlays)):
            with self.assertRaisesRegex(ValueError, "no compatible"):
                launcher.make_plan(root, self.paths[0], "launcher")
        (root / "build-release" / "game.toml").write_text(config + "# drift\n")
        with self.assertRaisesRegex(ValueError, "difieren"):
            launcher.make_plan(root, self.paths[0], "launcher")

    def test_peer_rejects_loopback_bad_ports_and_shell_fragments(self):
        for peer in ("127.0.0.1:7777", "0.0.0.0:7777", "224.0.0.1:7777",
                     "192.168.1.10:0", "host;bad:7777", "192.168.1.1:65536"):
            with self.subTest(peer=peer), self.assertRaises(ValueError):
                launcher.peer_address(peer)
        self.assertEqual(launcher.ps_quote("C:\\Javi's files\\game.exe"),
                         "'C:\\Javi''s files\\game.exe'")


class TcpTests(unittest.TestCase):
    def serve(self, reply: bytes, command="ping", delay=0.0, timeout=1.0):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        def worker():
            with server:
                server.settimeout(2)
                connection, _ = server.accept()
                with connection:
                    connection.recv(4096)
                    time.sleep(delay)
                    try:
                        midpoint = len(reply) // 2
                        connection.sendall(reply[:midpoint])
                        time.sleep(0.005)
                        connection.sendall(reply[midpoint:])
                    except OSError:
                        pass  # El cliente debe cortar respuestas tardías/grandes.

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            return smoke.query(port, command, 7, timeout)
        finally:
            thread.join(3)
            self.assertFalse(thread.is_alive())

    def test_fragmented_reply_and_documented_ping_fast_path(self):
        self.assertTrue(self.serve(b'{"id":7,"ok":true}\n')["ok"])
        self.assertTrue(self.serve(b'{"id":0,"ok":true,"pong":true,"io_thread":true}\n')["ok"])

    def test_wrong_id_and_errors_rejected(self):
        for reply in (b'{"id":8,"ok":true}\n', b'{"id":7,"ok":false}\n', b'[]\n'):
            with self.subTest(reply=reply), self.assertRaises(ValueError):
                self.serve(reply)
        with self.assertRaises(ValueError):
            self.serve(b'{"id":0,"ok":true,"pong":true,"io_thread":true}\n', "netplay_status")

    def test_timeout_and_response_cap(self):
        with self.assertRaises(TimeoutError):
            self.serve(b'{"id":7,"ok":true}\n', delay=0.12, timeout=0.03)
        with patch.object(smoke, "LIMIT", 128), self.assertRaisesRegex(ValueError, "supera"):
            self.serve(b'{"id":7,"ok":true,"long":"' + b"x" * 256 + b'"}\n')

    def test_failed_collection_never_claims_gameplay_pass(self):
        with patch.object(smoke, "query", side_effect=ConnectionRefusedError("synthetic")):
            result = smoke.collect(4370, "synthetic", 0)
        self.assertFalse(result["queries_ok"])
        self.assertEqual(len(result["errors"]), 12)
        self.assertEqual(result["visual_result"], "NOT_VERIFIED")
        self.assertEqual(result["netplay_determinism"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
