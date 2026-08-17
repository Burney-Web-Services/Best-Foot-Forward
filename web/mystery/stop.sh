#!/usr/bin/env bash
# Stops the local mystery6 web UI server started by the /web command, if one
# is running. Safe to run repeatedly, including when nothing is up.
#
# Manual only: ./web/mystery/stop.sh. Only ever acts on the PID recorded in
# its own server.pid — deliberately does NOT fall back to hunting for "any"
# mystery6 server process by command line, since multiple instances can be
# running on different ports at once (e.g. for testing) and this must never
# guess at killing one it didn't start.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$HERE/server.pid"

PID=""
if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE")"
fi

if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
  kill "$PID" 2>/dev/null
  for _ in $(seq 1 10); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.3
  done
  kill -0 "$PID" 2>/dev/null && kill -9 "$PID" 2>/dev/null
fi

rm -f "$PIDFILE"
exit 0
