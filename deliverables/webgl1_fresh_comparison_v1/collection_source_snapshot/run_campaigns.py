#!/usr/bin/env python3
"""Fresh v14 cohort through original attack runners; one owned read-only AVD at a time."""
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SDK = Path.home() / "Library/Android/sdk"
OLD = ROOT / "deliverables/rule_semantics_raw_only_expansion_v1"
sys.dont_write_bytecode = True
sys.path.insert(0, str(OLD))
from run_expansion import Expansion, REGISTRY, plan
from run_local_campaign import Campaign, load_config, read_jsonl, write_json, now
from runtime_analysis import smoke_plan

PACKAGE = "com.example.hybridguard.featureapp"
PORTS = (8000, 9222, 9223, 9224, 9226, 9333, 5670, 5671)


class FreshCampaign(Expansion):
    def __init__(self, config):
        super().__init__(config)
        self.installation = None

    def freeze(self):
        # New installation binding is observed once in the excluded smoke.
        # Never copy an installation ID or sessions from an earlier study.
        write_json(self.output / "protocol_snapshot.json", self.config, exclusive=True)
        write_json(self.output / "release_snapshot.json", self.release, exclusive=True)
        write_json(self.output / "configurations_snapshot.json", REGISTRY, exclusive=True)
        write_json(self.output / "plan.json", [smoke_plan(self.config["campaign_id"])] + plan(self.config), exclusive=True)

    def collect(self, step):
        self.active_configuration = step["configuration"]
        check_dir = self.output / "launch_checks" / step["step_id"]
        check_dir.mkdir(parents=True, exist_ok=False)
        self.adb(["shell", "am", "force-stop", PACKAGE], check_dir)
        stable = 0
        for _ in range(30):
            processes = self.adb(["shell", "ps", "-A", "-o", "PID,NAME"], check_dir)
            live = any(line.split()[-1:] == [PACKAGE] for line in processes.splitlines())
            stable = 0 if live else stable + 1
            if stable == 2:
                break
            time.sleep(0.2)
        if stable != 2:
            raise RuntimeError("Previous App process did not exit")
        # Reuse original capture/receipt/raw-status validation and independently
        # registered tool execution. No WebGL candidate is evaluated here.
        Campaign.collect(self, step)
        session = read_jsonl(self.output / "sessions.jsonl")[-1][1]
        identity = session["observation"]["identity"]
        if identity["android_api"] != self.config["expected_android_api"]:
            raise RuntimeError("Environment API differs from registration")
        if self.installation is None:
            if step["step_id"] != "smoke":
                raise RuntimeError("Independent smoke required before primary positions")
            self.installation = identity
            write_json(self.output / "SOURCE_REGISTRATION.json", {
                "source_reference": "deliverables/webgl1_fresh_comparison_v1/PROTOCOL.json",
                "environment_group_id": self.config["environment_group_id"],
                "identity": identity, "smoke_session_id": session["observation"]["session_id"],
                "binding_rule": "FIRST_NEW_INSTALL_SMOKE_THEN_REQUIRE_STABLE",
                "independent_of_candidate_state": True,
            }, exclusive=True)
        elif identity != self.installation:
            raise RuntimeError("Collector installation/environment changed")


