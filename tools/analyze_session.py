#!/usr/bin/env python3
"""analyze_session.py - Analyze a DBFinalBout play session.

After playing the game once (with overlay_cache=true +
overlay_capture_history=true), run this to produce a digest of everything
the session revealed:

  - overlays captured (load_addr, size, CRCs, executed PCs) from
    build-release/overlay_captures.json
  - per-overlay executed-PC coverage + function-entry discovery
  - which overlay is the fight render funnel (STEP40: screen-extent culls)
  - freeze dumps present (crash signatures)
  - recommended compile_overlays.py command to recompile them native
  - widescreen status: whether the 0x200/0x1E0 cull sites are in the
    captured set (=> the widened FOV culls can actually be baked)

Usage:
  python tools/analyze_session.py [--exe-dir build-release]
"""

import argparse, json, os, re, sys, glob

WS_W_IMMS = (0x200,)
WS_H_IMMS = (0x1E0,)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--exe-dir", default="build-release",
                   help="dir next to the exe holding overlay_captures.json")
    return p.parse_args()


def load_captures(exe_dir):
    cap_path = os.path.join(exe_dir, "overlay_captures.json")
    if not os.path.exists(cap_path):
        return None, None
    with open(cap_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        overlays = data
    elif isinstance(data, dict):
        overlays = data.get("overlays", [])
    else:
        overlays = []
    return overlays, cap_path


def scan_mips_for_imms(data, w_imms, h_imms):
    """Scan raw MIPS bytes for slti/sltiu (0x0A/0x0B) with the given
    immediates. Returns (found_w, found_h) booleans and hit offsets."""
    w_hits, h_hits = [], []
    if isinstance(data, memoryview):
        data = data.tobytes()
    for off in range(0, len(data) - 3, 4):
        w = int.from_bytes(data[off:off + 4], "little")
        op = w >> 26
        if op not in (0x0A, 0x0B):
            continue
        imm = w & 0xFFFF
        if imm in w_imms:
            w_hits.append(off)
        if imm in h_imms:
            h_hits.append(off)
    return w_hits, h_hits


def analyze():
    args = parse_args()
    exe_dir = args.exe_dir
    if not os.path.isdir(exe_dir):
        sys.exit(f"no such dir: {exe_dir}")

    print("=" * 70)
    print("DBFinalBout session analysis")
    print("=" * 70)

    overlays, cap_path = load_captures(exe_dir)
    if overlays is None:
        print(f"\n[!] No overlay_captures.json in {exe_dir}.")
        print("    Play the game first (menus + at least one fight), then")
        print("    re-run. The capture file appears next to the exe.")
        sys.exit(1)

    print(f"\nCapture manifest: {cap_path}")
    print(f"Overlays recorded: {len(overlays)}")

    # adendum / history
    addendum = os.path.join(exe_dir, "overlay_captures.addendum.jsonl")
    if os.path.exists(addendum):
        n = sum(1 for _ in open(addendum, encoding="utf-8"))
        print(f"Session history (addendum.jsonl): {n} records")

    # per-overlay breakdown
    print("\n--- captured overlays ---")
    total_pcs = 0
    fight_funnel = None
    for ov in overlays:
        if isinstance(ov, dict):
            addr = ov.get("load_addr") or ov.get("addr") or "?"
            crc = ov.get("crc") or ov.get("crc32") or "?"
            epcs = ov.get("executed_pcs") or []
            fepcs = ov.get("function_entry_pcs") or []
            total_pcs += len(epcs)
            print(f"  {addr}  crc={crc}  executed_pcs={len(epcs)}  "
                  f"fn_entries={len(fepcs)}")
            # check for widescreen cull signature inside captured bytes if present
            if "bytes" in ov or "data" in ov:
                raw = ov.get("bytes") or ov.get("data")
                if isinstance(raw, str):
                    raw = bytes.fromhex(raw.replace("0x", ""))
                else:
                    raw = bytes(raw)
                wh, hh = scan_mips_for_imms(raw, WS_W_IMMS, WS_H_IMMS)
                if wh and hh:
                    fight_funnel = addr
                    print(f"      ** widescreen funnel signature 0x200/0x1E0 "
                          f"FOUND (W={len(wh)}, H={len(hh)})")
        elif isinstance(ov, list) and len(ov) >= 2:
            print(f"  {ov[0]}  crc={ov[1]}")
    print(f"\nTotal executed overlay PCs across session: {total_pcs}")

    # freeze dumps (crash signature)
    dumps = sorted(glob.glob(os.path.join(exe_dir, "psx_freeze_dump_*.json")))
    print(f"\n--- freeze dumps ---")
    if dumps:
        print(f"{len(dumps)} crash/freeze dumps present")
        for d in dumps[-5:]:
            try:
                with open(d, encoding="utf-8") as f:
                    j = json.load(f)
                kind = j.get("wedge_kind_name") or j.get("wedge_kind") or "?"
                cur = j.get("current_func", "?")
                exc = j.get("in_exception", "?")
                store = j.get("last_store_pc", "?")
                print(f"  {os.path.basename(d)}: wedge={kind} "
                      f"in_exc={exc} cur_fn={cur} store_pc={store}")
            except Exception:
                print(f"  {os.path.basename(d)}: unparseable")
    else:
        print("none (good)")

    # recommendation
    print("\n--- next step ---")
    if overlays:
        print("Recompile captured overlays native (drops interpreter instability):")
        print(f"  python psxrecomp/tools/compile_overlays.py \\")
        print(f"      --captures {os.path.join(os.path.abspath(exe_dir), 'overlay_captures.json')} \\")
        print(f"      --game-toml game.toml \\")
        print(f"      --recompiler psxrecomp/recompiler/build/psxrecomp-game.exe \\")
        print(f"      --runtime-include psxrecomp/runtime/include \\")
        print(f"      --out-dir {os.path.join(os.path.abspath(exe_dir), 'cache')} \\")
        print(f"      --gcc C:/msys64/mingw64/bin/gcc.exe --cps")
    if fight_funnel:
        print(f"\nFight funnel overlay ({fight_funnel}) captured => widescreen "
              f"culls 0x200/0x1E0 can now be widened for real.")
    else:
        print("\nWidescreen funnel signature not found in captured bytes: capture")
        print("bytes are not embedded in overlay_captures.json; the widen sites")
        print("are applied at recompile time from game.toml screen_w_imms/H_imms.")


if __name__ == "__main__":
    analyze()
