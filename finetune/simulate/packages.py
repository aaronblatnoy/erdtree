"""finetune/simulate/packages.py — Rocky Linux 9 output simulator for the 'packages' tool.

Public API
----------
simulate_packages(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int | None   (None only for the remove dry-run preview path)
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 5 real operations declared in core/tools/packages.py
           (install, remove, update, search, info)
    args : dict of op arguments (may be {} for ops with all-optional args;
           required args receive a sensible default so the function never raises
           on KeyError — it returns a realistic "nothing supplied" failure case)
    ctx  : system context string produced by finetune.context.make_context(),
           OR a profile dict (same shape as finetune.context._PROFILES entries).
           Both forms are supported via isinstance checks.

Realism model
-------------
* stdout/stderr mirror real dnf output on Rocky Linux 9 / RHEL 9 (el9 RPM
  epochs, baseos/appstream repo labels, dependency resolution lines, transaction
  summaries, "Complete!" footers).
* Exit codes match dnf conventions:
    0  — success
    1  — package not found, dependency conflict, or "nothing to do"
         (dnf exits 1 for "no match" and 0 for "nothing to do"; we follow the
          dnf real behaviour: "nothing to do" exits 0, "no match" exits 1)
   None — dry-run preview for remove without gate_cleared (gate pending)
* Failure triggers are deterministic (hash-based + keyword triggers):
    - Token "notfound", "bogus", "fake", "missing", "noexist" in the package
      name -> package not found (install/info) or no results (search)
    - Token "conflict" in the package name -> dependency conflict error (install)
    - Token "conflict" in the keyword -> no matches (search)
    - Hash-based ~12% scatter: permission denied (root required) for install
    - Hash-based ~10% scatter: nothing-to-do result for update (patch level
      already current — realistic on recently-updated hosts)
* ctx is used to refine output:
    - install: if a package name appears in ctx's pkg_sample, the transaction
      shows "Already installed" and exits 0 instead of downloading.
    - remove: if a package name appears in ctx's pkg_sample, the dry-run plan
      lists it as a genuine transaction; otherwise treat as not installed.
    - info: if the package appears in ctx's pkg_sample, the repo shows
      "@System" (installed) rather than "appstream" (available).

I2 compliance
-------------
All `summary` strings are I2-clean (no forbidden terms: ai, llm, model, agent,
neural, machine learning, gpt, ollama, inference).  The assert_no_ai_language
guard is NOT called inline (to keep this module fast and dependency-light for
tests), but tests/finetune/test_i2.py asserts every returned summary.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (to avoid circular deps when
__init__.py imports simulate modules before coreimports is fully settled).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_META_EXPIRY = "0:14:07 ago on Thu 03 Jul 2026 08:30:00 AM UTC."


def _make_result(
    exit_code: int | None,
    stdout: str,
    stderr: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary": summary,
    }


def _pkg_in_ctx(pkg: str, ctx: Any) -> bool:
    """Return True if pkg appears to be installed according to ctx."""
    if isinstance(ctx, dict):
        sample: list[str] = ctx.get("pkg_sample", [])
        return any(pkg == p or pkg in p or p in pkg for p in sample)
    if isinstance(ctx, str):
        return pkg in ctx
    return False


def _hostname(ctx: Any) -> str:
    """Extract hostname short label from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _pkg_not_found_trigger(name: str) -> bool:
    """Return True if the package name should simulate a not-found failure."""
    lower = name.lower()
    for tok in ("notfound", "noexist", "bogus", "fake", "missing", "badpkg"):
        if tok in lower:
            return True
    return False


def _pkg_conflict_trigger(name: str) -> bool:
    """Return True if the package name should simulate a dependency conflict."""
    return "conflict" in name.lower()


def _perm_denied_trigger(name: str) -> bool:
    """Hash-based ~12% scatter: simulate permission denied (not running as root)."""
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return h % 9 == 0


def _update_nothing_to_do_trigger(pkg: str) -> bool:
    """Hash-based ~10% scatter: package is already at the latest version."""
    h = int(hashlib.md5((pkg + "update").encode()).hexdigest(), 16)
    return h % 10 == 0


# ---------------------------------------------------------------------------
# RPM version/release helpers (deterministic from package name)
# ---------------------------------------------------------------------------

