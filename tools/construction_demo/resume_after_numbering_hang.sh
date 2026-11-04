#!/usr/bin/env bash
# Recover a V3 run stuck in the original per-account rename phase.
# Never stops or restarts any Docker container, never touches original ERPNext.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="erpnext-clean-backend-1"
LOCK="/root/erpnext-clean/.complete-seeder.lock"
EXPECTED="/home/frappe/frappe-bench/env/bin/python /tmp/erpnext_clean_multicompany_v2.py --phase all"

test -f "$HERE/run_from_git.sh" || { echo "STOP: run_from_git.sh missing"; exit 1; }
test "$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$BACKEND")" = "erpnext-clean" || {
    echo "STOP: unexpected Docker project"; exit 1;
}
if ! command -v flock >/dev/null; then
    echo "STOP: flock missing"; exit 1;
fi

mapfile -t pids < <(docker top "$BACKEND" -eo pid,args | awk 'NR>1 && /\/tmp\/erpnext_clean_multicompany_v2.py --phase all[[:space:]]*$/ {print $1}')
if [ "${#pids[@]}" -gt 1 ]; then
    echo "STOP: multiple matching seeder processes. Investigate before changing anything."
    printf '%s\n' "${pids[@]}"
    exit 1
fi

if [ "${#pids[@]}" -eq 1 ]; then
    pid="${pids[0]}"
    test -r "/proc/$pid/cmdline" || { echo "STOP: target process changed"; exit 1; }
    cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
    if [ "${cmd% }" != "$EXPECTED" ]; then
        echo "STOP: unexpected PID command line: $cmd"
        exit 1
    fi
    echo "Interrupting ONLY demo seeder host PID $pid (SIGINT; no Docker restart)"
    kill -INT "$pid"
    for i in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
    done
fi

# Abort rather than launching a second concurrent seeder.
if docker top "$BACKEND" -eo pid,args | grep -E '[/]tmp/erpnext_clean_multicompany_v2.py --phase all' >/dev/null; then
    echo "STOP: old seeder is still active. Do not start another one."
    exit 1
fi
if ! flock -n "$LOCK" -c true; then
    echo "STOP: original runner still holds its lock. Run this recovery command again only after it exits."
    exit 1
fi

cd "$HERE"
python3 verify_kit_static.py
echo "Old seeder is inactive. Resuming clean site with corrected code."
exec bash run_from_git.sh
