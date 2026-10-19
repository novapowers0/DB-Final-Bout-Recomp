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
import sys
import tempfile
import tomllib
import unittest

from test_responsive_evidence import ROOT, fnv, regions

MANIFEST = ROOT / "mods/preloaded/packages/dbfb.responsive/0.1.0/manifest.toml"


def private_fixture():
    path = Path(os.environ.get("DBFB_RESPONSIVE_CAPTURE", ROOT / "build-release/vault/overlay_captures.json"))
    exe_path = Path(os.environ.get("DBFB_RESPONSIVE_EXE", ROOT / "disc/SLUS_004.93"))
    if not path.is_file() or not exe_path.is_file() or not (ROOT / 'disc/Dragon Ball GT - Final Bout (USA).bin').is_file():
        raise unittest.SkipTest("C harness requires local STEP40 capture, USA disc and EXE; no disc bytes are bundled")
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
    # Additional identity sites come from the private capture, not bundled bytes.
    for address, words in (
        (0x800666EC, (0x94232904,)),
        (0x8006672C, (0x94232904,)),
        (0x8006D1D4, (0x94232842,)),
        (0x8006D1DC, (0x2C6200C4,)),
        (0x80054AD4, (0x10820004, 0x2402FFFF, 0x3C018007, 0x00370821, 0xA4222856)),
        (0x80054ABC, (0, 0x2C420009, 0x14400008)),
        (0x8006A178, (0x38420001, 0x3C01800B, 0xAC22868C)),
        (0x8006A2F8, (0x8C63868C,)),
        (0x80054A60, (0x84242856,)),
        (0x80054AE8, (0x02C02021, 0x8FA50010, 0x8FA60014)),
        (0x80066D24, (0x00111400, 0x1C400002)),
        (0x8004F5A0, (0xA462FFE4,)),
        (0x800592A8, (0x00021200,)),
        (0x800592FC, (0x00021200,)),
        (0x80067A68, (0x02020018,)),
    ):
        expected = struct.pack('<' + 'I' * len(words), *words)
        pieces.append((address & 0x1FFFFFFF, block(address, len(expected), fnv(expected))))
    pieces.append((0x4E530, block(0x8004E530, 0xAE4, 0x6949A1DF)))
    pieces.append((0x420EC, block(0x800420EC, 0xC24, 0x0637584D)))
    sys.path.insert(0, str(ROOT / 'tools'))
    from combat_map import step40, sha
    image, _ = step40(ROOT / 'disc/Dragon Ball GT - Final Bout (USA).bin')
    assert sha(image) == '001adcdc2e129d3bd715c29b64e393fa8c2901a7ef39c2347874b321aae6b9dd'
    # Widen the existing argument-code piece, keeping the shared 22-block
    # stream contract used by the combat matrix harness. All bytes are private
    # and bound to the verified complete STEP40 hash, not manufactured guards.
    for address, expected in ((0x80056E64, 0x00A09821), (0x80056E6C, 0x00C0A021),
                              (0x80057238, 0x0C017499), (0x8005D314, 0x10820146),
                              (0x8005D910, 0xAC222804)):
        assert struct.unpack_from('<I', image, address-0x8003DFA0)[0] == expected
    pieces = [(address, image[0x80054AE8-0x8003DFA0:0x8005D914-0x8003DFA0]
               if address == 0x54AE8 else data) for address, data in pieces]
    offset = 0x80071CC0-0x8003DFA0
    pieces.append((0x71CC0, image[offset:offset+8]))
    return struct.pack("<I", len(pieces)) + b"".join(
        struct.pack("<II", address, len(data)) + data for address, data in pieces
    )


class ResponsiveTests(unittest.TestCase):
    def test_native_guard_and_cpu_difficulty_evidence(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        from combat_map import step40
        disc = ROOT / 'disc/Dragon Ball GT - Final Bout (USA).bin'
        if not disc.is_file():
            self.skipTest('Private local USA disc required')
        image, _ = step40(disc)
        # Pin the native reducer's LUI (bit 30, not low bit 14), CPU branch,
        # effective per-fighter difficulty stores and the AI's signed load.
        for address, expected in ((0x80066DC8, 0x3C024000),
                                  (0x80066DE8, 0x00A21024),
                                  (0x800549C8, 0x30420001),
                                  (0x800663A4, 0x00809021),
                                  (0x800663BC, 0x2E540001),
                                  (0x80053DE4, 0xA4222960),
                                  (0x80053EFC, 0xA4222984)):
            self.assertEqual(struct.unpack_from('<I', image, address-0x8003DFA0)[0], expected,
                             hex(address))

    def test_unlock_address_uses_signed_store_immediate(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        from combat_map import Iso
        disc = ROOT / 'disc/Dragon Ball GT - Final Bout (USA).bin'
        if not disc.is_file():
            self.skipTest('Private local USA disc required')
        iso = Iso(disc)
        _, lba, size = next(f for f in iso.files() if f[0] == 'MENU/STEP00.BIN')
        data = iso.read(lba, size)
        lui, store = struct.unpack_from('<II', data, 0x328)
        self.assertEqual(lui >> 26, 15)
        self.assertEqual(store >> 26, 43)
        self.assertEqual((lui >> 16) & 31, (store >> 21) & 31)
        signed_offset = ((store & 0xFFFF) ^ 0x8000)-0x8000
        self.assertEqual(((lui & 0xFFFF) << 16)+signed_offset, 0x8003BCC4)

    def test_manifest_choices_and_default_off(self):
        manifest = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
        features = {item["id"]: item for item in manifest["feature"]}
        self.assertEqual(set(features), {"trace", "standard", "unlock-all"})
        self.assertTrue(all(item["default_enabled"] is False for item in features.values()))
        self.assertEqual(features["trace"]["channel"], "developer")
        self.assertEqual(features["standard"]["channel"], "experimental")
        self.assertIn("offline", features["standard"]["description"].lower())
        self.assertIn("offline", features["unlock-all"]["description"].lower())
        self.assertFalse(manifest.get("option"), "Every feature must work without tuning any options")
        self.assertTrue(all(item["feature"] in features for item in manifest["plugin"]))
        player_features = [f for f in features.values() if f.get("channel") != "developer"]
        self.assertEqual([f["id"] for f in player_features], ["standard", "unlock-all"])

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
        self.assertIn("36 C scenario groups passed", output)
        print(f"Retained build (no fixture files): {build_dir}", flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