# Small lookup of real Rocky-9 versions for common packages.
_KNOWN_VERSIONS: dict[str, tuple[str, str, str]] = {
    # (epoch_prefix, version, release)
    "nginx":        ("1:",  "1.20.1",   "20.el9_4.1"),
    "httpd":        ("",    "2.4.57",   "11.el9_4"),
    "postgresql":   ("",    "16.3",     "1.el9_4"),
    "postgresql-server": ("", "16.3",   "1.el9_4"),
    "mysql":        ("",    "8.0.36",   "1.el9"),
    "python3":      ("",    "3.9.18",   "3.el9_4.1"),
    "openssl":      ("1:",  "3.0.7",    "25.el9_4"),
    "openssl-libs": ("1:",  "3.0.7",    "25.el9_4"),
    "curl":         ("",    "7.76.1",   "29.el9_4"),
    "libcurl":      ("",    "7.76.1",   "29.el9_4"),
    "vim-enhanced": ("2:",  "8.2.2637", "20.el9_4"),
    "vim":          ("2:",  "8.2.2637", "20.el9_4"),
    "git":          ("",    "2.43.5",   "1.el9_4"),
    "rsync":        ("",    "3.2.3",    "19.el9"),
    "tar":          ("2:",  "1.34",     "6.el9_4"),
    "wget":         ("",    "1.21.1",   "8.el9_4"),
    "sudo":         ("",    "1.9.5p2",  "10.el9_4"),
    "htop":         ("",    "3.2.2",    "1.el9"),
    "tmux":         ("",    "3.2a",     "6.el9"),
    "firewalld":    ("",    "1.3.4",    "1.el9"),
    "java-17-openjdk": ("1:", "17.0.11.0.9", "2.el9"),
    "podman":       ("4:",  "4.9.4",    "5.el9"),
    "golang":       ("",    "1.21.13",  "1.el9"),
    "nodejs":       ("1:",  "18.20.4",  "1.el9_4"),
    "redis":        ("",    "7.2.4",    "1.el9"),
    "haproxy":      ("",    "2.4.22",   "3.el9_4"),
    "bind":         ("32:", "9.16.23",  "18.el9_4"),
    "postfix":      ("2:",  "3.5.9",    "21.el9_4"),
    "rsyslog":      ("",    "8.2310.0", "3.el9"),
    "certbot":      ("",    "2.7.4",    "1.el9"),
    "dnf":          ("",    "4.14.0",   "9.el9"),
    "rpm":          ("",    "4.16.1.3", "27.el9"),
    "kernel":       ("",    "5.14.0",   "427.13.1.el9_4"),
}


def _version_tuple(pkg: str) -> tuple[str, str, str]:
    """Return (epoch_prefix, version, release) for a package name."""
    if pkg in _KNOWN_VERSIONS:
        return _KNOWN_VERSIONS[pkg]
    # Generate a plausible version deterministically from the name hash
    h = int(hashlib.md5(pkg.encode()).hexdigest(), 16)
    major = 1 + (h % 9)
    minor = h % 20
    patch = (h >> 8) % 10
    return ("", f"{major}.{minor}.{patch}", f"1.el9")


def _nvra(pkg: str) -> str:
    """Return a Name-Version-Release-Arch string for the package."""
    ep, ver, rel = _version_tuple(pkg)
    return f"{pkg}-{ep}{ver}-{rel}.x86_64"


def _size_str(pkg: str) -> str:
    """Return a realistic install size string for the package."""
    h = int(hashlib.md5(pkg.encode()).hexdigest(), 16)
    sizes = ["36 k", "108 k", "2.1 M", "298 k", "1.4 M", "84 k", "420 k", "7.2 M", "512 k", "3.8 M"]
    return sizes[h % len(sizes)]


