"""Only binding and experiment-admission boundaries; synthetic, not device evidence."""
import unittest
from analyze import environment_gate, triplet_passes, validate_binding


def positive():
    return dict(status="COMPLETE", target_effect=True, raw_graphics_restored=True,
                non_target_graphics_unchanged=True, sidecar_contexts_restored=True,
                relation_separation_observed=True, canonical_webgl1_link=True)


class Boundaries(unittest.TestCase):
    def test_wrong_or_changed_session_cannot_self_bind(self):
        observation = {"realm_binding": "featureapp:session-a:main-frame"}
        binding = dict(session_id_before="session-a", session_id_after="session-a",
                       url_before="file:///android_asset/expanded_probe.html", url_after="file:///android_asset/expanded_probe.html",
                       canonical_probe_revision="expanded-web-67-v2")
        self.assertTrue(validate_binding(binding, observation, "session-a", "expanded-web-67-v2"))
        self.assertFalse(validate_binding(binding, observation, "session-b", "expanded-web-67-v2"))
        binding["session_id_after"] = "session-b"
        self.assertFalse(validate_binding(binding, observation, "session-a", "expanded-web-67-v2"))

    def test_changed_document_or_revision_rejected(self):
        observation = {"realm_binding": "featureapp:session-a:main-frame"}
        for override in ({"url_after": "about:blank"}, {"canonical_probe_revision": "old"}):
            binding = dict(session_id_before="session-a", session_id_after="session-a",
                           url_before="file:///android_asset/expanded_probe.html", url_after="file:///android_asset/expanded_probe.html",
                           canonical_probe_revision="expanded-web-67-v2")
            binding.update(override)
            self.assertFalse(validate_binding(binding, observation, "session-a", "expanded-web-67-v2"))

    def test_failed_or_unknown_control_not_positive(self):
        self.assertTrue(triplet_passes(positive()))
        for key in ("target_effect", "raw_graphics_restored", "non_target_graphics_unchanged",
                    "sidecar_contexts_restored", "relation_separation_observed", "canonical_webgl1_link"):
            for value in (False, None, "UNKNOWN"):
                row = positive(); row[key] = value
                self.assertFalse(triplet_passes(row))

    def test_partial_run_kept_in_planned_denominator(self):
        self.assertTrue(environment_gate([positive(), positive()], 2, True))
        self.assertFalse(environment_gate([positive()], 2, True))
        self.assertFalse(environment_gate([positive(), positive()], 2, False))
        self.assertFalse(environment_gate([positive(), {"status": "INCOMPLETE"}], 2, True))


if __name__ == "__main__":
    unittest.main()
