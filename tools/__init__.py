"""tools/ — Build-time tooling for Erdtree.

This package contains BUILD-TIME-ONLY utilities (e.g. man-page parsers,
schema generators) that are never imported at runtime on the shipped box.
Nothing here runs inference, talks to a network, or executes system commands
during a normal boot sequence.
"""
