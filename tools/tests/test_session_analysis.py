"""Session attribution regressions. Synthetic fixtures are kept in TEMP/opencode.

The incident fixture uses the real report/heartbeat field layout and observed
metadata from frame 8418, without copying guest RAM, BIOS or disc bytes.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_latest_session as analysis


def report(**overrides):
    value = {
        "timestamp": "2026-10-03T22:46:42Z", "frame": 8418,
        "build": "nightly-157-g7d70880d-dirty (Sep 26 2026 20:07:11)",
        "reason": "atexit", "exit_origin": "unknown",
        "empty_irq_callback_returns": 0,
        "interp_unsupported": {"midblock_count": 0, "reason": "(none)"},
        "unknown_dispatch_tail": {"total": 0, "count": 0, "entries": []},
        "overlay_loader": {"registered": 334, "disp_native": 684176, "disp_interp": 2421119},
    }
    value.update(overrides)
    return value


def heartbeat(**overrides):
    value = {
        "backend": "psx-runtime", "wall_clock_epoch": 1791068527,
        "frame_count": 10603, "psx_cycle_count": 5985181440,
        "fatal": None, "automatic_freeze_dumps": 0, "failed_freeze_dumps": 0,
        "suppressed_freeze_events": 0, "empty_irq_callback_returns": 0,
        "dispatch_count": 0, "exception_entries": 68269,
    }
    value.update(overrides)
    return value


class SessionAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = Path(os.environ.get("TEMP", tempfile.gettempdir())) / "opencode"
        if not parent.is_dir():
            raise RuntimeError(f"Approved temporary parent missing: {parent}")
        cls.root = Path(tempfile.mkdtemp(prefix="dbfb-session-analysis-", dir=parent))

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix="case-", dir=self.root))

    def write(self, kind, value):
        name = analysis.FILES.get(kind, kind)
        (self.directory / name).write_text(json.dumps(value), encoding="utf-8")

    def cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = analysis.main(["--directory", str(self.directory), *args])
        return code, output.getvalue()

    def test_actual_failure_and_later_heartbeat_are_different_not_a_clean_session(self):
        self.write("report", report(
            reason="FAIL-FAST unknown dispatch: addr=0x00002934",
            empty_irq_callback_returns=1,
            unknown_dispatch_tail={"total": 1, "count": 1, "entries": [{"frame": 8418}]}))
        self.write("heartbeat", heartbeat())
        code, text = self.cli()
        self.assertEqual(code, 0)  # inspection is useful even for historical failures
        self.assertIn("session_relation=different", text)
        self.assertIn("report.fatal=yes", text)
        self.assertIn("heartbeat.fatal=no", text)
        self.assertNotIn("\nfatal=", text)
        self.assertIn("report.empty_irq_callback_returns=1", text)
        self.assertIn("heartbeat.empty_irq_callback_returns=0", text)
        code, text = self.cli("--json", "--strict")
        result = json.loads(text)
        self.assertEqual(code, 1)
        self.assertIn("process_counter_reset:empty_irq_callback_returns", result["relationship"]["reasons"])
        r, h = (result["artifacts"][k] for k in ("report", "heartbeat"))
        self.assertEqual(r["metadata"]["observed_epoch"], 1791067602)
        self.assertEqual(r["metrics"]["unknown_dispatch_total"], 1)
        self.assertEqual(r["metrics"]["midblock_count"], 0)
        self.assertIsNone(r["metrics"]["automatic_freeze_dumps"])
        self.assertEqual(h["metrics"]["automatic_freeze_dumps"], 0)
        self.assertIsNone(h["metrics"]["unknown_dispatch_total"])
        self.assertIsNone(h["metrics"]["midblock_count"])

    def test_matching_time_frame_and_build_do_not_prove_identity(self):
        r = report()
        self.write("report", r)
        self.write("heartbeat", heartbeat(wall_clock_epoch=1791067602, frame_count=8418, build=r["build"]))
        result = analysis.analyze(self.directory)
        self.assertEqual(result["relationship"]["status"], "unknown")
        self.assertFalse(result["strict"]["passed"])

    def test_time_gap_or_frame_reset_alone_does_not_prove_a_different_process(self):
        self.write("report", report())
        self.write("heartbeat", heartbeat(frame_count=12))  # guest may rewind
        self.assertEqual(analysis.analyze(self.directory)["relationship"]["status"], "unknown")

    def test_build_mismatch_is_reported_independently(self):
        self.write("report", report())
        self.write("heartbeat", heartbeat(build="another build"))
        relation = analysis.analyze(self.directory)["relationship"]
        self.assertEqual(relation, {"status": "different", "reasons": ["build_mismatch"]})

    def test_later_halted_heartbeat_does_not_imply_a_new_session(self):
        self.write("report", report(reason="FAIL-FAST unknown dispatch", empty_irq_callback_returns=1))
        self.write("heartbeat", heartbeat(fatal="FAIL-FAST unknown dispatch", empty_irq_callback_returns=1,
                                          frame_count=8418))
        self.assertEqual(analysis.analyze(self.directory)["relationship"]["status"], "unknown")

    def test_a_later_clear_fatal_state_contradicts_the_fatal_process(self):
        self.write("report", report(reason="FAIL-FAST unknown dispatch"))
        self.write("heartbeat", heartbeat())
        self.assertIn("fatal_state_cleared", analysis.analyze(self.directory)["relationship"]["reasons"])

    def test_reverse_time_order_process_counter_reset(self):
        self.write("report", report(timestamp="2026-10-03T23:10:00Z", empty_irq_callback_returns=0))
        self.write("heartbeat", heartbeat(empty_irq_callback_returns=4))
        self.assertEqual(analysis.analyze(self.directory)["relationship"]["status"], "different")

    def test_one_second_resolution_does_not_order_process_counters(self):
        self.write("report", report(empty_irq_callback_returns=1))
        self.write("heartbeat", heartbeat(wall_clock_epoch=1791067603))
        self.assertEqual(analysis.analyze(self.directory)["relationship"]["status"], "unknown")

    def test_report_only_does_not_invent_dump_or_heartbeat_counts(self):
        self.write("report", report())
        code, text = self.cli("--json", "--strict")
        result = json.loads(text)
        self.assertEqual(code, 1)
        self.assertEqual(result["artifacts"]["heartbeat"]["status"], "missing")
        self.assertEqual(result["artifacts"]["report"]["missing_evidence"], ["automatic_freeze_dumps"])

    def test_heartbeat_only_does_not_invent_dispatch_or_midblock_counts(self):
        self.write("heartbeat", heartbeat())
        code, text = self.cli("--json", "--strict")
        self.assertEqual(code, 1)
        h = json.loads(text)["artifacts"]["heartbeat"]
        self.assertEqual(h["missing_evidence"], ["unknown_dispatch_total", "midblock_count"])

    def test_no_artifacts_or_empty_objects_cannot_pass_strict(self):
        for values in ((), (("report", {}), ("heartbeat", {}))):
            for kind, value in values:
                self.write(kind, value)
            code, text = self.cli("--json", "--strict")
            self.assertEqual(code, 1)
            self.assertFalse(json.loads(text)["strict"]["passed"])

    def test_midblock_and_dump_issues_stay_with_their_source(self):
        self.write("report", report(interp_unsupported={"midblock_count": 7, "reason": "unsupported"}))
        self.write("heartbeat", heartbeat(automatic_freeze_dumps=2, failed_freeze_dumps=1,
                                          suppressed_freeze_events=3))
        result = analysis.analyze(self.directory)
        r, h = (result["artifacts"][k] for k in ("report", "heartbeat"))
        self.assertEqual(r["issues"], ["midblock_count"])
        self.assertEqual(h["issues"], ["automatic_freeze_dumps", "failed_freeze_dumps", "suppressed_freeze_events"])
        self.assertEqual(self.cli("--strict")[0], 1)

    def test_unknown_dispatch_in_reason_is_not_lost_when_tail_is_missing(self):
        r = report(reason="FAIL-FAST unknown dispatch 0x2934")
        r.pop("unknown_dispatch_tail")
        self.write("report", r)
        result = analysis.analyze(self.directory)["artifacts"]["report"]
        self.assertIsNone(result["metrics"]["unknown_dispatch_total"])
        self.assertIn("unknown_dispatch_in_reason", result["issues"])

    def test_normal_exit_marker_is_not_equivalent_to_complete_evidence(self):
        self.write("report", {"reason": "atexit"})
        result = analysis.analyze(self.directory)["artifacts"]["report"]
        self.assertFalse(result["metrics"]["fatal"])
        self.assertIsNone(result["metrics"]["midblock_count"])
        self.assertEqual(self.cli("--strict")[0], 1)

    def test_unrecognized_reason_does_not_silently_become_nonfatal(self):
        self.write("report", report(reason="unrecognized producer"))
        self.assertIsNone(analysis.analyze(self.directory)["artifacts"]["report"]["metrics"]["fatal"])

    def test_invalid_json_and_wrong_top_level_are_machine_readable_errors(self):
        for payload in ('{"frame":', "null", "[]", '{"timestamp":NaN}', '{"wall_clock_epoch":Infinity}'):
            with self.subTest(payload=payload):
                (self.directory / analysis.FILES["report"]).write_text(payload)
                code, text = self.cli("--json", "--strict")
                result = json.loads(text)
                self.assertEqual(code, 2)
                self.assertEqual(result["artifacts"]["report"]["status"], "invalid")
                self.assertFalse(result["strict"]["passed"])

    def test_bad_counter_types_do_not_turn_into_clean_zeros(self):
        for value in (None, False, "0", -1):
            with self.subTest(value=value):
                self.write("report", report(interp_unsupported={"midblock_count": value}))
                code, text = self.cli("--json")
                self.assertEqual(code, 2)
                self.assertIsNone(json.loads(text)["artifacts"]["report"]["metrics"]["midblock_count"])

    def test_malformed_nested_section_does_not_crash(self):
        self.write("report", report(interp_unsupported=None, unknown_dispatch_tail=[], overlay_loader="bad"))
        code, text = self.cli("--json")
        self.assertEqual(code, 2)
        self.assertEqual(len(json.loads(text)["artifacts"]["report"]["errors"]), 3)

    def test_inconsistent_unknown_tail_is_not_a_pass(self):
        self.write("report", report(unknown_dispatch_tail={"total": 0, "entries": [{"addr": "0x2934"}]}))
        code, text = self.cli("--json", "--strict")
        self.assertEqual(code, 2)
        self.assertIn("unknown_dispatch_entries", json.loads(text)["artifacts"]["report"]["issues"])

    def test_invalid_or_naive_timestamp_cannot_approve(self):
        for timestamp in ("nonsense", "2026-10-03T22:46:42", 123):
            with self.subTest(timestamp=timestamp):
                self.write("report", report(timestamp=timestamp))
                self.assertEqual(self.cli("--strict")[0], 2)

    def test_timezone_offset_and_zero_epoch_are_supported(self):
        self.write("report", report(timestamp="2026-10-04T00:46:42+02:00"))
        r = analysis.analyze(self.directory)["artifacts"]["report"]
        self.assertEqual(r["metadata"]["observed_epoch"], 1791067602)
        self.write("heartbeat", heartbeat(wall_clock_epoch=0))
        h = analysis.analyze(self.directory)["artifacts"]["heartbeat"]
        self.assertEqual(h["metadata"]["observed_epoch"], 0)

    def test_old_dump_inventory_is_unassigned_and_captures_are_preserved(self):
        # Non-JSON content proves inventory does not parse giant dump payloads.
        (self.directory / "psx_freeze_dump_old.json").write_text("not read")
        self.write("heartbeat", heartbeat())
        self.write("overlay_captures.json", [{"function_entry_pcs": []}])
        code, text = self.cli("--json")
        result = json.loads(text)
        self.assertEqual(code, 0)
        self.assertEqual(result["dump_inventory"]["files"], ["psx_freeze_dump_old.json"])
        self.assertEqual(result["dump_inventory"]["session_relation"], "unknown")
        self.assertEqual(result["artifacts"]["heartbeat"]["metrics"]["automatic_freeze_dumps"], 0)
        self.assertEqual(result["captures"]["regions_with_function_roots"], 0)
        self.assertIn("overlay_recompile=do-not-recompile-without-safe-roots", self.cli()[1])

    def test_invalid_capture_shape_is_reported(self):
        self.write("overlay_captures.json", [1])
        code, text = self.cli("--json")
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(text)["captures"]["status"], "invalid")

    def test_explicit_self_contained_record_can_pass_without_borrowed_counters(self):
        # A complete imported record can carry all diagnostics itself. Current
        # shipped reports do NOT carry this dump counter, so remain insufficient.
        self.write("report", report(automatic_freeze_dumps=0))
        code, text = self.cli("--json", "--strict")
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(text)["strict"]["passed"])

    def test_self_contained_metrics_without_build_or_recorded_frames_are_insufficient(self):
        for overrides in ({"build": None}, {"frame": 0}, {"timestamp": None}):
            with self.subTest(overrides=overrides):
                self.write("report", report(automatic_freeze_dumps=0, **overrides))
                self.assertEqual(self.cli("--strict")[0], 1)

    def test_real_cli_subprocess_json_and_input_files_remain_unchanged(self):
        self.write("report", report())
        self.write("heartbeat", heartbeat())
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.run(
            [sys.executable, str(Path(analysis.__file__)), "--directory", str(self.directory), "--json", "--strict"],
            env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertEqual(json.loads(process.stdout)["relationship"]["status"], "unknown")
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir()})

    def test_directory_argument_rejects_nonexistent_directory(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            analysis.main(["--directory", str(self.directory / "missing")])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
