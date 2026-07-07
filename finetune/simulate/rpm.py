"""finetune/simulate/rpm.py — Rocky Linux 9 output simulator for the 'rpm' tool.

Public API
----------
simulate_rpm(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 7 real operations declared in core/tools/rpm.py
           (query_info, query_files, query_file, verify, checksig, install,
            rpm2cpio)
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Both forms are supported via isinstance.

Realism model
-------------
* Exit codes mirror real rpm / rpm2cpio behaviour:
    0  — success
    1  — package not found, file not found, signature failure, install error
* stdout/stderr reflect actual Rocky 9 rpm output format:
    - rpm -qi: multi-line package metadata block
    - rpm -ql: one path per line
    - rpm -qf: "PACKAGE-VERSION-RELEASE.ARCH" on success
    - rpm -V / -Va: "<flags> <file>" lines on discrepancies (empty = clean)
    - rpm --checksig: "<file>: digests signatures OK"
    - rpm -ivh: Preparing... / Updating... progress lines
    - rpm2cpio: binary cpio data (simulated as placeholder text)
* Failure triggers are deterministic: token "notfound"/"noexist"/"missing"/
  "bogus" in package/file/rpm_file triggers not-found / error branch.
  A hash-based 15% scatter adds variety.

I2 compliance
-------------
All `summary` strings are I2-clean. No forbidden terms appear.

INV-read-only-core: this module imports NOTHING from core/ and NOTHING
from finetune.coreimports (avoids circular deps when __init__.py imports
simulate modules before coreimports is fully settled).
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    exit_code: int,
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


def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for use in realistic output lines."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _is_bad(name: str) -> bool:
    """Deterministically decide whether this name should trigger an error branch."""
    lower = name.lower()
    for tok in ("notfound", "noexist", "missing", "bogus", "broken", "fail"):
        if tok in lower:
            return True
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return h % 20 == 0


def _pkg_version(pkg: str) -> str:
    """Derive a plausible version string deterministically from package name."""
    h = int(hashlib.md5(pkg.encode()).hexdigest(), 16)
    major = (h % 5) + 1
    minor = (h >> 4) % 20
    patch = (h >> 8) % 10
    release = (h >> 12) % 50 + 1
    return f"{major}.{minor}.{patch}-{release}.el9.x86_64"


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_query_info(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    package = args.get("package", "unknown")

    if _is_bad(package):
        stderr = f"package {package} is not installed\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Package '{package}' is not installed.",
        )

    ver = _pkg_version(package)
    ver_parts = ver.split("-")
    version_str = ver_parts[0]
    release_str = ver_parts[1] if len(ver_parts) > 1 else "1.el9"

    stdout = (
        f"Name        : {package}\n"
        f"Version     : {version_str}\n"
        f"Release     : {release_str}\n"
        f"Architecture: x86_64\n"
        f"Install Date: Thu 03 Jul 2026 00:01:12 AM UTC\n"
        f"Group       : System Environment/Libraries\n"
        f"Size        : {(abs(hash(package)) % 50000000) + 10000}\n"
        f"License     : GPLv2+\n"
        f"Signature   : RSA/SHA256, Tue 01 Jan 2026 12:00:00 AM UTC, Key ID 199e2f91fd431d51\n"
        f"Source RPM  : {package}-{version_str}-{release_str.split('.')[0]}.el9.src.rpm\n"
        f"Build Date  : Mon 01 Jan 2026 00:00:00 AM UTC\n"
        f"Build Host  : build.rocky.local\n"
        f"Packager    : Rocky Linux\n"
        f"Vendor      : Rocky Enterprise Software Foundation\n"
        f"URL         : https://rocky.page/{package}\n"
        f"Summary     : The {package} package\n"
        f"Description :\n"
        f"This package provides {package} for Rocky Linux 9.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Package '{package}' metadata retrieved.",
    )


def _sim_query_files(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    package = args.get("package", "unknown")

    if _is_bad(package):
        stderr = f"package {package} is not installed\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Could not list files for package '{package}': not installed.",
        )

    # Generate a plausible file list
    base_files = [
        f"/usr/bin/{package}",
        f"/usr/lib64/lib{package}.so.0",
        f"/usr/share/doc/{package}/README",
        f"/usr/share/doc/{package}/COPYING",
        f"/usr/share/man/man1/{package}.1.gz",
        f"/etc/{package}/{package}.conf",
    ]
    stdout = "\n".join(base_files) + "\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Package '{package}' owns {len(base_files)} file(s).",
    )


def _sim_query_file(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    file_path = args.get("file", "/unknown")

    if _is_bad(file_path) or not file_path.startswith("/"):
        stderr = f"file {file_path} is not owned by any package\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"File '{file_path}' is not owned by any installed package.",
        )

    # Derive a plausible owner package name from the path
    parts = [p for p in file_path.split("/") if p]
    if parts:
        base = parts[-1].split(".")[0].rstrip("0123456789")
        pkg_name = base if base else "coreutils"
    else:
        pkg_name = "coreutils"

    ver = _pkg_version(pkg_name)
    owner = f"{pkg_name}-{ver}"
    stdout = f"{owner}\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"File '{file_path}' is owned by package '{owner}'.",
    )


def _sim_verify(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    package = args.get("package", "")

    if package and _is_bad(package):
        stderr = f"package {package} is not installed\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Cannot verify package '{package}': not installed.",
        )

    # Hash-based scatter: ~20% chance of finding discrepancies
    check_key = package if package else "all"
    h = int(hashlib.md5(check_key.encode()).hexdigest(), 16)
    has_discrepancy = (h % 5 == 0)

    target = f"package '{package}'" if package else "all installed packages"

    if has_discrepancy:
        pkg_for_output = package if package else "openssl-libs"
        stdout = (
            f"S.5....T.  c /etc/{pkg_for_output}/{pkg_for_output}.conf\n"
            f"..?......    /usr/lib64/lib{pkg_for_output}.so.0\n"
        )
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr="",
            summary=(
                f"Integrity verification of {target} found 2 discrepancy(ies) (exit 1)."
            ),
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Integrity verification of {target} passed; no discrepancies found.",
    )


def _sim_checksig(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    rpm_file = args.get("rpm_file", "/tmp/unknown.rpm")

    if _is_bad(rpm_file):
        stderr = f"error: open of {rpm_file} failed: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Signature check for '{rpm_file}' failed: file not found.",
        )

    # Hash-based: ~10% bad-signature scatter
    h = int(hashlib.md5(rpm_file.encode()).hexdigest(), 16)
    bad_sig = (h % 10 == 0)

    if bad_sig:
        stdout = f"{rpm_file}: digests SIGNATURES NOT OK\n"
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr="",
            summary=f"Signature check for '{rpm_file}' failed: signatures do not verify.",
        )

    stdout = f"{rpm_file}: digests signatures OK\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Signature check for '{rpm_file}' passed.",
    )


def _sim_install(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    rpm_file = args.get("rpm_file", "/tmp/unknown.rpm")

    if _is_bad(rpm_file):
        stderr = f"error: open of {rpm_file} failed: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Installation of '{rpm_file}' failed: file not found.",
        )

    # Hash-based: ~15% dependency conflict scatter
    h = int(hashlib.md5(rpm_file.encode()).hexdigest(), 16)
    dep_error = (h % 7 == 0)

    if dep_error:
        pkg_base = rpm_file.split("/")[-1].replace(".rpm", "")
        stderr = (
            f"error: Failed dependencies:\n"
            f"\tlibdep.so.1()(64bit) is needed by {pkg_base}\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Installation of '{rpm_file}' failed due to unresolved dependencies (exit 1).",
        )

    pkg_base = rpm_file.split("/")[-1].replace(".rpm", "")
    stdout = (
        f"Preparing...                          ########################################\n"
        f"Updating / installing...\n"
        f"   1:{pkg_base}              ########################################\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Package file '{rpm_file}' installed successfully.",
    )


def _sim_rpm2cpio(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    rpm_file = args.get("rpm_file", "/tmp/unknown.rpm")

    if _is_bad(rpm_file):
        stderr = f"error: open of {rpm_file} failed: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to extract cpio payload from '{rpm_file}': file not found.",
        )

    # Simulate binary cpio header placeholder
    stdout = (
        "07070100000000000000000000000000000000000000010000000000000000"
        "00000000000000000000000000000000000b00000000TRAILER!!!\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Extracted cpio payload from '{rpm_file}'.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "query_info":   _sim_query_info,
    "query_files":  _sim_query_files,
    "query_file":   _sim_query_file,
    "verify":       _sim_verify,
    "checksig":     _sim_checksig,
    "install":      _sim_install,
    "rpm2cpio":     _sim_rpm2cpio,
}


def simulate_rpm(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate an 'rpm' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 7 real ops declared in
           core/tools/rpm.py (query_info, query_files, query_file, verify,
           checksig, install, rpm2cpio).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either a snapshot_text str or a profile dict.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present.  summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_rpm: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
