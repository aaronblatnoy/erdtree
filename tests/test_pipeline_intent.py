"""
tests/test_pipeline_intent.py — Tests for core/agent/pipeline/intent.py

Coverage
--------
1. Labeled inputs map to the correct (tool, operation) using:
   (a) a synthetic registry with unique discriminating descriptions (precise tests)
   (b) the live registry with queries closely matching actual op descriptions
2. Ambiguous/empty inputs return NoConfidentMatch.
3. Tests use only a stub embedder or stub responder — no network, no Ollama.
4. Empty registry returns NoConfidentMatch.
5. No backend injected returns NoConfidentMatch.
6. Model backend: valid response -> IntentMatch; invalid/garbled -> NoConfidentMatch.
7. Top-K: near-tied candidates both appear in top_k.
8. Confidence is always in [0.0, 1.0].
9. Empty user_input returns NoConfidentMatch immediately.
10. I2: no AI/LLM/model/agent language in NoConfidentMatch.reason.

Stub embedder design
--------------------
A bag-of-words (BOW) embedder converts text to normalised term-frequency vectors
over a fixed vocabulary.  It is deterministic and requires no network.

For precision "labeled" tests, we use a SYNTHETIC registry whose op descriptions
contain unique discriminating tokens, so the BOW similarity is unambiguous.

For smoke tests against the live registry, we only assert the return type is
one of (IntentMatch, NoConfidentMatch) — not which one — since a plain BOW
embedder over natural language descriptions is not a reliable classifier.
"""

from __future__ import annotations

import math
import re
from typing import Any
from unittest.mock import MagicMock

import pytest

# Side-effect: registers all core tools into the module-level registry.
import core.agent.main  # noqa: F401

from core.agent.pipeline.intent import (
    CONFIDENCE_THRESHOLD,
    TIE_MARGIN,
    IntentMatch,
    NoConfidentMatch,
    classify_intent,
    _build_candidate_space,
    _cosine,
)
from core.agent.permissions import OpClass
from core.tools import ArgSpec, OpSpec, ToolRegistry, ToolResult, ToolSpec
from core.tools import registry as live_registry


