import { Router } from 'express';
import { execFile } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { requireLogin } from '../../mystery6-src/middleware/auth.js';

const router = Router();

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STATE_FILE = path.join(__dirname, '.chat-state.json');
const BFF_REPO_ROOT = path.resolve(__dirname, '../../../..');
const CLAUDE_BIN = process.env.BFF_CHAT_CLAUDE_BIN || 'claude';
// Heavier workflows (evaluate-job: reads bullets/skills/memory files, scores, writes DB)
// routinely run past two minutes — 100s was too tight and silently killed real replies.
const TIMEOUT_MS = 300_000;
const COMPACT_EVERY_N_TURNS = 20;

// Single shared conversation for the whole plugin (not per browser tab) — see plan.
// Self-healing: if this file is missing/corrupt, the next message just starts fresh.
async function readState() {
  try {
    const raw = await readFile(STATE_FILE, 'utf8');
    return JSON.parse(raw);
  } catch {
    return { sessionId: null, turnCount: 0 };
  }
}

async function writeState(state) {
  await writeFile(STATE_FILE, JSON.stringify(state, null, 2));
}

function runClaude(args) {
  return new Promise((resolve, reject) => {
    const child = execFile(
      CLAUDE_BIN,
      args,
      {
        cwd: BFF_REPO_ROOT,
        timeout: TIMEOUT_MS,
        maxBuffer: 10 * 1024 * 1024,
        // Lets CLAUDE.md's "Execution context awareness" section tell this session
        // it's headless — no TTY to approve a permission prompt, so non-allow-listed
        // actions hang until TIMEOUT_MS instead of erroring cleanly.
        env: { ...process.env, BFF_CHAT_HEADLESS: '1' },
      },
      (err, stdout, stderr) => {
        if (err) {
          err.stderr = stderr;
          return reject(err);
        }
        resolve(stdout);
      }
    );
    // Without this, claude -p sees an open (never-written) stdin pipe and burns
    // ~3s per call waiting to see if input is coming before proceeding.
    child.stdin.end();
  });
}

// Requests must not interleave against the same session transcript (e.g. two
// browser tabs firing at once) — serialize them through a single in-process chain.
let chain = Promise.resolve();
function enqueue(fn) {
  const result = chain.then(fn, fn);
  chain = result.catch(() => {});
  return result;
}

router.post('/message', requireLogin, (req, res) => {
  const message = String(req.body?.message ?? '').trim();
  if (!message) {
    return res.json({ status: 'error', message: 'Message is required.', data: null });
  }

  enqueue(async () => {
    try {
      const state = await readState();

      const args = ['-p', message, '--output-format', 'json'];
      if (state.sessionId) args.push('--resume', state.sessionId);

      let stdout;
      try {
        stdout = await runClaude(args);
      } catch (err) {
        const timedOut = err.killed && err.signal === 'SIGTERM';
        console.error('bff-chat: claude -p failed:', err.message, (err.stderr || '').slice(0, 500));
        return res.json({
          status: 'error',
          message: timedOut ? 'BFF took too long to respond.' : 'BFF hit an error — check server logs.',
          data: null,
        });
      }

      let parsed;
      try {
        parsed = JSON.parse(stdout);
      } catch {
        console.error('bff-chat: could not parse claude output:', stdout.slice(0, 500));
        return res.json({ status: 'error', message: 'Could not parse BFF response.', data: null });
      }

      if (parsed.is_error) {
        return res.json({ status: 'error', message: parsed.result || 'BFF returned an error.', data: null });
      }

      const nextState = { sessionId: parsed.session_id, turnCount: state.turnCount + 1 };
      await writeState(nextState);

      res.json({ status: 'ok', message: 'ok', data: { reply: parsed.result } });

      if (nextState.turnCount % COMPACT_EVERY_N_TURNS === 0) {
        enqueue(() =>
          runClaude(['-p', '/compact', '--output-format', 'json', '--resume', nextState.sessionId])
            .then(() => console.log(`bff-chat: compacted session at turn ${nextState.turnCount}`))
            .catch((err) => console.error('bff-chat: compaction failed:', err.message))
        );
      }
    } catch (err) {
      console.error('bff-chat: unexpected error:', err.message);
      if (!res.headersSent) {
        res.json({ status: 'error', message: 'BFF hit an unexpected error — check server logs.', data: null });
      }
    }
  });
});

export default router;
