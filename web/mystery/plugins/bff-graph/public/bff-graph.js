import { api } from '/js/api.js';
import { renderNav } from '/js/components/nav.js';

// Drop a PNG at plugins/bff-graph/public/graph-screenshot.png and it appears
// automatically — no code change. Until then the figure hides itself rather
// than showing a broken image.
const SCREENSHOT_SRC = '/plugins/bff-graph/graph-screenshot.png';

const STAT_TILES = [
  { key: 'entity', label: 'Companies' },
  { key: 'application', label: 'Applications' },
  { key: 'prep', label: 'Prep pages' },
  { key: 'notes', label: 'Notes pages' },
];

function escHtml(s) {
  return String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

export async function render(root) {
  renderNav(root, { title: '' });

  root.innerHTML = `
    <div class="page-wrap">
      <style>
        .bff-graph-head { display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem; }
        .bff-graph-head img { width: 72px; height: 72px; object-fit: contain; }
        .bff-graph-head h2 { margin: 0; color: var(--m-heading); }
        .bff-graph-head p { margin: 0.25rem 0 0; color: var(--m-text-muted, inherit); font-size: 0.95rem; }
        .bff-graph-body { max-width: 62rem; }
        .bff-graph-body h3 { color: var(--m-heading); margin: 2rem 0 0.75rem; font-size: 1.05rem; }
        .bff-graph-body p { line-height: 1.6; margin: 0 0 1rem; }
        .bff-graph-lede { font-size: 1.05rem; }

        /* Stat row: counts of one kind of thing, so no colour encoding —
           the numbers wear heading ink and the labels wear muted ink. */
        .bff-graph-stats { display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 1.5rem 0; }
        .bff-graph-stat {
          flex: 1 1 8rem; border: 1px solid var(--m-border); border-radius: 0.375rem;
          padding: 0.85rem 1rem;
        }
        .bff-graph-stat .num {
          display: block; font-size: 1.6rem; font-weight: 700; line-height: 1.1;
          color: var(--m-heading); font-variant-numeric: tabular-nums;
        }
        .bff-graph-stat .lbl { display: block; font-size: 0.8rem; margin-top: 0.2rem; opacity: 0.75; }

        .bff-graph-figure { margin: 1.5rem 0; }
        .bff-graph-figure img {
          max-width: 100%; height: auto; display: block;
          border: 1px solid var(--m-border); border-radius: 0.375rem;
        }
        .bff-graph-figure figcaption { font-size: 0.85rem; opacity: 0.75; margin-top: 0.5rem; }

        .bff-graph-path {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85rem;
          background: var(--m-row-hover); border: 1px solid var(--m-border);
          border-radius: 0.25rem; padding: 0.15rem 0.4rem;
        }
        .bff-graph-links { display: flex; flex-wrap: wrap; gap: 0.6rem; margin-top: 1rem; }
        .bff-graph-links a {
          display: inline-block; padding: 0.55rem 0.9rem; border-radius: 0.375rem;
          border: 1px solid var(--m-border); color: var(--m-link);
          text-decoration: none; font-weight: 600; font-size: 0.9rem;
        }
        .bff-graph-links a:hover { background: var(--m-row-hover); }
      </style>

      <div class="bff-graph-head">
        <img src="/images/bff-logo.png" alt="Best Foot Forward">
        <div>
          <h2>The BFF Graph</h2>
          <p>Where the application narrative actually lives.</p>
        </div>
      </div>

      <div class="bff-graph-body">
        <p class="bff-graph-lede">
          Most of what you see in this web interface — job descriptions, applications,
          contacts, prep — is a <strong>read-only mirror</strong>. The real record is a
          folder of plain Markdown files: one page per company, with a page per role
          underneath it for the application, the interview prep, and the running notes.
          The database you are browsing is rebuilt from those pages.
        </p>

        <div class="bff-graph-stats" id="bff-graph-stats"></div>

        <figure class="bff-graph-figure" id="bff-graph-figure" hidden>
          <img src="${SCREENSHOT_SRC}" alt="A company application page open in Logseq">
          <figcaption>An application page in Logseq — structured properties at the top, free-form narrative below.</figcaption>
        </figure>

        <h3>Why Markdown and not just a database</h3>
        <p>
          A job search has two halves. One half is genuinely relational — the reusable
          library of resume bullets, skills, and stories that gets assembled into a
          tailored document. That belongs in a table, and it stays in one.
        </p>
        <p>
          The other half is narrative: what the company actually does, how the screen went,
          what the hiring manager cared about, what to say differently next time. That is
          writing, not rows. Forcing it into a text column means it can only be reached
          through a query, it is invisible to anything else you keep notes in, and it is
          only as durable as the tool that wrote it.
        </p>
        <p>
          Keeping it as Markdown means it is editable in any text editor, greppable,
          diffable, version-controlled, linked to the rest of your notes, and readable in
          twenty years by something that has never heard of this application.
        </p>

        <h3>Opening it</h3>
        <p>
          The graph is a normal folder — you can open it with anything. It is laid out for
          <strong>Logseq OG</strong>, the file-based edition, which renders the page links,
          the properties, and the namespaces as a browsable graph while leaving the
          Markdown on disk exactly as it is.
        </p>
        <p id="bff-graph-path-line"></p>
        <div class="bff-graph-links">
          <a href="https://github.com/logseq/og" target="_blank" rel="noopener">Get Logseq OG ↗</a>
        </div>
        <p style="margin-top:1rem; font-size:0.9rem; opacity:0.8;">
          Open Logseq OG, choose <em>Add new graph</em>, and point it at the folder above.
          Edits you make there are the source of truth — re-running BFF's reconcile step
          brings them back into the tables on this site.
        </p>
      </div>
    </div>
  `;

  const statsEl = root.querySelector('#bff-graph-stats');
  const pathLineEl = root.querySelector('#bff-graph-path-line');
  const figureEl = root.querySelector('#bff-graph-figure');

  // Only reveal the figure once the image actually loads — keeps the page tidy
  // before a screenshot has been dropped in.
  const img = figureEl.querySelector('img');
  img.addEventListener('load', () => { figureEl.hidden = false; });
  img.addEventListener('error', () => { figureEl.remove(); });

  statsEl.innerHTML = '<p class="text-muted">Loading graph…</p>';

  const res = await api.get('/plugins/bff-graph/stats');
  if (res.status !== 'ok') {
    statsEl.innerHTML = '<p class="text-muted">Could not read the graph directory.</p>';
    return;
  }

  const { available, counts, total, graphPath } = res.data;

  pathLineEl.innerHTML = `On this machine it lives at <span class="bff-graph-path">${escHtml(graphPath)}</span>.`;

  if (!available) {
    statsEl.innerHTML = '<p class="text-muted">No graph found on disk yet.</p>';
    return;
  }

  statsEl.innerHTML = [
    ...STAT_TILES.map(({ key, label }) => `
      <div class="bff-graph-stat">
        <span class="num">${counts[key].toLocaleString()}</span>
        <span class="lbl">${label}</span>
      </div>
    `),
    `<div class="bff-graph-stat">
      <span class="num">${total.toLocaleString()}</span>
      <span class="lbl">Pages total</span>
    </div>`,
  ].join('');
}
