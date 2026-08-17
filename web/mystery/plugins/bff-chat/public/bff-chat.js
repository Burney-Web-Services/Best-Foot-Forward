import { api } from '/js/api.js';
import { renderNav } from '/js/components/nav.js';
import { flash } from '/js/components/flash.js';

const AVATAR_STATES = ['idle', 'speaking', 'listening', 'thinking'];

const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
function escapeHtml(str) {
  return str.replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]);
}

// Safe markdown. Escapes first so the reply's own text can never inject markup,
// then applies a small subset: fenced + inline code, bold, italic, bullet lists,
// and autolinked URLs. Code spans are stashed before the other rules run so their
// contents are never reprocessed.
function renderReplyHtml(text) {
  const codeStore = [];
  const stash = (html) => {
    const token = '\u0000CODE' + codeStore.length + '\u0000';
    codeStore.push(html);
    return token;
  };

  let html = escapeHtml(text);

  // Fenced ```code``` (optional language tag) — before inline code.
  html = html.replace(/```(?:[^\n`]*)\n?([\s\S]*?)```/g, (_, code) =>
    stash(`<pre class="bff-chat-code"><code>${code.replace(/\n$/, '')}</code></pre>`));
  // Inline `code`.
  html = html.replace(/`([^`\n]+)`/g, (_, code) =>
    stash(`<code class="bff-chat-code-inline">${code}</code>`));

  // Autolink bare http(s) URLs.
  html = html.replace(/https?:\/\/[^\s<]+/g, (url) =>
    `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`);

  // Bold before italic so ** isn't mistaken for *.
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(?!\s)([^*\n]+?)\*/g, '<em>$1</em>');

  // Consecutive `- ` / `* ` lines become a <ul>.
  html = html.replace(/(?:^|\n)((?:[-*] .*(?:\n|$))+)/g, (_, block) => {
    const items = block.trim().split('\n')
      .map((line) => `<li>${line.replace(/^[-*] /, '')}</li>`).join('');
    return `\n<ul class="bff-chat-list">${items}</ul>`;
  });

  // Restore stashed code spans.
  return html.replace(/\u0000CODE(\d+)\u0000/g, (_, i) => codeStore[Number(i)]);
}