def _repo_label(pkg: str) -> str:
    h = int(hashlib.md5(pkg.encode()).hexdigest(), 16)
    repos = ["appstream", "baseos", "extras", "crb"]
    return repos[h % len(repos)]


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_install(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    packages: list[str] = args.get("packages") or []
    if not packages:
        return _make_result(
            exit_code=1,
            stdout="",
            stderr="Error: No package names supplied to install.\n",
            summary="dnf install failed: no package names were supplied.",
        )

    # Check each package for failure triggers (use the first package name as key)
    first = packages[0]

    if _perm_denied_trigger(first):
        stderr = (
            "Error: This command has to be run with superuser privileges (under the root user on most systems).\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"dnf install failed: superuser privileges are required.",
        )

    for pkg in packages:
        if _pkg_not_found_trigger(pkg):
            stdout = (
                f"Last metadata expiration check: {_META_EXPIRY}\n"
                f"No match for argument: {pkg}\n"
                f"Error: Unable to find a match: {pkg}\n"
            )
            return _make_result(
                exit_code=1,
                stdout=stdout,
                stderr="",
                summary=f"Package '{pkg}' was not found in any configured repository.",
            )

        if _pkg_conflict_trigger(pkg):
            ep, ver, rel = _version_tuple(pkg)
            stdout = (
                f"Last metadata expiration check: {_META_EXPIRY}\n"
                "Error: \n"
                f" Problem: package {pkg}-{ep}{ver}-{rel}.x86_64 has conflicting requirements\n"
                "  - package foo-1.0-1.el9.x86_64 requires libbar.so.1()(64bit), but none of the providers can be installed\n"
                "  - conflicting requests\n"
                f"(try to add '--allowerasing' to command line to replace conflicting packages or '--skip-broken' to skip uninstallable packages)\n"
            )
            return _make_result(
                exit_code=1,
                stdout=stdout,
                stderr="",
                summary=f"dnf install failed for '{pkg}': dependency conflict detected.",
            )

    # Check for already-installed packages via ctx
    already_installed = [p for p in packages if _pkg_in_ctx(p, ctx)]
    new_packages = [p for p in packages if p not in already_installed]

    if already_installed and not new_packages:
        # All packages already installed
        pkg_list = ", ".join(already_installed)
        stdout = (
            f"Last metadata expiration check: {_META_EXPIRY}\n"
            "Package(s) already installed:\n"
        )
        for p in already_installed:
            ep, ver, rel = _version_tuple(p)
            stdout += f"  {p}-{ep}{ver}-{rel}.x86_64\n"
        stdout += "Nothing to do.\nComplete!\n"
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"Package(s) '{pkg_list}' already installed; nothing to do.",
        )

    # Normal install success path
    total_size_kb = sum(
        int(_size_str(p).split()[0]) if _size_str(p).endswith("k")
        else int(float(_size_str(p).split()[0]) * 1024)
        for p in new_packages
    )
    install_count = len(new_packages)
    upgrade_count = len(already_installed)

    header = (
        f"Last metadata expiration check: {_META_EXPIRY}\n"
        "Dependencies resolved.\n"
        "================================================================================\n"
        " Package                 Architecture   Version                  Repository  Size\n"
        "================================================================================\n"
    )

    installing_lines = ""
    if new_packages:
        installing_lines += "Installing:\n"
        for p in new_packages:
            ep, ver, rel = _version_tuple(p)
            repo = _repo_label(p)
            sz = _size_str(p)
            installing_lines += f" {p:<24} x86_64         {ep}{ver}-{rel:<24} {repo:<10} {sz}\n"

    upgrading_lines = ""
    if already_installed:
        upgrading_lines += "Upgrading:\n"
        for p in already_installed:
            ep, ver, rel = _version_tuple(p)
            repo = _repo_label(p)
            sz = _size_str(p)
            upgrading_lines += f" {p:<24} x86_64         {ep}{ver}-{rel:<24} {repo:<10} {sz}\n"

    summary_line_parts = []
    if install_count:
        summary_line_parts.append(f"Install  {install_count} Package{'s' if install_count > 1 else ''}")
    if upgrade_count:
        summary_line_parts.append(f"Upgrade  {upgrade_count} Package{'s' if upgrade_count > 1 else ''}")

    transaction_summary = (
        "\nTransaction Summary\n"
        "================================================================================\n"
        + "\n".join(summary_line_parts) + "\n\n"
        "Total download size: 2.4 M\n"
        "Downloading Packages:\n"
    )
    for p in new_packages + already_installed:
        nvra = _nvra(p)
        transaction_summary += f"{nvra}.rpm                              1.2 MB/s | 2.4 MB     00:02\n"

    transaction_body = (
        "Running transaction check\n"
        "Transaction check succeeded.\n"
        "Running transaction test\n"
        "Transaction test succeeded.\n"
        "Running transaction\n"
    )
    total_steps = len(new_packages) + len(already_installed)
    for i, p in enumerate(new_packages, 1):
        ep, ver, rel = _version_tuple(p)
        transaction_body += f"  Installing  : {p}-{ep}{ver}-{rel}.x86_64{' ' * max(1, 56 - len(p))}{i}/{total_steps}\n"
    for i, p in enumerate(already_installed, len(new_packages) + 1):
        ep, ver, rel = _version_tuple(p)
        transaction_body += f"  Upgrading   : {p}-{ep}{ver}-{rel}.x86_64{' ' * max(1, 56 - len(p))}{i}/{total_steps}\n"
    for i, p in enumerate(new_packages + already_installed, 1):
        ep, ver, rel = _version_tuple(p)
        transaction_body += f"  Verifying   : {p}-{ep}{ver}-{rel}.x86_64{' ' * max(1, 56 - len(p))}{i}/{total_steps}\n"

    installed_section = "\nInstalled:\n" if new_packages else ""
    for p in new_packages:
        installed_section += f"  {_nvra(p)}\n"
    upgraded_section = "\nUpgraded:\n" if already_installed else ""
    for p in already_installed:
        upgraded_section += f"  {_nvra(p)}\n"

    stdout = header + installing_lines + upgrading_lines + transaction_summary + transaction_body + installed_section + upgraded_section + "\nComplete!\n"
    pkg_list = ", ".join(packages)
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Successfully installed {pkg_list}.",
    )


