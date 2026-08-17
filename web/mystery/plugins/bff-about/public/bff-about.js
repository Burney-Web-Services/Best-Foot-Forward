import { renderNav } from '/js/components/nav.js';

const SITE_URL = 'https://best-foot-forward.com/';

export async function render(root) {
  renderNav(root, { title: '' });

  root.innerHTML = `
    <div class="page-wrap">
      <style>
        .bff-about { max-width: 44rem; margin: 2rem auto; text-align: center; }
        .bff-about img { width: 120px; height: 120px; object-fit: contain; }
        .bff-about h2 { margin: 1rem 0 0.25rem; color: var(--m-heading); }
        .bff-about .tagline { margin: 0 0 1.5rem; opacity: 0.8; }
        .bff-about p { line-height: 1.6; text-align: left; margin: 0 0 1rem; }
        .bff-about .cta {
          display: inline-block; margin-top: 1rem; padding: 0.7rem 1.4rem;
          border-radius: 0.375rem; border: 1px solid var(--m-accent);
          background: var(--m-accent); color: var(--m-accent-text);
          text-decoration: none; font-weight: 600;
        }
        .bff-about .cta:hover { opacity: 0.9; }
      </style>

      <div class="bff-about">
        <img src="/images/bff-logo.png" alt="Best Foot Forward">
        <h2>Best Foot Forward</h2>
        <p class="tagline">An AI-powered job search agent.</p>

        <p>
          Best Foot Forward keeps track of a job search end to end — evaluating and scoring
          job descriptions, tailoring a resume and cover letter from a reusable library of
          bullets and skills, preparing for screens and interviews, and following what
          happens after you apply.
        </p>
        <p>
          This site is its database view: a browsable window onto the same data the agent
          works with. Most of it is read-only on purpose — the narrative record lives in
          the BFF Graph, and the reusable library is edited here or through the agent.
        </p>

        <a class="cta" href="${SITE_URL}" target="_blank" rel="noopener">Visit best-foot-forward.com ↗</a>
      </div>
    </div>
  `;
}
