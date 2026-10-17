"""Read runtime artifacts independently; never join sessions by file proximity.

The current report has timestamp/frame/build; the heartbeat has
wall_clock_epoch/frame_count, but no process/session identifier or build.
Compatible times and frames therefore do NOT establish a shared session.
Missing counters remain unknown, never zero. No game or network access.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build-release"


FILES = {"report": "psx_last_run_report.json", "heartbeat": "psx_freeze_heartbeat.json"}
METRICS = ("fatal", "unknown_dispatch_total", "midblock_count", "automatic_freeze_dumps")


def reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def read_json(path: Path, expected: type) -> tuple[str, object, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=reject_constant)
        if not isinstance(data, expected):
            raise ValueError(f"expected {expected.__name__}")
        return "ok", data, []
    except FileNotFoundError:
        return "missing", None, []
    except (OSError, ValueError) as exc:
        return "invalid", None, [str(exc)]


def counter(data: dict, key: str, errors: list[str]) -> int | None:
    value = data.get(key)
    if key not in data:
        return None
    if type(value) is not int or value < 0:
        errors.append(f"{key}: expected nonnegative integer")
        return None
    return value


def section(data: dict, key: str, errors: list[str]) -> dict:
    value = data.get(key, {})
    if not isinstance(value, dict):
        errors.append(f"{key}: expected object")
        return {}
    return value


def metadata(data: dict, kind: str, errors: list[str]) -> dict:
    epoch = None
    timestamp = data.get("timestamp")
    if timestamp is not None:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                raise ValueError("timezone required")
            epoch = dt.timestamp()
        except (AttributeError, TypeError, ValueError, OverflowError):
            errors.append("timestamp: expected ISO-8601 with timezone")
    wall = counter(data, "wall_clock_epoch", errors)
    if epoch is not None and wall is not None and abs(epoch - wall) > 1:
        errors.append("timestamp and wall_clock_epoch disagree")
    build = data.get("build")
    if build is not None and (not isinstance(build, str) or not build.strip()):
        errors.append("build: expected nonempty string")
        build = None
    return {
        "timestamp": timestamp,
        "wall_clock_epoch": wall,
        "observed_epoch": epoch if epoch is not None else wall,
        "frame": counter(data, "frame" if kind == "report" else "frame_count", errors),
        "build": build,
    }


def summarize(data: dict, kind: str, errors: list[str]) -> dict:
    meta = metadata(data, kind, errors)
    reason = data.get("reason")
    if reason is not None and not isinstance(reason, str):
        errors.append("reason: expected string")
        reason = None
    fatal = None
    if "fatal" in data:
        value = data["fatal"]
        if value is None or value is False:
            fatal = False
        elif value is True or (isinstance(value, str) and value.strip()):
            fatal = True
        else:
            errors.append("fatal: expected null, boolean or nonempty reason")
    # These are report producers in crash_trace.c, not guesses from the heartbeat.
    if kind == "report" and reason:
        if (reason.startswith(("FAIL-FAST", "signal_")) or reason == "seh" or
                "recursion guard tripped" in reason):
            fatal = True
        elif reason == "atexit" and fatal is None:
            fatal = False  # No recorded fatal reason; not proof of a clean exit.
    unsupported = section(data, "interp_unsupported", errors)
    unknown = section(data, "unknown_dispatch_tail", errors)
    loader = section(data, "overlay_loader", errors)
    metrics = {
        "fatal": fatal,
        "fatal_reason": data.get("fatal") if data.get("fatal") else reason if fatal else None,
        "unknown_dispatch_total": counter(unknown, "total", errors),
        "midblock_count": counter(unsupported, "midblock_count", errors),
        "automatic_freeze_dumps": counter(data, "automatic_freeze_dumps", errors),
        "failed_freeze_dumps": counter(data, "failed_freeze_dumps", errors),
        "suppressed_freeze_events": counter(data, "suppressed_freeze_events", errors),
        "empty_irq_callback_returns": counter(data, "empty_irq_callback_returns", errors),
    }
    issues = [key for key in METRICS if metrics[key] is not None and metrics[key] > 0]
    for key in ("failed_freeze_dumps", "suppressed_freeze_events"):
        if metrics[key]:
            issues.append(key)
    if reason and "unknown dispatch" in reason.lower() and "unknown_dispatch_total" not in issues:
        issues.append("unknown_dispatch_in_reason")
    # A tail is positive evidence even if a malformed producer claims total=0.
    if unknown.get("entries"):
        if metrics["unknown_dispatch_total"] == 0:
            errors.append("unknown_dispatch_tail: entries contradict total=0")
        if "unknown_dispatch_total" not in issues:
            issues.append("unknown_dispatch_entries")
    return {
        "metadata": meta,
        "metrics": metrics,
        "issues": issues,
        "missing_evidence": [key for key in METRICS if metrics[key] is None],
        "details": {
            "exit_reason": reason,
            "exit_origin": data.get("exit_origin"),
            "dispatch": counter(data, "dispatch_count", errors),
            "exception_entries": counter(data, "exception_entries", errors),
            "last_store_pc": data.get("last_store_pc"),
            "interp_unsupported": unsupported.get("reason"),
            "overlay_registered": counter(loader, "registered", errors),
            "overlay_native": counter(loader, "disp_native", errors),
            "overlay_interp": counter(loader, "disp_interp", errors),
        },
    }


def relationship(report: dict, heartbeat: dict) -> dict:
    """Only contradictions establish different sessions; proximity proves nothing.

    A fatal process may keep writing heartbeats while halted, so a later wall
    clock alone is not a session boundary. Guest frames can rewind, too.
    """
    reasons = []
    if (report["status"] != "ok" or heartbeat["status"] != "ok" or
            report["errors"] or heartbeat["errors"]):
        return {"status": "unknown", "reasons": ["missing_or_invalid_artifact"]}
    r, h = report["metadata"], heartbeat["metadata"]
    if r["build"] is not None and h["build"] is not None and r["build"] != h["build"]:
        reasons.append("build_mismatch")
    # These are process-lifetime counters, not guest frame counters. A lower
    # value in a strictly later observation cannot belong to that same run.
    rt, ht = r["observed_epoch"], h["observed_epoch"]
    if rt is not None and ht is not None and abs(rt - ht) > 1:
        earlier, later = (report, heartbeat) if rt < ht else (heartbeat, report)
        for key in ("empty_irq_callback_returns", "unknown_dispatch_total", "midblock_count"):
            before, after = earlier["metrics"][key], later["metrics"][key]
            if before is not None and after is not None and after < before:
                reasons.append(f"process_counter_reset:{key}")
        if earlier["metrics"]["fatal"] is True and later["metrics"]["fatal"] is False:
            reasons.append("fatal_state_cleared")
    return {"status": "different" if reasons else "unknown",
            "reasons": reasons or ["no_shared_session_identifier; times_frames_build_are_not_identity"]}


def analyze(directory: Path) -> dict:
    artifacts = {}
    for kind, name in FILES.items():
        status, data, errors = read_json(directory / name, dict)
        item = {"file": name, "status": status, "errors": errors}
        if status == "ok":
            item.update(summarize(data, kind, errors))
        artifacts[kind] = item
    relation = relationship(artifacts["report"], artifacts["heartbeat"])
    status, data, errors = read_json(directory / "overlay_captures.json", list)
    captures = {"status": status, "errors": errors, "session_relation": "unknown"}
    if status == "ok":
        if not all(isinstance(item, dict) for item in data):
            captures.update(status="invalid", errors=["capture entries must be objects"])
        else:
            captures.update(regions=len(data), regions_with_function_roots=sum(
                bool(item.get("function_entry_pcs")) for item in data))
    # Inventory only. Old dumps and slow-frame dumps do not prove a failure in
    # either artifact's session. Never read the multi-MB payloads just to count.
    try:
        dumps = {"status": "ok", "files": sorted(p.name for p in directory.glob("psx_freeze_dump_*.json") if p.is_file()),
                 "session_relation": "unknown"}
    except OSError as exc:
        dumps = {"status": "invalid", "files": [], "session_relation": "unknown", "error": str(exc)}
    dumps["file_count"] = len(dumps["files"])
    present = [a for a in artifacts.values() if a["status"] == "ok"]
    blockers = []
    for kind, item in artifacts.items():
        if item["status"] == "invalid" or item["errors"]:
            blockers.append(f"{kind}:invalid")
        if item["status"] == "ok":
            blockers.extend(f"{kind}:{issue}" for issue in item["issues"])
    # Strict approval needs self-contained evidence. The shipped schemas have
    # no shared identity, and their complementary counters must not be joined.
    if len(present) != 1:
        blockers.append("need_one_self_contained_artifact; cannot_join_unidentified_sessions")
    if artifacts["report"]["status"] != "ok":
        blockers.append("missing_final_report")
    if captures["status"] == "invalid" or dumps["status"] == "invalid":
        blockers.append("invalid_auxiliary_artifact")
    for item in present:
        blockers.extend(f"{item['file']}:missing:{key}" for key in item["missing_evidence"])
        if item["metadata"]["observed_epoch"] is None or not item["metadata"]["frame"]:
            blockers.append(f"{item['file']}:missing_time_or_positive_frame")
        if item["file"] == FILES["report"] and item["metadata"]["build"] is None:
            blockers.append("report:missing_build")
    return {"directory": str(directory), "artifacts": artifacts, "relationship": relation,
            "captures": captures, "dump_inventory": dumps,
            "strict": {"passed": not blockers, "blockers": blockers}}


def display(value: object) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    # Artifact strings must not introduce unlabelled lines in the text CLI.
    return str(value).replace("\r", "\\r").replace("\n", "\\n")


def print_text(result: dict) -> None:
    print(f"directory={result['directory']}")
    print(f"session_relation={result['relationship']['status']}")
    print("relation_evidence=" + "; ".join(result["relationship"]["reasons"]))
    for kind, item in result["artifacts"].items():
        print(f"[{kind}] file={item['file']} status={item['status']}")
        for error in item["errors"]:
            print(f"{kind}.error={display(error)}")
        if item["status"] != "ok":
            continue
        for key, value in item["metadata"].items():
            print(f"{kind}.{key}={display(value)}")
        for key, value in {**item["metrics"], **item["details"]}.items():
            print(f"{kind}.{key}={display(value)}")
    captures = result["captures"]
    print(f"captures={captures['status']} session_relation=unknown")
    if captures["status"] == "ok":
        print(f"capture_regions={captures['regions']}")
        print(f"capture_regions_with_function_roots={captures['regions_with_function_roots']}")
        if captures["regions_with_function_roots"] == 0:
            print("overlay_recompile=do-not-recompile-without-safe-roots")
    for error in captures["errors"]:
        print(f"captures.error={display(error)}")
    print(f"dump_files_present={result['dump_inventory']['file_count']} session_relation=unknown")
    if result["dump_inventory"]["status"] != "ok":
        print(f"dump_inventory.error={display(result['dump_inventory']['error'])}")
    print(f"strict_passed={display(result['strict']['passed'])}")
    if result["strict"]["blockers"]:
        print("strict_blockers=" + "; ".join(result["strict"]["blockers"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=OUT, help="artifact directory (default: build-release)")
    parser.add_argument("--json", action="store_true", help="emit independent, normalized artifact summaries")
    parser.add_argument("--strict", action="store_true", help="exit 1 on incidents or insufficient session evidence")
    args = parser.parse_args(argv)
    if not args.directory.is_dir():
        parser.error(f"not an existing directory: {args.directory}")
    result = analyze(args.directory)
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
    else:
        print_text(result)
    invalid = any(a["status"] == "invalid" or a["errors"] for a in result["artifacts"].values())
    invalid = invalid or result["captures"]["status"] == "invalid" or result["dump_inventory"]["status"] == "invalid"
    if invalid:
        return 2
    return 1 if args.strict and not result["strict"]["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