def _sim_remove(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    packages: list[str] = args.get("packages") or []
    if not packages:
        return _make_result(
            exit_code=1,
            stdout="",
            stderr="Error: No package names supplied to remove.\n",
            summary="dnf remove failed: no package names were supplied.",
        )

    gate_cleared: bool = bool(args.get("gate_cleared", False))
    first = packages[0]

    # Detect critical packages for DESTRUCTIVE classification
    _CRITICAL_NAMES = frozenset({
        "kernel", "kernel-core", "openssh-server", "openssh",
        "sudo", "polkit", "pam", "glibc", "systemd", "dnf", "rpm",
        "bash", "coreutils",
    })
    has_critical = any(p in _CRITICAL_NAMES for p in packages)

    # Determine which packages are actually installed (present in ctx)
    installed = [p for p in packages if _pkg_in_ctx(p, ctx)]
    not_installed = [p for p in packages if not _pkg_in_ctx(p, ctx) and not _pkg_not_found_trigger(p)]
    # If ctx is empty, treat all as installed (can't determine state)
    if not isinstance(ctx, (dict, str)):
        installed = packages
        not_installed = []

    # If context says it's not there and not a not-found trigger, still proceed
    # (remove might work or might say not installed)
    pkg_list = ", ".join(packages)

    # Build the dry-run plan output
    dry_run_header = (
        f"Last metadata expiration check: {_META_EXPIRY}\n"
        "Dependencies resolved.\n"
        "================================================================================\n"
        " Package                 Architecture   Version                  Repository  Size\n"
        "================================================================================\n"
        "Removing:\n"
    )
    dry_run_body = ""
    for p in packages:
        ep, ver, rel = _version_tuple(p)
        sz = _size_str(p)
        dry_run_body += f" {p:<24} x86_64         {ep}{ver}-{rel:<24} @System     {sz}\n"

    tx_count = len(packages)
    dry_run_summary = (
        "\nTransaction Summary\n"
        "================================================================================\n"
        f"Remove  {tx_count} Package{'s' if tx_count > 1 else ''}\n"
        "\nFreed space: 14 M\n"
        "Operation aborted.\n"
    )
    if has_critical:
        dry_run_summary += (
            "\nWarning: critical system package(s) in transaction. "
            "Removing these may render the host unbootable or unreachable.\n"
        )

    tx_summary_text = f"Transaction will remove: {pkg_list}."
    if has_critical:
        tx_summary_text += " WARNING: critical system package(s) detected."

    if not gate_cleared:
        # Return the dry-run preview — gate is pending
        dry_stdout = dry_run_header + dry_run_body + dry_run_summary
        return _make_result(
            exit_code=None,
            stdout=dry_stdout,
            stderr="",
            summary=f"[dry-run preview — confirm required] {tx_summary_text}",
        )

    # Gate cleared: execute real remove
    # Simulate not-installed case for packages not in ctx
    if not_installed and not installed:
        not_inst_list = ", ".join(not_installed)
        stdout = (
            f"Last metadata expiration check: {_META_EXPIRY}\n"
            f"No match for argument: {not_installed[0]}\n"
            f"Error: No packages marked for removal.\n"
        )
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr="",
            summary=f"Package(s) '{not_inst_list}' not installed; nothing removed.",
        )

    remove_header = (
        f"Last metadata expiration check: {_META_EXPIRY}\n"
        "Dependencies resolved.\n"
        "================================================================================\n"
        " Package                 Architecture   Version                  Repository  Size\n"
        "================================================================================\n"
        "Removing:\n"
    )
    remove_body = ""
    for p in packages:
        ep, ver, rel = _version_tuple(p)
        sz = _size_str(p)
        remove_body += f" {p:<24} x86_64         {ep}{ver}-{rel:<24} @System     {sz}\n"

    remove_tx = (
        "\nTransaction Summary\n"
        "================================================================================\n"
        f"Remove  {tx_count} Package{'s' if tx_count > 1 else ''}\n"
        "\nFreed space: 14 M\n"
        "Running transaction check\n"
        "Transaction check succeeded.\n"
        "Running transaction test\n"
        "Transaction test succeeded.\n"
        "Running transaction\n"
    )
    for i, p in enumerate(packages, 1):
        ep, ver, rel = _version_tuple(p)
        remove_tx += f"  Erasing     : {p}-{ep}{ver}-{rel}.x86_64{' ' * max(1, 56 - len(p))}{i}/{tx_count}\n"
    for i, p in enumerate(packages, 1):
        ep, ver, rel = _version_tuple(p)
        remove_tx += f"  Verifying   : {p}-{ep}{ver}-{rel}.x86_64{' ' * max(1, 56 - len(p))}{i}/{tx_count}\n"

    removed_section = "\nRemoved:\n"
    for p in packages:
        removed_section += f"  {_nvra(p)}\n"

    stdout = remove_header + remove_body + remove_tx + removed_section + "\nComplete!\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Successfully removed {pkg_list}.",
    )


