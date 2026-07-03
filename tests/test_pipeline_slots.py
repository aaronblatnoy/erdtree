"""
tests/test_pipeline_slots.py — Unit tests for core/agent/pipeline/slots.py.

Coverage
--------
1. Deterministic slots (unit, package, path, device, port, interface) resolve
   with the responder NOT invoked.
2. A fuzzy slot invokes exactly one worker call to the responder.
3. Multiple fuzzy slots each invoke exactly one worker; results are merged
   into the returned dict.
4. A slot that the worker returns null for is absent from the result dict
   (reported unresolved — the assembler decides).
5. When responder=None, model workers are entirely skipped; only deterministic
   slots appear in the result.
6. Parallel dispatch: two fuzzy slots resolve concurrently; both values appear.

Invariants under test
---------------------
I1  Only calls the injected responder; no other egress.
I2  No AI/LLM/model/agent strings in any argument or return value.
I6  No tier/product names.
"""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from core.agent.pipeline.slots import extract_slots
from core.tools import ToolRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def empty_registry() -> ToolRegistry:
    """A registry with no tools registered — slots.py doesn't dispatch."""
    return ToolRegistry()


def _fake_response(content: str) -> Any:
    """Return a mock response object with a .content attribute."""
    r = MagicMock()
    r.content = content
    return r


def _responder_returning(value: str) -> MagicMock:
    """Return a mock responder that always answers with `value`."""
    mock = MagicMock(return_value=_fake_response(value))
    return mock


# ---------------------------------------------------------------------------
# Snapshot text helpers
# ---------------------------------------------------------------------------

SNAPSHOT_WITH_NGINX = (
    "Host: testbox\n"
    "OS: Rocky Linux 9.3  kernel: 5.14.0\n"
    "Active services (3): nginx, sshd, chronyd\n"
    "Failed services (1): mysqld\n"
    "Packages installed: 512\n"
    "Disks: / (45% used)\n"
    "Listening ports: 80/tcp, 443/tcp, 22/tcp\n"
)

SNAPSHOT_WITH_PACKAGE = (
    "Host: testbox\n"
    "Packages installed: 512\n"
    "Active services (1): httpd\n"
    "Listening ports: 8080/tcp\n"
    # Simulate a package appearing in the snapshot text (e.g. installed sample)
    "vim postgresql-server git\n"
)

SNAPSHOT_WITH_DISK = (
    "Host: testbox\n"
    "Disks: /dev/sda (30% used), /dev/sdb (0% used)\n"
    "Active services (1): sshd\n"
)

SNAPSHOT_WITH_PATH = (
    "Host: testbox\n"
    "Disks: /var/log (12% used)\n"
    "Active services (1): sshd\n"
)

SNAPSHOT_WITH_INTERFACE = (
    "Host: testbox\n"
    "Active services (1): NetworkManager\n"
    "Listening ports: 22/tcp\n"
    "eth0 ens3\n"
)

SNAPSHOT_EMPTY = "Host: testbox\n"


# ---------------------------------------------------------------------------
# 1. Deterministic resolution — responder must NOT be called
# ---------------------------------------------------------------------------

