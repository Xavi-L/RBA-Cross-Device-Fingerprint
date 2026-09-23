"""Require two explicit, disjoint, unused destinations before registry writes."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PROTECTED = (
    ROOT / "hybridguard_agent/config/formal_manipulation_v1",
    *(ROOT / "hybridguard_agent/artifacts/formal_manipulation_v1_20260923" / name
      for name in ("01_admission", "02_inputs", "03_registry")),
)


def validate_destinations(output, config_dir):
    if output is None or config_dir is None:
        raise ValueError("Both --output and --config-dir must be explicitly supplied")
    paths = tuple(Path(p).resolve() for p in (output, config_dir))
    if paths[0] == paths[1] or any(a in b.parents for a, b in (paths, paths[::-1])):
        raise ValueError("Output and config-dir must be separate, non-nested directories")
    for path in paths:
        for frozen in PROTECTED:
            frozen = frozen.resolve()
            if path == frozen or frozen in path.parents or path in frozen.parents:
                raise ValueError("An accepted S01/S02/S03 path cannot be a write destination")
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise ValueError("Registry destinations must be new or empty; use another version")
    return paths
