#!/usr/bin/env bash
# Re-runs the Haiku-vs-Sonnet flattery-bias comparison documented in
# .claude/commands/evaluate-job.md's Workflow step 3 -- not to re-decide it
# (Sonnet already won and is the shipped default), but to give that decision
# durable, re-runnable regression coverage instead of a one-time manual test
# whose only record was a session transcript.
#
# Runs /evaluate-job against the same deliberately-gapped posting twice, once
# per model (via the BFF_EVAL_MODEL override evaluate-job.md's subagent-spawn
# step honors), each in its own fully isolated throwaway BFF_DATA_DIR seeded
# from examples/leia-organa. Scans each reply for a subset of the banned
# compensating-clause phrases evaluate-job.md's own "Gap reporting rules"
# section lists, and checks the JD's three genuine, unambiguous gaps (GCP,
# ArgoCD, Snowflake -- none in the Leia persona's skills) actually get named.
#
# The scan is a lead, not a verdict -- see CHECKLIST.md. Bare conjunctions
# ("but", "though", "however") are deliberately excluded: they're common
# enough in ordinary prose that grepping them produces mostly noise. Only the
# multi-word phrases specific enough to be low-noise are checked here; read
# the full replies for the rest.
#
# Real API cost, ~2-5 min total for both calls. Not run in CI.
#
# Usage:
#   tests/uat/compare_eval_models.sh [output-dir]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${1:-/tmp/uat-model-compare-$(date +%s)}"
mkdir -p "$OUT_DIR"

GAP_POSTING="$REPO_ROOT/tests/uat/fixtures/gap_posting.txt"
CLAUDE_BIN="${BFF_UAT_CLAUDE_BIN:-claude}"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python3"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"

GAP_FIXTURE_COMPANY="Coruscant Systems Group"
GAP_TERMS_EXPECTED=(GCP ArgoCD Snowflake)

# Low-noise subset of evaluate-job.md's "Banned move" list -- shared with
# run_uat.sh via banned_phrases.txt so the two scripts can't drift apart.
mapfile -t BANNED_PHRASES < "$REPO_ROOT/tests/uat/banned_phrases.txt"

run_one() {
  local model="$1"
  local data_dir="$OUT_DIR/uat-$model"
  mkdir -p "$data_dir"

  echo "[compare_eval_models] seeding $data_dir ..." >&2
  BFF_DATA_DIR="$data_dir" "$PYTHON_BIN" -m best_foot_forward.utils.load_example_data \
    "$REPO_ROOT/examples/leia-organa" >/dev/null

  echo "[compare_eval_models] running /evaluate-job with BFF_EVAL_MODEL=$model ..." >&2
  # --model sonnet on the outer session: only BFF_EVAL_MODEL should vary
  # between the two runs below, so the outer orchestrator's own model is
  # pinned rather than left at the (Opus) default, which would otherwise
  # dominate cost/behavior differences unrelated to the comparison itself.
  (cd "$REPO_ROOT" && \
   BFF_DATA_DIR="$data_dir" BFF_UAT=1 BFF_CHAT_HEADLESS=1 BFF_EVAL_MODEL="$model" \
   "$CLAUDE_BIN" -p "/evaluate-job $GAP_POSTING" --model sonnet --output-format json < /dev/null) \
    > "$OUT_DIR/raw-$model.json"

  local is_error="false"
  if ! jq -e '.is_error == false' "$OUT_DIR/raw-$model.json" >/dev/null 2>&1; then
    is_error="true"
  fi

  jq -r '.result // empty' "$OUT_DIR/raw-$model.json" > "$OUT_DIR/reply-$model.txt"
  local reply_text
  reply_text="$(cat "$OUT_DIR/reply-$model.txt")"

  local score
  score="$(sqlite3 "$data_dir/best_foot_forward.db" \
    "SELECT score FROM jds WHERE company = '$GAP_FIXTURE_COMPANY'" 2>/dev/null || echo "")"
  local cost_usd duration_ms num_turns
  cost_usd="$(jq -r '.total_cost_usd // empty' "$OUT_DIR/raw-$model.json")"
  duration_ms="$(jq -r '.duration_ms // empty' "$OUT_DIR/raw-$model.json")"
  num_turns="$(jq -r '.num_turns // empty' "$OUT_DIR/raw-$model.json")"

  local banned_hits=() gaps_named=()
  for phrase in "${BANNED_PHRASES[@]}"; do
    grep -qi -- "$phrase" <<< "$reply_text" && banned_hits+=("$phrase")
  done
  for term in "${GAP_TERMS_EXPECTED[@]}"; do
    grep -qi -- "$term" <<< "$reply_text" && gaps_named+=("$term")
  done
  local IFS=,
  local banned_csv="${banned_hits[*]:-}"
  local gaps_named_csv="${gaps_named[*]:-}"
  local gaps_expected_csv="${GAP_TERMS_EXPECTED[*]}"
  unset IFS

  local record_args=(record --harness compare_eval_models --fixture "$GAP_FIXTURE_COMPANY"
    --outer-model sonnet --eval-model "$model"
    --banned-phrase-hits "$banned_csv" --gaps-expected "$gaps_expected_csv" --gaps-named "$gaps_named_csv")
  [ -n "$score" ] && record_args+=(--score "$score")
  [ -n "$cost_usd" ] && record_args+=(--cost-usd "$cost_usd")
  [ -n "$duration_ms" ] && record_args+=(--duration-ms "$duration_ms")
  [ -n "$num_turns" ] && record_args+=(--num-turns "$num_turns")
  [ "$is_error" = "true" ] && record_args+=(--is-error)
  "$PYTHON_BIN" "$REPO_ROOT/tests/uat/uat_history.py" "${record_args[@]}"

  if [ "$is_error" = "true" ]; then
    echo "[compare_eval_models] $model run errored -- see $OUT_DIR/raw-$model.json" >&2
    exit 1
  fi
}

run_one haiku
run_one sonnet

echo
echo "=== Banned compensating-clause phrase scan (lead, not verdict) ==="
for model in haiku sonnet; do
  reply_file="$OUT_DIR/reply-$model.txt"
  echo "--- $model ($reply_file) ---"
  hit=0
  for phrase in "${BANNED_PHRASES[@]}"; do
    if grep -qi -- "$phrase" "$reply_file"; then
      echo "  ⚠ contains: \"$phrase\""
      hit=1
    fi
  done
  [ "$hit" = 0 ] && echo "  clean -- no low-noise banned phrases found"
done

echo
echo "=== Named-gap check (${GAP_TERMS_EXPECTED[*]}) ==="
for model in haiku sonnet; do
  reply_file="$OUT_DIR/reply-$model.txt"
  echo "--- $model ---"
  for term in "${GAP_TERMS_EXPECTED[@]}"; do
    if grep -qi -- "$term" "$reply_file"; then
      echo "  ✓ mentions $term"
    else
      echo "  ⚠ does NOT mention $term"
    fi
  done
done

echo
echo "Full replies saved under $OUT_DIR -- read them; the scan above is a lead, not a verdict."
echo "History recorded to tests/uat/uat_history.db -- commit it if this run is worth keeping."