def run_environment(environment, protocol):
    eid = environment["environment_group_id"]
    config = load_config(HERE / ("config_" + eid + ".json"))
    output = Path(config["paths"]["output_dir"])
    output.mkdir(parents=True, exist_ok=False)
    record = {"environment_group_id": eid, "started_at": now(), "status": "STARTED", "commands": []}
    lifecycle = output / "LIFECYCLE.json"
    write_json(lifecycle, record, exclusive=True)
    receiver = emulator = None
    campaign = None

    def command(args, label, timeout=45):
        result = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=timeout)
        (output / (label + ".log")).write_text(result.stdout + result.stderr)
        record["commands"].append({"argv": list(map(str, args)), "returncode": result.returncode, "log": label + ".log"})
        write_json(lifecycle, record)
        if result.returncode:
            raise RuntimeError(label + " failed")
        return result.stdout

    adb = [config["paths"]["adb"], "-s", config["serial"]]
    try:
        for port in PORTS:
            with socket.socket() as check:
                if check.connect_ex(("127.0.0.1", port)) == 0:
                    raise RuntimeError(f"Port {port} is already occupied")
        args = [str(SDK / "emulator/emulator"), "-avd", environment["avd_name"], "-port", "5670",
                "-read-only", "-no-window", "-no-audio", "-no-snapshot", "-no-boot-anim", "-gpu", environment["gpu"]]
        record["emulator_command"] = args
        with (output / "emulator.log").open("x") as log:
            emulator = subprocess.Popen(args, env={**os.environ, "ANDROID_SDK_ROOT": str(SDK),
                "ANDROID_AVD_HOME": str(ROOT / environment["avd_home"])}, stdout=log, stderr=subprocess.STDOUT)
        record["emulator_pid"] = emulator.pid
        deadline = time.monotonic() + protocol["limits"]["boot_seconds"]
        while time.monotonic() < deadline:
            if emulator.poll() is not None:
                raise RuntimeError("Owned emulator exited during startup")
            boot = subprocess.run(adb + ["shell", "getprop", "sys.boot_completed"], capture_output=True, text=True, timeout=8)
            if boot.stdout.strip() == "1":
                break
            time.sleep(1)
        else:
            raise TimeoutError("Boot timeout")
        assert command(adb + ["shell", "getprop", "ro.build.version.sdk"], "android-api").strip() == str(environment["android_api"])
        provider = command(adb + ["shell", "dumpsys", "webviewupdate"], "webview-provider")
        assert f"({environment['expected_webview_package']}, {environment['expected_webview_version']})" in provider
        command(adb + ["install", "-r", str(ROOT / protocol["collector"]["apk"]["path"])], "install", 60)
        command(adb + ["shell", "pm", "clear", PACKAGE], "clear-owned-ephemeral-app-data")
        package = command(adb + ["shell", "dumpsys", "package", PACKAGE], "installed-package")
        assert re.search(r"versionCode=(\d+)", package).group(1) == "14"
        assert "versionName=" + protocol["collector"]["version_name"] in package
        command(adb + ["reverse", "tcp:8000", "tcp:8000"], "reverse")
        args = [str(ROOT / "backend_server/.venv-collection/bin/python"), "-B", "-m", "uvicorn", "main:app",
                "--host", "127.0.0.1", "--port", "8000", "--workers", "1"]
        record["receiver_command"] = args
        with (output / "receiver.log").open("x") as log:
            receiver = subprocess.Popen(args, cwd=ROOT / "backend_server", env={**os.environ,
                "HYBRIDGUARD_DATA_DIR": str(output / "backend"), "PYTHONDONTWRITEBYTECODE": "1"}, stdout=log, stderr=subprocess.STDOUT)
        record["receiver_pid"] = receiver.pid
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if receiver.poll() is not None:
                raise RuntimeError("Receiver exited during startup")
            if "Application startup complete" in (output / "receiver.log").read_text():
                break
            time.sleep(0.2)
        else:
            raise TimeoutError("Receiver startup timeout")
        write_json(output / "environment.json", {**environment, "app_code": 14,
            "app_version": protocol["collector"]["version_name"], "webview_package": environment["expected_webview_package"],
            "webview_version": environment["expected_webview_version"], "android_sdk": environment["android_api"],
            "read_only_owned_avd": True, "source": "android-api.log, webview-provider.log, installed-package.log"}, exclusive=True)
        campaign = FreshCampaign(config)
        campaign.freeze()
        deadline = time.monotonic() + protocol["limits"]["environment_seconds"]
        for step in [smoke_plan(config["campaign_id"])] + plan(config):
            if time.monotonic() > deadline:
                raise TimeoutError("Predeclared environment time limit")
            if receiver.poll() is not None or emulator.poll() is not None:
                raise RuntimeError("Owned runtime exited")
            campaign.collect(step)
        record["status"] = "COMPLETE"
    except Exception as error:
        record.update(status="FAILED_OR_INCOMPLETE", error=f"{type(error).__name__}: {error}")
    finally:
        if campaign:
            try:
                record["summary"] = campaign.analyze()
                if record["summary"]["status"] != "COMPLETE":
                    record["status"] = "FAILED_OR_INCOMPLETE"
            except Exception as error:
                record.update(status="FAILED_OR_INCOMPLETE", summary_error=f"{type(error).__name__}: {error}")
        for process, kind in ((receiver, "receiver"), (emulator, "emulator")):
            try:
                if process is not None and process.poll() is None:
                    process.send_signal(signal.SIGINT if kind == "receiver" else signal.SIGTERM)
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            except Exception as error:
                record.update(status="FAILED_OR_INCOMPLETE")
                record[kind + "_cleanup_error"] = f"{type(error).__name__}: {error}"
            finally:
                record[kind + "_returncode"] = process.poll() if process else None
        record["finished_at"] = now()
        write_json(lifecycle, record)
    print(json.dumps({"environment": eid, "status": record["status"], "error": record.get("error")}), flush=True)
    return record


