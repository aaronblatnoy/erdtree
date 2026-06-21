"""Tests for core/tools/packages.py — dnf package-management tool.

All subprocess calls are mocked (no dnf, no root, no Linux required).
Fully green on the macOS dev host.

Coverage:
  * ToolSpec registration: "packages" in registry, correct ops declared.
  * Permission class declarations: search/info=READ, install/update=WRITE,
    remove=DESTRUCTIVE.
  * execute() dispatch: unknown op -> ValueError.
  * search: success and no-match paths.
  * info: success and not-found paths.
  * install: success, failure, empty-package-list guard.
  * update: full-system (empty packages), named packages, failure.
  * remove (dry-run preview): gate_cleared absent/False returns preview.
  * remove (gate cleared): real remove runs, success/failure.
  * remove destructive escalation: critical pkg in plan -> WARNING in summary.
  * remove non-critical plan: no WARNING.
  * SELinux hint injection: AVC pattern in stderr -> hint in summary.
  * _is_critical_package: positive and negative cases.
  * _parse_transaction_plan: correct extraction from realistic dnf output.
  * _selinux_hint: AVC hit and miss.
  * Registry round-trip: dispatch search/info through registry (read, no gate).
  * Invariant I2: no AI/LLM/model/agent strings in any summary.

DEFERRED-TO-MOSSAD: live dnf execution, SELinux AVC triggers, real package
  transactions on a Rocky Linux 9 host.
"""

from __future__ import annotations

