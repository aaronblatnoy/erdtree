"""finetune/simulate/grub.py — Rocky Linux 9 output simulator for the 'grub' tool.

Public API
----------
simulate_grub(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 8 real operations declared in core/tools/grub.py
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Checked via isinstance; both forms are supported.

Realism model
-------------
* Outputs mirror real grubby / grub2-mkconfig output on Rocky Linux 9.
* grubby --info output includes index, kernel, args, root, initrd, title, id.
* grub2-mkconfig output shows the standard "Generating grub configuration..." lines.
* Failure branches are triggered deterministically by sentinel tokens
  ("notfound", "noexist", "bogus", "missing") in the kernel path, or a
  hash-based 15% scatter for variety.
* UEFI vs BIOS path selection is hash-based on ctx hostname.

I2 compliance
-------------
All `summary` strings are I2-clean.  No forbidden terms appear in any
user-facing string.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (avoids circular deps when
the Phase-13 __init__ imports simulators before coreimports is settled).
The 4-key dict mirrors ToolResult with no class dependency.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_KERNEL = "/boot/vmlinuz-5.14.0-362.13.1.el9_3.x86_64"
_KERNEL_ARGS_DEFAULT = (
    "ro crashkernel=1G-4G:192M,4G-64G:256M,64G-:512M "
    "resume=/dev/mapper/rhel-swap rd.lvm.lv=rhel/root rd.lvm.lv=rhel/swap "
    "rhgb quiet"
)


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


def _default_kernel(ctx: Any) -> str:
    """Return the 'active' default kernel for this context."""
    if isinstance(ctx, dict):
        return ctx.get("default_kernel", _DEFAULT_KERNEL)
    return _DEFAULT_KERNEL


def _kernel_not_found(kernel: str) -> bool:
    """Deterministically decide whether a kernel path should trigger a not-found error."""
    if kernel in ("ALL", "all"):
        return False
    lower = kernel.lower()
    for tok in ("notfound", "noexist", "bogus", "missing", "fail", "broken"):
        if tok in lower:
            return True
    # A path that doesn't look like a kernel path at all
    if not kernel.startswith("/") and kernel != "ALL":
        return True
    # Hash-based 15% scatter for realism
    h = int(hashlib.md5(kernel.encode()).hexdigest(), 16)
    return h % 20 == 0


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


def _grubby_info_block(kernel: str, index: int = 0) -> str:
    """Build a realistic grubby --info block for a single kernel."""
    ver = kernel.replace("/boot/vmlinuz-", "") if "/boot/vmlinuz-" in kernel else "5.14.0-362.13.1.el9_3.x86_64"
    initrd = f"/boot/initramfs-{ver}.img"
    kernel_id = hashlib.md5(kernel.encode()).hexdigest()[:32]
    return (
        f"index={index}\n"
        f"kernel=\"{kernel}\"\n"
        f"args=\"{_KERNEL_ARGS_DEFAULT}\"\n"
        f"root=\"/dev/mapper/rhel-root\"\n"
        f"initrd=\"{initrd}\"\n"
        f'title="Red Hat Enterprise Linux ({ver}) 9.3 (Plow)"\n'
        f'id="{kernel_id}-{ver}"\n'
    )


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_info(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    kernel = args.get("kernel", "ALL")
    dflt = _default_kernel(ctx)

    if kernel == "ALL":
        # Simulate two kernels installed
        ver_old = "5.14.0-284.30.1.el9_2.x86_64"
        old_kernel = f"/boot/vmlinuz-{ver_old}"
        stdout = (
            _grubby_info_block(dflt, index=0)
            + "\n"
            + _grubby_info_block(old_kernel, index=1)
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="Retrieved GRUB entry information for all installed kernels.",
        )

    if _kernel_not_found(kernel):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"error: {kernel}: could not find kernel\n",
            summary=f"No GRUB entry found for kernel '{kernel}'.",
        )

    stdout = _grubby_info_block(kernel, index=0)
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Retrieved GRUB entry information for '{kernel}'.",
    )


def _sim_default_kernel(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    dflt = _default_kernel(ctx)
    return _make_result(
        exit_code=0,
        stdout=f"{dflt}\n",
        stderr="",
        summary=f"Default kernel is '{dflt}'.",
    )


def _sim_set_default(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    kernel = args.get("kernel", _DEFAULT_KERNEL)

    if _kernel_not_found(kernel):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"error: {kernel}: could not find kernel\n",
            summary=f"Failed to set default kernel — '{kernel}' was not found in the boot menu.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Default boot kernel set to '{kernel}'.",
    )


def _sim_args_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    kernel = args.get("kernel", _DEFAULT_KERNEL)
    kernel_args = args.get("kernel_args", "")

    if _kernel_not_found(kernel):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"error: {kernel}: could not find kernel\n",
            summary=f"Failed to add kernel arguments — '{kernel}' was not found in the boot menu.",
        )

    if not kernel_args:
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="No kernel arguments specified; boot entry left unchanged.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Kernel arguments '{kernel_args}' added to '{kernel}'.",
    )


def _sim_args_remove(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    kernel = args.get("kernel", _DEFAULT_KERNEL)
    kernel_args = args.get("kernel_args", "")

    if _kernel_not_found(kernel):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"error: {kernel}: could not find kernel\n",
            summary=f"Failed to remove kernel arguments — '{kernel}' was not found in the boot menu.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Kernel arguments '{kernel_args}' removed from '{kernel}'.",
    )


def _sim_mkconfig(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    output_file = args.get("output_file", "/boot/grub2/grub.cfg")
    dflt = _default_kernel(ctx)
    ver = dflt.replace("/boot/vmlinuz-", "") if "/boot/vmlinuz-" in dflt else "5.14.0-362.13.1.el9_3.x86_64"

    # Hash-based failure scatter (10%)
    h = int(hashlib.md5((output_file + "mkconfig").encode()).hexdigest(), 16)
    if h % 10 == 0:
        stderr = (
            f"grub2-mkconfig: error: failed to get canonical path of {output_file}\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to regenerate GRUB configuration to '{output_file}'.",
        )

    stdout = (
        "Generating grub configuration file ...\n"
        "Adding boot menu entry for EFI firmware configuration\n"
        f"Found linux image: {dflt}\n"
        f"Found initrd image: /boot/initramfs-{ver}.img\n"
        f"Found linux image: /boot/vmlinuz-5.14.0-284.30.1.el9_2.x86_64\n"
        "Found initrd image: /boot/initramfs-5.14.0-284.30.1.el9_2.x86_64.img\n"
        "done\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"GRUB configuration regenerated and written to '{output_file}'.",
    )


def _sim_set_password(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    password = args.get("password", "")

    if not password:
        return _make_result(
            exit_code=1,
            stdout="",
            stderr="error: no password provided\n",
            summary="Failed to set GRUB bootloader password — no password was provided.",
        )

    # Hash-based failure scatter (10%)
    h = int(hashlib.md5(password.encode()).hexdigest(), 16)
    if h % 10 == 0:
        return _make_result(
            exit_code=1,
            stdout="",
            stderr="error: failed to open /boot/grub2/user.cfg for writing\n",
            summary="Failed to set GRUB bootloader password — could not write to configuration file.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="GRUB bootloader password set successfully.",
    )


def _sim_remove_kernel(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    kernel = args.get("kernel", "")

    if not kernel or _kernel_not_found(kernel):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"error: {kernel}: could not find kernel\n" if kernel else "error: no kernel path specified\n",
            summary=f"Failed to remove kernel entry '{kernel}' — it was not found in the boot menu.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Kernel entry '{kernel}' removed from the boot menu.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "info":           _sim_info,
    "default-kernel": _sim_default_kernel,
    "set-default":    _sim_set_default,
    "args-add":       _sim_args_add,
    "args-remove":    _sim_args_remove,
    "mkconfig":       _sim_mkconfig,
    "set-password":   _sim_set_password,
    "remove-kernel":  _sim_remove_kernel,
}


def simulate_grub(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'grub' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 8 real ops declared in the
           grub ToolSpec (info, default-kernel, set-default, args-add,
           args-remove, mkconfig, set-password, remove-kernel).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'hostname'/'default_kernel' keys.

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
            f"simulate_grub: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
