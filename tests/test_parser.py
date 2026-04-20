import json
from pathlib import Path

import pytest

from kalamine import KeyboardLayout
from kalamine.cli import build_all
from kalamine.layout import load_layout as resolve_layout

from .util import get_layout_dict


def load_layout(filename: str, angle_mod: bool = False) -> KeyboardLayout:
    return KeyboardLayout(get_layout_dict(filename), angle_mod)


def test_ansi():
    layout = load_layout("ansi")
    assert layout.layers[0]["ad01"] == "q"
    assert layout.layers[1]["ad01"] == "Q"
    assert layout.layers[0]["tlde"] == "`"
    assert layout.layers[1]["tlde"] == "~"
    assert not layout.has_altgr
    assert not layout.has_1dk
    assert "**" not in layout.dead_keys

    # ensure angle mod is NOT applied
    layout = load_layout("ansi", angle_mod=True)
    assert layout.layers[0]["ab01"] == "z"
    assert layout.layers[1]["ab01"] == "Z"


def test_prog():  # AltGr + dead keys
    layout = load_layout("prog")
    assert layout.layers[0]["ad01"] == "q"
    assert layout.layers[1]["ad01"] == "Q"
    assert layout.layers[0]["tlde"] == "`"
    assert layout.layers[1]["tlde"] == "~"
    assert layout.layers[4]["tlde"] == "*`"
    assert layout.layers[5]["tlde"] == "*~"
    assert layout.has_altgr
    assert not layout.has_1dk
    assert "**" not in layout.dead_keys
    assert len(layout.dead_keys["*`"]) == 18
    assert len(layout.dead_keys["*~"]) == 21


def test_intl():  # 1dk + dead keys
    layout = load_layout("intl")
    assert layout.layers[0]["ad01"] == "q"
    assert layout.layers[1]["ad01"] == "Q"
    assert layout.layers[0]["tlde"] == "*`"
    assert layout.layers[1]["tlde"] == "*~"
    assert not layout.has_altgr
    assert layout.has_1dk
    assert "**" in layout.dead_keys

    assert len(layout.dead_keys) == 5
    assert "**" in layout.dead_keys
    assert "*`" in layout.dead_keys
    assert "*^" in layout.dead_keys
    assert "*¨" in layout.dead_keys
    assert "*~" in layout.dead_keys
    assert len(layout.dead_keys["**"]) == 15
    assert len(layout.dead_keys["*`"]) == 18
    assert len(layout.dead_keys["*^"]) == 43
    assert len(layout.dead_keys["*¨"]) == 21
    assert len(layout.dead_keys["*~"]) == 21

    # ensure the 1dk parser does not accumulate values from a previous run
    layout = load_layout("intl")
    assert len(layout.dead_keys["*`"]) == 18
    assert len(layout.dead_keys["*~"]) == 21

    assert len(layout.dead_keys) == 5
    assert "**" in layout.dead_keys
    assert "*`" in layout.dead_keys
    assert "*^" in layout.dead_keys
    assert "*¨" in layout.dead_keys
    assert "*~" in layout.dead_keys
    assert len(layout.dead_keys["**"]) == 15
    assert len(layout.dead_keys["*`"]) == 18
    assert len(layout.dead_keys["*^"]) == 43
    assert len(layout.dead_keys["*¨"]) == 21
    assert len(layout.dead_keys["*~"]) == 21

    # ensure angle mod is working correctly
    layout = load_layout("intl", angle_mod=True)
    assert layout.layers[0]["lsgt"] == "z"
    assert layout.layers[1]["lsgt"] == "Z"
    assert layout.layers[0]["ab01"] == "x"
    assert layout.layers[1]["ab01"] == "X"


FIXTURES = Path(__file__).parent / "extended-diff"

