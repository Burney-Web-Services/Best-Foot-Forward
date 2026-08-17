#!/usr/bin/env bash
# Tier 1 of the UAT harness (see ~/.claude/plans/i-put-an-example-groovy-zephyr.md
# and examples/leia-organa/README.md). Seeds a throwaway BFF_DATA_DIR from the
# tracked examples/leia-organa fixture, then drives one real headless
# `claude -p` call for /evaluate-job against a deliberately-gapped posting --
# the only tier that exercises .claude/commands/evaluate-job.md end to end,
# not just the Python underneath it.
#
# Real API cost and 1-3 min for the evaluate-job call -- not run in CI. Run
# before a release or after touching .claude/commands/evaluate-job.md,
# save_lead_jd.py, or jd_skills.py.
#
# Usage:
#   BFF_DATA_DIR=/tmp/uat-$(date +%s) tests/uat/run_uat.sh
#   BFF_DATA_DIR=... .venv/bin/python3 -m pytest tests/uat/test_uat_pipeline.py -v
set -euo pipefail

if [ -z "${BFF_DATA_DIR:-}" ]; then
  echo "refusing: BFF_DATA_DIR must be set to an isolated uat-* directory" >&2
  echo "  example: BFF_DATA_DIR=/tmp/uat-\$(date +%s) $0" >&2
  exit 1
fi

BASENAME="$(basename "$BFF_DATA_DIR")"
case "$BASENAME" in
  uat-*) ;;
  *)
    echo "refusing: BFF_DATA_DIR's basename ('$BASENAME') must start with 'uat-'" >&2
    exit 1
    ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REAL_DATA_DIR="$REPO_ROOT/data"
RESOLVED_TARGET_PARENT="$(cd "$(dirname "$BFF_DATA_DIR")" 2>/dev/null && pwd || echo "")"
if [ -n "$RESOLVED_TARGET_PARENT" ] && [ "$RESOLVED_TARGET_PARENT/$(basename "$BFF_DATA_DIR")" = "$REAL_DATA_DIR" ]; then
  echo "refusing: BFF_DATA_DIR resolves to the real repo's data/ directory" >&2
  exit 1
fi

export BFF_DATA_DIR
export BFF_UAT=1
export BFF_CHAT_HEADLESS=1
CLAUDE_BIN="${BFF_UAT_CLAUDE_BIN:-claude}"

# Which agent harness drives the /evaluate-job call.
#
#   claude (default) -- unchanged behavior: `claude -p ... --output-format json`.
#   custom           -- run $BFF_UAT_AGENT_CMD instead, for testing whether a
#                       non-Claude harness (Codex/opencode against a local
#                       Ollama model, say) can drive the workflow at all. The
#                       command receives the prompt on stdin and must print the
#                       agent's final reply text on stdout; this script wraps
#                       that into the same envelope the `claude` path emits, so
#                       every check and history field downstream is identical.
#
# BFF_EVAL_MODEL is deliberately NOT the knob for this: it only reaches the
# scoring subagent evaluate-job.md spawns, which is a Claude Agent() call. A
# local model has to replace the harness, not the subagent.
RUNNER="${BFF_UAT_RUNNER:-claude}"
OUTER_MODEL="${BFF_UAT_OUTER_MODEL:-sonnet}"

case "$RUNNER" in
  claude) ;;
  custom)
    if [ -z "${BFF_UAT_AGENT_CMD:-}" ]; then
      echo "refusing: BFF_UAT_RUNNER=custom requires BFF_UAT_AGENT_CMD" >&2
      exit 1
    fi
    ;;
  *)
    echo "refusing: BFF_UAT_RUNNER must be 'claude' or 'custom' (got '$RUNNER')" >&2
    exit 1
    ;;
esac

# Emits the reply envelope to $2: {is_error, result, total_cost_usd?, duration_ms, num_turns?}
run_agent() {
  local prompt="$1" out="$2"
  case "$RUNNER" in
    claude)
      # --model on the *outer* session too: the default headless top-level
      # model is otherwise Opus, which dominates per-call cost far more than the
      # delegated scoring subagent this harness is actually comparing
      # (BFF_EVAL_MODEL only affects that inner subagent, not this orchestrator).
      (cd "$REPO_ROOT" && "$CLAUDE_BIN" -p "$prompt" --model "$OUTER_MODEL" \
        --output-format json < /dev/null > "$out")
      ;;
    custom)
      local t0 t1 rc reply
      t0="$(date +%s%3N)"
      set +e
      reply="$(cd "$REPO_ROOT" && printf '%s' "$prompt" | eval "$BFF_UAT_AGENT_CMD" 2>/dev/null)"
      rc=$?
      set -e
      t1="$(date +%s%3N)"
      # A local model costs nothing to run, so 0 here is the literal truth
      # rather than a missing value -- and it is the entire point of the test.
      jq -n --arg r "$reply" \
            --argjson d "$((t1 - t0))" \
            --argjson e "$([ "$rc" -eq 0 ] && echo false || echo true)" \
            '{is_error: $e, result: $r, duration_ms: $d, total_cost_usd: 0}' > "$out"
      ;;
  esac
}
PYTHON_BIN="$REPO_ROOT/.venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

mkdir -p "$BFF_DATA_DIR"