import re
import subprocess as sp
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.packages import (
    PACKAGES_SPEC,
    _dnf_dry_run,
    _is_critical_package,
    _parse_transaction_plan,
    _selinux_hint,
    _exec_install,
    _exec_remove,
    _exec_search,
    _exec_info,
    _exec_update,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> sp.CompletedProcess:
    return sp.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _mock_run(returncode: int = 0, stdout: str = "", stderr: str = ""):
    """Return a context-manager patch that makes subprocess.run return a fixed result."""
    return patch(
        "subprocess.run",
        return_value=_completed(returncode=returncode, stdout=stdout, stderr=stderr),
    )


# ---------------------------------------------------------------------------
# Realistic dnf --assumeno output fixture
# ---------------------------------------------------------------------------

_DNF_REMOVE_PLAN_BASIC = """\
Dependencies resolved.
===========================================================================
 Package            Arch      Version               Repository         Size
===========================================================================
Removing:
 htop               x86_64    3.2.2-1.el9           @baseos           318 k

Transaction Summary
===========================================================================
Remove  1 Package

Would remove 1 Package(s). Operation aborted.
"""

_DNF_REMOVE_PLAN_KERNEL = """\
Dependencies resolved.
===========================================================================
Removing:
 kernel-core        x86_64    5.14.0-427.el9        @baseos           82 M
 kernel             x86_64    5.14.0-427.el9        @baseos           0 B

Transaction Summary
===========================================================================
Remove  2 Packages

Operation aborted.
"""

_DNF_REMOVE_PLAN_SSH = """\
Dependencies resolved.
===========================================================================
Removing:
 openssh-server     x86_64    8.7p1-34.el9_4        @baseos          925 k

Transaction Summary
===========================================================================
Remove  1 Package

Operation aborted.
"""

_DNF_REMOVE_PLAN_MULTI = """\
Dependencies resolved.
===========================================================================
Removing:
 sudo               x86_64    1.9.5p2-10.el9        @baseos          2.4 M
 htop               x86_64    3.2.2-1.el9           @baseos          318 k

Transaction Summary
===========================================================================
Remove  2 Packages

Operation aborted.
"""


# ---------------------------------------------------------------------------
# _selinux_hint
# ---------------------------------------------------------------------------

class TestSelinuxHint:
    def test_no_avc_returns_empty(self) -> None:
        assert _selinux_hint("normal dnf output") == ""

    def test_avc_denied_returns_hint(self) -> None:
        hint = _selinux_hint("avc:  denied  { read } for pid=1234")
        assert "SELinux" in hint
        assert "ausearch" in hint

    def test_type_avc_returns_hint(self) -> None:
        hint = _selinux_hint("type=AVC msg=audit(1234567890.123:456)")
        assert "SELinux" in hint

    def test_case_insensitive(self) -> None:
        hint = _selinux_hint("AVC: DENIED")
        assert hint != ""

    def test_hint_has_no_ai_language(self) -> None:
        hint = _selinux_hint("avc: denied")
        for bad in ("AI", "LLM", "model", "agent", "agentic"):
            assert bad.lower() not in hint.lower()


# ---------------------------------------------------------------------------
# _is_critical_package
# ---------------------------------------------------------------------------

class TestIsCriticalPackage:
    def test_kernel_core(self) -> None:
        assert _is_critical_package("kernel-core")

    def test_kernel_bare(self) -> None:
        assert _is_critical_package("kernel")

    def test_kernel_versioned(self) -> None:
        assert _is_critical_package("kernel-5.14.0-427.el9.x86_64")

    def test_openssh_server(self) -> None:
        assert _is_critical_package("openssh-server")

    def test_openssh_bare(self) -> None:
        assert _is_critical_package("openssh")

    def test_sudo(self) -> None:
        assert _is_critical_package("sudo")

    def test_bash(self) -> None:
        assert _is_critical_package("bash")

    def test_glibc(self) -> None:
        assert _is_critical_package("glibc")

    def test_grub2_common(self) -> None:
        assert _is_critical_package("grub2-common")

    def test_htop_not_critical(self) -> None:
        assert not _is_critical_package("htop")

    def test_vim_not_critical(self) -> None:
        assert not _is_critical_package("vim-enhanced")

    def test_nginx_not_critical(self) -> None:
        assert not _is_critical_package("nginx")

    def test_python3_not_critical(self) -> None:
        assert not _is_critical_package("python3")


# ---------------------------------------------------------------------------
# _parse_transaction_plan
# ---------------------------------------------------------------------------

class TestParseTransactionPlan:
    def test_basic_single_package(self) -> None:
        names = _parse_transaction_plan(_DNF_REMOVE_PLAN_BASIC)
        assert "htop" in names

    def test_kernel_plan(self) -> None:
        names = _parse_transaction_plan(_DNF_REMOVE_PLAN_KERNEL)
        assert "kernel-core" in names
        assert "kernel" in names

    def test_ssh_plan(self) -> None:
        names = _parse_transaction_plan(_DNF_REMOVE_PLAN_SSH)
        assert "openssh-server" in names

    def test_multi_package(self) -> None:
        names = _parse_transaction_plan(_DNF_REMOVE_PLAN_MULTI)
        assert "sudo" in names
        assert "htop" in names

    def test_no_removing_section_returns_empty(self) -> None:
        assert _parse_transaction_plan("Nothing to do.") == []

    def test_empty_output_returns_empty(self) -> None:
        assert _parse_transaction_plan("") == []


# ---------------------------------------------------------------------------
# ToolSpec registration and declaration
# ---------------------------------------------------------------------------

class TestPackagesSpec:
    def test_registered_in_global_registry(self) -> None:
        spec = registry.get("packages")
        assert spec is not None
        assert spec.name == "packages"

    def test_ops_declared(self) -> None:
        spec = registry.get("packages")
        assert set(spec.ops.keys()) == {"install", "remove", "update", "search", "info"}

    def test_search_is_read(self) -> None:
        assert PACKAGES_SPEC.permission_class_for("search") is OpClass.READ

    def test_info_is_read(self) -> None:
        assert PACKAGES_SPEC.permission_class_for("info") is OpClass.READ

    def test_install_is_write(self) -> None:
        assert PACKAGES_SPEC.permission_class_for("install") is OpClass.WRITE

    def test_update_is_write(self) -> None:
        assert PACKAGES_SPEC.permission_class_for("update") is OpClass.WRITE

    def test_remove_is_destructive(self) -> None:
        assert PACKAGES_SPEC.permission_class_for("remove") is OpClass.DESTRUCTIVE

    def test_unknown_op_returns_none(self) -> None:
        assert PACKAGES_SPEC.permission_class_for("__bogus__") is None

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError, match="no operation"):
            PACKAGES_SPEC.execute("__bogus__", {})


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_success(self) -> None:
        stdout = "htop.x86_64 : An interactive process viewer"
        with _mock_run(returncode=0, stdout=stdout):
            result = _exec_search({"keyword": "htop"})
        assert result.exit_code == 0
        assert result.ok is True
        assert "htop" in result.summary
        assert result.stdout == stdout

    def test_no_matches(self) -> None:
        with _mock_run(returncode=1, stdout="No matches found."):
            result = _exec_search({"keyword": "xyzzy_nonexistent"})
        assert result.exit_code == 1
        assert "no matches" in result.summary.lower()

    def test_other_error(self) -> None:
        with _mock_run(returncode=2, stderr="repo error"):
            result = _exec_search({"keyword": "foo"})
        assert result.exit_code == 2
        assert "2" in result.summary

    def test_no_ai_language_in_summary(self) -> None:
        with _mock_run(returncode=0, stdout="result"):
            result = _exec_search({"keyword": "vim"})
        for bad in ("AI", "LLM", "model", "agent", "agentic"):
            assert bad.lower() not in result.summary.lower()


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------

