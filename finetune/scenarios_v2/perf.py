"""finetune/scenarios_v2/perf.py -- corpus v2 scenarios for 'perf'."""
from finetune.scenarios_v2 import V2

SCENARIOS_V2 = [
    V2(
        id='perf-top-v2-0001',
        tool='perf',
        operation='top',
        complexity='single',
        user_input='Show me live CPU hotspots for the next 20 seconds sorted by overhead.',
        args={'operation': 'top', 'duration': 20, 'sort': 'overhead'},
        answer="Samples: 8K of event 'cycles'\n  22.4%  postgres  [.] heap_hot_search_buffer\n  14.1%  nginx     [.] ngx_http_process_request\n   9.7%  [kernel]  [k] copy_user_enhanced_fast_string",
    ),
    V2(
        id='perf-top-v2-0002',
        tool='perf',
        operation='top',
        complexity='diagnostic',
        user_input="One core has been pegged at 100 percent for the last ten minutes and I can't tell why — take a quick look at what's hot right now.",
        args={'operation': 'top', 'duration': 15},
        answer="Samples: 6K of event 'cycles'\n  31.8%  java      [.] G1ParScanThreadState::copy_to_survivor_space\n  12.2%  [kernel]  [k] finish_task_switch\n   7.4%  memcached [.] process_command",
    ),
    V2(
        id='perf-record-v2-0003',
        tool='perf',
        operation='record',
        complexity='single',
        user_input='Record perf data for the nginx worker process for 30 seconds and save it to /var/tmp/nginx.perf.data.',
        args={'operation': 'record', 'output': '/var/tmp/nginx.perf.data', 'duration': 30},
        answer='[ perf record: Woken up 41 times to write data ]\n[ perf record: Captured and wrote 9.842 MB /var/tmp/nginx.perf.data (23841 samples) ]',
    ),
    V2(
        id='perf-record-v2-0004',
        tool='perf',
        operation='record',
        complexity='multi',
        user_input="Record perf data for PID 4821 with cache-misses events for a minute, then I'll run perf report on it.",
        args={'operation': 'record', 'pid': 4821, 'events': 'cache-misses', 'duration': 60},
        answer='[ perf record: Woken up 88 times to write data ]\n[ perf record: Captured and wrote 21.117 MB perf.data (54210 samples) ]',
    ),
    V2(
        id='perf-record-v2-0005',
        tool='perf',
        operation='record',
        complexity='diagnostic',
        user_input="The backup job's I/O wait is way higher than usual tonight — capture perf events while it runs so we can see the bottleneck.",
        args={'operation': 'record', 'command': '/usr/local/bin/nightly_backup.sh', 'events': 'cycles,iowait', 'duration': 120},
        answer='[ perf record: Woken up 210 times to write data ]\n[ perf record: Captured and wrote 48.902 MB perf.data (118732 samples) ]',
    ),
    V2(
        id='perf-record-v2-0006',
        tool='perf',
        operation='record',
        complexity='single',
        user_input="Capture a 45-second recording of 'openssl speed rsa2048' and store it as rsa-bench.data.",
        args={'operation': 'record', 'command': 'openssl speed rsa2048', 'output': 'rsa-bench.data', 'duration': 45},
        answer='[ perf record: Woken up 63 times to write data ]\n[ perf record: Captured and wrote 14.203 MB rsa-bench.data (36502 samples) ]',
    ),
]

from finetune.scenarios_v2 import check_module; check_module('perf', SCENARIOS_V2)
