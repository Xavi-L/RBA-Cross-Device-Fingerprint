"""Path-only adapter for the frozen Browser67 verifier; no evidence rewriting."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import re
import sys

VERSION = "browser67-windows-path-compat-v1"
VERIFIER_SHA256 = "9185c07796b69f5219432af80f32cd71b2947b235622798bdd05185161f5fad8"
PILOT = "pilot_r8"


class PathMappingError(ValueError):
    pass


def windows_path(value: str) -> PureWindowsPath:
    if not isinstance(value, str) or not value or "\0" in value:
        raise PathMappingError("UNSUPPORTED_WINDOWS_PATH")
    path = PureWindowsPath(value)
    if not path.is_absolute() or not re.fullmatch(r"[A-Za-z]:", path.drive):
        raise PathMappingError("UNSUPPORTED_WINDOWS_PATH")
    # Reject traversal before resolving; also exclude ADS, device/UNC paths,
    # wildcards and Windows trailing-dot/space aliases.
    if any(part == ".." or part.endswith((".", " "))
           or any(char in part for char in ':*?<>|"') for part in path.parts[1:]):
        raise PathMappingError("UNSUPPORTED_WINDOWS_PATH")
    return path


def allowed_roots(build: dict) -> tuple[PureWindowsPath, PureWindowsPath]:
    return (windows_path(build["source_checkout"]).parent,
            windows_path(build["resume_archive_origin"]["directory"]))


def map_locked_path(root: Path, build: dict, absolute: str) -> Path:
    path = windows_path(absolute)
    root = root.resolve(strict=True)
    for origin in allowed_roots(build):
        try:
            relative = path.relative_to(origin)
        except ValueError:
            continue
        candidate = root.joinpath(*relative.parts).resolve()
        if not candidate.is_relative_to(root):
            raise PathMappingError("LOCKED_PATH_ESCAPE")
        return candidate
    raise PathMappingError("LOCKED_PATH_OUTSIDE_RUN")


def load_verifier(root: Path, *, compatible: bool = True):
    path = root / "verify_pilot.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != VERIFIER_SHA256:
        raise ValueError("ARCHIVED_VERIFIER_DIGEST_MISMATCH")
    name = "_browser67_frozen_verifier_compat" if compatible else "_browser67_frozen_verifier_original"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    if compatible:
        def locked_path(inputs, absolute):
            try:
                return map_locked_path(inputs.root, inputs.build, absolute)
            except PathMappingError as error:
                raise module.VerificationError(str(error)) from error
        # This is the only replacement in the archived module. Its verification,
        # self-test mutations, source/APK locks and conditions run unchanged.
        module.Inputs.locked_path = locked_path
    return module


def run_verifier(root: Path, output: Path, *, self_test: bool = False) -> dict:
    root = root.resolve(strict=True)
    output = output.resolve()
    if output.is_relative_to(root):
        raise ValueError("OUTPUT_MUST_BE_OUTSIDE_EVIDENCE")
    module = load_verifier(root)
    provenance = root / PILOT / "session_provenance.jsonl"
    result = (module.self_test if self_test else module.verify)(root, provenance, PILOT)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--pilot", choices=[PILOT], default=PILOT)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    result = run_verifier(args.root, args.output, self_test=args.self_test)
    print(json.dumps({key: result[key] for key in ("verification", "tests", "passed", "verified_stages") if key in result}))


if __name__ == "__main__":
    main()
