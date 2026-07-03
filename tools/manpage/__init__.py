"""tools/manpage — Build-time man-page parser and schema generator.

DO NOT import this package at runtime on the shipped box.  It is a
build-time-only tool that:

  1. parse.py       — parses formatted man-page text into ParsedManPage objects.
  2. generate_schemas.py — converts ParsedManPage objects into the frozen
                           OpSpec/ArgSpec shape and emits/loads the versioned
                           JSON artifact at models/schemas/manpages.vN.json.

Usage (developer / CI):

    python -m tools.manpage.generate_schemas --output models/schemas/manpages.v1.json

The artifact is checked in; the shipped box loads it at boot via
generate_schemas.load_into_registry(registry).
"""
