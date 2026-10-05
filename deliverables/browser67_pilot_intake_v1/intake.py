#!/usr/bin/env python3
"""Offline B1 intake. No collector, device, training, detector or network calls."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import zipfile
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))
from path_compat import (PILOT, VERSION, VERIFIER_SHA256, allowed_roots,
                         load_verifier, map_locked_path, run_verifier)

PRIVATE = REPO / ".private/browser67_pilot_20261004"
MEASUREMENT_COMMIT = "a16ba9dea3078a66b4e8e4338d00d9dd9df9893b"
SOURCE_COMMIT = "59a0cff18386150eca90fcf09b2f6169ff186a1e"
PACKAGES = {
    "source": ("hybridguard-browser-fingerprint-research-browser67-pilot-20261004.zip", 46800765,
               "d0c82b4e6deec7db6e7c410b0a3a33b2bd173884c3a05114ff90d769d74b5bed"),
    "evidence": ("browser67_paired_pilot_evidence.zip", 13723281,
                 "9f05bb21f6caafe277f62619c47ec142f7798af8aff51414e7e8403ef0183df6"),
}
DATA_SOURCES = {
    "app_analysis": "expanded_collected_data.jsonl", "app_raw": "raw_expanded_payloads.jsonl",
    "app_receipts": "collection_receipts.jsonl", "collection_batches": "collection_batches.jsonl",
    "browser_analysis": "browser_collected_data.jsonl", "browser_raw": "raw_browser_payloads.jsonl",
    "browser_pair_provenance": "browser_pair_provenance.jsonl", "browser_pair_events": "browser_pair_events.jsonl",
}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def sha(path):
    with Path(path).open("rb") as handle:
        digest = hashlib.sha256()
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    # Parse every nonblank physical line; malformed input raises, never drops.
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_rows(path, values):
    Path(path).write_text("".join(json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n" for v in values), encoding="utf-8")


def canonical(value):
    # JSON comparison distinguishes booleans from integers (False != 0).
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def index_unique(values, key):
    result = {}
    for value in values:
        identity = value.get(key)
        require(isinstance(identity, str) and identity and identity not in result, "MISSING_OR_DUPLICATE_" + key.upper())
        result[identity] = value
    return result


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True)


def protect_private_inputs():
    names = [item[0] for item in PACKAGES.values()] + [".private/browser67_pilot_20261004"]
    require(not git("ls-files", "--", *names).strip(), "PRIVATE_INPUT_ALREADY_TRACKED_OR_STAGED")
    exclude = Path(git("rev-parse", "--git-path", "info/exclude").strip())
    if not exclude.is_absolute():
        exclude = REPO / exclude
    old = exclude.read_text() if exclude.exists() else ""
    patterns = ["/" + name for name in names[:2]] + ["/" + names[2] + "/"]
    missing = [p for p in patterns if p not in old.splitlines()]
    if missing:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a") as handle:
            handle.write("\n# Local Browser67 B1 evidence (private)\n" + "\n".join(missing) + "\n")
    for name in names[:2] + [names[2] + "/check"]:
        require(subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", "--", name]).returncode == 0,
                "PRIVATE_PATH_NOT_IGNORED")
    require(PRIVATE.resolve().is_relative_to(REPO.resolve()), "PRIVATE_ROOT_ESCAPE")


def relative_path(value):
    require(isinstance(value, str) and value and "\\" not in value and ":" not in value and "\0" not in value,
            "UNSUPPORTED_ARCHIVE_PATH")
    path = PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts, "ARCHIVE_PATH_ESCAPE")
    return path


def tree_hashes(root):
    require(not root.is_symlink(), "ORIGINAL_SYMLINK_REJECTED")
    result = {}
    for path in root.rglob("*"):
        require(not path.is_symlink(), "ORIGINAL_SYMLINK_REJECTED")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha(path)
    return result


def check_packages():
    results = []
    for kind, (name, size, expected) in PACKAGES.items():
        archive = REPO / name
        actual_size, actual_digest = archive.stat().st_size, sha(archive)
        require(actual_size == size and actual_digest == expected,
                f"ZIP_IDENTITY_MISMATCH:{kind}: expected {size}/{expected}; observed {actual_size}/{actual_digest}")
        destination = PRIVATE / "originals" / kind
        require(destination.resolve().is_relative_to(PRIVATE.resolve()), "ORIGINAL_DIRECTORY_ESCAPE")
        with zipfile.ZipFile(archive) as package:
            require(package.testzip() is None, "ZIP_CRC_MISMATCH:" + kind)
            require(kind != "source" or package.comment.decode() == SOURCE_COMMIT, "SOURCE_ZIP_COMMENT_MISMATCH")
            names = set()
            files = {}
            for entry in package.infolist():
                path = relative_path(entry.filename)
                require(path.as_posix() not in names, "DUPLICATE_ARCHIVE_MEMBER")
                names.add(path.as_posix())
                require(not stat.S_ISLNK(entry.external_attr >> 16), "ARCHIVE_SYMLINK_REJECTED")
                if not entry.is_dir():
                    files[path.as_posix()] = entry
            if not destination.exists():
                destination.mkdir(parents=True)
                package.extractall(destination)
            actual = tree_hashes(destination)
            require(set(actual) == set(files), "EXTRACTED_INVENTORY_MISMATCH:" + kind)
            for name_in_zip, entry in files.items():
                require(actual[name_in_zip] == hashlib.sha256(package.read(entry)).hexdigest(),
                        "EXTRACTED_BYTES_MISMATCH:" + name_in_zip)
        results.append({"kind": kind, "name": name, "bytes": size, "sha256": expected,
                        "crc": "passed", "safe_paths": True, "files": len(files)})
    return results


def check_inventory(root):
    manifest = read(root / "package_contents.json")
    items = manifest["files"]
    require(len(items) == 487 and manifest["selected_pilot"] == PILOT, "PACKAGE_INVENTORY_IDENTITY")
    expected = index_unique(items, "path")
    require(set(tree_hashes(root)) == set(expected) | {"package_contents.json"}, "PACKAGE_MEMBERS_DIFFER")
    for name, item in expected.items():
        path = root.joinpath(*relative_path(name).parts)
        require(path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], "MANIFEST_MEMBER_MISMATCH:" + name)
        if item.get("jsonl_rows") is not None:
            require(len(rows(path)) == item["jsonl_rows"], "MANIFEST_ROW_COUNT_MISMATCH:" + name)
    delivery = read(root / "delivery/delivery_manifest.json")
    require(sha(root / "delivery/delivery_manifest.json") == manifest["delivery_manifest_sha256"], "DELIVERY_MANIFEST_MISMATCH")
    require(manifest["source_commit"] == delivery["source_commit"] == MEASUREMENT_COMMIT, "MEASUREMENT_COMMIT_MISMATCH")
    require(delivery["selected_pilot"] == PILOT, "WRONG_SELECTED_PILOT")
    for item in delivery["files"]:
        name = item["path"]
        require(name in expected and all(item[k] == expected[name][k] for k in ("bytes", "sha256", "jsonl_rows")),
                "DELIVERY_MEMBER_MISMATCH:" + name)
    return {"listed_members_verified": len(items), "total_files": len(items) + 1,
            "package_contents_locked_by_zip_sha256": True}


def check_source_manifest(root):
    source = next((PRIVATE / "originals/source").iterdir()) / "execution_log/browser67_pilot_20261004"
    manifest = read(source / "source_manifest.json")
    require(manifest["upstream_commit"] == MEASUREMENT_COMMIT, "PUBLIC_SOURCE_UPSTREAM_MISMATCH")
    result = []
    for item in manifest["files"]:
        name = relative_path(item["path"]).as_posix()
        require(sha(source / name) == item["published_source_sha256"], "PUBLIC_SOURCE_DIGEST:" + name)
        require((source / name).stat().st_size == item["published_bytes"], "PUBLIC_SOURCE_SIZE:" + name)
        require(sha(root / name) == item["archived_source_sha256"], "ARCHIVED_SOURCE_DIGEST:" + name)
        result.append({"path": name, "published_equals_measured": item["published_source_sha256"] == item["archived_source_sha256"],
                       "publication_changes": item["publication_changes"]})
    return result


def generate_config(root, target):
    config = read(root / "delivery/latest_paired244_sources.local.json")
    build = read(root / "collector_build_manifest.json")
    release = config["release"]
    expected = {"featureapp_version_code": 16, "featureapp_version_name": "1.6.9-expanded-v2.2-geometry",
                "app_schema_version": "expanded-v2.2-status", "browser_schema_version": "browser-web-v1-status",
                "browser_probe_revision": "expanded-web-67-v2", "app_signal_count": 177, "browser_signal_count": 67}
    require(all(release.get(k) == v for k, v in expected.items()), "BATCH_RELEASE_MISMATCH")
    require(build["version_code"] == 16 and build["version_name"] == expected["featureapp_version_name"]
            and build["configuration"]["WEB_PROBE_REVISION"] == expected["browser_probe_revision"], "BUILD_IDENTITY_MISMATCH")
    require(set(config["sources"]) == set(DATA_SOURCES) | {"feature_catalog", "browser_probe_manifest"}, "SOURCE_CATALOG_MISMATCH")
    for key, filename in DATA_SOURCES.items():
        path = map_locked_path(root, build, config["sources"][key])
        require(path == (root / "data" / filename).resolve(), "DATA_SOURCE_MAPPING_MISMATCH:" + key)
        config["sources"][key] = str(path)
    for key in ("feature_catalog", "browser_probe_manifest"):
        config["sources"][key] = str(root / "upstream" / relative_path(config["sources"][key]))
    release["featureapp_build_file"] = str(root / "upstream" / relative_path(release["featureapp_build_file"]))
    write(target, config)
    return config


def compare_snapshots(expected, actual):
    details = []
    for filename in ("paired_244.jsonl", "sample_index.jsonl"):
        left, right = (index_unique(rows(folder / filename), "sample_id") for folder in (expected, actual))
        require(set(left) == set(right), "SNAPSHOT_MEMBER_SET_MISMATCH:" + filename)
        for key in sorted(left):
            require(canonical(left[key]) == canonical(right[key]), "SNAPSHOT_MEMBER_CONTENT_MISMATCH:" + filename + ":" + key)
            if filename == "paired_244.jsonl":
                require(len(right[key]["features"]) == len(right[key]["field_status"]) == 244, "FEATURE_COUNT_MISMATCH")
                details.append({"sample_id": key, "values_equal": 244, "states_equal": 244, "index_equal": True})
    for filename in ("app_only_177.jsonl", "quarantine.jsonl", "selection_audit.jsonl"):
        require(sorted(map(canonical, rows(expected / filename))) == sorted(map(canonical, rows(actual / filename))),
                "SNAPSHOT_AUXILIARY_MISMATCH:" + filename)
    require(canonical(read(expected / "feature_catalog.json")) == canonical(read(actual / "feature_catalog.json")), "FEATURE_CATALOG_MISMATCH")
    before, after = (read(folder / "qc_summary.json") for folder in (expected, actual))
    require({k:v for k,v in before.items() if k != "run_id"} == {k:v for k,v in after.items() if k != "run_id"}, "QC_SUMMARY_MISMATCH")
    old, new = ((folder / "paired_244.jsonl").read_bytes() for folder in (expected, actual))
    return {"members": len(details), "values_equal": len(details) * 244, "states_equal": len(details) * 244,
            "full_sample_index_equal": True, "catalog_equal": True, "qc_equal": True,
            "paired_bytes_equal": old == new, "paired_bytes_equal_after_crlf_to_lf": old.replace(b"\r\n", b"\n") == new.replace(b"\r\n", b"\n")}, details


def stage_inventory(root, snapshot):
    planned = read(root / PILOT / "run_manifest.json")["stages"]
    captures = index_unique(rows(root / PILOT / "captures.jsonl"), "capture_id")
    samples = index_unique(rows(snapshot / "sample_index.jsonl"), "app_session_id")
    require(set(captures) == {item["capture_id"] for item in planned}, "PLANNED_POSITIONS_DIFFER")
    result = []
    for slot in planned:
        capture = captures[slot["capture_id"]]
        binding = capture["binding"]
        sample = samples[binding["app_session_id"]]
        for key in ("app_session_id", "app_receipt_id", "app_payload_sha256", "browser_session_id",
                    "browser_receipt_id", "browser_payload_sha256", "collection_batch_id", "browser_pair_id"):
            require(sample[key] == binding["pair_id" if key == "browser_pair_id" else key], "CAPTURE_INDEX_BINDING_MISMATCH:" + key)
        result.append({**slot, "sample_id": sample["sample_id"], "result": capture["result"],
                       "disposition": sample["dataset_view"], "failure_code": capture.get("failure_code"),
                       "pair_binding_checked": True})
    require(len(result) == len(samples) == 18, "POSITIONS_LOST")
    return result


def quality_sidecar(root, snapshot):
    raw = index_unique(rows(root / "data/raw_expanded_payloads.jsonl"), "session_id")
    samples = index_unique(rows(snapshot / "sample_index.jsonl"), "sample_id")
    result = []
    for sample in rows(snapshot / "paired_244.jsonl"):
        payload = raw[samples[sample["sample_id"]]["app_session_id"]]["canonical_received_payload"]
        # These literals are review candidates, not a global invalid-value rule.
        candidates = {key: {"value": value, "field_status": sample["field_status"][key]}
                      for key, value in sample["features"].items()
                      if value is False or (type(value) in (int, float) and value in (0, -1))}
        result.append({"sample_id": sample["sample_id"], "literal_review_candidates": candidates,
                       "app_collection_observations": payload.get("collection_observations"),
                       "raw_refs": {"app": "data/raw_expanded_payloads.jsonl", "browser": "data/raw_browser_payloads.jsonl"},
                       "note": "observed is collection status, not task-specific comparability; values/states unchanged; no detector rule or T/F/U assigned"})
    return result


def source_comparison(root):
    relevant = {"hybridguard_agent/scripts/build_latest_paired244_snapshot.py",
                "hybridguard_agent/scripts/build_latest_experiment_plan.py",
                "hybridguard_agent/config/latest_paired244_sources.json",
                "hybridguard_agent/config/latest_experiment_protocol.v1.json",
                "hybridguard_agent/schemas/latest_experiment_fact_v1.schema.json",
                "android_app/HybridGuard/featureapp/build.gradle.kts",
                "android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv",
                "browser_probe_site/public/probe/manifest.json"}
    # Compare only modules actually imported by the two existing builders.
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename and Path(filename).resolve().is_relative_to(REPO / "hybridguard_agent"):
            relevant.add(Path(filename).resolve().relative_to(REPO).as_posix())
    return [{"path": name, "current_sha256": sha(REPO / name),
             "frozen_sha256": sha(root / "upstream" / name) if (root / "upstream" / name).is_file() else None,
             "same_bytes": (root / "upstream" / name).is_file() and (REPO / name).read_bytes() == (root / "upstream" / name).read_bytes()}
            for name in sorted(relevant)]


def run_focused_tests(run):
    suites = [
        ("intake", ["discover", "-s", str(HERE), "-p", "test_*.py", "-v"]),
        ("existing_builders", ["hybridguard_agent.tests.test_build_latest_paired244_snapshot",
                               "hybridguard_agent.tests.test_latest_experiment_plan", "-v"]),
    ]
    result = []
    for name, arguments in suites:
        completed = subprocess.run([sys.executable, "-B", "-m", "unittest", *arguments],
                                   cwd=REPO, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (run / (name + "_tests.log")).write_text(completed.stdout, encoding="utf-8")
        match = re.search(r"Ran (\d+) tests?", completed.stdout)
        require(completed.returncode == 0 and match and "skipped=" not in completed.stdout, "TEST_SUITE_FAILED:" + name)
        result.append({"suite": name, "tests": int(match.group(1)), "passed": True, "skipped": 0})
    return result


def write_report(summary):
    tests = summary["focused_tests"]
    comparisons = summary["source_comparison"]
    differences = [item["path"] for item in comparisons if not item["same_bytes"]]
    source_note = (f"核对 {len(comparisons)} 个相关文件，均与冻结副本字节一致。" if not differences
                   else "当前主仓与冻结副本的差异文件：" + ", ".join(differences))
    report = f"""# Browser67 B1 本地接入验收

