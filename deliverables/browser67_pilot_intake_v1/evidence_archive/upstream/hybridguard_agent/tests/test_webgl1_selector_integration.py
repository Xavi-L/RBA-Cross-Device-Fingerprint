"""Source, tri-state, structural identity and actual selector interface checks."""
import copy
from dataclasses import asdict, replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from hybridguard_agent.research import webgl1_selector_integration as integration
from hybridguard_agent.research.rule_learning.contracts import cell, logic, negate, state
from hybridguard_agent.research.rule_learning.models import Atom, Clause, Literal
from hybridguard_agent.research.rule_learning.predictor import clause_state
from hybridguard_agent.research.rule_learning_v2.adapter import approved_atoms
from hybridguard_agent.research.rule_learning_v2.common import SURFACES
from hybridguard_agent.research.rule_learning_v2.semantic_selection import semantic_catalog


class WebGL1IntegrationTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/webgl_parameter_equivalence_v1/observer_examples.json").read_text())
        self.observation = next(c["observation"] for c in fixture["cases"] if c["id"] == "normal")
        self.observation["realm_binding"] = "featureapp:test-session:main-frame"
        self.source = integration.SourceRegistration("synthetic-source-contract")
        self.raw = {"session_id": "test-session", "collector_app": "featureapp", "schema_version": "expanded-v2.2-status",
                    "collection_manifest": {"collector_version_code": 14,
                        "collector_version_name": integration.COLLECTOR_VERSION_NAME, "web_probe_revision": "expanded-web-67-v2"},
                    "collection_observations": {"observation_schema_version": "app-web-observations-v1", "webgl_parameter": {
                        "collection_revision": integration.COLLECTION_REVISION, "read_status": "observed",
                        "reason": None, "observation": self.observation}}}

    def compile(self, raw=None, **kwargs):
        return integration.compile_payload(self.raw if raw is None else raw,
            **{"expected_session_id": "test-session", "source_registration": self.source, **kwargs})

    def test_t_f_u_and_no_mutation_or_webgl2_borrowing(self):
        before = copy.deepcopy(self.raw)
        self.assertEqual(self.compile()["state"], "F")
        self.assertEqual(self.raw, before)
        self.observation["contexts"][1]["preflight"]["errors"] = [1280]
        compiled = self.compile()
        self.assertEqual(compiled["state"], "F")
        self.assertEqual(compiled["diagnostics"]["webgl2"]["outcome"], "UNKNOWN")
        for key in ("numeric_before", "numeric_after"):
            self.observation["contexts"][0]["parameters"]["renderer"][key]["value"] = "synthetic changed"
        self.assertEqual(self.compile()["state"], "T")
        self.observation["contexts"][0]["preflight"]["errors"] = [1280]
        self.assertEqual(self.compile()["state"], "U")

    def test_valid_conflict_survives_other_parameter_unknown_but_not_context_failure(self):
        context = self.observation["contexts"][0]
        for key in ("numeric_before", "numeric_after"):
            context["parameters"]["renderer"][key]["value"] = "synthetic changed"
        context["parameters"]["vendor"]["numeric_string"]["read_status"] = "runtime_error"
        compiled = self.compile()
        self.assertEqual(compiled["state"], "T")
        self.assertEqual(compiled["diagnostics"]["webgl1"]["parameters"]["vendor"]["outcome"], "UNKNOWN")
        context["preflight"]["errors"] = [1280]
        self.assertEqual(self.compile()["state"], "U")

    def test_missing_error_and_old_data_never_become_false(self):
        for key in ("collection_observations", "collection_manifest", "session_id"):
            raw = copy.deepcopy(self.raw); del raw[key]
            self.assertEqual(self.compile(raw)["state"], "U")
        for status in ("runtime_error", "unsupported", "not_collected", "unexpected", None):
            raw = copy.deepcopy(self.raw)
            raw["collection_observations"]["webgl_parameter"].update(read_status=status, observation=None)
            self.assertEqual(self.compile(raw)["state"], "U")
        self.raw["collection_manifest"]["collector_version_code"] = 13
        self.assertEqual(self.compile()["state"], "U")

    def test_external_source_session_and_full_envelope_gates(self):
        for kwargs in ({"source_registration": None}, {"source_registration": {}},
                       {"source_registration": replace(self.source, source_reference="")},
                       {"expected_session_id": "another"}, {"expected_session_id": ""}):
            self.assertEqual(self.compile(**kwargs)["state"], "U")
        for key in ("realm_binding", "observer_revision", "observation_scope", "observation_schema_version"):
            raw = copy.deepcopy(self.raw)
            raw["collection_observations"]["webgl_parameter"]["observation"][key] = "wrong"
            self.assertEqual(self.compile(raw)["state"], "U")
        self.observation["contexts"] = self.observation["contexts"][:1]
        self.assertEqual(self.compile()["state"], "U")

    def test_metadata_is_not_an_input_feature(self):
        before = integration.kernel_cell(self.compile())
        self.raw.update(supervised_label=1, phase="attack", config_id="anything", source_registration={"approved": True})
        self.raw["collection_manifest"].update(android_api=123, runtime_context="other", device_manifest_id="other")
        self.assertEqual(integration.kernel_cell(self.compile()), before)
        self.assertEqual(set(before), {"value", "available", "evaluation_status", "reason"})

    def test_definition_extension_saved_projection_and_existing_clause_execution(self):
        old = Atom("old", "f", ("app_web67",), ("SYNTHETIC",), (), "CONTROL_LE", {"field": "fixture.x", "threshold": 1})
        defs = {"atoms": [asdict(old)], "single_surface_allowlists": {s: ["old"] if s == "app_web67" else [] for s in SURFACES}}
        before = copy.deepcopy(defs)
        registered = integration.register_definitions(defs)
        self.assertEqual(defs, before)
        atoms = approved_atoms(registered)
        self.assertEqual(len(atoms), 2)
        self.assertEqual(semantic_catalog([old])["old"], semantic_catalog(atoms)["old"])
        with self.assertRaisesRegex(ValueError, "ALREADY_REGISTERED"):
            integration.register_definitions(registered)
        saved = {"match": self.compile(), "unknown": self.compile(source_registration=None)}
        for key in ("numeric_before", "numeric_after"):
            self.observation["contexts"][0]["parameters"]["renderer"][key]["value"] = "synthetic changed"
        saved["conflict"] = self.compile()
        base = {sid: {"old": cell("F")} for sid in saved}
        with patch.object(integration, "evaluate_webgl1_candidate", side_effect=AssertionError("no re-evaluation")):
            rows = integration.project_rows(base, registered, saved)
        clause = Clause((Literal(integration.CANDIDATE_ID),))
        self.assertEqual({sid: clause_state(clause, row) for sid, row in rows.items()},
                         {"match": "F", "unknown": "U", "conflict": "T"})
        self.assertEqual(negate(state(rows["unknown"][integration.CANDIDATE_ID])), "U")
        self.assertEqual(logic(["F", "U"], "OR"), "U")
        with self.assertRaisesRegex(ValueError, "EXACT_SAVED"):
            integration.project_rows(base, registered, {"match": saved["match"]})

    def test_structural_identity_and_reject_tampered_saved_encoding(self):
        original = integration.registered_atom()
        renamed = replace(original, atom_id="renamed", aliases=("other",),
                          provenance={**original.provenance, "candidate_id": "renamed"})
        catalog = semantic_catalog([original])[original.atom_id]
        self.assertEqual(catalog, semantic_catalog([renamed])["renamed"])
        self.assertEqual(catalog["quality"], 0)
        self.assertEqual(catalog["signal_group"], "graphics_identity")
        bad = replace(original, provenance={**original.provenance, "observer_revision": "other"})
        with self.assertRaisesRegex(ValueError, "UNREGISTERED_WEBGL1"):
            semantic_catalog([bad])
        for change in ({"value": 0}, {"available": 1}, {"state": "T"}, {"registration_version": "other"}):
            with self.assertRaises(ValueError):
                integration.kernel_cell({**self.compile(), **change})


if __name__ == "__main__":
    unittest.main()
