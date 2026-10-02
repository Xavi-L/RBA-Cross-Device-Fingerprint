#!/usr/bin/env python3
"""Run the frozen standalone observer across four existing emulator configurations."""
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SDK = Path.home() / "Library/Android/sdk"
ADB = SDK / "platform-tools/adb"
PACKAGE = "com.example.hybridguard.featureapp"
SERIAL = "emulator-5670"


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, data, exclusive=False):
    with path.open("x" if exclusive else "w") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def raw_rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines(keepends=True)
            if line.endswith("\n") and line.strip()]


def plan(cell):
    steps = []
    for number in range(1, cell["triplets"] + 1):
        for phase in ("clean_pre", "attack", "clean_post"):
            steps.append({"step_id": f"r{number}-{phase}", "phase": phase, "round": number, "controlled": True})
    return steps


def run_cell(cell, protocol):
    output = HERE / "runs" / f"api{cell['api']}_{cell['gpu']}"
    output.mkdir(parents=True, exist_ok=False)
    steps = plan(cell)
    write(output / "PLAN.json", steps, True)
    record = {**cell, "started_at": now(), "status": "STARTED", "captures": [], "commands": []}
    lifecycle = output / "LIFECYCLE.json"
    write(lifecycle, record)
    emulator = receiver = None
    receiver_port, cdp_port = protocol["runtime"]["receiver_port"], protocol["runtime"]["cdp_port"]
    endpoint = f"http://127.0.0.1:{receiver_port}/api/collect/fingerprint"
    raw = output / "backend/raw_expanded_payloads.jsonl"
    exported = output / "backend/expanded_collected_data.jsonl"
    catalog = ROOT / "android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv"
    with catalog.open() as stream:
        fields = {r["field"] for r in csv.DictReader(stream) if r["field"].startswith(("android_native_data.", "webview_data.", "web_data."))}
    assert len(fields) == 177

    def command(args, label, directory=output, timeout=30, required=True):
        argv = list(map(str, args))
        result = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        (directory / (label + ".log")).write_text(result.stdout + result.stderr)
        record["commands"].append({"argv": argv, "returncode": result.returncode,
                                   "log": str((directory / (label + ".log")).relative_to(output))})
        write(lifecycle, record)
        if required and result.returncode:
            raise RuntimeError(label + " failed")
        return result.stdout

    def adb(args, label, directory=output, **kwargs):
        return command([ADB, "-s", SERIAL, *args], label, directory, **kwargs)

    try:
        for port in (receiver_port, cdp_port, 5670, 5671):
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    raise RuntimeError(f"Port {port} already occupied")
        args = [str(SDK / "emulator/emulator"), "-avd", cell["avd_name"], "-port", "5670",
                "-read-only", "-no-window", "-no-audio", "-no-snapshot", "-no-boot-anim", "-gpu", cell["gpu"]]
        record["emulator_command"] = args
        with (output / "emulator.log").open("x") as log:
            emulator = subprocess.Popen(args, env={**os.environ, "ANDROID_SDK_ROOT": str(SDK),
                "ANDROID_AVD_HOME": str(ROOT / cell["avd_home"])},
                stdout=log, stderr=subprocess.STDOUT)
        record["emulator_pid"] = emulator.pid
        deadline = time.monotonic() + protocol["limits"]["boot_seconds"]
        while time.monotonic() < deadline:
            if emulator.poll() is not None:
                raise RuntimeError("Emulator exited during boot")
            boot = subprocess.run([str(ADB), "-s", SERIAL, "shell", "getprop", "sys.boot_completed"], capture_output=True, text=True, timeout=8)
            if boot.stdout.strip() == "1":
                break
            time.sleep(1)
        else:
            raise TimeoutError("Boot timeout")
        assert adb(["shell", "getprop", "ro.build.version.sdk"], "android-api").strip() == str(cell["api"])
        adb(["shell", "dumpsys", "webviewupdate"], "webview-provider")
        command([ADB, "-s", SERIAL, "install", "-r", ROOT / protocol["collector"]["apk"]], "install", timeout=60)
        adb(["shell", "pm", "clear", PACKAGE], "clear-ephemeral-app-data")
        adb(["reverse", f"tcp:{receiver_port}", f"tcp:{receiver_port}"], "reverse")
        args = [str(ROOT / "backend_server/.venv-collection/bin/python"), "-B", "-m", "uvicorn", "main:app",
                "--host", "127.0.0.1", "--port", str(receiver_port), "--workers", "1"]
        record["receiver_command"] = args
        with (output / "receiver.log").open("x") as log:
            receiver = subprocess.Popen(args, cwd=ROOT / "backend_server", env={**os.environ,
                "HYBRIDGUARD_DATA_DIR": str(output / "backend"), "PYTHONDONTWRITEBYTECODE": "1"},
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
            raise TimeoutError("Receiver startup timeout")

        identity = None
        for step in steps:
            step_dir = output / "attempts" / step["step_id"]
            step_dir.mkdir(parents=True)
            attempt = {**step, "started_at": now(), "status": "STARTED"}
            write(step_dir / "ATTEMPT.json", attempt, True)
            print(f"START api{cell['api']}_{cell['gpu']} {step['step_id']}", flush=True)
            try:
                previous = len(raw_rows(raw))
                adb(["shell", "am", "force-stop", PACKAGE], "stop", step_dir)
                stable = 0
                for check in range(30):
                    processes = adb(["shell", "ps", "-A", "-o", "PID,NAME"], f"process-{check}", step_dir)
                    live = any(line.split()[-1:] == [PACKAGE] for line in processes.splitlines())
                    stable = 0 if live else stable + 1
                    if stable == 2:
                        break
                    time.sleep(0.2)
                if stable != 2:
                    raise RuntimeError("Previous App process did not exit")
                context = f"webgl-parameter-api{cell['api']}-{cell['gpu']}:{step['step_id']}"
                device = f"webgl-parameter-api{cell['api']}-{cell['gpu']}"
                args = ["shell", "am", "start", "-S", "-W", "-n", PACKAGE + "/.MainActivity",
                        "--es", PACKAGE + ".COLLECT_ENDPOINT", endpoint,
                        "--es", PACKAGE + ".RUNTIME_CONTEXT", context,
                        "--es", PACKAGE + ".DEVICE_MANIFEST_ID", device,
                        "--ei", PACKAGE + ".COLLECTION_ROUND", str(step["round"])]
                if step["controlled"]:
                    args += ["--ez", PACKAGE + ".ENABLE_WEBVIEW_DEBUG", "true",
                             "--ez", PACKAGE + ".WAIT_FOR_WEBVIEW_CONTROL", "true",
                             "--el", PACKAGE + ".PROBE_DELAY_MS", "60000"]
                launched = adb(args, "start", step_dir)
                if "Activity not started" in launched or "Status: ok" not in launched:
                    raise RuntimeError("Fresh Activity launch not confirmed")
                if step["controlled"]:
                    pids = adb(["shell", "pidof", PACKAGE], "pid", step_dir).split()
                    sockets = adb(["shell", "cat", "/proc/net/unix"], "sockets", step_dir)
                    matches = [pid for pid in pids if f"webview_devtools_remote_{pid}" in sockets]
                    if len(matches) != 1:
                        raise RuntimeError("Expected exactly one owned WebView debugging socket")
                    adb(["forward", f"tcp:{cdp_port}", f"localabstract:webview_devtools_remote_{matches[0]}"], "forward", step_dir)
                    command([shutil.which("node"), HERE / "attach_probe.mjs", "attack" if step["phase"] == "attack" else "clean",
                             step_dir / "AUTOMATION.json"], "attach", step_dir, timeout=45)
                deadline = time.monotonic() + protocol["limits"]["capture_seconds"]
                while time.monotonic() < deadline:
                    captured = raw_rows(raw)[previous:]
                    if len(captured) > 1:
                        raise RuntimeError("More than one new payload")
                    if len(captured) == 1 and any(r.get("session_id") == captured[0].get("session_id") for r in raw_rows(exported)):
                        break
                    time.sleep(0.25)
                else:
                    raise TimeoutError("No fresh raw/exported payload before deadline")
                payload = captured[0]["canonical_received_payload"]
                manifest = payload["collection_manifest"]
                assert manifest["runtime_context"] == context and manifest["collection_round"] == step["round"]
                assert manifest["device_manifest_id"] == device and manifest["android_api"] == cell["api"]
                assert manifest["collector_version_code"] == protocol["collector"]["version_code"]
                assert manifest["collector_version_name"] == protocol["collector"]["version_name"]
                assert manifest["web_probe_revision"] == payload["collection_diagnostics"]["web_probe_revision"] == protocol["collector"]["probe_revision"]
                assert payload["schema_version"] == protocol["collector"]["schema_version"]
                assert manifest["upload_endpoint_origin"] == f"http://127.0.0.1:{receiver_port}"
                assert set(payload["collection_status"]["fields"]) == fields
                assert payload["collection_status"]["fixed_signal_count"] == 177
                current = {k: manifest[k] for k in ("collector_install_id", "android_api", "webview_provider_package", "webview_provider_version")}
                if identity is not None and current != identity:
                    raise RuntimeError("Environment identity changed within path")
                identity = current
                if payload["session_id"] in [r["session_id"] for r in record["captures"]]:
                    raise RuntimeError("Session reused")
                observation = json.loads((step_dir / "OBSERVATION.json").read_text())
                binding = json.loads((step_dir / "BINDING.json").read_text())
                assert binding["session_id_before"] == binding["session_id_after"] == payload["session_id"]
                assert binding["canonical_probe_revision"] == protocol["collector"]["probe_revision"]
                assert binding["url_before"] == binding["url_after"] == "file:///android_asset/expanded_probe.html"
                assert observation["observation_schema_version"] == protocol["observer"]["schema"]
                assert observation["observer_revision"] == protocol["observer"]["revision"]
                assert observation["observation_scope"] == protocol["observer"]["scope"]
                assert observation["realm_binding"] == "featureapp:" + payload["session_id"] + ":main-frame"
                assert [c["context_type"] for c in observation["contexts"]] == ["webgl", "webgl2"]
                provider = (output / "webview-provider.log").read_text()
                assert f"({manifest['webview_provider_package']}, {manifest['webview_provider_version']})" in provider
                saved = {**step, "raw_line": previous + 1, "session_id": payload["session_id"]}
                record["captures"].append(saved)
                attempt.update(status="CAPTURED", **saved)
                print(f"CAPTURED api{cell['api']}_{cell['gpu']} {step['step_id']}", flush=True)
            except Exception as error:
                attempt.update(status="FAILED", error=f"{type(error).__name__}: {error}")
                adb(["logcat", "-d", "-t", "500"], "failure-logcat", step_dir, required=False)
                raise
            finally:
                attempt["finished_at"] = now()
                write(step_dir / "ATTEMPT.json", attempt)
                adb(["shell", "am", "force-stop", PACKAGE], "stop-final", step_dir, required=False)
                if step["controlled"]:
                    adb(["forward", "--remove", f"tcp:{cdp_port}"], "unforward", step_dir, required=False)
                write(lifecycle, record)
        record.update(status="COMPLETE", environment_identity=identity)
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
        write(lifecycle, record)
    print(json.dumps({"api": cell["api"], "gpu": cell["gpu"], "status": record["status"], "captured": len(record["captures"]), "error": record.get("error")}), flush=True)
    return record


if __name__ == "__main__":
    protocol = json.loads((HERE / "PROTOCOL.json").read_text())
    with zipfile.ZipFile(ROOT / protocol["collector"]["apk"]) as apk:
        if apk.read("assets/canonical_web_probe.js") != (ROOT / "web_probe/canonical_web_probe.js").read_bytes():
            raise RuntimeError("APK canonical probe differs from current source")
    write(HERE / "STARTED.json", {"started_at": now(), "protocol": protocol, "apk_probe_matches_source": True}, True)
    snapshot = HERE / "source_snapshot"
    snapshot.mkdir(exist_ok=False)
    for name in ("PROTOCOL.json", "attach_probe.mjs", "run_pairs.py", "analyze.py", "diagnostic.js"):
        shutil.copyfile(HERE / name, snapshot / name)
    for key in ("source", "evaluator"):
        source = ROOT / protocol["observer"][key]
        shutil.copyfile(source, snapshot / source.name)
    results = [run_cell(cell, protocol) for cell in protocol["matrix"]]
    for source in (HERE / name for name in ("PROTOCOL.json", "attach_probe.mjs", "run_pairs.py", "analyze.py", "diagnostic.js")):
        assert source.read_bytes() == (snapshot / source.name).read_bytes(), str(source) + " changed during run"
    for key in ("source", "evaluator"):
        source = ROOT / protocol["observer"][key]
        assert source.read_bytes() == (snapshot / source.name).read_bytes(), str(source) + " changed during run"
    write(HERE / "FINISHED.json", {"finished_at": now(), "paths": results}, True)
