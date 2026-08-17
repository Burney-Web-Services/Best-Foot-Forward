#!/usr/bin/env python3
"""Mint a bearer token for the BFF MCP HTTP/SSE server.

Tokens authorize remote (LAN) callers of the BFF MCP server started with
`mcp_server.py --serve`. They live in data/mcp_tokens.json (gitignored) with:

    { "tokens": { "<secret>": { "name": "alex", "source": "alex" } } }

Re-running with an existing --name rotates that holder's token (the old secret
is removed). The new secret is printed once — copy it into the client's
`Authorization: Bearer <token>` header; it is not recoverable afterward.

Usage:
    python3 scripts/mint_token.py --name alex
    python3 scripts/mint_token.py --name laptop --source secondary
"""

import argparse
import json
import secrets
import sys
from pathlib import Path

TOKENS_PATH = Path(__file__).resolve().parent.parent / "data" / "mcp_tokens.json"


def _load():
    if not TOKENS_PATH.exists():
        return {"tokens": {}}
    try:
        data = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        sys.exit(f"Cannot read {TOKENS_PATH}: {e}")
    if not isinstance(data, dict) or not isinstance(data.get("tokens"), dict):
        sys.exit(f"Malformed token file (expected top-level 'tokens' object): {TOKENS_PATH}")
    return data


def main():
    ap = argparse.ArgumentParser(description="Mint a BFF MCP bearer token.")
    ap.add_argument("--name", required=True, help="Human label for the token holder (e.g. alex).")
    ap.add_argument("--source", help="Lead source tag recorded for this caller (default: --name).")
    args = ap.parse_args()

    source = args.source or args.name
    data = _load()
    tokens = data["tokens"]

    # Rotate: drop any existing secret for the same holder before adding the new one.
    rotated = [tok for tok, entry in tokens.items() if (entry or {}).get("name") == args.name]
    for tok in rotated:
        del tokens[tok]

    secret = secrets.token_urlsafe(32)
    tokens[secret] = {"name": args.name, "source": source}

    TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKENS_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    TOKENS_PATH.chmod(0o600)

    action = "Rotated" if rotated else "Minted"
    print(f"{action} token for {args.name!r} (source={source!r}).")
    print(f"  Registry: {TOKENS_PATH}")
    print()
    print(f"  {secret}")
    print()
    print("  Register on the client machine with:")
    print(f'    claude mcp add --transport http -s user bff-primary \\')
    print(f'      http://192.168.0.222:8765/mcp \\')
    print(f'      --header "Authorization: Bearer {secret}"')


if __name__ == "__main__":
    main()