接入日期：{summary['intake_date']}。状态：**B1 先导接入完成；正式分组未具备条件。**
Browser语言/时区两配置先导已完成主仓接入；跨端关系开发与正式评价尚未完成，最终消融仍暂停。

## 1. 本地双包与原始证据

两个根目录 ZIP 的大小、整包 SHA-256、CRC、安全路径及首次解压字节通过核验；证据包共488个文件，487项清单的大小、摘要及已登记JSONL行数全部一致。`package_contents.json` 由整包摘要锁定，不要求循环自哈希。

- 源码ZIP身份：`{SOURCE_COMMIT}`（ZIP comment）；用于实现及 source_manifest 核对。
- 测量主仓身份：`{MEASUREMENT_COMMIT}`；与本次重建HEAD一致。
- 使用证据包的测量计划、原始runner与冻结核验器。源码包runner包含便携ADB路径改动，source_manifest可回连；中性计划模板未覆盖归档计划。
- `pilot_r8` 原始证据 **18/18通过**，**6/6三阶段组的目标效果与恢复通过**；归档自测试 **8/8通过**（真实基线＋7种篡改拒绝）。两份新报告与原报告解析内容完全一致，包括输入摘要。
- 原ZIP及全部首次解压文件的前后摘要一致；旧工程失败/跳过尝试的归档说明保留，未混入本批分母。

