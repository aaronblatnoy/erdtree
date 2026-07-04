"""finetune/coreimports.py — the ONE seam between finetune/ and core/.

This module is the ONLY place in finetune/ that imports from core/.  All other
finetune modules MUST import exclusively from here, never directly from core/.
This design enforces INV-read-only-core and keeps drift detectable in one file.

Load-bearing invariants enforced here
--------------------------------------
INV-schema-sync   All tool schemas are derived LIVE from the registry and
                  registry_schemas(). Nothing in finetune/ hardcodes a tool
                  name, op name, arg name, or permission_class literal.  The
                  corpus tracks core/ drift automatically.

INV-house-prompt  The system prompt MUST come from core/agent/prompt's
                  _HOUSE_SYSTEM_PROMPT (re-exported below as HOUSE_SYSTEM_PROMPT).
                  NEVER use a hand-copied string.

INV-I2            Every assistant `content` string, every simulate `summary`,
                  and every injected snapshot/system-prompt string must pass
                  core's _assert_no_ai_language (re-exported as
                  assert_no_ai_language here).  The assert-function is imported
                  via its private underscore name _assert_no_ai_language — this
                  is DELIBERATE and load-bearing: we bind to the REAL filter
                  inside core/, not a copy.  If core/ is ever refactored to
                  rename or move that symbol, the ImportError surfaces HERE
                  immediately, catching any drift.

INV-offline       This module must import cleanly with no network, no Ollama,
                  and no ANTHROPIC_API_KEY.  Do not add any runtime I/O here.

INV-read-only-core  finetune/ imports FROM core/ and NEVER the reverse.  This
                    module is the enforcement boundary.  Do NOT modify anything
                    under core/ from within finetune/.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. Bring up the tool registry singleton.
#    core/tools/__init__.py defines `registry` as a module-level ToolRegistry.
# ---------------------------------------------------------------------------
from core.tools import registry  # noqa: E402

# ---------------------------------------------------------------------------
# 2. Side-effect tool imports — mirrors core/agent/main.py's registration block
#    exactly so all 11 tools self-register into `registry` at import time.
#
#    Each import is a pure side-effect (the module calls registry.register(...)
#    at import time).  Order mirrors main.py; do NOT reorder without also
#    updating main.py and the assertion below.
#
#    NOTE ON THE DOCS GUARD: main.py wraps `import core.tools.docs` in a
#    try/except because a missing corpus index must not crash startup (I9).
#    We mirror that guard here for the same reason — docs is optional at
#    import time (the tool degrades to empty-but-valid results at call time).
# ---------------------------------------------------------------------------
import core.tools.services   # noqa: F401
import core.tools.packages   # noqa: F401
import core.tools.logs       # noqa: F401
import core.tools.network    # noqa: F401
import core.tools.firewall   # noqa: F401
import core.tools.users      # noqa: F401
import core.tools.disk       # noqa: F401
import core.tools.processes  # noqa: F401
import core.tools.hardware   # noqa: F401
import core.tools.files      # noqa: F401

try:
    import core.tools.docs   # noqa: F401
except Exception:            # noqa: BLE001 — docs is optional; absence must never crash
    pass

# ---------------------------------------------------------------------------
# 3. Re-export router utilities.
# ---------------------------------------------------------------------------
from core.agent.router import (  # noqa: E402
    registry_schemas,
    validate_arguments,
    tool_to_function_schema,
)

# ---------------------------------------------------------------------------
# 4. Re-export prompt utilities.
#
#    DELIBERATE PRIVATE IMPORTS: _HOUSE_SYSTEM_PROMPT and _assert_no_ai_language
#    are underscore-prefixed names inside core/agent/prompt.py.  Importing them
#    here is INTENTIONAL and LOAD-BEARING:
#      * HOUSE_SYSTEM_PROMPT must be the REAL string, not a hand-copied stub
#        (INV-house-prompt).  Binding to the private name means a refactor that
#        renames or removes it in core/ will surface as an ImportError here,
#        preventing silent drift.
#      * assert_no_ai_language must be the REAL filter (INV-I2).  Same argument:
#        the underscore import is the canary that guarantees we are always using
#        core's authoritative implementation, never a loose copy.
#    A future core/ refactor that moves these symbols MUST update this file;
#    the ImportError is the intended signal.
# ---------------------------------------------------------------------------
from core.agent.prompt import (  # noqa: E402
    _HOUSE_SYSTEM_PROMPT as HOUSE_SYSTEM_PROMPT,   # deliberate private import — INV-house-prompt
    _assert_no_ai_language as assert_no_ai_language,  # deliberate private import — INV-I2
    build_tool_list,
    assemble_messages,
    PromptConfig,
)

# ---------------------------------------------------------------------------
# 5. Re-export permission class.
# ---------------------------------------------------------------------------
from core.agent.permissions import OpClass  # noqa: E402

# ---------------------------------------------------------------------------
# 6. Derived constants.
#
#    TOOL_NAMES is the LIVE sorted list of registered tool names.  It is
#    computed at import time (after all side-effect imports above have run)
#    so it reflects the real state of the registry.
#
#    The assertion is the P0 acceptance gate: exactly 11 tools must register.
#    If a tool module fails to import, or the docs guard swallows an unexpected
#    error, or a new tool is added without updating this count, this line fails
#    LOUDLY at import time — not silently at generation time.
#    Update the count here when core/ gains a new tool.
# ---------------------------------------------------------------------------
TOOL_NAMES: list[str] = sorted(registry.list_tools())
assert len(TOOL_NAMES) == 11, (
    f"Expected 11 registered tools, got {len(TOOL_NAMES)}: {TOOL_NAMES}\n"
    "Did a tool fail to import?  Check the side-effect imports above and "
    "core/agent/main.py's registration block for divergence."
)

# ---------------------------------------------------------------------------
# 7. Convenience helpers.
#
#    live_schemas() and live_tool_list() are thin wrappers that derive their
#    output from the live registry.  Call them at generation/validation time
#    (not module-import time) so that they reflect any registry mutations that
#    tests or fixtures may have made after this module was imported.
# ---------------------------------------------------------------------------

def live_schemas() -> list[dict]:
    """Return the live OpenAI-format function schemas for all registered tools.

    This is the authoritative source for tool schemas in finetune/.  NEVER
    hardcode a schema; always call this function (INV-schema-sync).
    """
    return registry_schemas(registry)


def live_tool_list() -> list[dict]:
    """Return the live tool list suitable for passing to assemble_messages().

    Equivalent to build_tool_list(live_schemas()).  Convenience wrapper that
    keeps call-sites in generate.py concise without adding any logic.
    """
    return build_tool_list(live_schemas())


# ---------------------------------------------------------------------------
# 8. Public surface summary (for static analysis / IDE support).
#    Everything listed here is safe to import from finetune.coreimports.
# ---------------------------------------------------------------------------
__all__ = [
    # Registry
    "registry",
    "TOOL_NAMES",
    # Router
    "registry_schemas",
    "validate_arguments",
    "tool_to_function_schema",
    # Prompt
    "HOUSE_SYSTEM_PROMPT",
    "assert_no_ai_language",
    "build_tool_list",
    "assemble_messages",
    "PromptConfig",
    # Permissions
    "OpClass",
    # Helpers
    "live_schemas",
    "live_tool_list",
]
