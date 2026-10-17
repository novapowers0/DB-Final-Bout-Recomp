"""Compile and exercise the real dbfb_responsive.c, without launching the game.

No dependencies are installed. The fixture is read from existing private local
captures and the USA boot EXE, passed over stdin, never saved or distributed.
Build products are retained in a fresh temp directory (nothing is deleted).
Override DBFB_RESPONSIVE_CAPTURE / DBFB_RESPONSIVE_EXE / CC if needed.
"""
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import tomllib
import unittest

from test_responsive_evidence import ROOT, fnv, regions

MANIFEST = ROOT / "mods/preloaded/packages/dbfb.responsive/0.1.0/manifest.toml"


def private_fixture():
    path = Path(os.environ.get("DBFB_RESPONSIVE_CAPTURE", ROOT / "build-release/vault/overlay_captures.json"))
    exe_path = Path(os.environ.get("DBFB_RESPONSIVE_EXE", ROOT / "disc/SLUS_004.93"))
    if not path.is_file() or not exe_path.is_file():
        raise unittest.SkipTest("C harness requires existing local STEP40 capture and USA EXE; no disc bytes are bundled")
    captured = list(regions(path))

    def block(address, size, expected):
        matches = set()
        for base, data in captured:
            start = address - base
            if 0 <= start and start + size <= len(data):
                part = data[start:start + size]
                if fnv(part) == expected:
                    matches.add(part)
        if len(matches) != 1:
            raise AssertionError(f"Missing/ambiguous verified code at {address:#x} in {path}")
        return matches.pop()

    exe = exe_path.read_bytes()
    assert exe[:8] == b"PS-X EXE"
    load = struct.unpack_from("<I", exe, 0x18)[0]
    offset = 0x80010F40 - load + 0x800
    padread = exe[offset:offset + 0x10C]
    assert fnv(padread) == 0xC4EF2A99, "Unsupported PadRead revision"
    # The two helper call instructions are also checked by the C guard.
    helper = struct.pack("<II", 0x0C00FF3C, 0x00002021)
    helper_hash = fnv(helper)
    pieces = [
        (0x3FCF0, block(0x8003FCF0, 0x294, 0x829BEBD2)),
        (0x539A8, block(0x800539A8, 0x28, 0x2B7A4598)),
        (0x3FCB4, block(0x8003FCB4, 8, helper_hash)),
        (0x10F40, padread),
    ]
    return struct.pack("<I", len(pieces)) + b"".join(
        struct.pack("<II", address, len(data)) + data for address, data in pieces
    )


class ResponsiveTests(unittest.TestCase):
    def test_manifest_choices_and_default_off(self):
        manifest = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
        features = {item["id"]: item for item in manifest["feature"]}
        self.assertEqual(set(features), {"trace", "input-buffer"})
        self.assertTrue(all(item["default_enabled"] is False for item in features.values()))
        self.assertEqual(features["trace"]["channel"], "developer")
        self.assertEqual(features["input-buffer"]["channel"], "experimental")
        self.assertIn("offline", features["input-buffer"]["description"].lower())
        options = {item["id"]: item for item in manifest["option"]}
        self.assertEqual({item["value"] for item in options["mode"]["choice"]},
                         {"original", "buffer", "hold"})
        self.assertEqual(options["mode"]["default"], "buffer")
        self.assertEqual((options["window"]["min"], options["window"]["max"], options["window"]["default"]),
                         (1, 6, 2))
        self.assertTrue(all(item["feature"] in features for item in manifest["plugin"]))

    def test_production_c(self):
        fixture = private_fixture()
        compiler = os.environ.get("CC") or shutil.which("gcc")
        if not compiler and os.name == "nt":
            compiler = r"C:\msys64\mingw64\bin\gcc.exe"
        self.assertTrue(compiler and Path(compiler).is_file(), "Existing gcc compiler required; nothing is installed")
        parent = Path(r"C:\Users\javie\AppData\Local\Temp\opencode") if os.name == "nt" else Path(tempfile.gettempdir())
        self.assertTrue(parent.is_dir(), f"Build parent must already exist: {parent}")
        build_dir = Path(tempfile.mkdtemp(prefix="dbfb-responsive-", dir=parent))
        binary = build_dir / ("test_responsive.exe" if os.name == "nt" else "test_responsive")
        command = [str(compiler), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                   "-I", str(ROOT / "psxrecomp/runtime/include"),
                   str(ROOT / "src/mods/dbfb_responsive.c"),
                   str(ROOT / "tools/tests/test_responsive_harness.c"), "-o", str(binary)]
        env = dict(os.environ)
        env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
        print("\nCompile:", subprocess.list2cmdline(command), flush=True)
        compiled = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        ran = subprocess.run([str(binary)], input=fixture, capture_output=True, timeout=30, env=env)
        output = (ran.stdout + ran.stderr).decode(errors="replace")
        print(output, flush=True)
        self.assertEqual(ran.returncode, 0, f"Harness exit {ran.returncode}:\n{output}")
        self.assertIn("17 C scenario groups passed", output)
        print(f"Retained build (no fixture files): {build_dir}", flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
