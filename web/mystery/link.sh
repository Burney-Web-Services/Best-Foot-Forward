#!/usr/bin/env bash
# Wires this directory's BFF-owned integration code into the dedicated
# mystery6 clone at web/mystery/app/ (created by the /web command).
#
# BFF owns this code (setup script, and future report/interviewer plugins);
# mystery6 stays a generic engine that only knows about it via symlinks.
# Run after cloning/installing app/, and any time you add a new plugin
# under plugins/ — /web does both automatically.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MYSTERY_ROOT="$HERE/app"

if [ ! -d "$MYSTERY_ROOT/node_modules" ]; then
  echo "error: $MYSTERY_ROOT/node_modules not found — run npm install in web/mystery/app first" >&2
  exit 1
fi

# Lets setup.mjs (which lives here in BFF's repo, not inside the clone)
# resolve the clone's npm dependencies (better-sqlite3, bcryptjs, ...).
ln -sfn "$MYSTERY_ROOT/node_modules" "$HERE/node_modules"
echo "linked node_modules -> $MYSTERY_ROOT/node_modules"

# Lets plugins import mystery6 core modules (middleware, db adapters, ...)
# via a relative path. Node resolves a plugin's relative imports against its
# *real* filesystem location (this repo), not the src/plugins/<name> symlink
# it's loaded through, so `../../middleware/auth.js` from a plugin can never
# reach the clone's src/ on its own — this symlink bridges that gap. Plugins
# import through it as e.g. `../../mystery6-src/middleware/auth.js`.
ln -sfn "$MYSTERY_ROOT/src" "$HERE/mystery6-src"
echo "linked mystery6-src -> $MYSTERY_ROOT/src"

# Each subdirectory of plugins/ is a mystery6 plugin (exports an Express
# Router as its index.js default export). Symlink it into the clone's own
# src/plugins/ so the plugin loader picks it up, and give it its own
# node_modules symlink too — Node resolves bare imports against a plugin's
# *real* path, not the symlink's apparent location, so without this a
# plugin's `import express` fails even though the file loads fine.
if [ -d "$HERE/plugins" ]; then
  for plugin in "$HERE"/plugins/*/; do
    [ -d "$plugin" ] || continue
    name="$(basename "${plugin%/}")"
    # Skip our own symlinks (e.g. a stale <name>node_modules sibling from a
    # pre-fix run) — only real plugin directories have an index.js.
    [ -f "${plugin%/}/index.js" ] || continue
    ln -sfn "${plugin%/}" "$MYSTERY_ROOT/src/plugins/$name"
    ln -sfn "$MYSTERY_ROOT/node_modules" "${plugin%/}/node_modules"
    echo "linked plugin: $name"
  done
else
  echo "no plugins/ directory yet — nothing to link"
fi
