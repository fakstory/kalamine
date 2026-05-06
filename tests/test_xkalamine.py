"""Tests for xkalamine CLI (install/remove commands)."""

import pytest
from click.testing import CliRunner

from kalamine import cli_xkb, xkb_manager
from kalamine.cli_xkb import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_xkb(monkeypatch, tmp_path):
    """Redirect XKB_HOME to a temp dir and force the system XKB_ROOT to be
    non-writable (raises PermissionError on update/list) so install/remove
    attempts fall back to user-space without touching the real developer's
    ~/.config/xkb or system /usr/share/X11/xkb.
    """
    home = tmp_path / "home"
    home.mkdir()
    fake_root = tmp_path / "system_xkb"
    fake_root.mkdir()
    monkeypatch.setattr(xkb_manager, "XKB_HOME", home / ".config" / "xkb")
    monkeypatch.setattr(xkb_manager, "XKB_ROOT", fake_root)

    real_update_rules = xkb_manager.update_rules
    real_list_rules = xkb_manager.list_rules

    def fake_update_rules(xkb_root, kbd_index):
        if xkb_root == fake_root:
            raise PermissionError(13, "Permission denied", str(xkb_root))
        return real_update_rules(xkb_root, kbd_index)

    def fake_list_rules(xkb_root, mask="*"):
        if xkb_root == fake_root:
            raise PermissionError(13, "Permission denied", str(xkb_root))
        return real_list_rules(xkb_root, mask)

    monkeypatch.setattr(xkb_manager, "update_rules", fake_update_rules)
    monkeypatch.setattr(xkb_manager, "list_rules", fake_list_rules)
    return home


@pytest.fixture
def mock_wayland(monkeypatch):
    monkeypatch.setattr(cli_xkb, "WAYLAND", True)
    monkeypatch.setattr(xkb_manager, "WAYLAND", True)


@pytest.fixture
def mock_xorg(monkeypatch):
    monkeypatch.setattr(cli_xkb, "WAYLAND", False)
    monkeypatch.setattr(xkb_manager, "WAYLAND", False)


@pytest.fixture
def non_root(monkeypatch):
    """Force is_root() → False so install falls into the user-space branch."""
    monkeypatch.setattr(cli_xkb, "is_root", lambda: False)


class TestInstallCommand:
    """Tests for xkalamine install command."""

    def test_install_no_args(self, runner, mock_wayland):
        result = runner.invoke(cli, ["install"])
        assert result.exit_code == 0

    def test_install_wayland_user_space(
        self, runner, mock_wayland, non_root, isolated_xkb
    ):
        """install on Wayland without sudo writes layout into user-space XKB."""
        result = runner.invoke(cli, ["install", "-y", "layouts/prog.toml"])
        assert result.exit_code == 0, result.output
        assert "User-space layout installed" in result.output
        # The fix should have actually written files under XKB_HOME.
        xkb_home = xkb_manager.XKB_HOME
        assert xkb_home.exists()
        assert (xkb_home / "rules" / "evdev.xml").exists()
        # No rules/evdev should be created (xkbcommon delegation fix).
        assert not (xkb_home / "rules" / "evdev").exists()
        # A symbols file for the layout should have been written.
        symbols = list((xkb_home / "symbols").iterdir())
        assert symbols, "expected a symbols file to be written"

    def test_install_xorg_no_sudo_message(
        self, runner, mock_xorg, non_root, isolated_xkb
    ):
        """install on Xorg without sudo prints sudo guidance and exits 1.

        Must NOT fall back to user-space.
        """
        result = runner.invoke(cli, ["install", "-y", "layouts/prog.toml"])
        assert result.exit_code == 1
        assert "XOrg" in result.output
        assert "sudo" in result.output
        # No user-space symbols should have been written.
        xkb_home = xkb_manager.XKB_HOME
        if xkb_home.exists():
            symbols_dir = xkb_home / "symbols"
            if symbols_dir.exists():
                assert not list(symbols_dir.iterdir())


class TestRemoveCommand:
    """Tests for xkalamine remove command."""

    def test_remove_wayland_user_space(
        self, runner, mock_wayland, non_root, isolated_xkb
    ):
        result = runner.invoke(cli, ["remove", "fr/prog"])
        assert result.exit_code == 0, result.output

    def test_remove_xorg_no_sudo_message(
        self, runner, mock_xorg, non_root, isolated_xkb
    ):
        result = runner.invoke(cli, ["remove", "fr/prog"])
        assert result.exit_code == 1
        assert "XOrg" in result.output
        assert "sudo" in result.output


class TestListCommand:
    """Tests for xkalamine list command."""

    def test_list_help(self, runner):
        result = runner.invoke(cli, ["list", "--help"])
        assert result.exit_code == 0
        assert "List installed Kalamine layouts" in result.output


class TestIsRoot:
    """Sanity checks for the is_root helper."""

    def test_is_root_returns_bool(self):
        assert isinstance(cli_xkb.is_root(), bool)
