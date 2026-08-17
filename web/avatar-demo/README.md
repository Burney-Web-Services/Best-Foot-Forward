# BFF Avatar — State Demo

Standalone, self-contained preview of an animated avatar built around the static
`bff-logo-transparent.png` robot mascot. No build step, no framework, no server
required — just open `avatar-demo.html` directly in a browser.

This is exploratory/preparatory work: there's no chat or interview UI in the
BFF Mystery web frontend yet, so this demo exists to design and tune the
avatar's states in isolation before it has a real integration point.

## States

- **idle** — gentle vertical bob + soft breathing glow (always running underneath the other states)
- **speaking** — pulsing equalizer bars below the avatar, brighter/faster glow
- **listening** — expanding sonar rings around the avatar, steady glow
- **thinking** — rotating dots around the avatar, distinct pulse rate

All effects are layered *around* the untouched source PNG (glow halo, rings, bars, spinner) —
the artwork itself is never modified or overlaid, since it's a single flat image with no
separate mouth/eye layers to animate.

## Try it

Open `avatar-demo.html` in a browser. Click the state buttons, press keys 1–4, or check
"Auto-cycle" to loop through states automatically.

## Status

This design has since shipped: `web/mystery/plugins/bff-chat/` is the live version, with the
avatar CSS/markup ported in and `setState()` wired to real request lifecycle events (`thinking`
while `claude -p` is in flight, `speaking` on reply, `listening` while the mic is active).

This standalone file is kept as a tuning sandbox — no server, no auth, no `claude -p` calls
required, just open it directly in a browser to iterate on animation timing before porting
changes back into the plugin.

## Integration later

`setState(nextState)` in the inline `<script>` is the single point where this would hook into
real events (TTS start/end → speaking, STT active → listening, LLM call in flight → thinking).