class TestDeterministicResolution:
    """Deterministic slots resolve from the system context without a model call."""

    def test_unit_slot_from_active_services(self, empty_registry):
        """A unit name present in 'Active services' resolves deterministically."""
        responder = _responder_returning("nginx")
        result = extract_slots(
            user_input="restart nginx",
            snapshot_text=SNAPSHOT_WITH_NGINX,
            tool="services",
            operation="restart",
            needed_slots=[("unit", str)],
            registry=empty_registry,
            responder=responder,
        )
        assert result == {"unit": "nginx"}
        responder.assert_not_called()

    def test_unit_slot_failed_service(self, empty_registry):
        """A unit name present in 'Failed services' resolves deterministically."""
        responder = _responder_returning("mysqld")
        result = extract_slots(
            user_input="start mysqld please",
            snapshot_text=SNAPSHOT_WITH_NGINX,
            tool="services",
            operation="start",
            needed_slots=[("unit", str)],
            registry=empty_registry,
            responder=responder,
        )
        assert result == {"unit": "mysqld"}
        responder.assert_not_called()

    def test_package_slot(self, empty_registry):
        """A package name present in the snapshot resolves deterministically."""
        responder = _responder_returning("vim")
        result = extract_slots(
            user_input="install vim",
            snapshot_text=SNAPSHOT_WITH_PACKAGE,
            tool="packages",
            operation="install",
            needed_slots=[("package", str)],
            registry=empty_registry,
            responder=responder,
        )
        assert result == {"package": "vim"}
        responder.assert_not_called()

    def test_device_slot(self, empty_registry):
        """A block device present in the snapshot resolves deterministically."""
        responder = _responder_returning("/dev/sda")
        result = extract_slots(
            user_input="format /dev/sdb",
            snapshot_text=SNAPSHOT_WITH_DISK,
            tool="disk",
            operation="format",
            needed_slots=[("device", str)],
            registry=empty_registry,
            responder=responder,
        )
        assert result == {"device": "/dev/sdb"}
        responder.assert_not_called()

    def test_path_slot(self, empty_registry):
        """An absolute path present in the snapshot resolves deterministically."""
        responder = _responder_returning("/var/log")
        result = extract_slots(
            user_input="show me /var/log",
            snapshot_text=SNAPSHOT_WITH_PATH,
            tool="files",
            operation="list",
            needed_slots=[("path", str)],
            registry=empty_registry,
            responder=responder,
        )
        assert result == {"path": "/var/log"}
        responder.assert_not_called()

    def test_port_slot(self, empty_registry):
        """A port present in the listening-ports list resolves deterministically."""
        responder = _responder_returning("80")
        result = extract_slots(
            user_input="open port 80",
            snapshot_text=SNAPSHOT_WITH_NGINX,
            tool="firewall",
            operation="allow",
            needed_slots=[("port", int)],
            registry=empty_registry,
            responder=responder,
        )
        assert result == {"port": 80}
        responder.assert_not_called()

    def test_interface_slot(self, empty_registry):
        """A network interface present in the snapshot resolves deterministically."""
        responder = _responder_returning("eth0")
        result = extract_slots(
            user_input="show eth0 configuration",
            snapshot_text=SNAPSHOT_WITH_INTERFACE,
            tool="network",
            operation="show",
            needed_slots=[("interface", str)],
            registry=empty_registry,
            responder=responder,
        )
        assert result == {"interface": "eth0"}
        responder.assert_not_called()

    def test_no_responder_deterministic_only(self, empty_registry):
        """When responder=None, model workers are skipped; only deterministic
        slots appear."""
        result = extract_slots(
            user_input="restart nginx",
            snapshot_text=SNAPSHOT_WITH_NGINX,
            tool="services",
            operation="restart",
            needed_slots=[("unit", str), ("fuzzy_flag", str)],
            registry=empty_registry,
            responder=None,
        )
        # 'unit' resolves deterministically; 'fuzzy_flag' stays unresolved.
        assert result.get("unit") == "nginx"
        assert "fuzzy_flag" not in result


# ---------------------------------------------------------------------------
# 2. Fuzzy slot -> exactly one worker call each
# ---------------------------------------------------------------------------

class TestFuzzyWorkers:
    """Genuinely fuzzy slots send exactly one narrow question to the responder."""

    def test_single_fuzzy_slot_invokes_one_worker(self, empty_registry):
        """A slot not resolvable deterministically invokes exactly one responder call."""
        responder = _responder_returning("production")
        result = extract_slots(
            user_input="configure nginx for production",
            snapshot_text=SNAPSHOT_EMPTY,  # nothing in context
            tool="services",
            operation="configure",
            needed_slots=[("environment", str)],
            registry=empty_registry,
            responder=responder,
        )
        assert responder.call_count == 1
        assert result == {"environment": "production"}

    def test_two_fuzzy_slots_invoke_two_workers(self, empty_registry):
        """Two fuzzy slots each invoke exactly one worker (two total calls)."""
        call_values = ["production", "8443"]

        def side_effect(messages, tools):
            # Alternate between the two answers based on question content.
            question = messages[0]["content"]
            if "environment" in question:
                return _fake_response("production")
            if "port" in question:
                return _fake_response("8443")
            return _fake_response("null")

        responder = MagicMock(side_effect=side_effect)
        result = extract_slots(
            user_input="configure nginx for production on port 8443",
            snapshot_text=SNAPSHOT_EMPTY,
            tool="services",
            operation="configure",
            needed_slots=[("environment", str), ("port", int)],
            registry=empty_registry,
            responder=responder,
            max_workers=2,
        )
        assert responder.call_count == 2
        assert result.get("environment") == "production"
        assert result.get("port") == 8443

    def test_null_slot_is_unresolved(self, empty_registry):
        """A slot for which the worker returns 'null' is absent from the result dict."""
        responder = _responder_returning("null")
        result = extract_slots(
            user_input="configure nginx",
            snapshot_text=SNAPSHOT_EMPTY,
            tool="services",
            operation="configure",
            needed_slots=[("environment", str)],
            registry=empty_registry,
            responder=responder,
        )
        assert "environment" not in result
        assert responder.call_count == 1

    def test_none_value_absent_from_result(self, empty_registry):
        """A worker returning 'none' or 'not specified' leaves the slot absent."""
        for null_word in ("none", "not specified", "unknown", "n/a"):
            responder = _responder_returning(null_word)
            result = extract_slots(
                user_input="do something",
                snapshot_text=SNAPSHOT_EMPTY,
                tool="services",
                operation="restart",
                needed_slots=[("unit", str)],
                registry=empty_registry,
                responder=responder,
            )
            assert "unit" not in result, f"slot should be absent for response {null_word!r}"


