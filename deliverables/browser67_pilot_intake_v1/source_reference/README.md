# Browser67 paired pilot harness (2026-10-04)

This directory contains the local collection, independent verification and delivery tooling behind the 18-stage Browser67/App177 pilot. The measured results and research limits are in [the report](../../reports/week10/20261004_browser67_pilot/review.md). Tracked files contain source and aggregate projections. The complete frozen evidence packet is prepared for delivery to authorized collaborators as a planned [Release attachment](https://github.com/computersciencefreshmen/hybridguard-browser-fingerprint-research/releases/tag/browser67-pilot-20261004) in this private repository, separate from the Git source tree. Upload awaits explicit authorization; the attachment is not yet available.

## Responsibilities and data flow

`run_paired_browser_pilot.mjs` controls an owned browser before releasing the original adapter script. `run_backend.py` wraps the pinned upstream backend and records one fresh batch. The upstream App and Chrome upload separately with one-stage pairing tickets. `verify_pilot.py` independently recomputes source/APK, raw-payload, receipt, ordering, effect and recovery checks. `build_delivery.mjs` prepares facts/sidecars and a white-listed manifest; the upstream snapshot/experiment tools derive 244 features and admission gates. `package_delivery.py` verifies the ZIP itself and independently replays a fresh extraction.

Two controls each use three `clean_pre / attack_active / clean_post` repetitions. The language control changes navigator language/languages; the timezone control changes browser timezone and offset. The Native/App Web target values and untargeted browser values must remain conserved. Completion, field effect, restoration and formal research admission are separate checks.

## Source identities

[source_manifest.json](source_manifest.json) distinguishes each measured private source digest from this publication copy. Only the runner ADB default was changed to use `ADB_PATH` or the executable on PATH; `--adb` remains available. The other six programs retain archived bytes. `pilot_plan.json` is a neutral configuration template with `DEVICE_SERIAL_REQUIRED` and a template run identity, not the original measured plan. Fill these privately before capture. The backend docstring retained the earlier "Future" wording; this wrapper was subsequently used for the selected r8 batch.

Pinned upstream: `a16ba9dea3078a66b4e8e4338d00d9dd9df9893b`. Actual measured release: FeatureApp v16, `1.6.9-expanded-v2.2-geometry`, `expanded-web-67-v2`. Historical v8/v1 defaults in upstream source config must be replaced by the actual batch lock before deriving a snapshot.

## Tests without a device

Run from the repository root (the observed environment used Node 24.14.0 and Python 3.12.8):

```powershell
New-Item -ItemType Directory -Path tmp -Force | Out-Null
node --test execution_log/browser67_pilot_20261004/test_paired_browser_pilot.mjs
python -B -m unittest discover -s execution_log/browser67_pilot_20261004 -p test_verify_pilot.py
python execution_log/browser67_pilot_20261004/package_delivery.py --self-test
```

The Node tests use temporary loopback sites and synthetic payloads; Python contract/package tests use temporary fixtures. They do not operate Android devices, start the real backend or access experiment data. Full evidence replay requires the [frozen evidence ZIP](https://github.com/computersciencefreshmen/hybridguard-browser-fingerprint-research/releases/download/browser67-pilot-20261004/browser67_paired_pilot_evidence.zip). Download it with repository access and run the following commands in a fresh extraction directory, using the archived verifier included in that packet:

```powershell
python verify_pilot.py --root <extracted-private-packet> --pilot pilot_r8
python verify_pilot.py --root <extracted-private-packet> --pilot pilot_r8 --self-test
```

## Preparing a new private run

Copy this harness into a fresh private run directory two levels below a chosen workspace, such as `<workspace>/tmp/<run>`. Keep a byte-exact LF checkout of pinned upstream in its `upstream` directory. Build the collector for the loopback endpoints, produce an honest `collector_build_manifest.json`, and confirm source/APK/installed/probe identities. The template expects ports 8000 (backend), 8001 (probe) and 9340 (Chrome debugging). Native endpoint configuration, ADB reverse mappings, owned-device serial and a fresh run ID must be set by the operator.

The Node runner first supports `--preflight`; device operations require explicit `--run --apk <apk> --build-manifest <manifest> --output pilot_r8`. The backend wrapper refuses an existing data directory or lifecycle artifact. Close it cooperatively using `backend.stop`, then export session provenance. Run the independent verifier and self-test before `build_delivery.mjs --prepare pilot_r8`; use the generated actual-release config for upstream snapshot/experiment tools and finalize only after their checks pass. The HMAC key is an external private input and never belongs in Git or the evidence ZIP.

The public aggregates establish paired collection, targeted effects and recovery. Candidate labels/run-scoped identity cannot authorize model tuning or cross-device performance evaluation.
