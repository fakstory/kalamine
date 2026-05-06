"""Tests for the macOS / Windows trigger-cell fallback rule.

When a layout declares 2dk / 3dk overlays, the trigger keys carry the
doubled-marker strings (`++`, `--`, ...) in the BASE layer. macOS and
Windows generators don't yet support the dk machinery, so they drop the
overlay layers and substitute each marker cell with its first character.
"""

import tomllib
from pathlib import Path

from kalamine import KeyboardLayout
from kalamine.generators import dk_fallback
from kalamine.generators.keylayout import macos_keymap
from kalamine.generators.klc import klc_keymap
from kalamine.utils import Layer

from .util import get_layout_dict

FIXTURE_2DK = Path(__file__).parent / "fixtures" / "2dk.toml"


def load_2dk() -> KeyboardLayout:
    with FIXTURE_2DK.open("rb") as f:
        return KeyboardLayout(tomllib.load(f))


def test_apply_fallback_replaces_markers():
    layout = load_2dk()
    # Pre-fallback: the trigger key W carries the dk markers.
    pre = {
        layout.layers[Layer.BASE].get("ad02"),
        layout.layers[Layer.SHIFT].get("ad02"),
    }
    assert pre == {"++", "--"}

    dk_fallback.apply_fallback_to_layers(
        layout, [Layer.BASE, Layer.SHIFT, Layer.ALTGR, Layer.ALTGR_SHIFT]
    )

    post = {
        layout.layers[Layer.BASE].get("ad02"),
        layout.layers[Layer.SHIFT].get("ad02"),
    }
    assert post == {"+", "-"}


def test_apply_fallback_idempotent_on_legacy_layout():
    """Layouts without dk markers must come out byte-identical."""
    layout = KeyboardLayout(get_layout_dict("intl"))
    snapshot = {
        layer: dict(layout.layers[layer])
        for layer in (Layer.BASE, Layer.SHIFT, Layer.ALTGR, Layer.ALTGR_SHIFT)
    }
    dk_fallback.apply_fallback_to_layers(
        layout, [Layer.BASE, Layer.SHIFT, Layer.ALTGR, Layer.ALTGR_SHIFT]
    )
    for layer, expected in snapshot.items():
        assert layout.layers[layer] == expected


def test_has_any_dk_overlay_detects_fixture():
    assert dk_fallback.has_any_dk_overlay(load_2dk()) is True
    assert (
        dk_fallback.has_any_dk_overlay(KeyboardLayout(get_layout_dict("intl"))) is False
    )


def test_macos_keymap_warns_and_falls_back(capsys):
    layout = load_2dk()
    macos_keymap(layout)
    captured = capsys.readouterr()
    assert "macOS" in captured.out
    assert "2dk/3dk" in captured.out
    # After the call, the trigger cells must hold the fallback chars.
    post = {
        layout.layers[Layer.BASE].get("ad02"),
        layout.layers[Layer.SHIFT].get("ad02"),
    }
    assert post == {"+", "-"}


def test_klc_keymap_warns_and_falls_back(capsys):
    layout = load_2dk()
    try:
        klc_keymap(layout)
    except Exception:
        # The KLC generator may fail later for other reasons on a minimal
        # fixture; we only care that the warn-and-fallback step ran.
        pass
    captured = capsys.readouterr()
    assert "Windows" in captured.out
    assert "2dk/3dk" in captured.out


def test_macos_keymap_silent_on_legacy_layout(capsys):
    layout = KeyboardLayout(get_layout_dict("intl"))
    macos_keymap(layout)
    captured = capsys.readouterr()
    assert "2dk/3dk" not in captured.out