echo "[run_uat] seeding $BFF_DATA_DIR from examples/leia-organa ..."
(cd "$REPO_ROOT" && "$PYTHON_BIN" -m best_foot_forward.utils.load_example_data "$REPO_ROOT/examples/leia-organa")

echo "[run_uat] running /evaluate-job against the deliberately-gapped fixture posting ..."
GAP_POSTING="$REPO_ROOT/tests/uat/fixtures/gap_posting.txt"
GAP_FIXTURE_COMPANY="Coruscant Systems Group"
GAP_TERMS_EXPECTED=(GCP ArgoCD Snowflake)
REPLY_FILE="$BFF_DATA_DIR/evaluate_job_reply.json"
# Claude Code resolves /evaluate-job as a slash command. Other harnesses don't:
# Codex discovers .agents/skills/evaluate-job/SKILL.md, which is only a pointer
# to .claude/commands/evaluate-job.md, and invokes it as $evaluate-job or plain
# prose. BFF_UAT_PROMPT lets a custom runner spell the request out explicitly
# rather than depending on that discovery working -- %s is the posting path.
PROMPT_TEMPLATE="${BFF_UAT_PROMPT:-/evaluate-job %s}"
# shellcheck disable=SC2059
run_agent "$(printf "$PROMPT_TEMPLATE" "$GAP_POSTING")" "$REPLY_FILE"

IS_ERROR="true"
if jq -e '.is_error == false' "$REPLY_FILE" >/dev/null 2>&1; then
  IS_ERROR="false"
fi

# Record this run in the tracked history DB regardless of pass/fail -- an
# errored run is itself a data point worth keeping, not just a reason to
# exit before it's logged.
SCORE="$(sqlite3 "$BFF_DATA_DIR/best_foot_forward.db" \
  "SELECT score FROM jds WHERE company = '$GAP_FIXTURE_COMPANY'" 2>/dev/null || echo "")"
COST_USD="$(jq -r '.total_cost_usd // empty' "$REPLY_FILE")"
DURATION_MS="$(jq -r '.duration_ms // empty' "$REPLY_FILE")"
NUM_TURNS="$(jq -r '.num_turns // empty' "$REPLY_FILE")"
REPLY_TEXT="$(jq -r '.result // empty' "$REPLY_FILE")"

BANNED_HITS=()
while IFS= read -r phrase; do
  [ -z "$phrase" ] && continue
  if grep -qi -- "$phrase" <<< "$REPLY_TEXT"; then
    BANNED_HITS+=("$phrase")
  fi
done < "$REPO_ROOT/tests/uat/banned_phrases.txt"

GAPS_NAMED=()
for term in "${GAP_TERMS_EXPECTED[@]}"; do
  grep -qi -- "$term" <<< "$REPLY_TEXT" && GAPS_NAMED+=("$term")
done

join_csv() { local IFS=,; echo "$*"; }
BANNED_CSV="$(join_csv "${BANNED_HITS[@]:-}")"
GAPS_NAMED_CSV="$(join_csv "${GAPS_NAMED[@]:-}")"
GAPS_EXPECTED_CSV="$(join_csv "${GAP_TERMS_EXPECTED[@]}")"

HARNESS_NAME="run_uat"
[ "$RUNNER" = "custom" ] && HARNESS_NAME="run_uat_custom"
RECORD_ARGS=(record --harness "$HARNESS_NAME" --fixture "$GAP_FIXTURE_COMPANY" --outer-model "$OUTER_MODEL"
  --banned-phrase-hits "$BANNED_CSV" --gaps-expected "$GAPS_EXPECTED_CSV" --gaps-named "$GAPS_NAMED_CSV")
[ -n "$SCORE" ] && [ "$SCORE" != "" ] && RECORD_ARGS+=(--score "$SCORE")
[ -n "$COST_USD" ] && RECORD_ARGS+=(--cost-usd "$COST_USD")
[ -n "$DURATION_MS" ] && RECORD_ARGS+=(--duration-ms "$DURATION_MS")
[ -n "$NUM_TURNS" ] && RECORD_ARGS+=(--num-turns "$NUM_TURNS")
[ "$IS_ERROR" = "true" ] && RECORD_ARGS+=(--is-error)

# Smoke-testing the harness itself shouldn't write junk rows into the tracked
# history DB; BFF_UAT_HISTORY_DB redirects them. Unset (the normal case) keeps
# the default tests/uat/uat_history.db.
if [ -n "${BFF_UAT_HISTORY_DB:-}" ]; then
  RECORD_ARGS=(--db-path "$BFF_UAT_HISTORY_DB" "${RECORD_ARGS[@]}")
fi
"$PYTHON_BIN" "$REPO_ROOT/tests/uat/uat_history.py" "${RECORD_ARGS[@]}"

if [ "$IS_ERROR" = "true" ]; then
  echo "[run_uat] evaluate-job call errored -- see $REPLY_FILE" >&2
  exit 1
fi

echo "[run_uat] done. DB at $BFF_DATA_DIR/best_foot_forward.db"
echo "[run_uat] reply saved to $REPLY_FILE"
echo "[run_uat] history recorded to ${BFF_UAT_HISTORY_DB:-tests/uat/uat_history.db} -- commit it if this run is worth keeping"
echo "[run_uat] assert with:"
echo "  BFF_DATA_DIR=$BFF_DATA_DIR $PYTHON_BIN -m pytest tests/uat/test_uat_pipeline.py -v"
