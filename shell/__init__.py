# shell/ — the login shell layer.
#
# shell.py     the main input loop: mode state, dispatch, dead-man
# prompt.py    colored prompt strings per tier and mode
# passthrough.py  run a bash command and stream its output
# dispatch.py  command-vs-English heuristic
# hooks/       shell lifecycle hooks (startup health check, etc.)
