import copy
import unittest

from hybridguard_agent.research import mtc_screen_relations as screen
from hybridguard_agent.research.rule_learning.contracts import negate, state, logic
from hybridguard_agent.research.rule_learning_v2.semantic_selection import semantic_catalog


def observation(values=(411, 710, 411.4286, 710.4762, 1)):
    return {"features": dict(zip(screen.FIELDS, values)),
            "field_status": dict.fromkeys(screen.FIELDS, "observed"),
            "field_quality": dict.fromkeys(screen.FIELDS, "observed_value"),
            "source_binding": {"binding_valid": True, "same_app_record": True,
                               "app_session_id": "same-session", "web_fields_same_sync_probe": True}}


def result(record):
    return screen.evaluate(record)[screen.ATOM_ID]


class ScreenRelationTests(unittest.TestCase):
    def test_css_rounding_large_display_rotation_keyboard_and_pinch(self):
        for values in ((411, 710, 411.4286, 710.4762, 1),
                       (1200, 1800, 1200, 1800, 1),
                       (1800, 1200, 1800, 1200, 1),
                       (411, 710, 411, 360, 1),
                       (411, 710, 205.5, 355, 2)):
            with self.subTest(values=values):
                self.assertEqual(state(result(observation(values))), "F")

    def test_observed_contradiction_is_not_discarded(self):
        for values in ((400, 700, 402, 700, 1), (400, 700, 400, 702, 1)):
            self.assertEqual(state(result(observation(values))), "T")
        self.assertEqual(state(result(observation((400, 700, 401, 701, 1)))), "F")

    def test_missing_sentinels_quality_wrong_type_and_domain(self):
        for value in (0, -1, -2, None, "400", True, float("nan"), float("inf")):
            r = observation(); r["features"][screen.FIELDS[0]] = value
            self.assertEqual(state(result(r)), "U")
        r = observation(); del r["features"][screen.FIELDS[0]]
        self.assertEqual(result(r)["diagnostics"]["field_issues"][screen.FIELDS[0]], "FIELD_MISSING")
        for map_name in ("field_status", "field_quality"):
            r = observation(); r[map_name][screen.FIELDS[0]] = "unavailable"
            self.assertEqual(state(result(r)), "U")
        r = observation((400, 700, 800, 1400, .5))
        self.assertEqual(result(r)["diagnostics"]["availability"], "not_applicable")

    def test_axis_or_and_literal_negation(self):
        r = observation((400, 700, 402, -1, 1))
        self.assertEqual(state(result(r)), "T")
        r["features"][screen.FIELDS[2]] = 400
        self.assertEqual(state(result(r)), "U")
        self.assertEqual(negate(state(result(r))), "U")
        self.assertEqual(logic(("T", state(result(r))), "OR"), "T")
        self.assertEqual(logic(("F", state(result(r))), "OR"), "U")

    def test_current_session_binding_and_no_metadata_prediction(self):
        r = observation(); before = copy.deepcopy(r)
        expected = result(r)
        r.update(sample_id="other", model="tablet", phase="attack", label=1, future_clean={})
        self.assertEqual(result(r), expected)
        self.assertEqual(before, observation())
        r["source_binding"]["field_session_ids"] = {screen.FIELDS[0]: "other-device"}
        self.assertEqual(result(r)["reason"], "CROSS_SESSION_FIELDS_FORBIDDEN")
        r = observation(); del r["source_binding"]
        self.assertEqual(state(result(r)), "U")

    def test_registration_one_surface_no_fitting_or_bonus(self):
        atoms = screen.registered_atoms()
        self.assertEqual(len(atoms), 1)
        self.assertEqual(atoms[0].surfaces, ("app_web67",))
        catalog = semantic_catalog(atoms)
        self.assertEqual(catalog[screen.ATOM_ID]["quality"], 0)
        self.assertEqual(catalog[screen.ATOM_ID]["signal_group"], "display_geometry")
        self.assertEqual(atoms[0].provenance["condition"]["parameters"]["parameter_fitting"], "NONE")


if __name__ == "__main__":
    unittest.main()
