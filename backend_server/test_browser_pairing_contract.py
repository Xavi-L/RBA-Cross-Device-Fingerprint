import asyncio
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest import mock

from fastapi.testclient import TestClient

import main


FIXED_NOW = 1_800_000_000


def complete_browser_status() -> dict:
    fields = {
        field: "observed"
        for field in sorted(main.BROWSER_EXPECTED_WEB_FIELDS)
    }
    return {
        "status_schema_version": main.BROWSER_FIELD_STATUS_SCHEMA_VERSION,
        "fixed_signal_count": main.EXPECTED_BROWSER_SIGNAL_COUNT,
        "counts": {
            "observed": main.EXPECTED_BROWSER_SIGNAL_COUNT,
            "unsupported_by_os": 0,
            "permission_denied": 0,
            "runtime_error": 0,
            "timeout": 0,
            "not_applicable": 0,
        },
        "fields": fields,
    }


def complete_web_data() -> dict:
    result = {}
    for path in sorted(main.BROWSER_EXPECTED_WEB_FIELDS):
        _, layer_name, field_name = path.split(".", 2)
        result.setdefault(layer_name, {})[field_name] = f"value:{field_name}"
    return result


def browser_payload(pair_id: str, browser_session_id: str = "browser-session-1") -> dict:
    return {
        "pair_id": pair_id,
        "browser_session_id": browser_session_id,
        "timestamp": 1_800_000_001,
        "collector_app": main.BROWSER_COLLECTOR_APP,
        "schema_version": main.BROWSER_PAYLOAD_SCHEMA_VERSION,
        "web_probe_revision": main.BROWSER_WEB_PROBE_REVISION,
        "web_data": complete_web_data(),
        "collection_diagnostics": {
            "diagnostics_schema_version": "browser-probe-diagnostics-v1",
            "probe_statuses": {},
        },
        "collection_status": complete_browser_status(),
        "probe_metadata": {
            "metadata_schema_version": main.BROWSER_PROBE_METADATA_SCHEMA_VERSION,
            "page_origin": "https://xavi-l.github.io",
            "page_path": "/RBA-Cross-Device-Fingerprint/",
            "core_revision": main.BROWSER_WEB_PROBE_REVISION,
            "core_bundle_sha256": main.BROWSER_WEB_PROBE_SHA256,
            "expected_signal_count": main.EXPECTED_BROWSER_SIGNAL_COUNT,
        },
    }


