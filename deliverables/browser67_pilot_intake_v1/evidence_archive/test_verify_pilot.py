"""Independent contract tests using synthetic records, never raw evidence."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from typing import Any
from unittest.mock import patch

import verify_pilot as verifier


def gate_fixture() -> tuple[
    dict[str, Any], dict[str, Any], list[dict[str, Any]],
    dict[str, Any], dict[str, bytes], list[dict[str, Any]],
]:
    """Create a clean stage with explicit command and upload ordering."""
    static = {name: name.encode("ascii") for name in verifier.STATIC_NAMES}
    ticket = {
        "pair_id": "synthetic-pair", "event": "provisional_ticket_issued",
        "event_at": "2026-10-04T00:00:01Z",
    }
    page_channel = "ws://127.0.0.1:9340/devtools/page/synthetic-target"
    browser_channel = "ws://127.0.0.1:9340/devtools/browser"
    target = {"id": "synthetic-target", "url": "http://127.0.0.1:8001/browser-probe.html#synthetic",
              "webSocketDebuggerUrl": page_channel}
    realm = {
        "href": target["url"], "readyState": "interactive",
        "coreRevision": "expanded-web-67-v2",
        "languageHasOwn": False, "languagesHasOwn": False,
    }
    events: list[dict[str, Any]] = [
        {"kind": "stage_started", "capture_id": "c0001", "at": "2026-10-04T00:00:00Z"},
        {"kind": "gate_held", "capture_id": "c0001", "at": "2026-10-04T00:00:02Z",
         "path": "/browser-probe-adapter.js", "upstream_adapter_sha256": verifier.digest(static["browser-probe-adapter.js"])},
        {"kind": "target_selected", "capture_id": "c0001", "at": "2026-10-04T00:00:03Z", "ticket": ticket, "target": target},
    ]
    for name in ("browser-probe.html", "browser-probe-bootstrap.js", "probe/canonical_web_probe.js"):
        events.append({"kind": "static_file_sent", "at": "2026-10-04T00:00:04Z", "capture_id": "c0001", "public_path": name,
                       "sha256": verifier.digest(static[name]), "byte_count": len(static[name])})
    events.append({"kind": "cdp_received", "at": "2026-10-04T00:00:04Z",
                   "cdp_channel": page_channel,
                   "message": {"id": 1, "result": {"result": {"value": realm}}}})
    events.append({"kind": "adb_received", "at": "2026-10-04T00:00:04Z",
                   "args": ["shell", "pidof", "com.android.chrome"], "stdout": "123\n"})

    def command(identifier: int, method: str, params: dict[str, Any], second: int, result: dict[str, Any]) -> None:
        stamp = f"2026-10-04T00:00:{second:02d}Z"
        channel = browser_channel if method == "Target.closeTarget" else page_channel
        events.extend([
            {"kind": "cdp_sent", "at": stamp, "cdp_channel": channel,
             "command": {"id": identifier, "method": method, "params": params}},
            {"kind": "cdp_received", "at": stamp, "cdp_channel": channel,
             "message": {"id": identifier, "result": result}},
        ])

    command(10, "Browser.getVersion", {}, 4, {"product": "Chrome/133.0.0.0"})
    command(2, "Emulation.setTimezoneOverride", {"timezoneId": ""}, 5, {})
    events.append({"kind": "gate_released", "capture_id": "c0001", "at": "2026-10-04T00:00:06Z",
                   "upstream_adapter_sha256": verifier.digest(static["browser-probe-adapter.js"]),
                   "response_byte_count": len(static["browser-probe-adapter.js"])})
    command(3, "Emulation.setTimezoneOverride", {"timezoneId": ""}, 8, {})
    command(4, "Target.closeTarget", {"targetId": target["id"]}, 9, {"success": True})
    capture = {
        "capture_id": "c0001", "stage": "clean_pre", "binding": {"pair_id": ticket["pair_id"]},
        "browser_pair_event_baseline_line": 0, "committed_realm": verifier.public_realm(realm),
        "control_installation": {"method": "none", "fresh_chrome_process": True, "timezone_reset_result": {}},
        "finished_at": "2026-10-04T00:00:10Z",
        "fresh_chrome_startup": {"webSocketDebuggerUrl": browser_channel,
                                 "Android-Package": "com.android.chrome", "Browser": "Chrome/133.0.0.0"},
        "browser_version": {"product": "Chrome/133.0.0.0"},
        "warmup_target": {"chrome_pid": "123"},
        "restoration": [
            {"method": "Emulation.setTimezoneOverride", "params": {"timezoneId": ""}, "result": {}},
            {"method": "Target.closeTarget", "params": {"targetId": target["id"]}, "result": {"success": True}},
        ],
    }
    browser = {"server_received_at": "2026-10-04T00:00:07Z"}
    return capture, browser, events, {}, static, [ticket]


class PayloadContractTests(unittest.TestCase):
    """Labels belong to the sidecar, while observations remain valid inputs."""

    def test_real_control_observations_are_allowed(self) -> None:
        verifier.verify_no_control_labels({
            "language": "fr-FR", "languages": ["fr-FR"],
            "timezone_id": "Asia/Tokyo", "timezone_offset": -540,
            "runtime_context": "opaque-device:c0001",
        })

    def test_nested_label_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(verifier.VerificationError, "^CONTROL_LABEL_KEY_IN_PAYLOAD$"):
            verifier.verify_no_control_labels({"metadata": [{"configuration_id": "language_fr"}]})

    def test_label_value_under_unrelated_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(verifier.VerificationError, "^CONTROL_LABEL_VALUE_IN_PAYLOAD$"):
            verifier.verify_no_control_labels({"metadata": {"note": "attack_active"}})

    def test_partial_jsonl_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rba-contract-test-") as directory:
            path = Path(directory) / "partial.jsonl"
            path.write_text('{"capture_id":"c0001"}', encoding="utf-8")
            with self.assertRaisesRegex(verifier.VerificationError, "^PARTIAL_JSONL_ROW$"):
                verifier.read_jsonl(path)

    def test_canonical_hash_ignores_key_order_and_preserves_unicode(self) -> None:
        payload = {"language": "中文", "values": [1, False, None]}
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.assertEqual(verifier.canonical_digest(payload), verifier.digest(encoded))
        self.assertEqual(verifier.canonical_digest(dict(reversed(list(payload.items())))), verifier.digest(encoded))

    def test_non_json_number_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            verifier.canonical_digest({"value": float("nan")})

    def test_catalog_metadata_does_not_count_as_signal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rba-catalog-test-") as directory:
            path = Path(directory) / "catalog.csv"
            path.write_text(
                "field,layer,type\n"
                "web_data.navigator_layer.language,web_data,string\n"
                "android_native_data.locale.native_language,android_native_data,string\n"
                "collector_app,collector_app,string\n"
                "schema_version,schema_version,string\n"
                "session_id,session_id,string\n"
                "timestamp,timestamp,number\n", encoding="utf-8",
            )
            self.assertEqual(verifier.app_signal_catalog(path), {
                "web_data.navigator_layer.language", "android_native_data.locale.native_language",
            })

    def test_unknown_catalog_metadata_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rba-catalog-test-") as directory:
            path = Path(directory) / "catalog.csv"
            path.write_text("field,layer,type\nunknown,unknown,string\n", encoding="utf-8")
            with self.assertRaisesRegex(verifier.VerificationError, "^SOURCE_APP_CATALOG_METADATA_MISMATCH$"):
                verifier.app_signal_catalog(path)


class GateContractTests(unittest.TestCase):
    """Check negative evidence cases using independently constructed events."""

    def test_closed_clean_stage_passes(self) -> None:
        verifier.verify_gate(*gate_fixture())

    def test_missing_backend_ticket_is_rejected(self) -> None:
        fixture = list(gate_fixture())
        fixture[-1] = [{"event": "provisional_ticket_issued", "pair_id": "another"}]
        with self.assertRaisesRegex(verifier.VerificationError, "^SELECTED_TICKET_EVENT_MISSING$"):
            verifier.verify_gate(*fixture)

    def test_old_backend_ticket_is_rejected(self) -> None:
        capture, browser, events, control, static, pair_events = deepcopy(gate_fixture())
        pair_events[0]["event_at"] = "2026-10-03T23:59:59Z"
        with self.assertRaisesRegex(verifier.VerificationError, "^SELECTED_TICKET_PRECEDES_STAGE$"):
            verifier.verify_gate(capture, browser, events, control, static, pair_events)

    def test_restoration_before_upload_is_rejected(self) -> None:
        capture, browser, events, control, static, pair_events = gate_fixture()
        browser["server_received_at"] = "2026-10-04T00:00:08.5Z"
        with self.assertRaisesRegex(verifier.VerificationError, "^RESTORATION_BEFORE_UPLOAD$"):
            verifier.verify_gate(capture, browser, events, control, static, pair_events)

    def test_forged_timestamps_cannot_hide_event_reordering(self) -> None:
        capture, browser, events, control, static, pair_events = gate_fixture()
        target = events.pop(2)
        events.insert(1, target)
        with self.assertRaisesRegex(verifier.VerificationError, "^GATE_EVENT_ORDER_INVALID$"):
            verifier.verify_gate(capture, browser, events, control, static, pair_events)

    def test_close_target_requires_success_true(self) -> None:
        capture, browser, events, control, static, pair_events = gate_fixture()
        events[-1]["message"]["result"]["success"] = False
        with self.assertRaisesRegex(verifier.VerificationError, "^BROWSER_TARGET_NOT_CLOSED$"):
            verifier.verify_gate(capture, browser, events, control, static, pair_events)

    def test_duplicate_release_is_rejected(self) -> None:
        capture, browser, events, control, static, pair_events = gate_fixture()
        events.append(next(deepcopy(row) for row in events if row["kind"] == "gate_released"))
        with self.assertRaisesRegex(verifier.VerificationError, "^GATE_RELEASE_NOT_UNIQUE$"):
            verifier.verify_gate(capture, browser, events, control, static, pair_events)

    def test_browser_exception_is_rejected(self) -> None:
        capture, browser, events, control, static, pair_events = gate_fixture()
        events[-1]["message"]["result"]["exceptionDetails"] = {"text": "synthetic failure"}
        with self.assertRaisesRegex(verifier.VerificationError, "^CDP_REALM_EXCEPTION$"):
            verifier.verify_gate(capture, browser, events, control, static, pair_events)

    def test_next_warmup_reusing_browser_command_id_is_excluded(self) -> None:
        capture, browser, events, control, static, pair_events = gate_fixture()
        events.extend([
            {"kind": "cdp_sent", "at": "2026-10-04T00:00:11Z",
             "cdp_channel": "ws://127.0.0.1:9340/devtools/browser",
             "command": {"id": 4, "method": "Target.closeTarget", "params": {"targetId": "next-warmup"}}},
            {"kind": "cdp_received", "at": "2026-10-04T00:00:12Z",
             "cdp_channel": "ws://127.0.0.1:9340/devtools/browser",
             "message": {"id": 4, "result": {"success": True}}},
        ])
        verifier.verify_gate(capture, browser, events, control, static, pair_events)

    def test_chrome_process_change_is_rejected(self) -> None:
        capture, browser, events, control, static, pair_events = gate_fixture()
        process = next(row for row in events if row["kind"] == "adb_received")
        process["stdout"] = "456\n"
        with self.assertRaisesRegex(verifier.VerificationError, "^PROBE_CHROME_PROCESS_MISMATCH$"):
            verifier.verify_gate(capture, browser, events, control, static, pair_events)


class CommandChannelTests(unittest.TestCase):
    """A browser reply with the same ID must never satisfy a page command."""

    def test_same_numeric_id_in_other_channel_is_ignored(self) -> None:
        _, _, events, _, _, _ = gate_fixture()
        before = events[:next(index for index, row in enumerate(events) if row["kind"] == "gate_released")]
        before.append({"kind": "cdp_received", "at": "2026-10-04T00:00:05Z",
                       "cdp_channel": "ws://127.0.0.1:9340/devtools/browser",
                       "message": {"id": 2, "result": {"wrong_channel": True}}})
        _, reply = verifier.successful_command(before, "Emulation.setTimezoneOverride", {"timezoneId": ""})
        self.assertEqual(reply["message"]["result"], {})

    def test_reply_from_wrong_socket_is_rejected(self) -> None:
        _, _, events, _, _, _ = gate_fixture()
        before = events[:next(index for index, row in enumerate(events) if row["kind"] == "gate_released")]
        before[-1]["cdp_channel"] = "ws://127.0.0.1:9340/devtools/browser"
        with self.assertRaisesRegex(verifier.VerificationError, "^CDP_COMMAND_NOT_SUCCESSFUL$"):
            verifier.successful_command(before, "Emulation.setTimezoneOverride", {"timezoneId": ""})

    def test_target_close_on_page_socket_is_rejected(self) -> None:
        _, _, events, _, _, _ = gate_fixture()
        events[-2]["cdp_channel"] = "ws://127.0.0.1:9340/devtools/page/synthetic-target"
        with self.assertRaisesRegex(verifier.VerificationError, "^CDP_COMMAND_CHANNEL_INVALID$"):
            verifier.successful_command(events, "Target.closeTarget", {"targetId": "synthetic-target"})

    def test_remote_websocket_is_rejected(self) -> None:
        _, _, events, _, _, _ = gate_fixture()
        events[-2]["cdp_channel"] = "ws://example.test:9340/devtools/browser"
        with self.assertRaisesRegex(verifier.VerificationError, "^CDP_COMMAND_CHANNEL_INVALID$"):
            verifier.successful_command(events, "Target.closeTarget", {"targetId": "synthetic-target"})


class ArtifactLocationTests(unittest.TestCase):
    """Historical paths can move, but every read stays in the current archive."""

    def test_recorded_current_and_prior_roots_resolve_to_copied_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rba-location-test-") as directory:
            base = Path(directory)
            current, prior, fixture = base / "current", base / "prior", base / "fixture"
            inputs = verifier.Inputs(fixture, fixture / "provenance.jsonl", {
                "source_checkout": str(current / "upstream"),
                "resume_archive_origin": {"directory": str(prior)},
            })
            for origin in (current, prior):
                self.assertEqual(inputs.locked_path(str(origin / "upstream/probe.js")),
                                 (fixture / "upstream/probe.js").resolve())

    def test_unrecorded_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rba-location-test-") as directory:
            base = Path(directory)
            inputs = verifier.Inputs(base / "fixture", base / "provenance.jsonl", {
                "source_checkout": str(base / "recorded/upstream"),
            })
            with self.assertRaisesRegex(verifier.VerificationError, "^LOCKED_PATH_OUTSIDE_RUN$"):
                inputs.locked_path(str(base / "unrecorded/probe.js"))

    def test_traversal_from_recorded_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rba-location-test-") as directory:
            base = Path(directory)
            inputs = verifier.Inputs(base / "fixture", base / "provenance.jsonl", {
                "source_checkout": str(base / "recorded/upstream"),
            })
            with self.assertRaisesRegex(verifier.VerificationError, "^LOCKED_PATH_ESCAPE$"):
                inputs.locked_path(str(base / "recorded/../outside/probe.js"))


class DeliveryContractTests(unittest.TestCase):
    """The delivery builder must retain failures and select fresh test evidence."""

    def call_builder(self, function: str, *arguments: Any) -> str:
        module = (Path(__file__).resolve().parent / "build_delivery.mjs").as_uri()
        script = (
            f"import {{ {function} }} from {json.dumps(module)}; "
            f"try {{ {function}(...JSON.parse(process.argv[1])); process.stdout.write('PASS'); }} "
            "catch (error) { process.stdout.write(error.message); }"
        )
        result = subprocess.run(["node", "--input-type=module", "-e", script, json.dumps(arguments)],
                                capture_output=True, text=True, check=True)
        return result.stdout

    def attempt_fixture(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        results = ["completed"] * 10 + ["failed"] + ["skipped"] * 7
        captures = [{"capture_id": f"c{index:04}", "result": result}
                    for index, result in enumerate(results, 1)]
        return {"planned": 18, "completed": 10, "failed": 1, "skipped": 7}, captures

    def test_failure_and_skipped_counts_are_retained(self) -> None:
        self.assertEqual(self.call_builder("validateAttemptSummary", *self.attempt_fixture()), "PASS")

    def test_summary_cannot_hide_failed_capture(self) -> None:
        summary, captures = self.attempt_fixture()
        summary.update({"completed": 11, "failed": 0})
        self.assertEqual(self.call_builder("validateAttemptSummary", summary, captures),
                         "ATTEMPT_SUMMARY_COUNT_MISMATCH")

    def test_summary_cannot_hide_missing_capture(self) -> None:
        summary, captures = self.attempt_fixture()
        self.assertEqual(self.call_builder("validateAttemptSummary", summary, captures[:-1]),
                         "ATTEMPT_PLANNED_COUNT_MISMATCH")

    def self_test_fixture(self) -> dict[str, Any]:
        return {"selected_pilot": "pilot_r8", "real_data_baseline_passed": True,
                "original_evidence_modified": False, "tests": 8, "passed": 8,
                "rejected_mutations": [f"independent-negative-{index}" for index in range(7)]}

    def test_current_complete_self_test_is_accepted(self) -> None:
        self.assertEqual(self.call_builder("validateVerifierSelfTest", self.self_test_fixture(), "pilot_r8"),
                         "PASS")

    def test_prior_attempt_self_test_is_rejected(self) -> None:
        report = self.self_test_fixture()
        report["selected_pilot"] = "pilot_r7"
        self.assertEqual(self.call_builder("validateVerifierSelfTest", report, "pilot_r8"),
                         "SELECTED_VERIFIER_SELF_TEST_REQUIRED")

    def test_failed_negative_test_is_rejected(self) -> None:
        report = self.self_test_fixture()
        report["passed"] = 7
        self.assertEqual(self.call_builder("validateVerifierSelfTest", report, "pilot_r8"),
                         "SELECTED_VERIFIER_SELF_TEST_REQUIRED")


class ReportLockTests(unittest.TestCase):
    """A passed report must name its attempt and the bytes it validated."""

    def test_report_names_selected_attempt_and_input_hashes(self) -> None:
        hashes = {"pilot_r4/captures.jsonl": "a" * 64}
        with tempfile.TemporaryDirectory(prefix="rba-report-test-") as directory:
            root = Path(directory)
            with patch.object(verifier, "input_hashes", return_value=hashes), patch.object(
                verifier, "verify_locked", return_value={"verification": "passed"}
            ):
                result = verifier.verify(root, root / "pilot_r4/session_provenance.jsonl", "pilot_r4")
        self.assertEqual(result["selected_pilot"], "pilot_r4")
        self.assertEqual(result["input_file_sha256"], hashes)

    def test_input_changes_during_verification_are_rejected(self) -> None:
        with patch.object(verifier, "input_hashes", side_effect=[{"input": "a" * 64}, {"input": "b" * 64}]), patch.object(
            verifier, "verify_locked", return_value={"verification": "passed"}
        ):
            with self.assertRaisesRegex(verifier.VerificationError, "^INPUT_CHANGED_DURING_VERIFICATION$"):
                verifier.verify(Path("synthetic-root"), Path("synthetic-provenance"), "pilot_r4")

    def test_active_batch_returning_before_report_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rba-report-test-") as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data/active_collection_batch.json").write_text("{}", encoding="utf-8")
            with patch.object(verifier, "input_hashes", return_value={}), patch.object(
                verifier, "verify_locked", return_value={"verification": "passed"}
            ):
                with self.assertRaisesRegex(verifier.VerificationError, "^ACTIVE_BATCH_MARKER_PRESENT$"):
                    verifier.verify(root, root / "pilot_r4/session_provenance.jsonl", "pilot_r4")


if __name__ == "__main__":
    unittest.main()
