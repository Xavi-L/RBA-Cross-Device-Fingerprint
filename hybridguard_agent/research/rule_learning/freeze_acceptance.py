"""Record independent R04 acceptance from the frozen dispatcher, never real fit."""
import io
import json
from pathlib import Path
import sys
import unittest

from .contracts import ROOT
from .job_runtime import write_json


def validate(output):
    from hybridguard_agent.tests import test_rule_learning_r04 as test_module
    test_module.OUTPUT = str(Path(output).resolve())
    test_module.EVIDENCE.clear()
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_module))
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "FOCUSED_TESTS.txt").write_text(stream.getvalue())
    write_json(out / "SYNTHETIC_CHAIN_VALIDATION.json", {"status": "PASS" if result.wasSuccessful() else "FAIL",
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "evidence": test_module.EVIDENCE, "real_fit_grants_issued": 0, "real_fits": 0, "real_predictions": 0,
        "root": str(ROOT), "cwd": str(Path.cwd()), "cwd_entries": sorted(p.name for p in Path.cwd().iterdir()),
        "loaded_modules": {name: str(module.__file__) for name, module in sorted(sys.modules.items())
                           if getattr(module, "__file__", None) and name.startswith(("hybridguard_agent", "numpy", "highspy"))}})
    if not result.wasSuccessful():
        raise AssertionError(stream.getvalue())
    print(json.dumps({"status": "PASS_INDEPENDENT_SYNTHETIC_CHAIN", "tests": result.testsRun,
                      "real_fits": 0, "real_risk_predictions": 0}))