## 2. 跨平台兼容

macOS直接调用原核验函数复现 `FileNotFoundError`，原因是本机 `Path` 解释Windows路径。`path_compat.py`（`{VERSION}`）仅替换归档模块的 `Inputs.locked_path`；原核验函数、8项自测试、断言和证据字节均保留。

只接受构建清单中 `source_checkout` 的父目录和 `resume_archive_origin.directory` 两个根；以 `PureWindowsPath.relative_to` 映射完整相对路径，拒绝未知盘符/根、`..`、不支持路径和符号链接逃逸。完整旧根与本机路径只记在私有 `path_mapping.json`。归档核验器SHA-256：`{VERIFIER_SHA256}`。

## 3. 主仓重建与逐成员一致性

调用实际主仓 `build_latest_paired244_snapshot.py`，生成独立的批次配置：App versionCode=16、versionName=`1.6.9-expanded-v2.2-geometry`、App schema=`expanded-v2.2-status`、Browser schema=`browser-web-v1-status`、probe=`expanded-web-67-v2`。8个数据源按登记原根映射到归档 `data/`；构建文件、177/67目录和探针manifest引用包内冻结材料。历史v8/v1默认配置与发布校验保留。

{source_note} 明细见 `INTAKE_SUMMARY.json` 的 `source_comparison`。

