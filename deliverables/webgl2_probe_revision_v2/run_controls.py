#!/usr/bin/env python3
"""Bounded benign collection. Uses owned read-only AVDs and an isolated receiver."""
import json
import argparse
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SDK = Path.home() / "Library/Android/sdk"
ADB = SDK / "platform-tools/adb"
SERIAL = "emulator-5670"
PORT = 8765
PACKAGE = "com.example.hybridguard.featureapp"
APK = HERE / "runtime/featureapp-v13-local-only.apk"
AVDS = {
    36: (ROOT / "deliverables/featureapp_webdriver_runtime_v1/runtime/avd", "Codex_Webdriver_Raw_API36_1"),
    29: (ROOT / "deliverables/featureapp_webdriver_raw_multienv_v1/runtime/avd", "Codex_Webdriver_Raw_API29"),
    30: (ROOT / "deliverables/rule_semantics_raw_only_expansion_v1/runtime/avd", "Codex_Webdriver_Raw_API30"),
}


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def cell_run(cell, output_root=HERE, fresh_launch=False):
    name = f"api{cell['api']}_{cell['gpu']}"
    output = output_root / "controls" / name
    output.mkdir(parents=True, exist_ok=False)
    record = {**cell, "started_at": now(), "status": "STARTED", "commands": [], "captures": []}
    lifecycle = output / "LIFECYCLE.json"
    save(lifecycle, record)
    emulator = receiver = None

    def call(args, label, timeout=30):
        args = list(map(str, args))
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        (output / (label + ".log")).write_text(result.stdout + result.stderr)
        record["commands"].append({"argv": args, "returncode": result.returncode, "log": label + ".log"})
        save(lifecycle, record)
        if result.returncode:
            raise RuntimeError(label + " failed")
        return result.stdout

    try:
        for port in (PORT, 5670, 5671):
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    raise RuntimeError(f"Port {port} is already occupied")
        avd_home, avd_name = AVDS[cell["api"]]
        emulator_args = [str(SDK / "emulator/emulator"), "-avd", avd_name, "-port", "5670",
                         "-read-only", "-no-window", "-no-audio", "-no-snapshot", "-no-boot-anim", "-gpu", cell["gpu"]]
        record["emulator_command"] = emulator_args
        with (output / "emulator.log").open("x") as log:
            emulator = subprocess.Popen(emulator_args, env={**os.environ, "ANDROID_AVD_HOME": str(avd_home),
                "ANDROID_SDK_ROOT": str(SDK)}, stdout=log, stderr=subprocess.STDOUT)
        record["emulator_pid"] = emulator.pid
        save(lifecycle, record)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if emulator.poll() is not None:
                raise RuntimeError("Emulator exited during boot")
            boot = subprocess.run([str(ADB), "-s", SERIAL, "shell", "getprop", "sys.boot_completed"],
                                  capture_output=True, text=True, timeout=8)
            if boot.stdout.strip() == "1":
                break
            time.sleep(1)
        else:
            raise TimeoutError("Emulator boot exceeded 120 seconds")
        api = call([ADB, "-s", SERIAL, "shell", "getprop", "ro.build.version.sdk"], "android-api").strip()
        if api != str(cell["api"]):
            raise RuntimeError("Unexpected Android API " + api)
        call([ADB, "-s", SERIAL, "shell", "dumpsys", "webviewupdate"], "webview-provider")
        call([ADB, "-s", SERIAL, "install", "-r", APK], "install", 60)
        call([ADB, "-s", SERIAL, "shell", "pm", "clear", PACKAGE], "clear-ephemeral-app-data")
        call([ADB, "-s", SERIAL, "shell", "dumpsys", "package", PACKAGE], "installed-package")
        call([ADB, "-s", SERIAL, "reverse", f"tcp:{PORT}", f"tcp:{PORT}"], "reverse")
        receiver_args = [str(ROOT / "backend_server/.venv-collection/bin/python"), "-B", "-m", "uvicorn", "main:app",
                         "--host", "127.0.0.1", "--port", str(PORT), "--workers", "1"]
        record["receiver_command"] = receiver_args
        with (output / "receiver.log").open("x") as log:
            receiver = subprocess.Popen(receiver_args, cwd=ROOT / "backend_server",
                env={**os.environ, "HYBRIDGUARD_DATA_DIR": str(output / "backend"), "PYTHONDONTWRITEBYTECODE": "1"},
                stdout=log, stderr=subprocess.STDOUT)
        record["receiver_pid"] = receiver.pid
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if receiver.poll() is not None:
                raise RuntimeError("Receiver exited during startup")
            if "Application startup complete" in (output / "receiver.log").read_text():
                break
            time.sleep(0.2)
        else:
            raise TimeoutError("Receiver startup exceeded 15 seconds")
        raw_path = output / "backend/raw_expanded_payloads.jsonl"
        for launch in range(1, cell["launches"] + 1):
            previous = len(rows(raw_path))
            call([ADB, "-s", SERIAL, "shell", "am", "force-stop", PACKAGE], f"stop-{launch}")
            if fresh_launch:
                stable = 0
                for check in range(30):
                    processes = call([ADB, "-s", SERIAL, "shell", "ps", "-A", "-o", "PID,NAME"], f"process-{launch}-{check}")
                    live = any(line.split()[-1:] == [PACKAGE] for line in processes.splitlines())
                    stable = 0 if live else stable + 1
                    if stable == 2:
                        break
                    time.sleep(0.2)
                if stable != 2:
                    raise RuntimeError("Previous FeatureApp process did not exit")
            launch_args = [ADB, "-s", SERIAL, "shell", "am", "start"]
            if fresh_launch:
                launch_args += ["-S", "-W"]
            started = call([*launch_args, "-n", PACKAGE + "/.MainActivity",
                  "--es", PACKAGE + ".COLLECT_ENDPOINT", f"http://127.0.0.1:{PORT}/api/collect/fingerprint",
                  "--es", PACKAGE + ".RUNTIME_CONTEXT", "benign-webgl2-" + name,
                  "--es", PACKAGE + ".DEVICE_MANIFEST_ID", "webgl2-control-" + name,
                  "--ei", PACKAGE + ".COLLECTION_ROUND", str(launch)], f"start-{launch}")
            if fresh_launch and ("Activity not started" in started or "Status: ok" not in started):
                raise RuntimeError("Fresh Activity launch was not confirmed")
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if len(rows(raw_path)) > previous:
                    break
                time.sleep(0.5)
            else:
                raise TimeoutError(f"Capture {launch} exceeded 45 seconds")
            captured = rows(raw_path)[previous:]
            if len(captured) != 1:
                raise RuntimeError("Expected exactly one new raw payload per launch")
            payload = captured[0]["canonical_received_payload"]
            manifest = payload.get("collection_manifest", {})
            if manifest.get("web_probe_revision") != "expanded-web-67-v2" or manifest.get("collector_version_code") != 13:
                raise RuntimeError("Captured payload does not declare expected probe/App version")
            record["captures"].append({"launch": launch, "raw_line": previous + 1, "session_id": payload["session_id"]})
            save(lifecycle, record)
        call([ADB, "-s", SERIAL, "shell", "am", "force-stop", PACKAGE], "stop-final")
        record["status"] = "COMPLETE"
    except Exception as error:
        record.update(status="FAILED_OR_INCOMPLETE", error=f"{type(error).__name__}: {error}")
    finally:
        for process, label in ((receiver, "receiver"), (emulator, "emulator")):
            if process is not None and process.poll() is None:
                process.send_signal(signal.SIGINT if label == "receiver" else signal.SIGTERM)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            record[label + "_returncode"] = process.returncode if process else None
        record["finished_at"] = now()
        save(lifecycle, record)
    print(json.dumps({"cell": name, "status": record["status"], "captured": len(record["captures"]), "error": record.get("error")}), flush=True)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh-launch-check", action="store_true")
    args = parser.parse_args()
    output_root = HERE / "fresh_launch" if args.fresh_launch_check else HERE
    plan = json.loads((output_root / "PLAN.json").read_text())
    with (output_root / "CONTROLS_STARTED.json").open("x") as stream:
        json.dump({"started_at": now(), "plan": plan}, stream, indent=2)
    results = [cell_run(cell, output_root, args.fresh_launch_check) for cell in plan["matrix"]]
    save(output_root / "CONTROLS_FINISHED.json", {"finished_at": now(), "cells": results})
