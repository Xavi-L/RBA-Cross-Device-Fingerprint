"""Language/first-item relation only; no Native, model, or historical record access."""
from __future__ import annotations

from copy import deepcopy
import re

from .contracts import ContractError, Issue, make_cell
from .input_adapter import binding_issues, issue_cell, read_observation

CANDIDATE_ID = "RSR-LANG-FIRST-v1"
LANGUAGE_FIELD = "app.web_data.navigator_layer.language"
LANGUAGES_FIELD = "app.web_data.navigator_layer.languages"
_TAG = re.compile(r"([A-Za-z]{2,3})(?:-([A-Za-z]{4}))?(?:-([A-Za-z]{2}|[0-9]{3}))?")
_EXCLUDED_PRIMARY = frozenset(("und", "mul", "zxx", "iw", "in", "ji"))


def limited_full_tag(value: object) -> str | None:
    """An explicit subset, not a complete BCP47 validity test. No trimming."""
    if type(value) is not str:
        return None
    match = _TAG.fullmatch(value)
    if match is None or match[1].lower() in _EXCLUDED_PRIMARY:
        return None
    # The full match has already constrained every letter to ASCII.
    return value.lower()


def web_language_first_difference(payload: object, source_binding=None):
    """Return T iff supported full language and first list tag differ.

    Precedence: envelope/enums, field availability (language then languages),
    source association, operand shape, limited tag domain, comparison. Any
    structural FAILED is retained even if another input is missing. T/F never
    says whether the reported language is the user's genuine preference.
    """
    try:
        language = read_observation(payload, LANGUAGE_FIELD)
        languages = read_observation(payload, LANGUAGES_FIELD)
        issues = (*language.issues, *languages.issues,
                  *binding_issues(source_binding, "navigator_sync_v1"))
        diagnostics = {"information_relation": "SAME_LAYER_SELF_CONSISTENCY",
                       "implementation_conformance": "UNVERIFIED"}
        if type(languages.value) is list:
            diagnostics["languages_tail"] = deepcopy(languages.value[1:])
            diagnostics["tail_issues"] = [
                {"index": index, "reason": "NONSTRING_TAIL_ITEM" if type(value) is not str else "UNSUPPORTED_TAIL_TAG"}
                for index, value in enumerate(languages.value[1:], 1)
                if limited_full_tag(value) is None]
        if issues:
            return issue_cell(CANDIDATE_ID, issues, diagnostics=diagnostics)
        if (type(language.value) is not str or type(languages.value) is not list or
                not languages.value or type(languages.value[0]) is not str):
            return make_cell(CANDIDATE_ID, "U", "MISSING_OR_INVALID_LANGUAGE_INPUT", diagnostics=diagnostics)
        left, right = limited_full_tag(language.value), limited_full_tag(languages.value[0])
        if left is None or right is None:
            return make_cell(CANDIDATE_ID, "U", "UNSUPPORTED_OR_INVALID_FIRST_LANGUAGE_TAG", diagnostics=diagnostics)
        return make_cell(CANDIDATE_ID, "T" if left != right else "F",
                         "FIRST_TAG_DIFFERS" if left != right else "FIRST_TAG_EQUAL", diagnostics=diagnostics)
    except ContractError as error:
        return make_cell(CANDIDATE_ID, "FAILED", error.reason)
    except Exception as error:
        return make_cell(CANDIDATE_ID, "FAILED", "EXECUTOR_ERROR",
                         diagnostics={"exception_type": type(error).__name__})
