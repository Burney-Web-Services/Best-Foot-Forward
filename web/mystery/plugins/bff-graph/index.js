// BFF Graph — explainer page for the Logseq markdown graph that is master for
// BFF's pipeline layer (see docs/adr/0008-logseq-graph-pipeline-master.md).
//
// The point of this plugin is orientation, not data entry: someone looking at
// the read-only pipeline tables in this web UI should be able to find out where
// those rows actually come from, and how to open the real thing.
//
// The single endpoint counts pages straight off the filesystem rather than out
// of SQLite, deliberately — the whole claim of the page is "the graph is the
// master," so the numbers it quotes should come from the graph.

import { Router } from 'express';
import { readdir } from 'fs/promises';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { requireLogin } from '../../mystery6-src/middleware/auth.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Plugins are loaded through a symlink at mystery6's src/plugins/<key>, but
// relative paths resolve against the plugin's *real* location inside the BFF
// repo — same reason the mystery6-src import above works. See project memory.
// __dirname here is .../BFF_ROOT/web/mystery/plugins/bff-graph -- four levels
// up, not three (confirmed 2026-08-16: the previous three-level version
// resolved to .../BFF_ROOT/web, so GRAPH_ROOT pointed at a path that never
// existed and this endpoint always reported available:false/total:0 for
// every user, not just under a BFF_DATA_DIR override).
const BFF_ROOT = resolve(__dirname, '..', '..', '..', '..');
// BFF_DATA_DIR (same override db.py and web/mystery/setup.mjs honor) lets
// /web point its graph explainer at a throwaway/demo dataset too, e.g. the
// UAT fixture, instead of always the real data/BestFootForward.
const GRAPH_ROOT = resolve(process.env.BFF_DATA_DIR || resolve(BFF_ROOT, 'data'), 'BestFootForward');
const PAGES_DIR = resolve(GRAPH_ROOT, 'pages');

// Logseq encodes namespace separators as `___` in filenames (the
// :file/name-format :triple-lowbar convention this graph depends on), so a
// page's kind is readable from its filename alone.
function classify(filename) {
  const stem = filename.replace(/\.md$/i, '');
  if (!stem.includes('___')) return 'entity';
  const leaf = stem.split('___').pop();
  if (leaf === 'Application') return 'application';
  if (leaf === 'Prep') return 'prep';
  if (leaf === 'Notes') return 'notes';
  return 'other';
}

const router = Router();

router.get('/stats', requireLogin, async (req, res, next) => {
  try {
    let files;
    try {
      files = await readdir(PAGES_DIR);
    } catch (err) {
      if (err.code === 'ENOENT') {
        res.json({
          status: 'ok',
          message: 'ok',
          data: { available: false, graphPath: GRAPH_ROOT, counts: null, total: 0 },
        });
        return;
      }
      throw err;
    }

    const counts = { entity: 0, application: 0, prep: 0, notes: 0, other: 0 };
    let total = 0;
    for (const f of files) {
      if (!f.toLowerCase().endsWith('.md')) continue;
      counts[classify(f)] += 1;
      total += 1;
    }

    res.json({
      status: 'ok',
      message: 'ok',
      data: { available: true, graphPath: GRAPH_ROOT, counts, total },
    });
  } catch (err) {
    next(err);
  }
});

export default router;