export async function render(root) {
  renderNav(root, { title: 'BFF Chat' });

  root.innerHTML = `
    <div class="page-wrap">
      <div id="flash-area"></div>
      <style>
        /* ---- Avatar (ported from web/avatar-demo/avatar-demo.html) ---- */
        .avatar {
          --avatar-size: clamp(120px, 18vw, 180px);
          --avatar-teal: #2dd4bf;
          --avatar-teal-soft: rgba(45, 212, 191, 0.35);
          position: relative;
          width: var(--avatar-size);
          height: var(--avatar-size);
          margin: 0 0 1rem;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .avatar__glow {
          position: absolute;
          inset: -10%;
          border-radius: 50%;
          background: radial-gradient(circle, var(--avatar-teal-soft) 0%, transparent 70%);
          z-index: 0;
          animation: bff-avatar-glow-idle 4s ease-in-out infinite;
        }
        .avatar[data-state="speaking"] .avatar__glow { animation-name: bff-avatar-glow-speaking; animation-duration: 0.9s; }
        .avatar[data-state="listening"] .avatar__glow { animation-name: bff-avatar-glow-listening; animation-duration: 3s; }
        .avatar[data-state="thinking"] .avatar__glow { animation-name: bff-avatar-glow-thinking; animation-duration: 2.5s; }
        @keyframes bff-avatar-glow-idle { 0%, 100% { opacity: 0.35; transform: scale(1); } 50% { opacity: 0.55; transform: scale(1.04); } }
        @keyframes bff-avatar-glow-speaking { 0%, 100% { opacity: 0.5; transform: scale(1); } 50% { opacity: 0.85; transform: scale(1.08); } }
        @keyframes bff-avatar-glow-listening { 0%, 100% { opacity: 0.45; transform: scale(1); } 50% { opacity: 0.6; transform: scale(1.02); } }
        @keyframes bff-avatar-glow-thinking { 0%, 100% { opacity: 0.4; transform: scale(1); } 50% { opacity: 0.65; transform: scale(1.05); } }
        .avatar__float {
          position: relative;
          width: 75%;
          height: 75%;
          z-index: 2;
          display: flex;
          align-items: center;
          justify-content: center;
          animation: bff-avatar-bob 3.2s ease-in-out infinite;
        }
        @keyframes bff-avatar-bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
        .avatar__img { width: 100%; height: 100%; object-fit: contain; display: block; }
        .avatar__ring { position: absolute; inset: 6%; z-index: 1; opacity: 0; transition: opacity 0.15s ease; pointer-events: none; }
        .avatar[data-state="listening"] .avatar__ring { opacity: 1; }
        .avatar__ring span { position: absolute; inset: 0; border-radius: 50%; border: 2px solid var(--avatar-teal); animation: bff-ring-pulse 1.8s ease-out infinite; }
        .avatar__ring span:nth-child(1) { animation-delay: 0s; }
        .avatar__ring span:nth-child(2) { animation-delay: 0.6s; }
        .avatar__ring span:nth-child(3) { animation-delay: 1.2s; }
        @keyframes bff-ring-pulse { 0% { transform: scale(0.9); opacity: 0.7; } 100% { transform: scale(1.45); opacity: 0; } }
        .avatar__bars {
          position: absolute; bottom: -4%; left: 50%; transform: translateX(-50%);
          display: flex; align-items: flex-end; gap: 4px;
          height: calc(var(--avatar-size) * 0.09); z-index: 3;
          opacity: 0; transition: opacity 0.15s ease; pointer-events: none;
        }
        .avatar[data-state="speaking"] .avatar__bars { opacity: 1; }
        .avatar__bars span { width: 4px; height: 100%; border-radius: 2px; background: var(--avatar-teal); transform-origin: bottom center; animation: bff-bar-bounce 0.6s ease-in-out infinite; }
        .avatar__bars span:nth-child(1) { animation-delay: 0s; animation-duration: 0.5s; }
        .avatar__bars span:nth-child(2) { animation-delay: 0.12s; animation-duration: 0.65s; }
        .avatar__bars span:nth-child(3) { animation-delay: 0.24s; animation-duration: 0.55s; }
        .avatar__bars span:nth-child(4) { animation-delay: 0.12s; animation-duration: 0.7s; }
        .avatar__bars span:nth-child(5) { animation-delay: 0s; animation-duration: 0.6s; }
        @keyframes bff-bar-bounce { 0%, 100% { transform: scaleY(0.25); } 50% { transform: scaleY(1); } }
        .avatar__spinner { position: absolute; inset: 0; z-index: 1; opacity: 0; transition: opacity 0.15s ease; pointer-events: none; animation: bff-spinner-rotate 1.8s linear infinite; }
        .avatar[data-state="thinking"] .avatar__spinner { opacity: 1; }
        .avatar__spinner span { position: absolute; top: 50%; left: 50%; width: 8px; height: 8px; border-radius: 50%; background: var(--avatar-teal); margin: -4px 0 0 -4px; }
        .avatar__spinner span:nth-child(1) { transform: rotate(0deg) translateX(calc(var(--avatar-size) * 0.46)); }
        .avatar__spinner span:nth-child(2) { transform: rotate(120deg) translateX(calc(var(--avatar-size) * 0.46)); }
        .avatar__spinner span:nth-child(3) { transform: rotate(240deg) translateX(calc(var(--avatar-size) * 0.46)); }
        @keyframes bff-spinner-rotate { to { transform: rotate(360deg); } }
        @media (prefers-reduced-motion: reduce) {
          .avatar__glow, .avatar__float, .avatar__ring span, .avatar__bars span, .avatar__spinner {
            animation-duration: 0.001ms !important;
            animation-iteration-count: 1 !important;
          }
        }

        /* ---- Chat layout ---- */
        .bff-chat-layout { max-width: 40rem; margin: 0 auto; display: flex; flex-direction: column; }
        .bff-chat-avatar-col { display: flex; flex-direction: column; align-items: center; }
        .bff-chat-main { display: flex; flex-direction: column; min-width: 0; }
        /* Thought bubble above the avatar — shown only while thinking. */
        .bff-chat-bubble {
          align-self: center; max-width: 12rem; margin-bottom: 0.5rem;
          padding: 0.35rem 0.7rem; border: 1px solid var(--m-border); border-radius: 0.9rem;
          background: var(--m-surface); color: var(--m-text);
          font-size: 0.8rem; text-align: center; position: relative;
        }
        .bff-chat-bubble::after {
          content: ''; position: absolute; left: 50%; bottom: -6px; transform: translateX(-50%);
          border: 6px solid transparent; border-top-color: var(--m-border); border-bottom: 0;
        }
        .bff-chat-bubble[hidden] { display: none; }
        /* Widescreen: avatar to the left, chat gets the vertical room. */
        @media (min-width: 48rem) {
          .bff-chat-layout { max-width: 56rem; flex-direction: row; align-items: flex-start; gap: 1.25rem; }
          .bff-chat-avatar-col { flex: 0 0 auto; width: clamp(120px, 18vw, 180px); }
          .bff-chat-main { flex: 1; }
          .bff-chat-main .bff-chat-log { max-height: 70vh; }
        }
        .bff-chat-log {
          overflow-y: auto; max-height: 50vh; min-height: 12rem;
          border: 1px solid var(--m-border); border-radius: 0.5rem;
          background: var(--m-surface); padding: 0.75rem; margin-bottom: 0.75rem;
          display: flex; flex-direction: column; gap: 0.5rem;
        }
        .bff-chat-msg .bff-chat-code {
          margin: 0.35rem 0; padding: 0.5rem 0.65rem; border-radius: 0.4rem;
          background: var(--m-row-alt); border: 1px solid var(--m-border);
          font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
          font-size: 0.85em; white-space: pre; overflow-x: auto;
        }
        .bff-chat-msg .bff-chat-code code { font: inherit; background: none; padding: 0; }
        .bff-chat-msg .bff-chat-code-inline {
          padding: 0.05rem 0.3rem; border-radius: 0.3rem; background: var(--m-row-alt);
          font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.85em;
        }
        .bff-chat-msg .bff-chat-list { margin: 0.25rem 0; padding-left: 1.25rem; }
        #bff-chat-send:disabled { opacity: 0.55; cursor: not-allowed; }
        .bff-chat-msg { padding: 0.5rem 0.75rem; border-radius: 0.5rem; max-width: 85%; white-space: pre-wrap; word-break: break-word; }
        .bff-chat-msg-user { align-self: flex-end; background: var(--m-accent); color: var(--m-accent-text); }
        .bff-chat-msg-bff { align-self: flex-start; background: var(--m-row-alt); color: var(--m-text); }
        .bff-chat-msg-error { align-self: center; color: var(--m-danger, #dc2626); font-size: 0.85rem; }
        .bff-chat-form { display: flex; gap: 0.5rem; align-items: flex-end; }
        .bff-chat-input-wrap { position: relative; flex: 1; }
        .bff-chat-form textarea { width: 100%; resize: none; transition: height 0.15s ease; }
        .bff-chat-expand {
          position: absolute; top: 0.3rem; right: 0.3rem; z-index: 1;
          width: 1.5rem; height: 1.5rem; padding: 0; line-height: 1;
          border-radius: 0.3rem; border: 1px solid var(--m-border);
          background: var(--m-surface); color: var(--m-text);
          font-size: 0.85rem; opacity: 0.7; cursor: pointer;
        }
        .bff-chat-expand:hover { opacity: 1; background: var(--m-row-hover); }
        .bff-chat-layout.input-expanded .bff-chat-form textarea { height: 33vh; }
        .bff-chat-layout.input-expanded .bff-chat-log { max-height: 30vh; transition: max-height 0.15s ease; }
        @media (prefers-reduced-motion: reduce) {
          .bff-chat-form textarea, .bff-chat-log { transition: none; }
        }
        .bff-chat-mic {
          flex: 0 0 auto; width: 2.5rem; height: 2.5rem; padding: 0;
          border-radius: 50%; border: 1px solid var(--m-border);
          background: var(--m-surface); font-size: 1.1rem; line-height: 1; cursor: pointer;
        }
        .bff-chat-mic:hover { background: var(--m-row-hover); }
        .bff-chat-mic.active {
          background: var(--m-danger, #dc2626); border-color: var(--m-danger, #dc2626);
          animation: bff-mic-pulse 0.9s ease-in-out infinite alternate;
        }
        .bff-chat-mic[hidden] { display: none; }
        @keyframes bff-mic-pulse { from { opacity: 1; } to { opacity: 0.55; } }
      </style>
      <div class="bff-chat-layout">
        <div class="bff-chat-avatar-col">
          <div class="bff-chat-bubble" id="bff-chat-bubble" role="status" aria-live="polite" hidden>still thinking…</div>
          <div class="avatar" data-state="idle" id="bff-chat-avatar" aria-hidden="true">
            <div class="avatar__glow"></div>
            <div class="avatar__ring"><span></span><span></span><span></span></div>
            <div class="avatar__spinner"><span></span><span></span><span></span></div>
            <div class="avatar__float">
              <img class="avatar__img" src="/images/bff-logo.png" alt="BFF">
            </div>
            <div class="avatar__bars"><span></span><span></span><span></span><span></span><span></span></div>
          </div>
        </div>
        <div class="bff-chat-main">
          <div class="bff-chat-log" id="bff-chat-log" aria-live="polite"></div>
          <form class="bff-chat-form" id="bff-chat-form">
            <button type="button" class="bff-chat-mic" id="bff-chat-mic" title="Speak your message">🎤</button>
            <div class="bff-chat-input-wrap">
              <textarea id="bff-chat-input" class="form-input" rows="3" placeholder="Ask BFF…"></textarea>
              <button type="button" class="bff-chat-expand" id="bff-chat-expand" title="Expand input" aria-pressed="false">⤢</button>
            </div>
            <button type="submit" class="btn btn-primary" id="bff-chat-send">Send</button>
          </form>
        </div>
      </div>
    </div>
  `;

  const layoutEl = root.querySelector('.bff-chat-layout');
  const avatarEl = root.querySelector('#bff-chat-avatar');
  const bubbleEl = root.querySelector('#bff-chat-bubble');
  const logEl = root.querySelector('#bff-chat-log');
  const formEl = root.querySelector('#bff-chat-form');
  const inputEl = root.querySelector('#bff-chat-input');
  const sendBtn = root.querySelector('#bff-chat-send');
  const micBtn = root.querySelector('#bff-chat-mic');
  const expandBtn = root.querySelector('#bff-chat-expand');

  const HISTORY_KEY = 'bff-chat-history-v1';
  const HISTORY_MAX_AGE_MS = 24 * 60 * 60 * 1000;

  // ---- Expand toggle (persisted per-browser) ----
  const EXPANDED_KEY = 'bff-chat-input-expanded';

  function setExpanded(expanded) {
    layoutEl.classList.toggle('input-expanded', expanded);
    expandBtn.textContent = expanded ? '⤡' : '⤢';
    expandBtn.title = expanded ? 'Collapse input' : 'Expand input';
    expandBtn.setAttribute('aria-pressed', String(expanded));
    try {
      localStorage.setItem(EXPANDED_KEY, String(expanded));
    } catch { /* storage unavailable — expansion just won't persist */ }
  }

  let storedExpanded = false;
  try {
    storedExpanded = localStorage.getItem(EXPANDED_KEY) === 'true';
  } catch { /* storage unavailable — default to collapsed */ }
  setExpanded(storedExpanded);

  expandBtn.addEventListener('click', () => {
    setExpanded(!layoutEl.classList.contains('input-expanded'));
  });

  // ---- Chat history recall ----
  // The AI's actual memory lives server-side in the persistent `claude -p --resume`
  // session (see index.js) — it never forgets. This just restores what was on
  // screen so a reload doesn't look like the conversation reset.
  {
    const history = pruneHistory(loadHistory());
    history.forEach((entry) => appendMessage(entry.kind, entry.text, false));
    saveHistory(history);
  }

  function setState(next) {
    if (!AVATAR_STATES.includes(next)) return;
    avatarEl.dataset.state = next;
  }

  // ---- "Still thinking…" thought bubble ----
  // The reply is a single long await (up to 5 min) with no progress signal, so
  // pulse a bubble (5s on / 5s off) with a live elapsed timer while it's in flight.
  let thinkingTimer = null;
  let thinkingStart = 0;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function bubbleText() {
    const secs = Math.floor((Date.now() - thinkingStart) / 1000);
    const mins = Math.floor(secs / 60);
    const label = mins > 0 ? `${mins}m ${secs % 60}s` : `${secs}s`;
    return `still thinking… (${label})`;
  }

  function startThinking() {
    thinkingStart = Date.now();
    bubbleEl.textContent = bubbleText();
    bubbleEl.hidden = false;
    if (thinkingTimer) clearInterval(thinkingTimer);
    let visible = true;
    thinkingTimer = setInterval(() => {
      if (!reduceMotion) {
        // Blink: refresh the timer text while visible, blank out while hidden.
        visible = !visible;
        bubbleEl.hidden = !visible;
      }
      if (!bubbleEl.hidden) bubbleEl.textContent = bubbleText();
    }, reduceMotion ? 1000 : 5000);
  }

  function stopThinking() {
    if (thinkingTimer) clearInterval(thinkingTimer);
    thinkingTimer = null;
    bubbleEl.hidden = true;
    bubbleEl.textContent = 'still thinking…';
  }

  // ---- Speech-to-text (dictate into the textarea, not auto-send) ----
  const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  let recognition = null;
  let recognizing = false;
  let baseValueBeforeListening = '';
  let finalTranscript = '';

  if (!SpeechRecognitionCtor) {
    micBtn.hidden = true;
  } else {
    micBtn.addEventListener('click', () => {
      recognizing ? stopListening() : startListening();
    });
  }

  function startListening() {
    baseValueBeforeListening = inputEl.value ? `${inputEl.value.trim()} ` : '';
    finalTranscript = '';

    recognition = new SpeechRecognitionCtor();
    recognition.lang = 'en-US';
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalTranscript += `${result[0].transcript} `;
        } else {
          interim += result[0].transcript;
        }
      }
      inputEl.value = baseValueBeforeListening + finalTranscript + interim;
    };

    recognition.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        flash(root.querySelector('.page-wrap') ?? root, 'Microphone access denied — allow it in your browser and try again.');
      }
      stopListening();
    };

    recognition.onend = () => {
      recognizing = false;
      micBtn.classList.remove('active');
      if (avatarEl.dataset.state === 'listening') setState('idle');
    };

    recognizing = true;
    micBtn.classList.add('active');
    setState('listening');
    try {
      recognition.start();
    } catch {
      recognizing = false;
      micBtn.classList.remove('active');
      setState('idle');
    }
  }

  function stopListening() {
    recognizing = false;
    micBtn.classList.remove('active');
    if (avatarEl.dataset.state === 'listening') setState('idle');
    if (recognition) {
      try { recognition.stop(); } catch { /* already stopped */ }
    }
  }

  function loadHistory() {
    try {
      const raw = localStorage.getItem(HISTORY_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function saveHistory(entries) {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(entries));
    } catch { /* storage unavailable — history just won't persist */ }
  }

  function pruneHistory(entries) {
    const cutoff = Date.now() - HISTORY_MAX_AGE_MS;
    return entries.filter((entry) => entry && entry.ts > cutoff);
  }

  function appendMessage(kind, text, persist = true) {
    const div = document.createElement('div');
    div.className = `bff-chat-msg bff-chat-msg-${kind}`;
    if (kind === 'bff') {
      div.innerHTML = renderReplyHtml(text);
    } else {
      div.textContent = text;
    }
    logEl.appendChild(div);
    logEl.scrollTop = logEl.scrollHeight;

    if (persist && (kind === 'user' || kind === 'bff')) {
      const entries = pruneHistory(loadHistory());
      entries.push({ kind, text, ts: Date.now() });
      saveHistory(entries);
    }
  }

  // While a reply is in flight the user may keep typing their next message,
  // but can't send it until the reply comes back.
  let inFlight = false;

  async function sendMessage() {
    if (inFlight) return;
    if (recognizing) stopListening();

    const text = inputEl.value.trim();
    if (!text) return;

    appendMessage('user', text);
    inputEl.value = '';
    inFlight = true;
    sendBtn.disabled = true;
    setState('thinking');
    startThinking();

    try {
      const res = await api.post('/plugins/bff-chat/message', { message: text });

      if (res.status !== 'ok') {
        setState('idle');
        flash(root.querySelector('.page-wrap') ?? root, res.message);
      } else {
        setState('speaking');
        appendMessage('bff', res.data.reply);
        setTimeout(() => setState('idle'), 1200);
      }
    } finally {
      stopThinking();
      inFlight = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  formEl.addEventListener('submit', (e) => {
    e.preventDefault();
    sendMessage();
  });

  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      // Enter never inserts a newline here; it sends — unless a reply is in flight,
      // in which case it's a no-op so the draft stays put until Send re-enables.
      e.preventDefault();
      if (!inFlight) sendMessage();
    }
  });

  inputEl.focus();
}