class TestInfo:
    def test_success(self) -> None:
        stdout = "Name         : htop\nVersion      : 3.2.2\n"
        with _mock_run(returncode=0, stdout=stdout):
            result = _exec_info({"package": "htop"})
        assert result.exit_code == 0
        assert result.ok is True
        assert "htop" in result.summary

    def test_not_found(self) -> None:
        with _mock_run(returncode=1, stdout="No matching packages to list"):
            result = _exec_info({"package": "xyzzy_nonexistent"})
        assert result.exit_code == 1
        assert "not found" in result.summary.lower()

    def test_other_error(self) -> None:
        with _mock_run(returncode=3, stderr="network error"):
            result = _exec_info({"package": "foo"})
        assert result.exit_code == 3

    def test_no_ai_language_in_summary(self) -> None:
        with _mock_run(returncode=0, stdout="info"):
            result = _exec_info({"package": "vim"})
        for bad in ("AI", "LLM", "model", "agent", "agentic"):
            assert bad.lower() not in result.summary.lower()


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

class TestInstall:
    def test_success(self) -> None:
        with _mock_run(returncode=0, stdout="Installed: htop-3.2.2"):
            result = _exec_install({"packages": ["htop"]})
        assert result.ok is True
        assert "htop" in result.summary
        assert "successfully" in result.summary

    def test_failure(self) -> None:
        with _mock_run(returncode=1, stderr="No package htop available."):
            result = _exec_install({"packages": ["htop"]})
        assert result.exit_code == 1
        assert not result.ok

    def test_empty_package_list(self) -> None:
        result = _exec_install({"packages": []})
        assert result.exit_code == 1
        assert "no package" in result.summary.lower()

    def test_multiple_packages(self) -> None:
        with _mock_run(returncode=0, stdout="Installed: vim-enhanced, git"):
            result = _exec_install({"packages": ["vim-enhanced", "git"]})
        assert result.ok is True
        assert "vim-enhanced" in result.summary

    def test_selinux_hint_in_summary(self) -> None:
        with _mock_run(returncode=0, stderr="avc: denied { read }"):
            result = _exec_install({"packages": ["foo"]})
        assert "SELinux" in result.summary

    def test_no_ai_language_in_summary(self) -> None:
        with _mock_run(returncode=0):
            result = _exec_install({"packages": ["htop"]})
        for bad in ("AI", "LLM", "model", "agent", "agentic"):
            assert bad.lower() not in result.summary.lower()


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_full_system_update(self) -> None:
        with _mock_run(returncode=0, stdout="Updated: 42 packages"):
            result = _exec_update({"packages": []})
        assert result.ok is True
        assert "all packages" in result.summary

    def test_named_package_update(self) -> None:
        with _mock_run(returncode=0, stdout="Updated: vim-enhanced"):
            result = _exec_update({"packages": ["vim-enhanced"]})
        assert result.ok is True
        assert "vim-enhanced" in result.summary

    def test_update_failure(self) -> None:
        with _mock_run(returncode=1, stderr="Errors during downloading"):
            result = _exec_update({"packages": []})
        assert not result.ok
        assert result.exit_code == 1

    def test_packages_none_treated_as_full_system(self) -> None:
        with _mock_run(returncode=0):
            result = _exec_update({"packages": None})
        assert "all packages" in result.summary

    def test_no_ai_language_in_summary(self) -> None:
        with _mock_run(returncode=0):
            result = _exec_update({})
        for bad in ("AI", "LLM", "model", "agent", "agentic"):
            assert bad.lower() not in result.summary.lower()