| 验收项 | 结果 |
|---|---:|
| paired244 / App-only / quarantine | 18 / 0 / 0 |
| 逐sample_id的244项原值 | 18/18，4,392项一致 |
| 逐sample_id的244项原状态 | 18/18，4,392项一致 |
| 完整sample_index（两端session、摘要、receipt、pair、batch等） | 18/18一致 |
| 捕获位置与重建索引的来源绑定 | 18/18一致 |
| 字段目录、QC、选择审计和其他分流视图 | 一致 |

交付与重建的 paired JSONL 仅CRLF/LF不同，未为匹配文件摘要修改输入。18个预定位置完整保留。`observed`共App 3,186项、Browser 1,206项，只说明原始采集状态，不代表每种任务都可比较。原值与状态不改；私有 `field_quality_sidecar.jsonl` 记录0/-1/false等需逐字段解释的字面值和附加观测引用，不统一判有效或无效，不生成检测规则或将未知补F。几何、WebGL1、webdriver附加观测保留在原始引用/侧表，不扩充244目录。

## 4. 控制、保持与恢复

范围为 **1个API36模拟器、独立 `com.android.chrome`、实录Chrome/133.0.6943.137**，App v16、Browser probe v2。

| 配置 | 核验内容 | 完整三阶段组 |
|---|---|---:|
| language_fr | active阶段Browser language/languages变为fr-FR；Browser时区目标保持；App Native/App Web语言与时区目标保持；post恢复pre | 3/3 |
| timezone_tokyo | active阶段Browser时区为Asia/Tokyo、offset=-540；Browser语言目标保持；App Native/App Web语言与时区目标保持；post恢复pre | 3/3 |