EXTENDED_DIFF_CASES = [
    pytest.param(
        FIXTURES / "base" / "Bépo.toml",
        FIXTURES / "extended" / "bepo_extended.toml",
        {
            (0, "tlde"): "=",
            (0, "ae02"): "<",
            (0, "ae03"): ">",
            (0, "ae11"): "$",
            (0, "ad11"): "w",
            (1, "ad11"): "W",
            (0, "ad12"): "z",
            (1, "ad12"): "Z",
            (4, "ae02"): "«",
            (4, "ae03"): "»",
        },
        [(0, "ae01"), (1, "ae01"), (0, "ac01"), (1, "ac01")],
        {"name": "bepo-extended", "variant": "bepo-extended"},
        id="bepo",
    ),
    pytest.param(
        FIXTURES / "base" / "Bépolar.toml",
        FIXTURES / "extended" / "bepolar_extended.toml",
        {
            (0, "tlde"): "=",
            (1, "tlde"): "#",
            (1, "ae02"): "<",
            (1, "ae03"): "<",   # the fixture really has `<` at ae03 shift
            (0, "ae11"): "$",
            (0, "ad11"): "w",
            (1, "ad11"): "W",
            (0, "ad12"): "z",
            (1, "ad12"): "Z",
            (4, "ae02"): "«",
            (4, "ae03"): "»",
        },
        [(0, "ac01"), (1, "ac01"), (0, "ac02"), (1, "ac02")],
        {"name": "bepolar-extended", "variant": "bepolar-extended"},
        id="bepolar",
    ),
]


@pytest.mark.parametrize(
    "parent_path, child_path, overrides, untouched, expected_meta",
    EXTENDED_DIFF_CASES,
)
def test_extends_diff(parent_path, child_path, overrides, untouched, expected_meta):
    """base_diff / altgr_diff overlay on parent."""
    parent = KeyboardLayout(resolve_layout(parent_path))
    child = KeyboardLayout(resolve_layout(child_path))

    for (layer, key), value in overrides.items():
        assert child.layers[layer][key] == value, (layer, key)
        assert child.layers[layer][key] != parent.layers[layer].get(key), (layer, key)

    for layer, key in untouched:
        assert child.layers[layer][key] == parent.layers[layer][key], (layer, key)

    assert child.has_altgr == parent.has_altgr
    assert set(child.dead_keys) == set(parent.dead_keys)

    for field, value in expected_meta.items():
        assert child.meta[field] == value
    assert child.meta["geometry"] == parent.meta["geometry"]


@pytest.mark.parametrize(
    "parent_path, child_path, overrides, untouched, expected_meta",
    EXTENDED_DIFF_CASES,
)
def test_extends_diff_build(
    tmp_path, parent_path, child_path, overrides, untouched, expected_meta
):
    """Full build + merged.toml round-trip for an extends_diff child."""
    del parent_path  # provided by shared parametrize signature; unused here
    child = KeyboardLayout(resolve_layout(child_path))
    dist = tmp_path / "dist"

    build_all(child, dist)

    stem = child.meta["fileName"]
    exts = (".ahk", ".klc", ".keylayout", ".xkb_keymap", ".xkb_symbols",
            ".json", ".svg", "_merged.toml")
    for ext in exts:
        assert (dist / f"{stem}{ext}").exists(), f"missing {stem}{ext}"

    # klc fails when name8 is too long and writes a 0-byte file
    for ext in (".ahk", ".keylayout", ".xkb_keymap", ".xkb_symbols",
                ".json", ".svg", "_merged.toml"):
        assert (dist / f"{stem}{ext}").stat().st_size > 0, f"empty {stem}{ext}"

    data = json.loads((dist / f"{stem}.json").read_text(encoding="utf-8"))
    assert data["name"] == expected_meta["name"]

    # Merged TOML: reload it as a standalone (no `extends`) layout and verify
    # the overrides survive a full round-trip through disk.
    reloaded = KeyboardLayout(resolve_layout(dist / f"{stem}_merged.toml"))
    assert "extends" not in reloaded.meta
    for (layer, key), value in overrides.items():
        assert reloaded.layers[layer][key] == value, (layer, key)
    for layer, key in untouched:
        assert reloaded.layers[layer][key] == child.layers[layer][key], (layer, key)
    assert reloaded.has_altgr == child.has_altgr