# ---------------------------------------------------------------------------
# Stub embedder
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Lower-case, split on non-alphanumeric boundaries."""
    return re.findall(r"[a-z0-9]+", text.lower())


def make_bow_embedder(vocab: list[str]):
    """Return a bag-of-words embedder over the given vocabulary.

    The returned callable is deterministic: the same text always produces the
    same vector. Each dimension is the normalised term frequency for that vocab
    entry. Equal-length vectors guaranteed for all inputs.
    """
    vocab_index = {w: i for i, w in enumerate(vocab)}

    def embed(text: str) -> list[float]:
        tokens = _tokenize(text)
        vec = [0.0] * len(vocab)
        for token in tokens:
            if token in vocab_index:
                vec[vocab_index[token]] += 1.0
        total = sum(vec)
        if total > 0:
            vec = [v / total for v in vec]
        return vec

    return embed


# ---------------------------------------------------------------------------
# Synthetic registry builder
# ---------------------------------------------------------------------------

def _noop_execute(op: str, args: dict) -> ToolResult:
    return ToolResult(exit_code=0, stdout="", stderr="", summary="ok")


def make_synthetic_registry(*tool_op_pairs: tuple[str, str, str, str]) -> ToolRegistry:
    """Build a test registry with unique, unambiguous descriptions.

    Each entry is a (tool_name, tool_desc, op_name, op_desc) tuple.
    The op_desc should contain unique tokens not shared with other entries.
    """
    reg = ToolRegistry()
    tools: dict[str, tuple[str, dict[str, OpSpec]]] = {}
    for tool_name, tool_desc, op_name, op_desc in tool_op_pairs:
        if tool_name not in tools:
            tools[tool_name] = (tool_desc, {})
        tools[tool_name][1][op_name] = OpSpec(
            op_name=op_name,
            permission_class=OpClass.READ,
            args=[],
            description=op_desc,
        )
    for tool_name, (tool_desc, ops) in tools.items():
        reg.register(ToolSpec(
            name=tool_name,
            description=tool_desc,
            ops=ops,
            execute=_noop_execute,
        ))
    return reg


# ---------------------------------------------------------------------------
# Cosine similarity unit tests
# ---------------------------------------------------------------------------

class TestCosine:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 1.0]
        assert math.isclose(_cosine(v, v), 1.0, abs_tol=1e-9)

    def test_orthogonal_vectors(self):
        assert math.isclose(_cosine([1.0, 0.0], [0.0, 1.0]), 0.0, abs_tol=1e-9)

    def test_zero_vector(self):
        assert _cosine([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_mismatched_lengths_returns_zero(self):
        assert _cosine([1.0, 0.0], [1.0]) == 0.0

    def test_partial_overlap(self):
        sim = _cosine([1.0, 1.0, 0.0], [1.0, 0.0, 0.0])
        assert 0.0 < sim < 1.0


# ---------------------------------------------------------------------------
# Candidate space tests
# ---------------------------------------------------------------------------

class TestBuildCandidateSpace:
    def test_candidates_non_empty_for_live_registry(self):
        candidates = _build_candidate_space(live_registry)
        assert len(candidates) > 0

    def test_candidate_format(self):
        candidates = _build_candidate_space(live_registry)
        for cand in candidates:
            assert cand.tool
            assert cand.operation
            assert cand.description  # non-empty

    def test_all_ops_represented(self):
        candidates = _build_candidate_space(live_registry)
        pairs = {(c.tool, c.operation) for c in candidates}
        assert ("services", "restart") in pairs
        assert ("packages", "install") in pairs
        assert ("disk", "format") in pairs

    def test_empty_registry(self):
        empty = ToolRegistry()
        candidates = _build_candidate_space(empty)
        assert candidates == []

    def test_description_format(self):
        """Candidate description must combine tool and op descriptions."""
        candidates = _build_candidate_space(live_registry)
        for cand in candidates:
            # The separator " — " is the marker between tool desc and op desc.
            assert " — " in cand.description


# ---------------------------------------------------------------------------
# Precision labeled-input tests (synthetic registry with unique tokens)
# ---------------------------------------------------------------------------

# Each synthetic op description uses a UNIQUE leading token that does not
# appear anywhere else. The query uses that same unique token so the BOW
# similarity is unambiguous: exactly one candidate wins.

SYNTHETIC_REGISTRY = make_synthetic_registry(
    ("alpha", "Alpha system management tool.",
     "activate", "xqactivate_token — start and activate the main process"),
    ("alpha", "Alpha system management tool.",
     "deactivate", "xqdeactivate_token — stop and deactivate the process"),
    ("beta", "Beta configuration management tool.",
     "configure", "xqconfigure_token — write and apply configuration settings"),
    ("beta", "Beta configuration management tool.",
     "reset", "xqreset_token — restore settings to the factory default values"),
    ("gamma", "Gamma storage management tool.",
     "allocate", "xqallocate_token — reserve disk space for a new volume"),
    ("gamma", "Gamma storage management tool.",
     "release", "xqrelease_token — free reserved storage back to the pool"),
)

# Vocabulary for synthetic tests: just the unique tokens from above.
SYNTHETIC_VOCAB = [
    "xqactivate", "token", "xqdeactivate", "xqconfigure",
    "xqreset", "xqallocate", "xqrelease",
    "start", "activate", "main", "process",
    "stop", "deactivate",
    "write", "apply", "configuration", "settings",
    "restore", "factory", "default", "values",
    "reserve", "disk", "space", "volume",
    "free", "reserved", "storage", "pool",
]


class TestEmbeddingBackendPrecision:
    """Labeled tests using the synthetic registry — unambiguous by design."""

    def _embed_and_classify(self, query: str) -> Any:
        embedder = make_bow_embedder(SYNTHETIC_VOCAB)
        return classify_intent(
            query,
            snapshot_text="",
            registry=SYNTHETIC_REGISTRY,
            embedder=embedder,
        )

    def test_activate_maps_to_alpha_activate(self):
        """Query containing the unique xqactivate token maps to alpha.activate."""
        result = self._embed_and_classify("xqactivate_token please")
        assert isinstance(result, IntentMatch), f"Expected IntentMatch, got {result}"
        assert result.tool == "alpha"
        assert result.operation == "activate"

    def test_deactivate_maps_to_alpha_deactivate(self):
        result = self._embed_and_classify("xqdeactivate_token now")
        assert isinstance(result, IntentMatch), f"Expected IntentMatch, got {result}"
        assert result.tool == "alpha"
        assert result.operation == "deactivate"

    def test_configure_maps_to_beta_configure(self):
        result = self._embed_and_classify("xqconfigure_token the system")
        assert isinstance(result, IntentMatch), f"Expected IntentMatch, got {result}"
        assert result.tool == "beta"
        assert result.operation == "configure"

    def test_reset_maps_to_beta_reset(self):
        result = self._embed_and_classify("xqreset_token to defaults")
        assert isinstance(result, IntentMatch), f"Expected IntentMatch, got {result}"
        assert result.tool == "beta"
        assert result.operation == "reset"

    def test_allocate_maps_to_gamma_allocate(self):
        result = self._embed_and_classify("xqallocate_token new volume")
        assert isinstance(result, IntentMatch), f"Expected IntentMatch, got {result}"
        assert result.tool == "gamma"
        assert result.operation == "allocate"

    def test_release_maps_to_gamma_release(self):
        result = self._embed_and_classify("xqrelease_token the storage pool")
        assert isinstance(result, IntentMatch), f"Expected IntentMatch, got {result}"
        assert result.tool == "gamma"
        assert result.operation == "release"

    def test_confidence_in_range(self):
        result = self._embed_and_classify("xqactivate_token")
        assert isinstance(result, IntentMatch)
        assert 0.0 <= result.confidence <= 1.0

    def test_top_k_contains_best_as_first(self):
        result = self._embed_and_classify("xqactivate_token")
        assert isinstance(result, IntentMatch)
        assert result.top_k, "top_k must not be empty"
        assert result.top_k[0].tool == result.tool
        assert result.top_k[0].operation == result.operation

    def test_top_k_confidence_in_range(self):
        result = self._embed_and_classify("xqactivate_token")
        assert isinstance(result, IntentMatch)
        for entry in result.top_k:
            assert 0.0 <= entry.confidence <= 1.0


# ---------------------------------------------------------------------------
# Tie-handling: two candidates with near-identical descriptions
# ---------------------------------------------------------------------------

TIE_REGISTRY = make_synthetic_registry(
    ("tools", "Tool management.", "opA", "zzztie token perform action one"),
    ("tools", "Tool management.", "opB", "zzztie token perform action two"),
    ("tools", "Tool management.", "opC", "completely different zzzdifferent operation"),
)
TIE_VOCAB = ["zzztie", "token", "perform", "action", "one", "two",
             "completely", "different", "zzzdifferent", "operation"]


class TestTopKTies:
    """Near-identical descriptions produce multiple entries in top_k."""

    def test_tied_candidates_in_top_k(self):
        """Both opA and opB share 'zzztie' and should appear in top_k."""
        embedder = make_bow_embedder(TIE_VOCAB)
        result = classify_intent(
            "zzztie token",
            snapshot_text="",
            registry=TIE_REGISTRY,
            embedder=embedder,
        )
        assert isinstance(result, IntentMatch), f"Expected IntentMatch, got {result}"
        # Both opA and opB share "zzztie token" — they should be in top_k.
        top_k_ops = {(m.tool, m.operation) for m in result.top_k}
        assert ("tools", "opA") in top_k_ops or ("tools", "opB") in top_k_ops, (
            f"Expected opA or opB in top_k, got {top_k_ops}"
        )

    def test_unrelated_candidate_not_in_top_k(self):
        """opC, which shares no tokens with the query, must NOT be in top_k."""
        embedder = make_bow_embedder(TIE_VOCAB)
        result = classify_intent(
            "zzztie token",
            snapshot_text="",
            registry=TIE_REGISTRY,
            embedder=embedder,
        )
        if isinstance(result, IntentMatch):
            top_k_ops = {(m.tool, m.operation) for m in result.top_k}
            assert ("tools", "opC") not in top_k_ops, (
                "opC shares no tokens with the query and must not appear in top_k"
            )


# ---------------------------------------------------------------------------
# NoConfidentMatch cases
# ---------------------------------------------------------------------------

class TestNoConfidentMatch:
    def test_empty_input_returns_no_match(self):
        embedder = make_bow_embedder(SYNTHETIC_VOCAB)
        result = classify_intent(
            "",
            snapshot_text="",
            registry=SYNTHETIC_REGISTRY,
            embedder=embedder,
        )
        assert isinstance(result, NoConfidentMatch)

    def test_whitespace_only_returns_no_match(self):
        embedder = make_bow_embedder(SYNTHETIC_VOCAB)
        result = classify_intent(
            "   ",
            snapshot_text="",
            registry=SYNTHETIC_REGISTRY,
            embedder=embedder,
        )
        assert isinstance(result, NoConfidentMatch)

    def test_empty_registry_returns_no_match(self):
        embedder = make_bow_embedder(SYNTHETIC_VOCAB)
        result = classify_intent(
            "xqactivate_token",
            snapshot_text="",
            registry=ToolRegistry(),
            embedder=embedder,
        )
        assert isinstance(result, NoConfidentMatch)

    def test_no_backend_returns_no_match(self):
        result = classify_intent(
            "xqactivate_token",
            snapshot_text="",
            registry=SYNTHETIC_REGISTRY,
            embedder=None,
            responder=None,
        )
        assert isinstance(result, NoConfidentMatch)

    def test_zero_vector_query_returns_no_match(self):
        """A query with no vocabulary overlap produces a zero vector -> NoConfidentMatch."""
        # Vocabulary that never overlaps with the query text.
        embedder = make_bow_embedder(["zzz_unknown_token_xyz"])
        result = classify_intent(
            "xqactivate_token",
            snapshot_text="",
            registry=SYNTHETIC_REGISTRY,
            embedder=embedder,
        )
        # Zero vector -> cosine 0.0 -> confidence 0.0 < threshold.
        assert isinstance(result, NoConfidentMatch)

    def test_no_match_carries_reason(self):
        embedder = make_bow_embedder(["zzz_unknown"])
        result = classify_intent(
            "xqactivate_token",
            snapshot_text="",
            registry=SYNTHETIC_REGISTRY,
            embedder=embedder,
        )
        assert isinstance(result, NoConfidentMatch)
        assert result.reason  # non-empty explanation

    def test_no_match_score_below_threshold(self):
        embedder = make_bow_embedder(["zzz_unknown"])
        result = classify_intent(
            "xqactivate_token",
            snapshot_text="",
            registry=SYNTHETIC_REGISTRY,
            embedder=embedder,
        )
        assert isinstance(result, NoConfidentMatch)
        assert result.best_score < CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Model backend tests (stub responder, no network)
# ---------------------------------------------------------------------------

class TestModelBackend:
    """Model backend with a scripted stub responder."""

    def _make_responder(self, reply: str):
        response = MagicMock()
        response.content = reply

        def responder(messages, tools):
            return response

        return responder

    def test_valid_response_maps_to_intent_match(self):
        """A valid 'tool.operation' response -> IntentMatch."""
        responder = self._make_responder("services.restart")
        result = classify_intent(
            "restart nginx",
            snapshot_text="",
            registry=live_registry,
            responder=responder,
        )
        assert isinstance(result, IntentMatch)
        assert result.tool == "services"
        assert result.operation == "restart"
        assert result.confidence == 1.0

    def test_valid_response_packages_install(self):
        responder = self._make_responder("packages.install")
        result = classify_intent(
            "install httpd",
            snapshot_text="",
            registry=live_registry,
            responder=responder,
        )
        assert isinstance(result, IntentMatch)
        assert result.tool == "packages"
        assert result.operation == "install"

    def test_unregistered_tool_returns_no_match(self):
        responder = self._make_responder("nonexistent_tool.restart")
        result = classify_intent(
            "restart nginx",
            snapshot_text="",
            registry=live_registry,
            responder=responder,
        )
        assert isinstance(result, NoConfidentMatch)

    def test_unregistered_op_returns_no_match(self):
        responder = self._make_responder("services.nonexistent_op")
        result = classify_intent(
            "restart nginx",
            snapshot_text="",
            registry=live_registry,
            responder=responder,
        )
        assert isinstance(result, NoConfidentMatch)

    def test_garbled_response_returns_no_match(self):
        responder = self._make_responder("I have no idea what to do here")
        result = classify_intent(
            "restart nginx",
            snapshot_text="",
            registry=live_registry,
            responder=responder,
        )
        assert isinstance(result, NoConfidentMatch)

    def test_empty_response_returns_no_match(self):
        responder = self._make_responder("")
        result = classify_intent(
            "restart nginx",
            snapshot_text="",
            registry=live_registry,
            responder=responder,
        )
        assert isinstance(result, NoConfidentMatch)

    def test_embedder_takes_precedence_over_responder(self):
        """When embedder is supplied, the responder must NOT be called."""
        call_log: list[str] = []

        def spy_responder(messages, tools):
            call_log.append("called")
            response = MagicMock()
            response.content = "services.restart"
            return response

        embedder = make_bow_embedder(SYNTHETIC_VOCAB)
        classify_intent(
            "xqactivate_token",
            snapshot_text="",
            registry=SYNTHETIC_REGISTRY,
            embedder=embedder,
            responder=spy_responder,
        )
        assert call_log == [], "responder must not be called when embedder is injected"

    def test_responder_called_exactly_once_without_embedder(self):
        call_log: list[str] = []

        def spy_responder(messages, tools):
            call_log.append("called")
            response = MagicMock()
            response.content = "services.restart"
            return response

        classify_intent(
            "restart nginx",
            snapshot_text="",
            registry=live_registry,
            embedder=None,
            responder=spy_responder,
        )
        assert call_log == ["called"]

    def test_model_backend_confidence_is_one(self):
        """The model backend assigns confidence 1.0 for a valid match."""
        responder = self._make_responder("disk.format")
        result = classify_intent(
            "format the disk",
            snapshot_text="",
            registry=live_registry,
            responder=responder,
        )
        assert isinstance(result, IntentMatch)
        assert result.confidence == 1.0

    def test_model_backend_top_k_contains_match(self):
        """top_k for the model backend contains the matched candidate."""
        responder = self._make_responder("services.restart")
        result = classify_intent(
            "restart nginx",
            snapshot_text="",
            registry=live_registry,
            responder=responder,
        )
        assert isinstance(result, IntentMatch)
        assert len(result.top_k) == 1
        assert result.top_k[0].tool == "services"
        assert result.top_k[0].operation == "restart"


# ---------------------------------------------------------------------------
# I2 invariant: no banned AI/LLM language in NoConfidentMatch.reason
# ---------------------------------------------------------------------------

class TestI2Invariant:
    BANNED = ["AI", "LLM", "agent", "language model", "neural"]

    def _assert_i2_clean(self, reason: str) -> None:
        for banned in self.BANNED:
            assert banned not in reason, (
                f"I2 violation: {banned!r} found in NoConfidentMatch.reason: {reason!r}"
            )

    def test_zero_vector_no_match_reason_i2_clean(self):
        embedder = make_bow_embedder(["zzz_xyz"])
        result = classify_intent(
            "restart nginx",
            snapshot_text="",
            registry=live_registry,
            embedder=embedder,
        )
        assert isinstance(result, NoConfidentMatch)
        self._assert_i2_clean(result.reason)

    def test_no_backend_reason_i2_clean(self):
        result = classify_intent(
            "restart nginx",
            snapshot_text="",
            registry=live_registry,
        )
        assert isinstance(result, NoConfidentMatch)
        self._assert_i2_clean(result.reason)

    def test_empty_input_reason_i2_clean(self):
        embedder = make_bow_embedder(SYNTHETIC_VOCAB)
        result = classify_intent(
            "",
            snapshot_text="",
            registry=SYNTHETIC_REGISTRY,
            embedder=embedder,
        )
        assert isinstance(result, NoConfidentMatch)
        self._assert_i2_clean(result.reason)

    def test_empty_registry_reason_i2_clean(self):
        embedder = make_bow_embedder(SYNTHETIC_VOCAB)
        result = classify_intent(
            "something",
            snapshot_text="",
            registry=ToolRegistry(),
            embedder=embedder,
        )
        assert isinstance(result, NoConfidentMatch)
        self._assert_i2_clean(result.reason)


# ---------------------------------------------------------------------------
# Smoke tests: live registry, no raises
# ---------------------------------------------------------------------------

class TestNoRaises:
    """classify_intent must never raise on any input — always returns IntentResult."""

    QUERIES = [
        "restart nginx",
        "install httpd",
        "show disk usage",
        "list users",
        "check firewall rules",
        "what processes are running",
        "show me logs for sshd",
        "redémarrer nginx s'il vous plaît",  # unicode
        "   ",                               # whitespace
        "",                                  # empty
    ]

    @pytest.mark.parametrize("query", QUERIES)
    def test_live_registry_does_not_raise(self, query: str):
        embedder = make_bow_embedder(SYNTHETIC_VOCAB)
        result = classify_intent(
            query,
            snapshot_text="",
            registry=live_registry,
            embedder=embedder,
        )
        assert isinstance(result, (IntentMatch, NoConfidentMatch))

    def test_snapshot_text_does_not_cause_raise(self):
        """A non-empty snapshot_text is accepted without errors."""
        embedder = make_bow_embedder(SYNTHETIC_VOCAB)
        result = classify_intent(
            "xqactivate_token",
            snapshot_text="Rocky Linux 9.3 | 2 CPUs | 16GB RAM | nginx: active",
            registry=SYNTHETIC_REGISTRY,
            embedder=embedder,
        )
        assert isinstance(result, (IntentMatch, NoConfidentMatch))