归档事件顺序确认控制先于Browser采集生效、上传之后再撤销；安装APK与源APK、探针字节、版本锁及干净停批次一致。摘要、回执与关联复核不等于重新执行HMAC密码学签名验证。

18阶段＝6个干预位置＋12个前后对照位置，不是18种攻击或18台设备；6/6为目标效果/恢复，不是检测率。未主张全载荷恒定。

## 5. 正式分组为何为空

本批facts原样保留 `candidate`、`identity_scope=run_profile`、`identity_stability=run_scoped_unverified`。实际主仓 `build_latest_experiment_plan.py` 使用原协议产生 train/development/test **0/0/0**；`structural_ready=false`、`grouped_data_prerequisites_met=false`，与交付readiness完全一致。

阻塞原因是无verified标签、无可信跨运行独立分组，继而不满足各split组数和类别覆盖；6组重复不能当成6台设备。该状态是正式研究准入限制，B1接入本身已完成。

## 6. 后续与停止边界

可以在**下一轮明确范围后**开展App冻结基线回放及少量、标明先导性质的App↔Browser关系诊断；本批不自动并入旧E1分母，不获得正式train/dev/test或泛化评价资格。本轮 **0训练、0新增采集、0检测器评分**，未执行E1、B2、E2；无自动提交或推送。

