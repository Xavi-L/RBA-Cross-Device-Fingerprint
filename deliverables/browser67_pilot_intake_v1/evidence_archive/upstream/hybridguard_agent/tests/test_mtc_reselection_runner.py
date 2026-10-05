"""Stage boundaries and selective historical reads without real model fits."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[2] / "deliverables/mtc_constrained_reselection_v1/run_experiment.py"
SPEC = importlib.util.spec_from_file_location("mtc_reselection_runner", PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class RunnerBoundaryTests(unittest.TestCase):
    def test_training_reader_does_not_parse_unselected_evaluation_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            good = {"sample_id": "train", "dataset_view": "paired_244"}
            (path / "paired_244.jsonl").write_text(json.dumps(good) + "\nBAD_EVALUATION_JSON\n")
            registry = {"train": {"source_view": "paired_244", "source_line": 1},
                        "eval": {"source_view": "paired_244", "source_line": 2}}
            rows, errors = runner.load_selected_mtc(registry, ["train"], path, allowed_ids=["train"])
            self.assertEqual(rows, {"train": good})
            self.assertFalse(errors)
            with self.assertRaises(PermissionError):
                runner.load_selected_mtc(registry, ["eval"], path, allowed_ids=["train"])
            rows, errors = runner.load_selected_mtc(registry, ["eval"], path, allowed_ids=["eval"])
            self.assertFalse(rows)
            self.assertIn("eval", errors)

    def test_evaluation_requires_all_twelve_prespecified_fits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            cfg = {"folds": [{"fold_id": str(i)} for i in range(3)]}
            models = [{"scheme": s, "fold_id": f["fold_id"], "stage": stage}
                      for s in runner.SCHEMES for f in cfg["folds"] for stage in runner.STAGES]
            runner.write(path / "SETTINGS.json", cfg)
            runner.write(path / "EXECUTION.json", {"all_fits_closed": True, "actual_fit_calls": 12})
            runner.write(path / "models.json", {"models": models})
            (path / "FIT_CALLS.jsonl").write_text("{}\n" * 11)
            with self.assertRaises(PermissionError):
                runner.require_evaluation_ready(path)
            (path / "FIT_CALLS.jsonl").write_text("{}\n" * 12)
            self.assertEqual(len(runner.require_evaluation_ready(path)["models"]), 12)

    def test_prespecified_mtc_groups_do_not_cross_train_evaluation(self):
        cfg = runner.read(PATH.parent / "SETTINGS.json")
        registry = runner.registry(cfg)
        members = cfg["mtc_primary_ids"]
        self.assertEqual([len(members[k]) for k in ("discovery", "development", "reserved_validation")], [630, 144, 117])
        train_groups = {registry[s]["group_id"] for s in members["discovery"]}
        evaluation = members["development"] + members["reserved_validation"]
        self.assertFalse(train_groups & {registry[s]["group_id"] for s in evaluation})
        self.assertEqual(cfg["planned_fit_calls"], 12)
        self.assertEqual(cfg["mtc_normal_train_ids"], members["discovery"])


if __name__ == "__main__":
    unittest.main()