def _sim_update(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    packages: list[str] = args.get("packages") or []
    target = ", ".join(packages) if packages else "all packages"
    is_full_update = not packages

    # For single packages, check not-found trigger
    if packages:
        for pkg in packages:
            if _pkg_not_found_trigger(pkg):
                stdout = (
                    f"Last metadata expiration check: {_META_EXPIRY}\n"
                    f"No match for argument: {pkg}\n"
                    f"Error: Unable to find a match: {pkg}\n"
                )
                return _make_result(
                    exit_code=1,
                    stdout=stdout,
                    stderr="",
                    summary=f"Package '{pkg}' was not found in any configured repository.",
                )

    # Hash-based nothing-to-do path (realistic on recently patched hosts)
    trigger_key = packages[0] if packages else "fullsystem"
    if _update_nothing_to_do_trigger(trigger_key):
        stdout = (
            f"Last metadata expiration check: {_META_EXPIRY}\n"
            "Dependencies resolved.\n"
            "Nothing to do.\n"
            "Complete!\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"Update of {target}: all packages already at the latest version.",
        )

    # Build realistic update output
    # For full update, pick a set of common system packages to upgrade
    if is_full_update:
        to_upgrade = [
            ("curl",     "",    "7.76.1", "29.el9_4",  "298 k", "baseos"),
            ("libcurl",  "",    "7.76.1", "29.el9_4",  "283 k", "baseos"),
            ("openssl",  "1:",  "3.0.7",  "25.el9_4",  "1.2 M", "baseos"),
            ("openssl-libs", "1:", "3.0.7", "25.el9_4","2.2 M", "baseos"),
            ("python3",  "",    "3.9.18", "3.el9_4.1", "32 k",  "appstream"),
        ]
        count = len(to_upgrade)
    else:
        to_upgrade = []
        for pkg in packages:
            ep, ver, rel = _version_tuple(pkg)
            sz = _size_str(pkg)
            repo = _repo_label(pkg)
            to_upgrade.append((pkg, ep, ver, rel, sz, repo))
        count = len(to_upgrade)

    header = (
        f"Last metadata expiration check: {_META_EXPIRY}\n"
        "Dependencies resolved.\n"
        "================================================================================\n"
        " Package                 Architecture   Version                  Repository  Size\n"
        "================================================================================\n"
        "Upgrading:\n"
    )
    pkg_lines = ""
    for pkg, ep, ver, rel, sz, repo in to_upgrade:
        pkg_lines += f" {pkg:<24} x86_64         {ep}{ver}-{rel:<24} {repo:<10} {sz}\n"

    tx_summary = (
        "\nTransaction Summary\n"
        "================================================================================\n"
        f"Upgrade  {count} Package{'s' if count > 1 else ''}\n\n"
        "Total download size: 4.0 M\n"
        "Downloading Packages:\n"
    )
    for pkg, ep, ver, rel, sz, repo in to_upgrade:
        tx_summary += f"{pkg}-{ep}{ver}-{rel}.x86_64.rpm                    1.8 MB/s | 4.0 MB     00:02\n"

    tx_body = (
        "Running transaction check\n"
        "Transaction check succeeded.\n"
        "Running transaction test\n"
        "Transaction test succeeded.\n"
        "Running transaction\n"
    )
    total_steps = count * 2
    for i, (pkg, ep, ver, rel, sz, repo) in enumerate(to_upgrade, 1):
        tx_body += f"  Upgrading   : {pkg}-{ep}{ver}-{rel}.x86_64{' ' * max(1, 54 - len(pkg))}{i}/{total_steps}\n"
    for i, (pkg, ep, ver, rel, sz, repo) in enumerate(to_upgrade, count + 1):
        tx_body += f"  Verifying   : {pkg}-{ep}{ver}-{rel}.x86_64{' ' * max(1, 54 - len(pkg))}{i}/{total_steps}\n"

    upgraded_section = "\nUpgraded:\n"
    for pkg, ep, ver, rel, sz, repo in to_upgrade:
        upgraded_section += f"  {pkg}-{ep}{ver}-{rel}.x86_64\n"

    stdout = header + pkg_lines + tx_summary + tx_body + upgraded_section + "\nComplete!\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Successfully updated {target}; {count} package{'s' if count > 1 else ''} upgraded.",
    )


