"""Initialize a fresh Logseq graph for BFF and populate it from the SQLite DB.

Runs at the end of onboarding (/onboard Phase 7) to bootstrap the BFF graph.
Idempotent — safe to run multiple times.

Usage:
    python -m best_foot_forward.utils.init_graph [--graph-root PATH]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import markdown_graph_kit as mgk
from best_foot_forward.db import DATA_DIR


def _graph_root_default() -> Path:
    """Default BFF graph location."""
    return Path(DATA_DIR) / "BestFootForward"


def _register_with_config_json(graph_root: Path, graph_name: str = "bff") -> tuple[str, str]:
    """Auto-register the graph with markdown-graph-mcp's config.json.

    If config.json exists, adds an entry like {"bff": "/abs/path"} if the name
    is not taken by a different path. If the name is taken, picks an alternate
    (bff-2, bff-3, etc.). If config.json is missing or unwritable, skips — that's
    OK when running on a machine without an MCP server, but the skip must be
    reported honestly rather than as a success: the caller used to print
    "✓ registered" regardless of which of these paths ran, indistinguishable from
    an actual registration.

    Returns (name, status), status one of: "registered", "already", "renamed",
    "skipped:no-config", "skipped:unreadable-config", "skipped:unwritable-config".
    """
    config_path = Path.home() / ".config" / "logseq_mcp" / "config.json"
    if not config_path.exists():
        return graph_name, "skipped:no-config"

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError):
        return graph_name, "skipped:unreadable-config"

    graphs = config.setdefault("graphs", {})
    graph_abs = str(graph_root.resolve())

    # If the name is already taken by the same path, nothing to do
    if graphs.get(graph_name) == graph_abs:
        return graph_name, "already"

    # If the name is taken by a *different* path, find an alternate
    if graph_name in graphs:
        i = 2
        while f"{graph_name}-{i}" in graphs:
            i += 1
        final_name = f"{graph_name}-{i}"
    else:
        final_name = graph_name

    graphs[final_name] = graph_abs

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except OSError:
        return final_name, "skipped:unwritable-config"

    return final_name, ("renamed" if final_name != graph_name else "registered")


def main(graph_root: str | Path | None = None) -> Path:
    """Initialize a fresh BFF graph and populate it from the DB.

    Args:
        graph_root: Path to create/initialize. Defaults to data/BestFootForward/.

    Returns:
        Path to the initialized graph root.
    """
    if graph_root is None:
        graph_root = _graph_root_default()
    graph_root = Path(graph_root).resolve()

    # Step 1: Bootstrap the graph (create directories, config.edn)
    mgk.bootstrap_graph(graph_root)
    print(f"✓ bootstrapped graph at {graph_root}")

    # Step 2: Populate pages from SQLite (company/application/prep/notes)
    # Importing here to avoid circular dependency on mgk path setup
    from best_foot_forward.utils import export_graph

    db_path = Path(DATA_DIR) / "best_foot_forward.db"
    export_graph.export(str(db_path), str(graph_root))
    print(f"✓ exported {db_path} to pages/")

    # Step 3: Generate Home.md + Leads Dashboard
    from best_foot_forward.utils import generate_home

    generate_home.main()
    print(f"✓ generated Home.md + Leads Dashboard")

    # Step 4: Auto-register with config.json (if present)
    registered_name, status = _register_with_config_json(graph_root)
    config_path_str = "~/.config/logseq_mcp/config.json"
    if status == "registered":
        print(f"✓ registered as '{registered_name}' in markdown-graph-mcp config.json")
    elif status == "already":
        print(f"✓ already registered as '{registered_name}' in markdown-graph-mcp config.json")
    elif status == "renamed":
        print(f"✓ registered as '{registered_name}' in markdown-graph-mcp config.json "
              f"('{graph_root.name}' was taken by a different path)")
    elif status == "skipped:no-config":
        print(f"– skipped markdown-graph-mcp registration: no config at {config_path_str}.")
        print(f"  The graph itself is fine. MCP tools just won't find it by name until you add:")
        print(f'    {{"graphs": {{"bff": "{graph_root}"}}}}')
    elif status == "skipped:unreadable-config":
        print(f"– skipped markdown-graph-mcp registration: {config_path_str} exists but could not be parsed.")
    elif status == "skipped:unwritable-config":
        print(f"– skipped markdown-graph-mcp registration: could not write {config_path_str} (permissions?).")

    return graph_root


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Initialize a fresh BFF Logseq graph.")
    ap.add_argument("--graph-root", default=None, help="Graph root path (default: data/BestFootForward).")
    args = ap.parse_args()
    main(args.graph_root)