# ---------------------------------------------------------------------------
# remove — dry-run preview path (gate not cleared)
# ---------------------------------------------------------------------------

class TestRemoveDryRun:
    def test_no_gate_cleared_returns_preview(self) -> None:
        with _mock_run(returncode=1, stdout=_DNF_REMOVE_PLAN_BASIC):
            result = _exec_remove({"packages": ["htop"]})
        assert result.exit_code is None
        assert "dry-run" in result.summary.lower() or "preview" in result.summary.lower()
        assert "confirm" in result.summary.lower()

    def test_gate_false_returns_preview(self) -> None:
        with _mock_run(returncode=1, stdout=_DNF_REMOVE_PLAN_BASIC):
            result = _exec_remove({"packages": ["htop"], "gate_cleared": False})
        assert result.exit_code is None

    def test_preview_surfaces_package_names(self) -> None:
        with _mock_run(returncode=1, stdout=_DNF_REMOVE_PLAN_BASIC):
            result = _exec_remove({"packages": ["htop"]})
        # transaction summary embeds "htop" from the parsed plan
        assert "htop" in result.summary

    def test_preview_no_critical_has_no_warning(self) -> None:
        with _mock_run(returncode=1, stdout=_DNF_REMOVE_PLAN_BASIC):
            result = _exec_remove({"packages": ["htop"]})
        assert "WARNING" not in result.summary

    def test_preview_critical_pkg_has_warning(self) -> None:
        with _mock_run(returncode=1, stdout=_DNF_REMOVE_PLAN_KERNEL):
            result = _exec_remove({"packages": ["kernel-core"]})
        assert "WARNING" in result.summary

    def test_preview_ssh_critical_has_warning(self) -> None:
        with _mock_run(returncode=1, stdout=_DNF_REMOVE_PLAN_SSH):
            result = _exec_remove({"packages": ["openssh-server"]})
        assert "WARNING" in result.summary

    def test_empty_package_list(self) -> None:
        result = _exec_remove({"packages": []})
        assert result.exit_code == 1
        assert "no package" in result.summary.lower()


# ---------------------------------------------------------------------------
# remove — gate cleared (real execute path)
# ---------------------------------------------------------------------------

class TestRemoveGateCleared:
    def test_success(self) -> None:
        dry_stdout = _DNF_REMOVE_PLAN_BASIC
        real_stdout = "Removed: htop-3.2.2-1.el9.x86_64"

        call_count = 0

        def _fake_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if "--assumeno" in cmd:
                return _completed(returncode=1, stdout=dry_stdout)
            return _completed(returncode=0, stdout=real_stdout)

        with patch("subprocess.run", side_effect=_fake_run):
            result = _exec_remove({"packages": ["htop"], "gate_cleared": True})

        assert call_count == 2  # dry-run + real
        assert result.exit_code == 0
        assert result.ok is True
        assert "htop" in result.summary
        assert "successfully" in result.summary

    def test_failure(self) -> None:
        dry_stdout = _DNF_REMOVE_PLAN_BASIC
        call_count = 0

        def _fake_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if "--assumeno" in cmd:
                return _completed(returncode=1, stdout=dry_stdout)
            return _completed(returncode=1, stderr="dependency error")

        with patch("subprocess.run", side_effect=_fake_run):
            result = _exec_remove({"packages": ["htop"], "gate_cleared": True})

        assert result.exit_code == 1
        assert not result.ok

    def test_selinux_hint_in_summary_on_success(self) -> None:
        def _fake_run(cmd, **kwargs):
            if "--assumeno" in cmd:
                return _completed(returncode=1, stdout=_DNF_REMOVE_PLAN_BASIC)
            return _completed(returncode=0, stderr="avc: denied { read }")

        with patch("subprocess.run", side_effect=_fake_run):
            result = _exec_remove({"packages": ["htop"], "gate_cleared": True})

        assert "SELinux" in result.summary

    def test_critical_pkg_warning_in_summary(self) -> None:
        def _fake_run(cmd, **kwargs):
            if "--assumeno" in cmd:
                return _completed(returncode=1, stdout=_DNF_REMOVE_PLAN_KERNEL)
            return _completed(returncode=0, stdout="Removed kernel")

        with patch("subprocess.run", side_effect=_fake_run):
            result = _exec_remove({"packages": ["kernel-core"], "gate_cleared": True})

        assert "WARNING" in result.summary

    def test_no_ai_language_in_summary(self) -> None:
        def _fake_run(cmd, **kwargs):
            if "--assumeno" in cmd:
                return _completed(returncode=1, stdout=_DNF_REMOVE_PLAN_BASIC)
            return _completed(returncode=0)

        with patch("subprocess.run", side_effect=_fake_run):
            result = _exec_remove({"packages": ["htop"], "gate_cleared": True})

        for bad in ("AI", "LLM", "model", "agent", "agentic"):
            assert bad.lower() not in result.summary.lower()