def _sim_search(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    keyword: str = args.get("keyword", "")

    if not keyword:
        stdout = f"Last metadata expiration check: {_META_EXPIRY}\nError: No keyword given.\n"
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr="",
            summary="dnf search failed: no keyword was supplied.",
        )

    lower = keyword.lower()

    # No-results triggers
    no_results = any(tok in lower for tok in ("notfound", "noexist", "bogus", "conflict", "xyzzy", "fake"))
    if no_results:
        stdout = (
            f"Last metadata expiration check: {_META_EXPIRY}\n"
            f'No matches found for: {keyword}\n'
        )
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr="",
            summary=f"dnf search '{keyword}': no packages found matching that keyword.",
        )

    # Build realistic search results keyed on keyword
    # Map common keywords to plausible result sets
    _SEARCH_RESULTS: dict[str, list[tuple[str, str]]] = {
        "nginx": [
            ("nginx.x86_64",                    "A high performance web server"),
            ("nginx-all-modules.noarch",         "A meta package that installs all available Nginx modules"),
            ("nginx-filesystem.noarch",          "The basic directory layout for the Nginx server"),
            ("nginx-mod-http-image-filter.x86_64", "Nginx HTTP image filter module"),
        ],
        "postgresql": [
            ("postgresql.x86_64",               "PostgreSQL client programs"),
            ("postgresql-server.x86_64",         "The programs needed to create and run a PostgreSQL server"),
            ("postgresql-contrib.x86_64",        "Extension modules distributed with PostgreSQL"),
            ("postgresql-libs.x86_64",           "The shared libraries required for any PostgreSQL clients"),
            ("pgbackrest.x86_64",                "Reliable PostgreSQL Backup and Restore"),
        ],
        "python": [
            ("python3.x86_64",                  "Python 3.9 interpreter"),
            ("python3-pip.noarch",               "Package manager for Python 3"),
            ("python3-setuptools.noarch",        "Easily download, build, install, upgrade Python packages"),
            ("python3-devel.x86_64",             "Libraries and header files needed for Python 3 development"),
        ],
        "java": [
            ("java-17-openjdk.x86_64",          "OpenJDK 17 Runtime Environment"),
            ("java-17-openjdk-devel.x86_64",    "OpenJDK 17 Development Environment"),
            ("java-11-openjdk.x86_64",          "OpenJDK 11 Runtime Environment"),
        ],
        "git": [
            ("git.x86_64",                      "Fast Version Control System"),
            ("git-core.x86_64",                 "Core package of git with most of the functionality"),
            ("git-lfs.x86_64",                  "Git Large File Storage"),
        ],
        "mysql": [
            ("mysql.x86_64",                    "MySQL client programs and shared library"),
            ("mysql-server.x86_64",             "The MySQL server and related files"),
            ("mysql-common.x86_64",             "The shared files required for MySQL client"),
        ],
        "redis": [
            ("redis.x86_64",                    "A persistent key-value database"),
            ("redis-devel.x86_64",              "Development header files for redis"),
        ],
        "haproxy": [
            ("haproxy.x86_64",                  "TCP/HTTP proxy and load balancer for high availability"),
        ],
        "vim": [
            ("vim-enhanced.x86_64",             "A version of the VIM editor which includes recent enhancements"),
            ("vim-common.x86_64",               "The common files needed by any version of the VIM editor"),
            ("vim-filesystem.noarch",            "VIM filesystem layout"),
        ],
        "curl": [
            ("curl.x86_64",                     "A utility for getting files from remote servers"),
            ("libcurl.x86_64",                  "The multiprotocol file transfer library"),
            ("libcurl-devel.x86_64",            "Files needed for building applications with libcurl"),
        ],
        "firewalld": [
            ("firewalld.noarch",                "A firewall daemon with D-BUS interface for dynamic management"),
            ("firewalld-filesystem.noarch",      "Firewalld directory layout and files"),
        ],
        "rsync": [
            ("rsync.x86_64",                    "A program for synchronizing files over a network"),
        ],
        "docker": [
            ("docker-ce.x86_64",                "Docker Engine"),
            ("docker-ce-cli.x86_64",            "Docker CLI"),
            ("docker-compose-plugin.x86_64",    "Docker Compose plugin for Docker CLI"),
        ],
        "podman": [
            ("podman.x86_64",                   "Manage Pods, Containers and Container Images"),
            ("podman-compose.noarch",            "Run docker-compose.yml using podman"),
        ],
        "golang": [
            ("golang.x86_64",                   "The Go Programming Language"),
            ("golang-bin.x86_64",               "Golang core compiler tools"),
        ],
        "nodejs": [
            ("nodejs.x86_64",                   "JavaScript runtime"),
            ("nodejs-npm.x86_64",               "Node.js Package Manager"),
        ],
        "bind": [
            ("bind.x86_64",                     "The Berkeley Internet Name Domain (BIND) DNS server"),
            ("bind-utils.x86_64",               "Utilities for querying DNS name servers"),
        ],
        "postfix": [
            ("postfix.x86_64",                  "Postfix Mail Transport Agent"),
            ("postfix-pcre.x86_64",             "Postfix Perl-Compatible Regular Expression support"),
        ],
        "htop": [
            ("htop.x86_64",                     "Interactive process viewer"),
        ],
    }

    # Try to find results for keyword
    results = None
    for key, rows in _SEARCH_RESULTS.items():
        if key in lower or lower in key:
            results = rows
            break

    if results is None:
        # Generate a generic result set for unrecognised keywords
        h = int(hashlib.md5(keyword.encode()).hexdigest(), 16)
        generic_names = [
            f"{keyword}-utils",
            f"{keyword}-libs",
            f"{keyword}-devel",
            f"python3-{keyword}",
        ]
        results = [
            (f"{n}.x86_64", f"Utilities and libraries related to {keyword}")
            for n in generic_names[:2 + (h % 3)]
        ]

    exact_header = f"{'=' * 20} Name Exactly Matched: {keyword} {'=' * 20}\n"
    name_header = f"{'=' * 18} Name & Summary Matched: {keyword} {'=' * 18}\n"
    rows_str = ""
    for i, (pkg_arch, desc) in enumerate(results):
        if i == 0:
            rows_str += exact_header
        elif i == 1:
            rows_str += name_header
        rows_str += f"{pkg_arch} : {desc}\n"

    stdout = f"Last metadata expiration check: {_META_EXPIRY}\n{rows_str}"
    count = len(results)
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"dnf search '{keyword}' returned {count} result{'s' if count != 1 else ''}.",
    )


