"""Adjudications for the held-out pools, written after auditing model misses (2026-09-21).

The pools are scored against one reference call per item.  An audit of the items that BOTH
current models missed showed that many were flaws in the item, not in the model: the request
allowed a second correct answer, or the reference contained a value that appears nowhere in the
request.  Each entry below records the reason.  The harness reports raw scores (reference only)
and adjudicated scores side by side, so an adjudication can never silently inflate a result.

Rules for adding an entry:
- ALSO_OK only when the alternative call genuinely satisfies the request as written.
- UNSTATED_ARGS only when the reference value cannot be derived from the request or history.
- Never adjudicate a plain confusion (those become contrastive training data instead).
"""

# item id -> {"tool.operation": reason}
ALSO_OK = {
    "disk-format-eval-0002": {"disk.wipe": "request says 'wiped and formatted'; wipe is the stated first step"},
    "sysctl-set-eval-0002": {"sysctl.persist": "request says 'and persist it so it survives a reboot'"},
    "buildah-build-eval-0002": {"podman.build": "request names no build tool; podman build does the same job"},
    "postgresql-dropdb-eval-0002": {"mariadb.drop_database": "request never names the database engine"},
    "mariadb-drop_database-eval-0002": {"postgresql.dropdb": "request never names the database engine"},
    "mt-eval-0028": {"services.logs": "'check its logs' for a unit; services.logs reads the same journal"},
    "mt-eval-0043": {"services.logs": "'check its service logs'; services.logs reads the same journal"},
    "mt-eval-0048": {"services.logs": "'check its recent logs' for a service; same journal"},
    "mt-eval-0053": {"virsh.logs": "'its logs' refers to the VM; the VM log is more direct than the libvirtd journal"},
    "mt-eval-0078": {"network.status": "'interface status' is answered by either interfaces or status"},
}

# Arguments whose value is free text written by the model.  Exact equality with the reference
# wording is meaningless; they are scored as present and non-empty.
FREE_TEXT_ARGS = {"query", "rule", "content", "command", "key_comment", "message", "description"}

# item id -> argument names whose reference value is not stated in the request or history.
UNSTATED_ARGS = {
    "tar-extract-eval-0002": {"archive", "dest"},
    "rsync-sync-delete-eval-0002": {"src", "dest"},
    "grub-remove-kernel-eval-0002": {"kernel"},
    "mt-eval-0068": {"name"},
}