# ---------------------------------------------------------------------------
# Registry round-trip (read ops go through the global registry)
# ---------------------------------------------------------------------------

class TestRegistryRoundTrip:
    def test_search_via_registry(self) -> None:
        with _mock_run(returncode=0, stdout="htop : interactive process viewer"):
            result = registry.dispatch("packages", "search", {"keyword": "htop"})
        assert isinstance(result, ToolResult)
        assert result.ok is True

    def test_info_via_registry(self) -> None:
        with _mock_run(returncode=0, stdout="Name: vim"):
            result = registry.dispatch("packages", "info", {"package": "vim"})
        assert isinstance(result, ToolResult)
        assert result.ok is True

    def test_permission_class_search_via_registry(self) -> None:
        cls = registry.permission_class_for("packages", "search")
        assert cls is OpClass.READ

    def test_permission_class_remove_via_registry(self) -> None:
        cls = registry.permission_class_for("packages", "remove")
        assert cls is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# I2 invariant scan — all executor paths
# ---------------------------------------------------------------------------

_AI_TERMS = ("AI", "LLM", "model", "agent", "agentic", "artificial", "intelligence")
# Compile as whole-word patterns (word boundary on both sides).
_AI_PATTERNS = [re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE) for t in _AI_TERMS]


class TestI2InvariantAllPaths:
    """Ensure no AI/LLM/model/agent language leaks into any ToolResult summary.

    Uses whole-word matching so incidental substrings (e.g. 'detail**s**' or
    'st**ai**r') do not trigger false positives. The invariant forbids the
    TERMS as standalone words, not as arbitrary substrings.
    """

    def _assert_no_ai(self, result: ToolResult) -> None:
        for term, pat in zip(_AI_TERMS, _AI_PATTERNS):
            assert not pat.search(result.summary), (
                f"I2 violation: '{term}' found as a word in summary: {result.summary!r}"
            )

    def test_search_success(self) -> None:
        with _mock_run(returncode=0, stdout="result"):
            self._assert_no_ai(_exec_search({"keyword": "x"}))

    def test_search_no_match(self) -> None:
        with _mock_run(returncode=1):
            self._assert_no_ai(_exec_search({"keyword": "x"}))

    def test_info_success(self) -> None:
        with _mock_run(returncode=0, stdout="info"):
            self._assert_no_ai(_exec_info({"package": "x"}))

    def test_info_not_found(self) -> None:
        with _mock_run(returncode=1):
            self._assert_no_ai(_exec_info({"package": "x"}))

    def test_install_success(self) -> None:
        with _mock_run(returncode=0):
            self._assert_no_ai(_exec_install({"packages": ["x"]}))

    def test_install_failure(self) -> None:
        with _mock_run(returncode=1, stderr="err"):
            self._assert_no_ai(_exec_install({"packages": ["x"]}))

    def test_update_success(self) -> None:
        with _mock_run(returncode=0):
            self._assert_no_ai(_exec_update({}))

    def test_remove_preview(self) -> None:
        with _mock_run(returncode=1, stdout=_DNF_REMOVE_PLAN_BASIC):
            self._assert_no_ai(_exec_remove({"packages": ["htop"]}))

    def test_remove_gate_cleared_success(self) -> None:
        def _fake(cmd, **kw):
            if "--assumeno" in cmd:
                return _completed(returncode=1, stdout=_DNF_REMOVE_PLAN_BASIC)
            return _completed(returncode=0)

        with patch("subprocess.run", side_effect=_fake):
            self._assert_no_ai(_exec_remove({"packages": ["htop"], "gate_cleared": True}))