def _sim_info(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    package: str = args.get("package", "")

    if not package:
        stdout = f"Last metadata expiration check: {_META_EXPIRY}\nError: No package name given.\n"
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr="",
            summary="dnf info failed: no package name was supplied.",
        )

    if _pkg_not_found_trigger(package):
        stdout = (
            f"Last metadata expiration check: {_META_EXPIRY}\n"
            f"Error: No matching Packages to list\n"
        )
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr="",
            summary=f"Package '{package}' was not found in any configured repository.",
        )

    ep, ver, rel = _version_tuple(package)
    repo = _repo_label(package)
    installed = _pkg_in_ctx(package, ctx)

    # Generate a plausible summary line for the package
    _PKG_SUMMARIES: dict[str, str] = {
        "nginx":               "A high performance web server and a reverse proxy server",
        "httpd":               "Apache HTTP Server",
        "postgresql":          "PostgreSQL client programs",
        "postgresql-server":   "The programs needed to create and run a PostgreSQL server",
        "mysql":               "MySQL client programs and shared library",
        "mysql-server":        "The MySQL server and related files",
        "python3":             "Python 3.9 interpreter",
        "openssl":             "Utilities from the general purpose cryptography library",
        "openssl-libs":        "A general purpose cryptography library",
        "curl":                "A utility for getting files from remote servers",
        "libcurl":             "The multiprotocol file transfer library",
        "git":                 "Fast Version Control System",
        "rsync":               "A program for synchronizing files over a network",
        "vim-enhanced":        "A version of the VIM editor which includes recent enhancements",
        "vim":                 "The VIM editor",
        "sudo":                "Allows restricted root access for specified users",
        "htop":                "Interactive process viewer",
        "tmux":                "A terminal multiplexer",
        "firewalld":           "A firewall daemon with D-BUS interface for dynamic management",
        "haproxy":             "TCP/HTTP proxy and load balancer for high availability",
        "redis":               "A persistent key-value database",
        "nodejs":              "JavaScript runtime",
        "golang":              "The Go Programming Language",
        "java-17-openjdk":     "OpenJDK 17 Runtime Environment",
        "podman":              "Manage Pods, Containers and Container Images",
        "bind":                "The Berkeley Internet Name Domain (BIND) DNS server",
        "postfix":             "Postfix Mail Transport Agent",
        "certbot":             "A free, automated certificate client",
        "rsyslog":             "Enhanced system logging and kernel message trapping daemon",
        "dnf":                 "Package manager",
        "rpm":                 "The RPM package management system",
        "kernel":              "The Linux kernel",
    }
    pkg_summary = _PKG_SUMMARIES.get(package, f"Package providing {package} functionality on Rocky Linux 9")

    # Installed vs available section
    section = "Installed Packages" if installed else "Available Packages"
    repo_display = "@System" if installed else repo
    from_repo = repo

    h = int(hashlib.md5(package.encode()).hexdigest(), 16)
    size_kb = 36 + (h % 4000)
    size_str = f"{size_kb} k" if size_kb < 1024 else f"{size_kb / 1024:.1f} M"

    stdout = (
        f"Last metadata expiration check: {_META_EXPIRY}\n"
        f"{section}\n"
        f"Name         : {package}\n"
    )
    if ep:
        epoch_val = ep.rstrip(":")
        stdout += f"Epoch        : {epoch_val}\n"
    stdout += (
        f"Version      : {ver}\n"
        f"Release      : {rel}\n"
        f"Architecture : x86_64\n"
        f"Size         : {size_str}\n"
        f"Source       : {package}-{ep}{ver}-{rel}.src.rpm\n"
        f"Repository   : {repo_display}\n"
        f"From repo    : {from_repo}\n"
        f"Summary      : {pkg_summary}\n"
        f"URL          : https://rocky.example.com/packages/{package}\n"
        f"License      : GPLv2+\n"
        f"Description  : {pkg_summary}.\n"
        f"             : See the upstream documentation for details.\n"
    )

    status = "installed" if installed else "available"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Package '{package}' ({status}): version {ep}{ver}-{rel}.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "install": _sim_install,
    "remove":  _sim_remove,
    "update":  _sim_update,
    "search":  _sim_search,
    "info":    _sim_info,
}


def simulate_packages(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'packages' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 5 real ops declared in the
           packages ToolSpec (install, remove, update, search, info).
    args : argument dict (may be sparse; ops with required args return a
           realistic error when those args are absent).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with a 'pkg_sample' list.

    Returns
    -------
    dict with keys: exit_code (int | None), stdout (str), stderr (str),
    summary (str).  All four keys are always present.  summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_packages: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
