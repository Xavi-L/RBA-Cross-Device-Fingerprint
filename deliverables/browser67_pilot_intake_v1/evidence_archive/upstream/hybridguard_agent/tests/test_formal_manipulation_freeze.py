"""S05 tests read static accepted directories; never execute sample predictions."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from hybridguard_agent.research.manipulation_eval import freeze as f


class FreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = f.build()
        cls.a = f.ROOT / f.ARTIFACT / "01_admission"
        cls.i = f.ROOT / f.ARTIFACT / "02_inputs"

    def population_args(self):
        return [f.lines(self.a / "facts_and_eligibility.jsonl"), f.lines(self.i / "evaluation_index.jsonl"),
                f.lines(self.i / "inference_inputs.jsonl"), f.lines(self.a / "triplet_registry.jsonl"),
                f.lines(self.a / "material_inventory.jsonl")]

    def test_static_262_accounting_and_inherited_denominators(self):
        p = self.data["population"]
        self.assertEqual(p["counts"]["raw_stages"], 262)
        self.assertEqual(len(p["main_ids"]), 216)
        self.assertEqual(len(p["descriptive_ids"]), 46)
        self.assertEqual({k: p["denominators"][k]["n"] for k in ["positive", "clean_pre", "clean_post", "eligible_triplets", "control_mid", "all_negative", "unknown_truth"]},
                         dict(positive=54, clean_pre=54, clean_post=54, eligible_triplets=54, control_mid=0, all_negative=108, unknown_truth=100))
        self.assertEqual(sum(r["raw_rows"] == 0 for r in self.data["inventory"]), 1)

    def test_fact_conflict_never_silently_relabels(self):
        args = self.population_args()
        args[1][0]["admission_fact"]["eligible_detection"] = True
        with self.assertRaisesRegex(ValueError, "fact conflict"):
            f.population(*args)

    def test_raw_label_change_cannot_grant_eligibility(self):
        args = self.population_args()
        for fact in args[0]:
            fact["original_label"] = {"manipulation_present": False, "label_status": "verified_control"}
        mapped = {r["candidate_id"]: r for r in args[0]}
        for r in args[1]:
            r["admission_fact"] = deepcopy(mapped[r["candidate_id"]])
        self.assertEqual(f.population(*args)["denominators"], self.data["population"]["denominators"])

    def test_duplicate_and_missing_stage_keys_fail(self):
        args = self.population_args()
        args[1].append(deepcopy(args[1][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            f.population(*args)
        args = self.population_args()
        args[2].pop()
        with self.assertRaisesRegex(ValueError, "Input/index"):
            f.population(*args)

    def test_same_payload_different_units_are_not_deduplicated(self):
        args = self.population_args()
        args[2][1]["payload"] = deepcopy(args[2][0]["payload"])
        p = f.population(*args)
        units, _ = f.matrices(p, args[2], self.data["bindings"])
        self.assertEqual(len(units), 2854)
        self.assertTrue({args[2][0]["opaque_id"], args[2][1]["opaque_id"]} <= {r["opaque_id"] for r in units})

    def test_shared_variants_execute_once_and_descriptive_rows_stay_separate(self):
        units = self.data["expected"]
        self.assertEqual(len({(r["opaque_id"], r["variant_id"]) for r in units}), 2854)
        self.assertEqual(dict(f.Counter(r["first_execution_step"] for r in units)), {"S06": 432, "S07": 1512, "S08": 864, "S10": 46})
        self.assertEqual(self.data["variants"]["four_source_mapping"], {"C": "SRC-000", "B0": "SRC-000", "E": "SRC-001", "O": "SRC-110", "EO": "SRC-111"})
        self.assertEqual(self.data["variants"]["experiments"]["S07"]["reuse_from_S06"], [f.BASE])

    def test_version_missing_conflict_and_threshold_drift_rejected(self):
        # Only the small config directories necessary for static binding tests.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copytree(f.ROOT / "hybridguard_agent/config", root / "hybridguard_agent/config", ignore=shutil.ignore_patterns("formal_manipulation_protocol_v2"))
            p = root / f.ROLE / "decision_roles.json"
            original = p.read_bytes()
            data = f.read(p); data["contract_version"] = "v1"
            p.write_bytes(f.encoded(data))
            with self.assertRaisesRegex(ValueError, "v2 config"):
                f.load_bindings(root)
            p.write_bytes(original)
            policy = root / f.POLICY_DIR / "decision_policy.json"
            v = f.read(policy); v["threshold"] = 2; policy.write_bytes(f.encoded(v))
            with self.assertRaisesRegex(ValueError, "threshold"):
                f.load_bindings(root)
            p.unlink()
            with self.assertRaises(FileNotFoundError):
                f.load_bindings(root)

    def test_destinations_require_both_and_reject_overlap_existing_and_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            with self.assertRaisesRegex(ValueError, "Both"):
                f.destinations(f.ROOT, p / "out", None)
            with self.assertRaisesRegex(ValueError, "Overlapping"):
                f.destinations(f.ROOT, p / "out", p / "out/config")
            (p / "existing").mkdir()
            with self.assertRaisesRegex(ValueError, "exists"):
                f.destinations(f.ROOT, p / "existing", p / "other")
            (p / "link").symlink_to(f.ROOT / f.ROLE, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Protected"):
                f.destinations(f.ROOT, p / "out", p / "link/new-config")
            self.assertFalse((p / "out").exists())

    def test_timing_sampling_independent_of_row_order_and_never_result_selected(self):
        selected, strata = f.select_timing(self.data["enriched"], self.data["population"]["main_ids"])
        other, _ = f.select_timing(list(reversed(self.data["enriched"])), self.data["population"]["main_ids"])
        self.assertEqual(selected, other)
        self.assertEqual(len(set(selected)), 24)
        self.assertTrue(all(s["selected_ids"] for s in strata))
        self.assertEqual(len(self.data["timing_units"]), 24 * 2 * (1 + 3 + 20))

    def test_diagnostics_finite_domains_and_no_fake_risk_labels(self):
        definitions = {d["diagnostic_id"]: d for d in self.data["diagnostics"]["definitions"]}
        self.assertEqual(definitions["D2_UNKNOWN_AS_COMPARABLE"]["domains"], ["synthetic_semantic"])
        self.assertEqual(definitions["D4_RAW_UNCONDITIONAL_EQUALITY"]["domains"], ["synthetic_semantic"])
        self.assertFalse(self.data["diagnostics"]["common"]["formal_risk_prediction"])
        self.assertEqual(len(self.data["diag_units"]), 480)
        self.assertEqual(len(self.data["synthetic"]), 49)
        self.assertTrue(all(r["truth"] == "UNKNOWN_SYNTHETIC_NO_ATTACK_LABEL" for r in self.data["synthetic"]))
        twins = [r for r in self.data["synthetic"] if r["fixture_id"] in {"COORDINATED_IDENTITIES", "INDISTINGUISHABLE_TWIN"}]
        self.assertEqual(twins[0]["payload"], twins[1]["payload"])
        self.assertNotEqual(twins[0]["opaque_id"], twins[1]["opaque_id"])

    def test_strata_enrichment_preserves_all_S01_facts_and_original_S02(self):
        original = f.lines(self.i / "evaluation_index.jsonl")
        for old, new in zip(original, self.data["enriched"]):
            self.assertEqual(old["admission_fact"], new["admission_fact"])
            self.assertEqual(old["configuration_id"], new["S02_configuration_id"])
            self.assertTrue(new["configuration_id"])
        self.assertTrue(all(m["control_key"] is None for m in self.data["matching"]))
        self.assertEqual(len(self.data["matching"]), 54)

    def test_figure6_cannot_substitute_another_FPR_population(self):
        fig = f.figure_spec(f.ROOT, self.data["enriched"])
        self.assertEqual(fig["figures"][-1]["status"], "NOT_EVALUATED_NO_ELIGIBLE_TEMPORAL_CONTROL_LABELS")
        self.assertIn("Do not replace", fig["figures"][-1]["fallback"])

    def test_static_import_closure_and_no_runtime_modules_loaded(self):
        paths = f.source_closure(f.ROOT, ["hybridguard_agent/scripts/run_formal_manipulation_eval.py"])
        self.assertIn(Path("hybridguard_agent/rules/paired244.py"), paths)
        self.assertIn(Path("hybridguard_agent/research/manipulation_eval/provenance_revision.py"), paths)
        self.assertFalse(any(m.startswith(("hybridguard_agent.rules", "hybridguard_agent.runtime", "hybridguard_agent.verification")) for m in sys.modules))

    def test_duplicate_json_and_nonfinite_config_rejected(self):
        for data in ('{"threshold":1,"threshold":2}', '{"threshold":NaN}'):
            with self.assertRaises(ValueError):
                f.decode(data)


if __name__ == "__main__":
    unittest.main()
