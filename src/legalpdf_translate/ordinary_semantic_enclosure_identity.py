"""Opt-in old-occurrence identity around ordinary, semantically unverified additions."""
import unicodedata

from . import ordinary_semantic_review as review

POLICY = "bounded_distinct_additions_v1"
MAX_PAGE_OCCURRENCES = 8
MAX_TOTAL_OCCURRENCES = 24
MAX_VALUE_CHARS = 512
MAX_PAGE_CHARS = 2048
MAX_TOTAL_CHARS = 8192
MAX_WORK = 1_200_000


def _fail(code):
    review._fail("enclosure_identity_" + code)


def check_policy(policy):
    if policy is not None and (type(policy) is not str or policy != POLICY):
        _fail("policy")


def descriptor():
    return {"policy": POLICY, "mapping": "complete_old_sequence_at_actual_candidate_indices_v1",
        "exclusions": "page_local_original_and_projected_values_v1",
        "additions": "identity_only_semantically_unverified_v1",
        "max_page_occurrences": MAX_PAGE_OCCURRENCES, "max_total_occurrences": MAX_TOTAL_OCCURRENCES,
        "max_value_codepoints": MAX_VALUE_CHARS, "max_page_codepoints": MAX_PAGE_CHARS,
        "max_total_codepoints": MAX_TOTAL_CHARS, "max_work_codepoints": MAX_WORK}


class WorkBudget:
    """Shared by both pre/post-normalization checks of one validation call."""
    def __init__(self):
        self.charged = 0

    def charge(self, originals, projected, candidates):
        # Original/projected scans include their page-local alias-set construction.
        self.charged += sum(len(text) for group in (originals, projected, candidates) for text in group)
        if self.charged > MAX_WORK:
            _fail("work_bound")


class AdditionBudget:
    """One complete candidate pass; repeated new values consume separate slots."""
    def __init__(self):
        self.occurrences = 0
        self.characters = 0

    def mapping(self, tokens, expected, original_values):
        forbidden = set(original_values) | set(expected)
        indices = []; count = chars = 0
        for index, token in enumerate(tokens):
            value = token[2]
            if value in forbidden:
                if len(indices) >= len(expected) or value != expected[len(indices)]:
                    _fail("old_sequence")
                indices.append(index)
            else:
                count += 1; chars += len(value)
                if (len(value) > MAX_VALUE_CHARS or not value
                        or any(unicodedata.category(char) in {"Cc", "Cf"} for char in value)):
                    _fail("addition_value")
                if count > MAX_PAGE_OCCURRENCES or chars > MAX_PAGE_CHARS:
                    _fail("page_bound")
        if len(indices) != len(expected):
            _fail("old_sequence")
        self.occurrences += count; self.characters += chars
        if self.occurrences > MAX_TOTAL_OCCURRENCES or self.characters > MAX_TOTAL_CHARS:
            _fail("total_bound")
        return indices
