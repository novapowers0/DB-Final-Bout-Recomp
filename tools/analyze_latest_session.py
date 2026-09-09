"""Summarize the latest runtime session without launching the game."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build-release"


def read_json(name: str):
    path = OUT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main() -> int:
    heartbeat = read_json("psx_freeze_heartbeat.json")
    report = read_json("psx_last_run_report.json")
    captures = read_json("overlay_captures.json")
    if heartbeat:
        fatal = heartbeat.get("fatal")
        print(f"frames={heartbeat.get('frame_count', 0)}")
        print(f"dispatch={heartbeat.get('dispatch_count', 0)}")
        print(f"exception_entries={heartbeat.get('exception_entries', 0)}")
        print(f"automatic_freeze_dumps={heartbeat.get('automatic_freeze_dumps', 0)}")
        print(f"fatal={'yes' if fatal else 'no'}")
        print(f"last_store_pc={heartbeat.get('last_store_pc', 'n/a')}")
    else:
        print("heartbeat=missing")
    if report:
        print(f"exit_reason={report.get('reason', 'n/a')}")
        print(f"interp_unsupported={report.get('interp_unsupported', {}).get('reason', 'n/a')}")
        loader = report.get("overlay_loader", {})
        print(f"overlay_registered={loader.get('registered', 0)}")
        print(f"overlay_native={loader.get('disp_native', 0)}")
        print(f"overlay_interp={loader.get('disp_interp', 0)}")
    if captures is not None:
        roots = sum(bool(item.get("function_entry_pcs")) for item in captures)
        print(f"capture_regions={len(captures)}")
        print(f"capture_regions_with_function_roots={roots}")
        if roots == 0:
            print("overlay_recompile=do-not-recompile-without-safe-roots")
    else:
        print("captures=missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
