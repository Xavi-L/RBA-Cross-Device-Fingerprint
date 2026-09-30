#!/usr/bin/env python3
"""Bounded local collection orchestrator. Service/device startup belongs to the operator."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

from runtime_analysis import campaign_plan, smoke_plan, describe_payload, payload_issues, summarize_sessions

PACKAGE = "com.example.hybridguard.featureapp"
HERE = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def append_json(path, value):
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_jsonl(path, offset=0):
    path = Path(path)
    if not path.exists():
        return []
    result = []
    with path.open("rb") as stream:
        stream.seek(offset)
        while True:
            start = stream.tell()
            line = stream.readline()
            if not line or not line.endswith(b"\n"):
                break
            if line.strip():
                result.append((start, json.loads(line)))
    return result


def file_size(path):
    return Path(path).stat().st_size if Path(path).exists() else 0


def load_config(path):
    config = json.loads(Path(path).read_text())
    paths = config["paths"]
    for name in ("root", "output_dir", "adb", "node", "tool_node_dir", "curl_bin_dir", "release_manifest"):
        if not Path(paths[name]).is_absolute():
            raise ValueError(f"paths.{name} must be absolute")
    if config["endpoint"] != "http://127.0.0.1:8000/api/collect/fingerprint":
        raise ValueError("Frozen low-level runner requires local receiver port 8000")
    paths.setdefault("runner", str(Path(paths["root"]) / "hybridguard-browser-fingerprint-research/execution_log/tools/week6_webview_automation_runner.mjs"))
    paths.setdefault("backend_jsonl", str(Path(paths["output_dir"]) / "backend/expanded_collected_data.jsonl"))
    paths.setdefault("raw_jsonl", str(Path(paths["output_dir"]) / "backend/raw_expanded_payloads.jsonl"))
    output = Path(paths["output_dir"]).resolve()
    for key in ("backend_jsonl", "raw_jsonl"):
        if not Path(paths[key]).resolve().is_relative_to(output):
            raise ValueError(f"paths.{key} must stay in this isolated output directory")
    return config


class Campaign:
    def __init__(self, config):
        self.config = config
        self.paths = config["paths"]
        self.output = Path(self.paths["output_dir"])
        self.release = json.loads(Path(self.paths["release_manifest"]).read_text())
        catalog_path = Path(self.paths["root"]) / self.release["field_catalog"]["path"]
        with catalog_path.open(newline="") as catalog:
            self.field_paths = {
                row["field"] for row in csv.DictReader(catalog)
                if row["field"].startswith(("android_native_data.", "webview_data.", "web_data."))
            }
        if len(self.field_paths) != self.release["fixed_signal_count"]:
            raise ValueError("Release catalog does not contain its declared field count")
        self.output.mkdir(parents=True, exist_ok=True)
        self.command_number = 0

    def freeze(self):
        frozen = self.output / "protocol_snapshot.json"
        if frozen.exists():
            if json.loads(frozen.read_text()) != self.config:
                raise ValueError("Protocol changed after the first collection attempt")
        else:
            write_json(frozen, self.config, exclusive=True)
            write_json(self.output / "release_snapshot.json", self.release, exclusive=True)
            write_json(self.output / "plan.json", [smoke_plan(self.config["campaign_id"])] + campaign_plan(self.config["campaign_id"]), exclusive=True)
        if json.loads((self.output / "release_snapshot.json").read_text()) != self.release:
            raise ValueError("Release manifest changed after protocol freeze")

    def command(self, argv, step_dir, env=None, timeout=35, required=True):
        self.command_number += 1
        prefix = step_dir / f"command-{self.command_number:03d}"
        receipt = {"argv": [str(value) for value in argv], "started_at": now(), "timeout_seconds": timeout, "status": "STARTED"}
        write_json(prefix.with_suffix(".json"), receipt, exclusive=True)
        with prefix.with_suffix(".stdout.txt").open("wb") as stdout, prefix.with_suffix(".stderr.txt").open("wb") as stderr:
            try:
                process = subprocess.Popen(argv, cwd=self.output, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
                return_code = process.wait(timeout=timeout)
                receipt.update(return_code=return_code, status="COMPLETED" if return_code == 0 else "FAILED")
            except subprocess.TimeoutExpired:
                import signal
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                receipt.update(return_code=process.returncode, status="TIMEOUT")
            except OSError as error:
                receipt.update(return_code=None, status="FAILED", error=str(error))
            finally:
                receipt["finished_at"] = now()
                write_json(prefix.with_suffix(".json"), receipt)
        if required and receipt["status"] != "COMPLETED":
            raise RuntimeError(f"Command failed ({receipt['status']}): {prefix.name}")
        return prefix.with_suffix(".stdout.txt").read_text(errors="replace")

    def adb(self, args, step_dir, required=True):
        return self.command([self.paths["adb"], "-s", self.config["serial"], *args], step_dir, required=required)

    def launch_direct(self, step, step_dir, controlled=False):
        self.adb(["shell", "am", "force-stop", PACKAGE], step_dir)
        args = ["shell", "am", "start", "-n", f"{PACKAGE}/.MainActivity",
                "--es", f"{PACKAGE}.COLLECT_ENDPOINT", self.config["endpoint"],
                "--es", f"{PACKAGE}.RUNTIME_CONTEXT", step["runtime_context"],
                "--ei", f"{PACKAGE}.COLLECTION_ROUND", str(step["round"]),
                "--es", f"{PACKAGE}.DEVICE_MANIFEST_ID", self.config["device_manifest_id"]]
        if controlled:
            args += ["--ez", f"{PACKAGE}.ENABLE_WEBVIEW_DEBUG", "true",
                     "--ez", f"{PACKAGE}.WAIT_FOR_WEBVIEW_CONTROL", "true",
                     "--el", f"{PACKAGE}.PROBE_DELAY_MS", "60000"]
        self.adb(args, step_dir)

    def run_transport_control(self, step, step_dir):
        self.launch_direct(step, step_dir, controlled=True)
        time.sleep(2.5)
        pids = self.adb(["shell", "pidof", PACKAGE], step_dir).strip().split()
        sockets = self.adb(["shell", "cat", "/proc/net/unix"], step_dir)
        matching = [pid for pid in pids if f"webview_devtools_remote_{pid}" in sockets]
        if len(matching) != 1:
            raise RuntimeError("Expected exactly one FeatureApp debugging socket")
        self.adb(["forward", "tcp:9222", f"localabstract:webview_devtools_remote_{matching[0]}"], step_dir)
        self.command([self.paths["node"], str(HERE / "cdp_transport_control.mjs"),
                      "http://127.0.0.1:9222", str(step_dir / "control_receipt.json")], step_dir, timeout=60)

    def run_injection(self, step, step_dir):
        overrides = {
            "WEEK6_ADB": self.paths["adb"], "WEEK6_ADB_SERIAL": self.config["serial"],
            "HYBRIDGUARD_BACKEND_JSONL": self.paths["backend_jsonl"],
            "HYBRIDGUARD_AUTOMATION_LOG_DIR": str(step_dir / "automation"),
            "HYBRIDGUARD_TOOL_NODE_DIR": self.paths["tool_node_dir"],
            "HYBRIDGUARD_COLLECTION_ENDPOINT": self.config["endpoint"],
            "HYBRIDGUARD_EXPECTED_SCHEMA": self.release["schema_version"],
            "HYBRIDGUARD_PAIRED_MODE": "1",
            "WEEK7_RUNTIME_CONTEXT": step["runtime_context"],
            "WEEK7_COLLECTION_ROUND": str(step["round"]),
            "WEEK7_DEVICE_MANIFEST_ID": self.config["device_manifest_id"],
            "PATH": self.paths["curl_bin_dir"] + os.pathsep + os.environ.get("PATH", ""),
        }
        write_json(step_dir / "runner_environment.json", overrides, exclusive=True)
        self.command([self.paths["node"], self.paths["runner"], step["configuration"]],
                     step_dir, env={**os.environ, **overrides}, timeout=150)
        logs = list((step_dir / "automation").glob("*.json"))
        if len(logs) != 1:
            raise RuntimeError("Expected exactly one low-level runner receipt")
        result = json.loads(logs[0].read_text())
        if result.get("status") != "MEASURED" or result.get("configurationId") != step["configuration"]:
            raise RuntimeError(f"Low-level runner did not observe its declared profile: {result.get('status')}")
        return result

    def wait_for_payload(self, step, starts, timeout=75):
        deadline = time.monotonic() + timeout
        found_at = None
        while time.monotonic() < deadline:
            raw = [(offset, row) for offset, row in read_jsonl(self.paths["raw_jsonl"], starts["raw"])
                   if (row.get("canonical_received_payload", {}).get("collection_manifest") or {}).get("runtime_context") == step["runtime_context"]]
            exported = [row for _, row in read_jsonl(self.paths["backend_jsonl"], starts["export"])
                        if (row.get("collection_manifest") or {}).get("runtime_context") == step["runtime_context"]]
            if len(raw) > 1 or len(exported) > 1:
                raise RuntimeError("Ambiguous multiple payloads for one planned launch")
            if len(raw) == len(exported) == 1:
                if raw[0][1].get("session_id") != exported[0].get("session_id"):
                    raise RuntimeError("Raw/export session mismatch")
                if found_at is None:
                    found_at = time.monotonic()
                if time.monotonic() - found_at >= 1:
                    return raw[0], exported[0]
            time.sleep(0.25)
        raise RuntimeError("No unique fresh raw/export pair arrived before the deadline")

    def collect(self, step):
        step_dir = self.output / "attempts" / step["step_id"]
        step_dir.mkdir(parents=True, exist_ok=False)
        starts = {"raw": file_size(self.paths["raw_jsonl"]), "export": file_size(self.paths["backend_jsonl"])}
        receipt = {**step, "started_at": now(), "status": "STARTED", "file_start_offsets": starts}
        write_json(step_dir / "attempt.json", receipt, exclusive=True)
        print(f"START {step['step_id']}", flush=True)
        try:
            evidence = None
            if step["configuration"]:
                evidence = self.run_injection(step, step_dir)
            elif step["debug_transport_only"]:
                self.run_transport_control(step, step_dir)
            else:
                self.launch_direct(step, step_dir)
            (raw_offset, raw), exported = self.wait_for_payload(step, starts)
            payload = raw["canonical_received_payload"]
            issues = payload_issues(payload, step, self.config, self.release, self.field_paths)
            if raw.get("session_id") != payload.get("session_id"):
                issues.append("raw_envelope_session_mismatch")
            if exported.get("collection_observations") != payload.get("collection_observations"):
                issues.append("raw_export_observation_mismatch")
            if evidence and evidence.get("measuredSessionIds") != [payload.get("session_id")]:
                issues.append("runner_measured_session_mismatch")
            observation = describe_payload(payload)
            prior = [row for _, row in read_jsonl(self.output / "sessions.jsonl")]
            if any(row["observation"]["session_id"] == payload.get("session_id") for row in prior):
                issues.append("session_reused")
            if prior and prior[0]["observation"]["identity"] != observation["identity"]:
                issues.append("stable_environment_identity_changed")
            session = {**step, "accepted": not issues, "issues": issues, "raw_archive_byte_offset": raw_offset,
                       "raw_archive": self.paths["raw_jsonl"], "observation": observation}
            append_json(self.output / "sessions.jsonl", session)
            receipt["session_id"] = payload.get("session_id")
            if issues:
                raise RuntimeError("; ".join(issues))
            receipt["status"] = "ACCEPTED"
            print(f"ACCEPT {step['step_id']} {receipt['session_id']}", flush=True)
        except Exception as error:
            receipt.update(status="FAILED", error=str(error), traceback=traceback.format_exc())
            write_json(step_dir / "error.json", receipt, exclusive=True)
            raise
        finally:
            receipt.update(finished_at=now(), file_end_offsets={"raw": file_size(self.paths["raw_jsonl"]), "export": file_size(self.paths["backend_jsonl"])})
            write_json(step_dir / "attempt.json", receipt)
            # Same dedicated AVD only; leave every payload and failed command log intact.
            self.adb(["shell", "am", "force-stop", PACKAGE], step_dir, required=False)
            if step["configuration"] or step["debug_transport_only"]:
                port = "9226" if step["configuration"] == "stealth_languages_only_v1" else "9222"
                self.adb(["forward", "--remove", f"tcp:{port}"], step_dir, required=False)

    def analyze(self):
        sessions = [row for _, row in read_jsonl(self.output / "sessions.jsonl")]
        summary = summarize_sessions(sessions, campaign_plan(self.config["campaign_id"]))
        attempts = [json.loads(path.read_text()) for path in sorted((self.output / "attempts").glob("*/attempt.json"))]
        summary.update(attempts_started=len(attempts), failed_attempts=sum(row["status"] == "FAILED" for row in attempts),
                       incomplete_attempts=sum(row["status"] == "STARTED" for row in attempts),
                       raw_archive_rows=len(read_jsonl(self.paths["raw_jsonl"])),
                       total_planned_sessions=31, analyzed_at=now())
        summary["status"] = "COMPLETE" if len(sessions) == 31 and summary["accepted_sessions"] == 31 and summary["failed_attempts"] == 0 else "INCOMPLETE_OR_FAILED"
        write_json(self.output / "SUMMARY.json", summary)
        return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--stage", choices=("smoke", "campaign", "analyze"), required=True)
    args = parser.parse_args()
    campaign = Campaign(load_config(args.config))
    if args.stage == "analyze":
        print(json.dumps(campaign.analyze(), ensure_ascii=False, indent=2))
        return
    campaign.freeze()
    if args.stage == "campaign":
        smoke_receipt = campaign.output / "attempts/smoke/attempt.json"
        if not smoke_receipt.exists() or json.loads(smoke_receipt.read_text()).get("status") != "ACCEPTED":
            raise RuntimeError("Campaign requires its single successful smoke attempt")
    write_json(campaign.output / f"{args.stage.upper()}_STARTED.json", {"at": now()}, exclusive=True)
    try:
        steps = [smoke_plan(campaign.config["campaign_id"])] if args.stage == "smoke" else campaign_plan(campaign.config["campaign_id"])
        for step in steps:
            campaign.collect(step)
    finally:
        campaign.analyze()


if __name__ == "__main__":
    main()
