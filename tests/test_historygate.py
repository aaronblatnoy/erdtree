from core.agent.historygate import needs_history


def test_fresh_requests_get_no_history():
    for s in ["restart nginx", "show me disk usage on this server", "is anything wrong with dns",
              "add 10.0.0.5 web1 to /etc/hosts", "run an aide integrity check so I have a baseline"]:
        assert not needs_history(s), s


def test_followups_get_history():
    for s in ["do it", "yes", "the second one", "now do the same for postgres", "undo that",
              "use these", "try again", "what happened", "and now restart it", "same for the other node"]:
        assert needs_history(s), s