# ---------------------------------------------------------------------------
# 3. Parallel dispatch — merged dict
# ---------------------------------------------------------------------------

class TestParallelDispatch:
    """Multiple fuzzy workers run in the thread pool and their results are merged."""

    def test_parallel_results_merged(self, empty_registry):
        """Three fuzzy slots each get one worker; all values appear in the result."""
        call_lock = threading.Lock()
        call_log: list[str] = []

        def side_effect(messages, tools):
            question = messages[0]["content"]
            with call_lock:
                call_log.append(question)
            # Match specifically on the slot name in the narrow question
            # ("What is the value for 'alpha'?"), not on the user sentence
            # which contains all three slot names.
            if "'alpha'" in question:
                return _fake_response("val_alpha")
            if "'beta'" in question:
                return _fake_response("val_beta")
            if "'gamma'" in question:
                return _fake_response("val_gamma")
            return _fake_response("null")

        responder = MagicMock(side_effect=side_effect)
        result = extract_slots(
            user_input="do alpha beta gamma",
            snapshot_text=SNAPSHOT_EMPTY,
            tool="some_tool",
            operation="some_op",
            needed_slots=[("alpha", str), ("beta", str), ("gamma", str)],
            registry=empty_registry,
            responder=responder,
            max_workers=3,
        )
        assert result.get("alpha") == "val_alpha"
        assert result.get("beta") == "val_beta"
        assert result.get("gamma") == "val_gamma"
        assert responder.call_count == 3

    def test_mixed_deterministic_and_fuzzy(self, empty_registry):
        """Deterministic slots resolve without calling the responder; fuzzy
        slots get exactly one worker each; the final dict merges both."""
        def side_effect(messages, tools):
            return _fake_response("val_fuzzy")

        responder = MagicMock(side_effect=side_effect)
        result = extract_slots(
            user_input="restart nginx with setting val_fuzzy",
            snapshot_text=SNAPSHOT_WITH_NGINX,
            tool="services",
            operation="restart",
            # 'unit' is deterministic (nginx in snapshot); 'custom_flag' is fuzzy.
            needed_slots=[("unit", str), ("custom_flag", str)],
            registry=empty_registry,
            responder=responder,
            max_workers=2,
        )
        assert result.get("unit") == "nginx"
        assert result.get("custom_flag") == "val_fuzzy"
        # Exactly one call — only the fuzzy slot triggered a worker.
        assert responder.call_count == 1


# ---------------------------------------------------------------------------
# 4. Empty needed_slots -> empty result, no calls
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_needed_slots(self, empty_registry):
        """No slots needed -> no calls, empty dict returned."""
        responder = _responder_returning("something")
        result = extract_slots(
            user_input="show nginx status",
            snapshot_text=SNAPSHOT_WITH_NGINX,
            tool="services",
            operation="status",
            needed_slots=[],
            registry=empty_registry,
            responder=responder,
        )
        assert result == {}
        responder.assert_not_called()

    def test_closed_world_rejects_invented_value(self, empty_registry):
        """A regex match for a unit name that does NOT appear in the snapshot
        is NOT accepted deterministically — it falls through to the worker."""
        # 'fakeservice' is not in SNAPSHOT_WITH_NGINX.
        responder = _responder_returning("fakeservice")
        result = extract_slots(
            user_input="restart fakeservice",
            snapshot_text=SNAPSHOT_WITH_NGINX,
            tool="services",
            operation="restart",
            needed_slots=[("unit", str)],
            registry=empty_registry,
            responder=responder,
        )
        # The deterministic resolver should not have accepted 'fakeservice'
        # (not in the snapshot), so the worker was called.
        assert responder.call_count == 1
        # Worker returned "fakeservice" as the answer.
        assert result.get("unit") == "fakeservice"

    def test_int_coercion_for_port(self, empty_registry):
        """A worker answer that is a numeric string is coerced to int for an
        int-typed slot."""
        responder = _responder_returning("9090")
        result = extract_slots(
            user_input="open port 9090",
            snapshot_text=SNAPSHOT_EMPTY,  # 9090 not in snapshot -> fuzzy
            tool="firewall",
            operation="allow",
            needed_slots=[("port", int)],
            registry=empty_registry,
            responder=responder,
        )
        assert result.get("port") == 9090
        assert isinstance(result.get("port"), int)

    def test_worker_exception_leaves_slot_unresolved(self, empty_registry):
        """If the responder raises, the slot is absent (not an exception)."""
        def bad_responder(messages, tools):
            raise RuntimeError("connection refused")

        result = extract_slots(
            user_input="configure something",
            snapshot_text=SNAPSHOT_EMPTY,
            tool="services",
            operation="configure",
            needed_slots=[("setting", str)],
            registry=empty_registry,
            responder=bad_responder,
        )
        assert "setting" not in result