def preflight(protocol):
    registry = json.loads((HERE / "CONFIGURATIONS.json").read_text())
    assert {r["id"]: r for r in registry} == REGISTRY
    assert len(protocol["configuration_ids"]) == 14
    counts = []
    for env in protocol["environments"]:
        config = load_config(HERE / ("config_" + env["environment_group_id"] + ".json"))
        positions = plan(config)
        assert len(positions) == 126 and len({p["step_id"] for p in positions}) == 126
        assert config["additional_configurations"] == protocol["configuration_ids"]
        assert config["expected_collector_install_id"] is None
        counts.append(len(positions))
    assert sum(counts) == protocol["expected_primary_n"] == 378
    with zipfile.ZipFile(ROOT / protocol["collector"]["apk"]["path"]) as apk:
        for name, source in {
            "canonical_web_probe.js": "web_probe/canonical_web_probe.js",
            "webgl_parameter_observer.js": "web_probe/webgl_parameter_observer.js",
            "expanded_webview_adapter.js": "android_app/HybridGuard/featureapp/src/main/assets/expanded_webview_adapter.js",
            "expanded_probe.html": "android_app/HybridGuard/featureapp/src/main/assets/expanded_probe.html",
        }.items():
            assert apk.read("assets/" + name) == (ROOT / source).read_bytes(), name
    return {"status": "PASS", "primary_positions": sum(counts), "smoke_positions": len(counts),
            "apk_assets_match_reviewed_collector": True, "registry_matches_existing_runners": True}


if __name__ == "__main__":
    protocol = json.loads((HERE / "PROTOCOL.json").read_text())
    checked = preflight(protocol)
    if "--preflight" in sys.argv:
        print(json.dumps(checked))
        raise SystemExit(0)
    write_json(HERE / "STARTED.json", {"started_at": now(), "protocol": protocol, "preflight": checked}, exclusive=True)
    snapshot = HERE / "collection_source_snapshot"
    snapshot.mkdir(exist_ok=False)
    for name in ("PROTOCOL.json", "CONFIGURATIONS.json", "release_manifest.json", "run_campaigns.py",
                 *("config_" + env["environment_group_id"] + ".json" for env in protocol["environments"])):
        shutil.copyfile(HERE / name, snapshot / name)
    paths = [run_environment(env, protocol) for env in protocol["environments"]]
    write_json(HERE / "FINISHED.json", {"finished_at": now(), "environments": paths}, exclusive=True)
    raise SystemExit(0 if all(r["status"] == "COMPLETE" for r in paths) else 1)
