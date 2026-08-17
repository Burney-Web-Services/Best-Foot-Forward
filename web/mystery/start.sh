#!/usr/bin/env bash
# Launches the local mystery6 web UI ("BFF-Terminal") for browsing BFF's live
# database. Safe to run repeatedly — a no-op if an instance is already up on
# the target port. Mirrors stop.sh's structure: everything the /web command
# needs lives in one script so it collapses to a single permission prompt
# instead of one per step. See .claude/commands/web.md for the full workflow.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${1:-3071}"
PIDFILE="$HERE/server.pid"
APP_DIR="$HERE/app"

# 1. Already running?
if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE")"
  if kill -0 "$PID" 2>/dev/null && curl -sf "http://localhost:$PORT/api/auth/branding" >/dev/null 2>&1; then
    echo "ALREADY_RUNNING http://localhost:$PORT"
    exit 0
  fi
  rm -f "$PIDFILE"   # stale — process died or port doesn't match
fi

# Something else already listening on $PORT that isn't ours — don't guess,
# don't kill it, surface the conflict instead.
if curl -sf "http://localhost:$PORT/api/auth/branding" >/dev/null 2>&1; then
  echo "PORT_CONFLICT $PORT"
  exit 1
fi

# 2. Dedicated clone — never touch Paul's personal mystery6 checkout.
if [ ! -d "$APP_DIR/.git" ]; then
  rm -rf "$APP_DIR"
  git clone https://github.com/Burney-Web-Services/Mystery-Database-Administration.git "$APP_DIR"
fi

# 3. Dependencies
if [ ! -d "$APP_DIR/node_modules" ]; then
  (cd "$APP_DIR" && npm install)
fi

# 4. Wire node_modules + plugins
"$HERE/link.sh"

# 5. Configure against BFF's live database (idempotent)
node "$HERE/setup.mjs" "$APP_DIR" "$PORT"

# 6. Start, detached — absolute path, no cd, so $! stays accurate.
nohup node "$APP_DIR/src/server.js" > "$HERE/server.log" 2>&1 &
echo $! > "$PIDFILE"
disown

# 7. Confirm it's up
for _ in $(seq 1 10); do
  curl -sf "http://localhost:$PORT/api/auth/branding" >/dev/null 2>&1 && break
  sleep 0.5
done

if ! curl -sf "http://localhost:$PORT/api/auth/branding" >/dev/null 2>&1; then
  echo "FAILED_TO_START"
  tail -n 40 "$HERE/server.log"
  exit 1
fi

NO_AUTH="0"
grep -q "NO_AUTH=true" "$APP_DIR/.env" 2>/dev/null && NO_AUTH="1"
echo "UP http://localhost:$PORT NO_AUTH=$NO_AUTH"
