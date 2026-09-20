#!/usr/bin/env bash
# pod_guard.sh — hard spend cap for a rented RunPod pod, enforced ON the pod.
#
#   pod_guard.sh <budget_usd> <hourly_usd> -- <command ...>
#
# 1. Computes the deadline = budget / hourly price and starts a detached timer
#    that STOPS this pod when the deadline passes, whatever else is happening.
# 2. Runs <command>.  When it exits, for ANY reason (success, crash, OOM), the
#    pod is stopped immediately so an idle pod never bills.
#
# "stop" releases the GPU (billing ends) but keeps the volume, so results stay
# recoverable.  Uses runpodctl (shipped in RunPod images, authorised by the
# pod-scoped RUNPOD_API_KEY) and falls back to the REST API.
#
# History: two runs on 2026-09-14 and 2026-09-20 billed ~$80 of idle time
# because nothing stopped the pods after the job ended.  Never launch a pod
# job without this wrapper.
set -uo pipefail
BUDGET="${1:?budget usd}"; HOURLY="${2:?hourly usd}"; shift 2
[ "${1:-}" = "--" ] && shift
# SSH sessions on RunPod images do not inherit the container's environment; the
# pod id and the pod-scoped API key live in PID 1's environment.
if [ -z "${RUNPOD_POD_ID:-}" ] && [ -r /proc/1/environ ]; then
  while IFS= read -r -d '' kv; do
    case "$kv" in RUNPOD_POD_ID=*|RUNPOD_API_KEY=*) export "$kv" ;; esac
  done < /proc/1/environ
fi
POD="${RUNPOD_POD_ID:?not on a RunPod pod (RUNPOD_POD_ID missing)}"
# runpodctl is unauthorised until configured with the pod-scoped key; verified
# 2026-09-20 that `runpodctl stop pod <self>` succeeds after this.
runpodctl config --apiKey "${RUNPOD_API_KEY:-}" > /dev/null 2>&1 || true
SECS=$(python3 -c "print(int(float('$BUDGET')/float('$HOURLY')*3600))")
LOG=/workspace/pod_guard.log

stop_pod() {
  echo "[$(date '+%F %T')] stopping pod $POD: $1" >> "$LOG"
  runpodctl stop pod "$POD" >> "$LOG" 2>&1 && return 0
  curl -s -X POST "https://rest.runpod.io/v1/pods/$POD/stop" \
       -H "Authorization: Bearer ${RUNPOD_API_KEY:-}" >> "$LOG" 2>&1
}

echo "[$(date '+%F %T')] guard armed: budget \$$BUDGET at \$$HOURLY/h = ${SECS}s" >> "$LOG"
( sleep "$SECS"; stop_pod "budget of \$$BUDGET reached" ) > /dev/null 2>&1 &
disown

"$@"
RC=$?
echo "[$(date '+%F %T')] command exited $RC" >> "$LOG"
stop_pod "job finished (exit $RC)"
exit $RC
