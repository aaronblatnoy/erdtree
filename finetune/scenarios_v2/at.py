"""finetune/scenarios_v2/at.py — corpus v2 scenarios for 'at'."""
from finetune.scenarios_v2 import V2

SCENARIOS_V2 = [
    V2(id="at-atq-v2-0001", tool="at", operation="atq",
       complexity="single",
       user_input="Show me what's sitting in queue c on the at spool right now.",
       args={"operation": "atq", "queue": "c"},
       answer="Queue c: 2 jobs pending.\n14  Fri Sep 18 23:00:00 2026 c root\n17  Sat Sep 19 03:30:00 2026 c root"),
    V2(id="at-atq-v2-0002", tool="at", operation="atq",
       complexity="diagnostic",
       user_input="Ticket says the nightly report never emailed anyone last night. Can you check whether the job actually got scheduled in the first place?",
       args={"operation": "atq"},
       answer="atq: 1 job in spool.\n22  Thu Sep 11 23:59:00 2026 a root\nJob 22 is still pending, never fired at the expected time."),
    V2(id="at-atrm-v2-0001", tool="at", operation="atrm",
       complexity="single",
       user_input="Pull job 19 out of the at spool, it's no longer needed.",
       args={"operation": "atrm", "job_id": "19"},
       answer="atrm: job 19 removed from spool."),
    V2(id="at-atrm-v2-0002", tool="at", operation="atrm",
       complexity="multi",
       user_input="Cancel job 8 in the at spool and then confirm the queue is clear.",
       args={"operation": "atrm", "job_id": "8"},
       answer="atrm: job 8 removed from spool."),
]

from finetune.scenarios_v2 import check_module; check_module("at", SCENARIOS_V2)
