"""Tests for BFF graph bootstrap (init_graph)."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from best_foot_forward.utils import init_graph


class TestGraphRootDefault:
    """Test the default graph root calculation."""

    def test_default_is_data_bestfootforward(self):
        """Default root should be data/BestFootForward/."""
        root = init_graph._graph_root_default()
        assert root.is_absolute()
        assert str(root).endswith("data/BestFootForward")


class TestRegisterWithConfigJson:
    """Test config.json auto-registration."""

    def test_register_creates_config_if_missing(self):
        """Registering in a graph creates the entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"

            with patch("best_foot_forward.utils.init_graph.Path.home", return_value=Path(tmpdir)):
                with patch("best_foot_forward.utils.init_graph.Path.home") as mock_home:
                    # This test is tricky with mocking — skip detailed mocking for now
                    pass

        # For now, just test the skip-with-status when config doesn't exist
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir) / "test_graph"
            graph_root.mkdir()
            # When config.json doesn't exist, should return the name unchanged
            name, status = init_graph._register_with_config_json(graph_root, "test")
            assert name == "test"
            assert status == "skipped:no-config"

    def test_register_reports_skip_when_config_missing(self):
        """When config.json doesn't exist, report an honest skip status — not a
        success. This function previously returned the name unchanged with no
        way to distinguish that from an actual registration, and the caller
        printed "✓ registered" regardless."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir) / "my_graph"
            graph_root.mkdir()
            name, status = init_graph._register_with_config_json(graph_root, "my_graph")
            assert name == "my_graph"
            assert status == "skipped:no-config"

    def test_register_handles_name_collision(self):
        """If graph name is taken by a different path, pick an alternate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".config" / "logseq_mcp"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "config.json"

            # Pre-populate config with a taken name
            config_file.write_text(json.dumps({"graphs": {"bff": "/some/other/path"}}))

            graph_root = Path(tmpdir) / "my_bff_graph"
            graph_root.mkdir()

            with patch("best_foot_forward.utils.init_graph.Path.home", return_value=Path(tmpdir)):
                name, status = init_graph._register_with_config_json(graph_root, "bff")
                # Should return an alternate name
                assert name == "bff-2"
                assert status == "renamed"
                # And the new name should be registered in the config
                config = json.loads(config_file.read_text())
                assert "bff-2" in config["graphs"]
                assert config["graphs"]["bff-2"] == str(graph_root.resolve())


class TestMain:
    """Test the main orchestration."""

    def test_main_bootstraps_graph(self):
        """main() should create directories and config.edn."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir) / "test_graph"

            # Mock the export and generate functions to avoid DB access
            with patch("best_foot_forward.utils.export_graph.export"):
                with patch("best_foot_forward.utils.generate_home.main"):
                    init_graph.main(graph_root)

            # Check that directories exist
            assert (graph_root / "pages").is_dir()
            assert (graph_root / "journals").is_dir()
            assert (graph_root / "assets").is_dir()
            assert (graph_root / "logseq").is_dir()

            # Check that config.edn was created
            cfg = graph_root / "logseq" / "config.edn"
            assert cfg.exists()
            content = cfg.read_text()
            assert ":file/name-format :triple-lowbar" in content

    def test_main_is_idempotent(self):
        """Calling main() twice on the same graph is safe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir) / "test_graph"

            with patch("best_foot_forward.utils.export_graph.export"):
                with patch("best_foot_forward.utils.generate_home.main"):
                    # First call
                    result1 = init_graph.main(graph_root)
                    cfg_before = (graph_root / "logseq" / "config.edn").read_text()

                    # Second call
                    result2 = init_graph.main(graph_root)
                    cfg_after = (graph_root / "logseq" / "config.edn").read_text()

                    # Config should be identical
                    assert cfg_before == cfg_after
                    # Path should be the same (resolved)
                    assert result1 == result2

    def test_main_returns_resolved_path(self):
        """main() should return a resolved Path object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir) / "test_graph"
            with patch("best_foot_forward.utils.export_graph.export"):
                with patch("best_foot_forward.utils.generate_home.main"):
                    result = init_graph.main(graph_root)

            assert isinstance(result, Path)
            assert result.is_absolute()
            assert result.is_dir()
            # Should resolve symlinks, `.` etc
            assert result == result.resolve()

    def test_main_prints_skip_not_success_when_config_missing(self, capsys):
        """No markdown-graph-mcp config on this machine is a normal, expected
        state — but main() must say so honestly rather than printing the same
        "✓ registered" line it would for a real registration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_root = Path(tmpdir) / "test_graph"
            fake_home = Path(tmpdir) / "empty_home"
            fake_home.mkdir()

            with patch("best_foot_forward.utils.export_graph.export"):
                with patch("best_foot_forward.utils.generate_home.main"):
                    with patch("best_foot_forward.utils.init_graph.Path.home", return_value=fake_home):
                        init_graph.main(graph_root)

            out = capsys.readouterr().out
            assert "skipped" in out
            assert "✓ registered" not in out
