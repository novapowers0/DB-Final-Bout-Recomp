"""Verify the DBFinalBout build state without launching the game."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CACHE_RE = re.compile(r"^cg10_[0-9a-f]{8}_gc[0-9a-f]{8}_f0$")


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def require(path: Path, description: str, root: Path) -> None:
    if not path.exists():
        fail(f"missing {description}: {path.relative_to(root)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()

    source_config = root / "game.toml"
    deployed_config = root / "build-release" / "game.toml"
    require(source_config, "source game.toml", root)
    require(deployed_config, "deployed game.toml", root)
    if source_config.read_bytes() != deployed_config.read_bytes():
        fail("build-release/game.toml is not byte-identical to game.toml")
    require(
        root / "psxrecomp" / "mods" / "builtin" / "packages" /
        "psx.enhancement.widescreen" / "1.0.0" / "manifest.toml",
        "widescreen mod manifest",
        root,
    )
    manifest_text = (
        root / "psxrecomp" / "mods" / "builtin" / "packages" /
        "psx.enhancement.widescreen" / "1.0.0" / "manifest.toml"
    ).read_text(encoding="utf-8")
    if 'id = "psx.enhancement.widescreen"' not in manifest_text:
        fail("widescreen manifest has the wrong package id")

    try:
        import tomllib

        config = tomllib.loads(source_config.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"game.toml cannot be parsed: {exc}")

    video = config.get("video", {})
    widescreen = config.get("widescreen", {})
    controller = config.get("controller", {})
    expected = {
        "video.renderer": video.get("renderer") == "software",
        "video.offer_vulkan": video.get("offer_vulkan") is True,
        "video.aspect_ratio": video.get("aspect_ratio") == "4:3",
        "video.supersampling": video.get("supersampling") == 1,
        "video.antialiasing": video.get("antialiasing") is False,
        "video.texture_filtering": video.get("texture_filtering") == "nearest",
        "video.geometry_correction": video.get("geometry_correction") is False,
        "video.perspective_texturing": video.get("perspective_texturing") is False,
        "video.pgxp_cpu_mode": video.get("pgxp_cpu_mode") is False,
        "widescreen.offer": widescreen.get("offer") is True,
        "widescreen.adaptive_view": widescreen.get("adaptive_view") is True,
        "widescreen.precise_nclip": widescreen.get("precise_nclip") is False,
        "controller.sio_no_tx_gate": controller.get("sio_no_tx_gate") is True,
    }
    for key, valid in expected.items():
        if not valid:
            fail(f"unsafe or unexpected profile value: {key}")

    for path, description in (
        (root / "generated" / "SLUS_004.93_dispatch.c", "generated dispatch"),
        (root / "build-recompiler" / "psxrecomp-game.exe", "Clang recompiler"),
        (root / "build-release" / "DBFinalBout_Recompiled.exe", "release runtime"),
        (root / "build-release" / "DBFinalBout_Recompiled_pgxp.exe", "PGXP runtime"),
    ):
        require(path, description, root)

    hash_header = root / "build-recompiler-clang" / "psxrecomp_baked_codegen_hash.h"
    require(hash_header, "codegen hash header", root)
    hash_match = re.search(
        r"PSX_OVERLAY_CODEGEN_HASH\s+0x([0-9a-fA-F]{8})u",
        hash_header.read_text(encoding="utf-8"),
    )
    if not hash_match:
        fail("codegen hash header has no parseable hash")
    codegen_hash = hash_match.group(1).lower()

    cache_root = root / "build-release" / "cache" / "SLUS-00493" / "gcc" / "win-x64"
    require(cache_root, "overlay cache root", root)
    cache_dirs = [path for path in cache_root.iterdir() if path.is_dir()]
    matching = [
        path for path in cache_dirs
        if EXPECTED_CACHE_RE.match(path.name) and f"cg10_{codegen_hash}_" in path.name
    ]
    if len(matching) != 1:
        fail(f"expected exactly one current codegen cache, found {len(matching)}")
    cache = matching[0]
    dlls = sorted(cache.glob("*.dll"))
    if len(dlls) != 10:
        fail(f"expected 10 native overlay DLLs, found {len(dlls)} in {cache.name}")
    for dll in dlls:
        if not dll.with_suffix(".ranges").exists():
            fail(f"overlay DLL has no matching ranges file: {dll.name}")

    print("OFFLINE VERIFICATION PASSED")
    print(f"  config: source/deployed identical ({source_config.stat().st_size} bytes)")
    print(f"  codegen: {codegen_hash}")
    print(f"  overlays: {len(dlls)} DLLs with ranges in {cache.name}")
    print("  presentation: 16:9/adaptive offered; guest culling remains disabled")
    print("  Vulkan: offered when the compiled backend is available")
    cmake_cache = root / "build-release" / "CMakeCache.txt"
    if cmake_cache.exists():
        cache_text = cmake_cache.read_text(encoding="utf-8", errors="replace")
        if "PSX_ENABLE_VULKAN:BOOL=ON" not in cache_text:
            fail("build-release CMakeCache does not enable Vulkan")
        if "PSX_NETPLAY:BOOL=ON" not in cache_text:
            fail("build-release CMakeCache does not enable netplay")
        print("  build: Vulkan + netplay compiled; ICE intentionally disabled offline")
    print("  runtime: normal + PGXP present")
    print("  game: not launched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