## 本地复现

从实际主仓根目录运行（Python 3.10+，标准库；无需网络、ADB、Node采集runner或HMAC密钥）：

```sh
python3 -B deliverables/browser67_pilot_intake_v1/intake.py run
python3 -B deliverables/browser67_pilot_intake_v1/intake.py summarize
```

第一条确认本地排除、核验双包、复用/首次解压原件、运行冻结核验和自测试、生成v16/v2配置、调用两个主仓builder、逐成员比较并运行必要测试；每次生成新的私有run。第二条只读取最近一次验收保存结果并重写脱敏摘要/本报告，**不代表重新核验当前输入**。也可指定 `--run-id` 选择私有run；已有run不覆盖。

本次私有run引用：`{summary['private_run_ref']}`。`.private/browser67_pilot_20261004/originals/`保留两个首次解压树；`latest_run.json`记录最近验收；run内含verification、自测试、路径映射、本机配置、paired/app-only/quarantine、sample_index、QC、目录/来源清单、阶段去向、逐成员比对、字段质量侧表、readiness和测试日志。本机原件保留在被本地忽略的私有目录；后续获授权的证据公开副本见下方说明。

验证：本次接入测试 **{tests[0]['tests']}/{tests[0]['tests']}**、现有快照/准入回归 **{tests[1]['tests']}/{tests[1]['tests']}**，均无跳过。接入测试包含真实材料的8项归档自测试。无私有证据的其他检出环境会显式跳过真实材料测试，不视为真实验收通过。旧模型、历史结果及子模块指针未修改。
"""
    if "evidence_publication" in summary:
        report += "\n## 后续授权的证据公开\n\n用户于2026-10-06明确授权提交有用证据，排除凭据和两个ZIP。现提供488个测量归档文件的原字节副本、13个B1源码参考文件和主仓验收留档。详见[EVIDENCE_PUBLICATION.md](EVIDENCE_PUBLICATION.md)与[公开证据复核结果](PUBLIC_REVIEW.json)。\n\n远端无需ZIP或本机私有目录，运行：\n\n```sh\npython3 -B deliverables/browser67_pilot_intake_v1/review_evidence.py verify\n```\n\n原B1结果和正式准入边界保持不变；本节更新的是公开范围。\n"
    (HERE / "REPORT.md").write_text(report, encoding="utf-8")


def summarize(run):
    receipt = read(run / "intake_receipt.json")
    require(receipt["status"] == "passed", "INTAKE_NOT_PASSED")
    verification = read(run / "verification.json")
    tests = read(run / "verification_tests.json")
    comparison = read(run / "comparison.json")
    readiness = read(run / "experiment_plan/experiment_readiness.json")
    summary = {"schema_version": "browser67-pilot-intake-v1", "intake_date": receipt["intake_date"], "status": "passed",
               "source_archive_commit": SOURCE_COMMIT, "measurement_main_commit": MEASUREMENT_COMMIT,
               "rebuild_main_commit": receipt["main_commit"], "selected_pilot": PILOT,
               "packages": receipt["packages"], "inventory": receipt["inventory"],
               "path_compatibility": {"version": VERSION, "archived_verifier_sha256": VERIFIER_SHA256,
                                      "allowed_root_fields": ["source_checkout.parent", "resume_archive_origin.directory"],
                                      "original_failure": receipt["original_failure"], "evidence_unchanged": receipt["inputs_unchanged"]},
               "verification": {k:v for k,v in verification.items() if k != "input_file_sha256"},
               "archived_self_tests": tests, "original_reports_equal": receipt["original_reports_equal"],
               "rebuild": comparison, "qc_counts": read(run / "paired244_snapshot/qc_summary.json")["counts"],
               "source_comparison": read(run / "source_comparison.json"),
               "public_harness_source_comparison": receipt["public_source_comparison"],
               "focused_tests": receipt["focused_tests"],
               "research_admission": {"label_status": "candidate", "identity_scope": "run_profile",
                                      "identity_stability": "run_scoped_unverified", "readiness": readiness},
               "operations": {"training": 0, "new_collection": 0, "detector_scoring": 0},
               "private_run_ref": run.relative_to(REPO).as_posix(),
               "claim_boundary": "Pilot collection/control/effect/recovery and pairing QC only; no HMAC re-verification, detector efficacy or generalization claim."}
    if (HERE / "PUBLICATION.json").is_file():
        publication = read(HERE / "PUBLICATION.json")
        summary["evidence_publication"] = {"manifest": "PUBLICATION.json", "documentation": "EVIDENCE_PUBLICATION.md",
            "archive_file_count": publication["archive_file_count"], "source_reference_file_count": publication["source_reference_file_count"],
            "measurement_bytes_unchanged": publication["original_measurement_bytes_unchanged"],
            "zip_required_for_public_review": False, "public_review_result": "PUBLIC_REVIEW.json"}
    write(HERE / "INTAKE_SUMMARY.json", summary)
    write_report(summary)
    return summary


def run_intake(run_id):
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id), "INVALID_RUN_ID")
    protect_private_inputs()
    PRIVATE.mkdir(parents=True, exist_ok=True)
    run = PRIVATE / "runs" / run_id
    require(not run.exists(), "RUN_ALREADY_EXISTS_USE_SUMMARIZE_OR_NEW_RUN_ID")
    run.mkdir(parents=True)
    write(run / "git_before.json", {"head": git("rev-parse", "HEAD").strip(), "status": git("status", "--porcelain=v1"),
                                    "submodule_index": git("ls-files", "--stage", "--", "hybridguard-browser-fingerprint-research")})
    packages = check_packages()
    root = PRIVATE / "originals/evidence"
    inventory = check_inventory(root)
    public_sources = check_source_manifest(root)
    before = tree_hashes(PRIVATE / "originals")
    original_failure = None
    original = load_verifier(root, compatible=False)
    try:
        original.verify(root, root / PILOT / "session_provenance.jsonl", PILOT)
    except FileNotFoundError as error:
        original_failure = type(error).__name__
        write(run / "direct_compatibility_issue.json", {"exception": original_failure, "detail": str(error),
               "explanation": "Host Path interprets archived Windows roots incorrectly; external adapter uses PureWindowsPath."})
    build = read(root / "collector_build_manifest.json")
    write(run / "path_mapping.json", {"version": VERSION, "verifier_sha256": VERIFIER_SHA256,
                                      "allowed_roots": list(map(str, allowed_roots(build))), "mapped_root": str(root)})
    verification = run_verifier(root, run / "verification.json")
    tests = run_verifier(root, run / "verification_tests.json", self_test=True)
    equal = verification == read(root / "verification.json") and tests == read(root / "verification_tests.json")
    require(equal, "ARCHIVED_REPORT_DIFFERENCE")
    config_path = run / "latest_paired244_sources.browser67_pilot_v16_v2.local.json"
    generate_config(root, config_path)
    from hybridguard_agent.scripts.build_latest_paired244_snapshot import build_snapshot
    from hybridguard_agent.scripts.build_latest_experiment_plan import build_plan, DEFAULT_PROTOCOL_PATH
    build_snapshot(config_path, run / "paired244_snapshot", run_id)
    comparison, members = compare_snapshots(root / "delivery/paired244_snapshot", run / "paired244_snapshot")
    write(run / "comparison.json", comparison)
    write_rows(run / "member_comparison.jsonl", members)
    write_rows(run / "stage_inventory.jsonl", stage_inventory(root, run / "paired244_snapshot"))
    write_rows(run / "field_quality_sidecar.jsonl", quality_sidecar(root, run / "paired244_snapshot"))
    facts = root / "delivery/latest_experiment_facts.jsonl"
    require(len(rows(facts)) == 18 and all(r["label_status"] == "candidate" and r["identity_scope"] == "run_profile"
            and r["identity_stability"] == "run_scoped_unverified" for r in rows(facts)), "FACT_SCOPE_CHANGED")
    readiness = build_plan(snapshot_dir=run / "paired244_snapshot", output_dir=run / "experiment_plan",
                           facts_path=facts, protocol_path=DEFAULT_PROTOCOL_PATH)
    require(readiness == read(root / "delivery/experiment_plan/experiment_readiness.json"), "READINESS_DIFFERENCE")
    require(not readiness["structural_ready"] and not readiness["grouped_data_prerequisites_met"]
            and readiness["counts"]["split_assigned_count"] == 0, "FORMAL_ADMISSION_CHANGED")
    write(run / "source_comparison.json", source_comparison(root))
    focused_tests = run_focused_tests(run)
    after = tree_hashes(PRIVATE / "originals")
    require(before == after, "ORIGINAL_EVIDENCE_CHANGED")
    require(all(sha(REPO / item[0]) == item[2] for item in PACKAGES.values()), "INPUT_ZIP_CHANGED")
    write(run / "immutable_inputs.json", {"before": before, "after": after, "equal": True})
    protect_private_inputs()
    write(run / "intake_receipt.json", {"status": "passed", "intake_date": datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(),
          "main_commit": git("rev-parse", "HEAD").strip(), "packages": packages, "inventory": inventory,
          "public_source_comparison": public_sources, "inputs_unchanged": True,
          "focused_tests": focused_tests,
          "original_failure": original_failure, "original_reports_equal": equal})
    write(PRIVATE / "latest_run.json", {"run_id": run_id})
    return summarize(run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "summarize"])
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.command == "run":
        run_id = args.run_id or datetime.now(ZoneInfo("Asia/Shanghai")).strftime("b1_%Y%m%d_%H%M%S")
        summary = run_intake(run_id)
    else:
        run_id = args.run_id or read(PRIVATE / "latest_run.json")["run_id"]
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id), "INVALID_RUN_ID")
        summary = summarize(PRIVATE / "runs" / run_id)
    print(json.dumps({"status": summary["status"], "paired": summary["rebuild"]["members"],
                      "structural_ready": summary["research_admission"]["readiness"]["structural_ready"]}))


if __name__ == "__main__":
    main()