class BrowserPairingContractTests(unittest.TestCase):
    @contextmanager
    def isolated_backend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            original_batch = main.active_collection_batch
            original_pairs = main.browser_pairs_db
            original_requests = main.browser_ticket_requests_db
            main.active_collection_batch = None
            main.browser_pairs_db = {}
            main.browser_ticket_requests_db = {}
            try:
                with (
                    mock.patch.multiple(
                        main,
                        COLLECTION_BATCHES_JSONL_FILE=temp / "collection_batches.jsonl",
                        ACTIVE_COLLECTION_BATCH_STATE_FILE=temp / "active_collection_batch.json",
                        COLLECTION_RECEIPTS_JSONL_FILE=temp / "collection_receipts.jsonl",
                        RAW_EXPANDED_PAYLOADS_JSONL_FILE=temp / "raw_expanded_payloads.jsonl",
                        EXPANDED_COLLECTED_JSONL_FILE=temp / "expanded_collected_data.jsonl",
                        EXPANDED_DB_FILE=temp / "expanded_merged_sessions.json",
                        RAW_BROWSER_PAYLOADS_JSONL_FILE=temp / "raw_browser_payloads.jsonl",
                        BROWSER_PROVISIONAL_PAYLOADS_JSONL_FILE=temp
                        / "browser_provisional_payloads.jsonl",
                        BROWSER_COLLECTED_DATA_JSONL_FILE=temp / "browser_collected_data.jsonl",
                        BROWSER_PAIR_EVENTS_JSONL_FILE=temp / "browser_pair_events.jsonl",
                        BROWSER_PAIR_PROVENANCE_JSONL_FILE=temp
                        / "browser_pair_provenance.jsonl",
                        BROWSER_TOKEN_HMAC_KEY=b"browser-contract-test-secret",
                        expanded_sessions_db={},
                    ),
                    mock.patch.object(main, "browser_token_now", return_value=FIXED_NOW),
                ):
                    batch = main.start_collection_batch()
                    receipt = {
                        "receipt_schema_version": "collection-receipt-v1",
                        "receipt_id": "app-receipt-1",
                        "server_received_at": "2027-01-15T08:00:00Z",
                        "session_id": "app-session-1",
                        "payload_sha256": "a" * 64,
                        "collector_app": "featureapp",
                        "schema_version": "expanded-v2.2-status",
                        "stored_new_jsonl_row": True,
                        "duplicate_payload": False,
                        "collection_batch_id": batch["collection_batch_id"],
                        "collection_batch_id_source": main.COLLECTION_BATCH_ID_SOURCE,
                    }
                    main.append_jsonl_durably(
                        receipt,
                        main.COLLECTION_RECEIPTS_JSONL_FILE,
                    )
                    yield temp, batch
                    if main.active_collection_batch is not None:
                        main.close_active_collection_batch()
            finally:
                main.active_collection_batch = original_batch
                main.browser_pairs_db = original_pairs
                main.browser_ticket_requests_db = original_requests

    @staticmethod
    def ticket_request(**overrides) -> main.BrowserTicketRequest:
        data = {
            "app_session_id": "app-session-1",
            "app_receipt_id": "app-receipt-1",
            "app_payload_sha256": "a" * 64,
            "ticket_request_id": "ticket-request-1",
            "resolved_browser_package": "com.android.chrome",
            "selected_browser_package": "com.android.chrome",
            "launch_resolution_status": "available_browser_resolved",
            "selected_browser_activity":
                "com.google.android.apps.chrome.Main",
            "browser_candidate_packages": [
                "com.android.chrome",
                "com.sina.weibo",
            ],
            "browser_selection_policy_revision": "available-browser-v1",
            "web_probe_revision": main.BROWSER_WEB_PROBE_REVISION,
            "browser_probe_base_url":
                "https://xavi-l.github.io/RBA-Cross-Device-Fingerprint/?campaign=test",
        }
        data.update(overrides)
        return main.BrowserTicketRequest(**data)

    @staticmethod
    def provisional_ticket_request(**overrides) -> main.BrowserTicketRequest:
        data = {
            "app_session_id": "provisional-app-session",
            "ticket_request_id": "provisional-ticket-request-1",
            "resolved_browser_package": "com.android.chrome",
            "selected_browser_package": "com.android.chrome",
            "launch_resolution_status": "available_browser_ranked",
            "selected_browser_activity":
                "com.google.android.apps.chrome.Main",
            "browser_candidate_packages": [
                "com.android.chrome",
                "com.sina.weibo",
            ],
            "browser_selection_policy_revision": "available-browser-v1",
            "web_probe_revision": main.BROWSER_WEB_PROBE_REVISION,
            "browser_probe_base_url":
                "https://xavi-l.github.io/RBA-Cross-Device-Fingerprint/?campaign=test",
        }
        data.update(overrides)
        return main.BrowserTicketRequest(**data)

    @staticmethod
    def issue(request=None) -> dict:
        return main.issue_browser_ticket_for_upload_url(
            request or BrowserPairingContractTests.ticket_request(),
            "https://collector.example.test/api/collect/browser-fingerprint",
        )

    @staticmethod
    def collect_provisional_app(
        session_id: str = "provisional-app-session",
        ticket_request_id: str = "provisional-ticket-request-1",
    ) -> dict:
        payload = main.FingerprintPayload(
            session_id=session_id,
            timestamp=1_800_000_002,
            browser_ticket_request_id=ticket_request_id,
            collector_app="featureapp",
            schema_version="expanded-v2.2-status",
            android_native_data={"build_fingerprint_layer": {"device_model": "test"}},
            webview_data={"navigator_layer": {"user_agent": "test"}},
            web_data={"navigator_layer": {"user_agent": "test"}},
        )
        result = asyncio.run(main.collect_fingerprint(payload))
        return result["receipt"]

    @staticmethod
    def jsonl_rows(path: Path) -> list[dict]:
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_ticket_is_bound_to_receipt_idempotent_and_fragment_only(self):
        with self.isolated_backend() as (temp, batch):
            first = self.issue()
            second = self.issue()

            self.assertEqual(first["collection_batch_id"], batch["collection_batch_id"])
            self.assertEqual(first["ticket_binding_mode"], "receipt_bound")
            self.assertEqual(first["pair_id"], second["pair_id"])
            self.assertEqual(first["browser_ticket"], second["browser_ticket"])
            self.assertEqual(first["poll_token"], second["poll_token"])
            self.assertFalse(first["duplicate_ticket_request"])
            self.assertTrue(second["duplicate_ticket_request"])
            pair = main.browser_pairs_db[first["pair_id"]]
            self.assertEqual(
                pair["selected_browser_package"],
                "com.android.chrome",
            )
            self.assertEqual(
                pair["selected_browser_activity"],
                "com.google.android.apps.chrome.Main",
            )
            self.assertEqual(
                pair["browser_candidate_packages"],
                ["com.android.chrome", "com.sina.weibo"],
            )
            self.assertEqual(
                pair["browser_selection_policy_revision"],
                "available-browser-v1",
            )

            parsed = urlsplit(first["probe_url"])
            self.assertEqual(
                parse_qs(parsed.query),
                {"campaign": ["test"]},
            )
            fragment = parse_qs(parsed.fragment)
            self.assertEqual(fragment["pair_id"], [first["pair_id"]])
            self.assertEqual(fragment["browser_ticket"], [first["browser_ticket"]])
            self.assertEqual(
                fragment["browser_upload_url"],
                [first["browser_upload_url"]],
            )
            self.assertEqual(
                fragment["browser_stage_url"],
                [first["browser_stage_url"]],
            )
            self.assertEqual(fragment["launch_attempt"], ["1"])
            self.assertEqual(
                first["browser_stage_url"],
                "https://collector.example.test/api/collect/browser-stage",
            )
            self.assertNotIn("browser_ticket", parsed.query)

            events = self.jsonl_rows(temp / "browser_pair_events.jsonl")
            self.assertEqual(
                [event["event"] for event in events],
                ["ticket_issued", "ticket_request_idempotent_replay"],
            )
            self.assertTrue(
                all("browser_ticket" not in event and "poll_token" not in event for event in events)
            )

            conflicting = self.ticket_request(
                resolved_browser_package="org.mozilla.firefox"
            )
            with self.assertRaises(main.HTTPException) as raised:
                self.issue(conflicting)
            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(
                raised.exception.detail["code"],
                "TICKET_REQUEST_REPLAY_CONFLICT",
            )

    def test_browser_stage_telemetry_distinguishes_app_launch_from_page_load(self):
        with self.isolated_backend() as (temp, _):
            ticket = self.issue()
            launch = main.record_browser_stage(
                main.BrowserStagePayload(
                    pair_id=ticket["pair_id"],
                    stage="launch_attempted",
                    launch_attempt=1,
                    client_stage_at_ms=1_800_000_000_100,
                ),
                ticket["poll_token"],
            )
            page = main.record_browser_stage(
                main.BrowserStagePayload(
                    pair_id=ticket["pair_id"],
                    stage="page_loaded",
                    launch_attempt=1,
                    client_stage_at_ms=1_800_000_000_200,
                ),
                ticket["browser_ticket"],
            )
            duplicate_page = main.record_browser_stage(
                main.BrowserStagePayload(
                    pair_id=ticket["pair_id"],
                    stage="page_loaded",
                    launch_attempt=1,
                ),
                ticket["browser_ticket"],
            )

            self.assertFalse(launch["duplicate_stage"])
            self.assertFalse(page["duplicate_stage"])
            self.assertTrue(duplicate_page["duplicate_stage"])
            poll = main.browser_pair_status_response(
                main.browser_pairs_db[ticket["pair_id"]]
            )
            self.assertEqual(poll["latest_browser_stage"], "page_loaded")
            self.assertEqual(poll["browser_stage_count"], 1)
            self.assertEqual(poll["app_launch_attempt_count"], 1)
            self.assertEqual(poll["latest_launch_attempt"], 1)

            events = self.jsonl_rows(temp / "browser_pair_events.jsonl")
            self.assertEqual(
                [event["event"] for event in events],
                [
                    "ticket_issued",
                    "browser_stage_observed",
                    "browser_stage_observed",
                ],
            )

            with self.assertRaises(main.HTTPException) as wrong_token:
                main.record_browser_stage(
                    main.BrowserStagePayload(
                        pair_id=ticket["pair_id"],
                        stage="page_loaded",
                    ),
                    ticket["poll_token"],
                )
            self.assertEqual(wrong_token.exception.status_code, 403)
            self.assertEqual(
                wrong_token.exception.detail["code"],
                "BROWSER_STAGE_TOKEN_WRONG_USE",
            )

    def test_ticket_receipt_and_hash_must_be_both_present_or_both_absent(self):
        with self.isolated_backend():
            with self.assertRaises(main.HTTPException) as missing_hash:
                self.issue(self.ticket_request(app_payload_sha256=None))
            self.assertEqual(missing_hash.exception.status_code, 422)
            self.assertEqual(
                missing_hash.exception.detail["code"],
                "APP_RECEIPT_BINDING_INCOMPLETE",
            )

            with self.assertRaises(main.HTTPException) as missing_receipt:
                self.issue(
                    self.provisional_ticket_request(
                        app_payload_sha256="a" * 64,
                    )
                )
            self.assertEqual(missing_receipt.exception.status_code, 422)
            self.assertEqual(
                missing_receipt.exception.detail["code"],
                "APP_RECEIPT_BINDING_INCOMPLETE",
            )

    def test_provisional_app_first_binds_before_browser_upload(self):
        with self.isolated_backend() as (temp, batch):
            app_receipt = self.collect_provisional_app()
            ticket = self.issue(self.provisional_ticket_request())

            self.assertEqual(ticket["ticket_binding_mode"], "provisional_session")
            self.assertEqual(ticket["pair_status"], "awaiting_browser")
            self.assertEqual(ticket["collection_batch_id"], batch["collection_batch_id"])
            self.assertEqual(ticket["app_receipt_id"], app_receipt["receipt_id"])
            self.assertEqual(
                ticket["app_payload_sha256"],
                app_receipt["payload_sha256"],
            )

            result = main.store_browser_fingerprint(
                main.BrowserFingerprintPayload(
                    **browser_payload(ticket["pair_id"])
                ),
                ticket["browser_ticket"],
            )
            self.assertEqual(result["pair_status"], "completed")
            self.assertTrue(result["receipt"]["stored_new_jsonl_row"])
            self.assertEqual(
                len(self.jsonl_rows(temp / "browser_provisional_payloads.jsonl")),
                0,
            )
            self.assertEqual(len(self.jsonl_rows(temp / "raw_browser_payloads.jsonl")), 1)
            self.assertEqual(
                len(self.jsonl_rows(temp / "browser_collected_data.jsonl")),
                1,
            )
            self.assertEqual(
                len(self.jsonl_rows(temp / "browser_pair_provenance.jsonl")),
                1,
            )

    def test_provisional_browser_first_stages_then_receipt_finalizes_idempotently(self):
        with self.isolated_backend() as (temp, _):
            ticket = self.issue(self.provisional_ticket_request())
            replayed_ticket = self.issue(self.provisional_ticket_request())
            self.assertEqual(ticket["pair_status"], "awaiting_app_and_browser")
            self.assertEqual(ticket["ticket_binding_mode"], "provisional_session")
            self.assertIsNone(ticket["app_receipt_id"])
            self.assertIsNone(ticket["app_payload_sha256"])
            self.assertEqual(ticket["pair_id"], replayed_ticket["pair_id"])
            self.assertEqual(ticket["browser_ticket"], replayed_ticket["browser_ticket"])
            self.assertTrue(replayed_ticket["duplicate_ticket_request"])

            payload = main.BrowserFingerprintPayload(
                **browser_payload(ticket["pair_id"])
            )
            staged = main.store_browser_fingerprint(
                payload,
                ticket["browser_ticket"],
            )
            duplicate_staged = main.store_browser_fingerprint(
                payload,
                ticket["browser_ticket"],
            )
            self.assertEqual(staged["pair_status"], "awaiting_app")
            self.assertTrue(staged["receipt"]["provisional_payload_staged"])
            self.assertFalse(staged["receipt"]["stored_new_jsonl_row"])
            self.assertTrue(duplicate_staged["duplicate_payload"])
            provisional_rows = self.jsonl_rows(
                temp / "browser_provisional_payloads.jsonl"
            )
            self.assertEqual(len(provisional_rows), 1)
            self.assertEqual(
                provisional_rows[0]["ticket_request_id"],
                ticket["ticket_request_id"],
            )
            self.assertEqual(len(self.jsonl_rows(temp / "raw_browser_payloads.jsonl")), 0)
            self.assertEqual(
                len(self.jsonl_rows(temp / "browser_collected_data.jsonl")),
                0,
            )
            self.assertEqual(
                len(self.jsonl_rows(temp / "browser_pair_provenance.jsonl")),
                0,
            )

            app_receipt = self.collect_provisional_app()
            pair, _ = main.authorize_browser_pair(
                ticket["poll_token"],
                "pair_poll",
                expected_pair_id=ticket["pair_id"],
            )
            poll = main.browser_pair_status_response(pair)
            self.assertEqual(poll["pair_status"], "completed")
            self.assertEqual(poll["app_receipt_id"], app_receipt["receipt_id"])
            self.assertEqual(
                poll["app_payload_sha256"],
                app_receipt["payload_sha256"],
            )

            duplicate_after_binding = main.store_browser_fingerprint(
                payload,
                ticket["browser_ticket"],
            )
            self.assertTrue(duplicate_after_binding["duplicate_payload"])
            duplicate_app_receipt = self.collect_provisional_app()
            self.assertTrue(duplicate_app_receipt["duplicate_payload"])
            self.assertEqual(len(self.jsonl_rows(temp / "raw_browser_payloads.jsonl")), 1)
            self.assertEqual(
                len(self.jsonl_rows(temp / "browser_collected_data.jsonl")),
                1,
            )
            provenance_rows = self.jsonl_rows(
                temp / "browser_pair_provenance.jsonl"
            )
            self.assertEqual(len(provenance_rows), 1)
            self.assertEqual(
                provenance_rows[0]["browser_receipt_id"],
                staged["browser_receipt_id"],
            )
            self.assertEqual(
                provenance_rows[0]["app_receipt_id"],
                app_receipt["receipt_id"],
            )
            self.assertEqual(
                provenance_rows[0]["ticket_request_id"],
                ticket["ticket_request_id"],
            )

    def test_browser_upload_duplicate_and_conflict_have_one_durable_data_row(self):
        with self.isolated_backend() as (temp, _):
            ticket = self.issue()
            payload = main.BrowserFingerprintPayload(
                **browser_payload(ticket["pair_id"])
            )

            initial_pair, _ = main.authorize_browser_pair(
                ticket["poll_token"],
                "pair_poll",
                expected_pair_id=ticket["pair_id"],
            )
            self.assertEqual(
                main.browser_pair_status_response(initial_pair)["pair_status"],
                "awaiting_browser",
            )

            first = main.store_browser_fingerprint(payload, ticket["browser_ticket"])
            duplicate = main.store_browser_fingerprint(payload, ticket["browser_ticket"])
            self.assertFalse(first["duplicate_payload"])
            self.assertTrue(duplicate["duplicate_payload"])
            self.assertEqual(
                first["receipt"]["browser_receipt_id"],
                duplicate["receipt"]["browser_receipt_id"],
            )
            self.assertEqual(
                first["receipt_id"],
                first["receipt"]["browser_receipt_id"],
            )
            self.assertTrue(first["receipt"]["stored_new_jsonl_row"])
            self.assertFalse(duplicate["receipt"]["stored_new_jsonl_row"])

            conflicting_payload = main.BrowserFingerprintPayload(
                **browser_payload(
                    ticket["pair_id"],
                    browser_session_id="different-browser-session",
                )
            )
            with self.assertRaises(main.HTTPException) as raised:
                main.store_browser_fingerprint(
                    conflicting_payload,
                    ticket["browser_ticket"],
                )
            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(
                raised.exception.detail["code"],
                "BROWSER_TICKET_REPLAY_CONFLICT",
            )

            raw_rows = self.jsonl_rows(temp / "raw_browser_payloads.jsonl")
            collected_rows = self.jsonl_rows(temp / "browser_collected_data.jsonl")
            provenance_rows = self.jsonl_rows(temp / "browser_pair_provenance.jsonl")
            self.assertEqual(len(raw_rows), 1)
            self.assertEqual(len(collected_rows), 1)
            self.assertEqual(len(provenance_rows), 1)
            self.assertEqual(
                main.canonical_payload_sha256(raw_rows[0]["canonical_received_payload"]),
                first["receipt"]["browser_payload_sha256"],
            )
            self.assertNotIn("field_statuses", collected_rows[0])
            self.assertEqual(
                collected_rows[0]["collection_status"]["fixed_signal_count"],
                main.EXPECTED_BROWSER_SIGNAL_COUNT,
            )
            self.assertEqual(
                provenance_rows[0]["app_payload_sha256"],
                "a" * 64,
            )
            self.assertEqual(
                provenance_rows[0]["browser_payload_sha256"],
                first["receipt"]["browser_payload_sha256"],
            )

            pair, _ = main.authorize_browser_pair(
                ticket["poll_token"],
                "pair_poll",
                expected_pair_id=ticket["pair_id"],
            )
            poll = main.browser_pair_status_response(pair)
            self.assertEqual(poll["pair_status"], "completed")
            self.assertEqual(
                poll["browser_receipt_id"],
                first["receipt"]["browser_receipt_id"],
            )

    def test_probe_origin_and_core_hash_are_bound_to_deployed_bundle(self):
        with self.isolated_backend():
            ticket = self.issue()
            wrong_origin = browser_payload(ticket["pair_id"])
            wrong_origin["probe_metadata"]["page_origin"] = "https://attacker.example"
            with self.assertRaises(main.HTTPException) as origin_error:
                main.store_browser_fingerprint(
                    main.BrowserFingerprintPayload(**wrong_origin),
                    ticket["browser_ticket"],
                )
            self.assertEqual(
                origin_error.exception.detail["code"],
                "BROWSER_PROBE_PAGE_ORIGIN_MISMATCH",
            )

            wrong_hash = browser_payload(ticket["pair_id"])
            wrong_hash["probe_metadata"]["core_bundle_sha256"] = "0" * 64
            with self.assertRaises(main.HTTPException) as hash_error:
                main.store_browser_fingerprint(
                    main.BrowserFingerprintPayload(**wrong_hash),
                    ticket["browser_ticket"],
                )
            self.assertEqual(
                hash_error.exception.detail["code"],
                "BROWSER_PROBE_CORE_HASH_MISMATCH",
            )

    def test_ticket_rejects_an_untrusted_probe_origin(self):
        with self.isolated_backend():
            request = self.ticket_request(
                browser_probe_base_url="https://attacker.example/probe/"
            )
            with self.assertRaises(main.HTTPException) as raised:
                self.issue(request)
            self.assertEqual(
                raised.exception.detail["code"],
                "BROWSER_PROBE_ORIGIN_NOT_ALLOWED",
            )

    def test_expired_upload_and_cross_batch_tokens_are_rejected(self):
        with self.isolated_backend() as (_, first_batch):
            ticket = self.issue()
            expired_at = FIXED_NOW + main.BROWSER_TICKET_TTL_SECONDS + 1
            with mock.patch.object(
                main,
                "browser_token_now",
                return_value=expired_at,
            ):
                with self.assertRaises(main.HTTPException) as raised:
                    main.store_browser_fingerprint(
                        main.BrowserFingerprintPayload(
                            **browser_payload(ticket["pair_id"])
                        ),
                        ticket["browser_ticket"],
                    )
                self.assertEqual(raised.exception.status_code, 410)
                self.assertEqual(
                    raised.exception.detail["code"],
                    "BROWSER_TOKEN_EXPIRED",
                )
                pair, _ = main.authorize_browser_pair(
                    ticket["poll_token"],
                    "pair_poll",
                    expected_pair_id=ticket["pair_id"],
                )
                self.assertEqual(
                    main.browser_pair_status_response(pair)["pair_status"],
                    "expired",
                )

            main.close_active_collection_batch()
            second_batch = main.start_collection_batch()
            self.assertNotEqual(
                first_batch["collection_batch_id"],
                second_batch["collection_batch_id"],
            )
            with self.assertRaises(main.HTTPException) as raised:
                main.authorize_browser_pair(
                    ticket["poll_token"],
                    "pair_poll",
                    expected_pair_id=ticket["pair_id"],
                )
            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(
                raised.exception.detail["code"],
                "BROWSER_TOKEN_BATCH_MISMATCH",
            )

    def test_hmac_use_and_receipt_hash_bindings_fail_closed(self):
        with self.isolated_backend():
            with self.assertRaises(main.HTTPException) as raised:
                self.issue(
                    self.ticket_request(app_payload_sha256="b" * 64)
                )
            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(
                raised.exception.detail["code"],
                "APP_PAYLOAD_HASH_MISMATCH",
            )

            ticket = self.issue()
            with self.assertRaises(main.HTTPException) as raised:
                main.authorize_browser_pair(
                    ticket["poll_token"],
                    "browser_upload",
                )
            self.assertEqual(raised.exception.status_code, 403)
            self.assertEqual(
                raised.exception.detail["code"],
                "BROWSER_TOKEN_WRONG_USE",
            )

            prefix, payload, signature = ticket["browser_ticket"].split(".")
            replacement = "A" if signature[0] != "A" else "B"
            tampered = f"{prefix}.{payload}.{replacement}{signature[1:]}"
            with self.assertRaises(main.HTTPException) as raised:
                main.decode_browser_token(tampered)
            self.assertEqual(raised.exception.status_code, 401)
            self.assertEqual(
                raised.exception.detail["code"],
                "BROWSER_TOKEN_INVALID",
            )

    def test_status_alias_and_cors_custom_headers_contract(self):
        with self.isolated_backend():
            ticket = self.issue()
            data = browser_payload(ticket["pair_id"])
            data["field_statuses"] = data.pop("collection_status")["fields"]
            result = main.store_browser_fingerprint(
                main.BrowserFingerprintPayload(**data),
                ticket["browser_ticket"],
            )
            self.assertEqual(result["pair_status"], "completed")

        preflight = TestClient(main.app).options(
            "/api/collect/browser-fingerprint",
            headers={
                "Origin": "https://probe.example.test",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": (
                    "authorization,content-type,ngrok-skip-browser-warning"
                ),
            },
        )
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(
            preflight.headers["access-control-allow-origin"],
            "https://probe.example.test",
        )
        allowed_headers = preflight.headers["access-control-allow-headers"].lower()
        self.assertIn("authorization", allowed_headers)
        self.assertIn("content-type", allowed_headers)
        self.assertIn("ngrok-skip-browser-warning", allowed_headers)

        stage_preflight = TestClient(main.app).options(
            "/api/collect/browser-stage",
            headers={
                "Origin": "https://probe.example.test",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": (
                    "authorization,content-type,ngrok-skip-browser-warning"
                ),
            },
        )
        self.assertEqual(stage_preflight.status_code, 200)


if __name__ == "__main__":
    unittest.main()
