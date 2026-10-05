"""Contract tests for the Agent Runtime's isolated, read-only API router."""

from __future__ import annotations

import json
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

try:
    from agent_runtime_api import create_agent_runtime_router
except ModuleNotFoundError:
    from backend_server.agent_runtime_api import create_agent_runtime_router


def runtime_payload() -> dict:
    """A valid inline v2.2-style payload with unique raw leak sentinels."""
    return {
        "session_id": "runtime-session-secret-9f3c1b",
        "client_ip": "203.0.113.99",
        "collector_app": "featureapp",
        "schema_version": "expanded-v2.2-status",
        "android_native_data": {
            "build_fingerprint_layer": {
                "os_version": "14",
                "device_model": "RuntimeSensitiveModel-9f3c1b",
                "build_fingerprint": "runtime-build-fingerprint-secret-9f3c1b",
                "build_tags": "release-keys",
                "build_type": "user",
            },
            "sensor_matrix_layer": {"sensor_total_count": 13},
            "battery_dynamics_layer": {"battery_level_pct": 62, "is_charging": False},
            "security_config_layer": {"is_adb_enabled": False},
        },
        "webview_data": {
            "bridge_routing_layer": {"jsbridge_injected": True},
            "kernel_container_layer": {
                "system_http_agent": "RuntimeHttpAgentSecret Android 14 9f3c1b",
                "default_ua_native": "RuntimeDefaultUaSecret Android 14 9f3c1b",
            },
            "host_security_layer": {
                "is_debuggable": False,
                "is_cleartext_traffic_permitted": False,
                "installer_package": "com.android.vending",
            },
        },
        "web_data": {
            "navigator_layer": {
                "user_agent": "RuntimeWebUaSecret Android 14 9f3c1b",
                "platform": "Linux armv8l",
                "max_touch_points": 5,
            },
            "execution_layer": {"timezone_offset": 480},
        },
    }


class AgentRuntimeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(create_agent_runtime_router())
        self.client = TestClient(app)

    def test_readiness_is_available_without_main_startup(self) -> None:
        response = self.client.get("/api/agent/readiness")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ready")
        self.assertTrue(body["deterministic_only"])
        self.assertFalse(body["decision_persistence"])
        self.assertEqual(body["calibration_status"], "not_available")

    def test_runtime_only_application_mounts_the_router_without_collector_lifecycle(self) -> None:
        from backend_server.agent_runtime_app import app as runtime_only_app

        routes = {route.path for route in runtime_only_app.routes}
        self.assertIn("/api/agent/readiness", routes)
        self.assertIn("/api/agent/analyze", routes)

    def test_summary_is_redacted_and_uncalibrated(self) -> None:
        response = self.client.post(
            "/api/agent/analyze",
            json={"trace_detail": "summary", "payload": runtime_payload()},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "completed")
        self.assertIsNone(body["decision"]["calibrated_risk_score"])
        self.assertEqual(body["decision"]["calibration_status"], "not_available")
        self.assertNotIn("evidence_bundle", body)
        self.assertNotIn("context_pack", body)
        self.assertTrue(body["decision_trace"]["verification"]["valid"])
        rendered = json.dumps(body, ensure_ascii=False)
        for raw_value in (
            "runtime-session-secret-9f3c1b",
            "203.0.113.99",
            "RuntimeSensitiveModel-9f3c1b",
            "runtime-build-fingerprint-secret-9f3c1b",
            "RuntimeHttpAgentSecret Android 14 9f3c1b",
            "RuntimeDefaultUaSecret Android 14 9f3c1b",
            "RuntimeWebUaSecret Android 14 9f3c1b",
        ):
            self.assertNotIn(raw_value, rendered)

    def test_full_trace_has_no_raw_values_and_is_not_persisted(self) -> None:
        response = self.client.post(
            "/api/agent/analyze",
            json={"trace_detail": "full", "payload": runtime_payload()},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIn("evidence_bundle", body)
        self.assertTrue(body["decision_trace"]["verification"]["valid"])
        self.assertFalse(body["decision_trace"]["runtime"]["decision_persisted"])
        rendered = json.dumps(body, ensure_ascii=False)
        self.assertNotIn("runtime-build-fingerprint-secret-9f3c1b", rendered)
        self.assertNotIn("RuntimeWebUaSecret Android 14 9f3c1b", rendered)

    def test_extra_and_path_controls_are_rejected(self) -> None:
        extra_response = self.client.post(
            "/api/agent/analyze",
            json={"payload": runtime_payload(), "snapshot_dir": "/private/tmp/not-allowed"},
        )
        self.assertEqual(extra_response.status_code, 422)

        payload_with_path = runtime_payload()
        payload_with_path["collection_manifest"] = {"snapshot_path": "/private/tmp/not-allowed"}
        path_response = self.client.post(
            "/api/agent/analyze",
            json={"payload": payload_with_path},
        )
        self.assertEqual(path_response.status_code, 422)

    def test_unknown_trace_detail_is_rejected_by_request_contract(self) -> None:
        response = self.client.post(
            "/api/agent/analyze",
            json={"trace_detail": "verbose", "payload": runtime_payload()},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
