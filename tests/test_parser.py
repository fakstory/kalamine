import json
from pathlib import Path

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


def test_extends_diff():  # base_diff / altgr_diff overlay on parent
    fixtures = Path(__file__).parent / "extended-diff"
    parent = KeyboardLayout(resolve_layout(fixtures / "base" / "Bépo.toml"))
    child = KeyboardLayout(
        resolve_layout(fixtures / "extended" / "bepo_extended.toml")
    )

    # sanity: parent is a normal extends_diff-free Bépo
    assert parent.has_altgr
    assert parent.meta["name"] == "bepo"

    overrides = {
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
    }
    for (layer, key), value in overrides.items():
        assert child.layers[layer][key] == value
        assert child.layers[layer][key] != parent.layers[layer].get(key)

    # untouched cells come from parent
    assert child.layers[0]["ae01"] == parent.layers[0]["ae01"]
    assert child.layers[1]["ae01"] == parent.layers[1]["ae01"]
    assert child.layers[0]["ac01"] == parent.layers[0]["ac01"]
    assert child.layers[1]["ac01"] == parent.layers[1]["ac01"]

    # has_altgr carries from parent even though child only declared diffs
    assert child.has_altgr

    # parent dead keys are preserved
    assert set(child.dead_keys) == set(parent.dead_keys)

    # metadata: child's own fields win, parent fills in the rest
    assert child.meta["name"] == "bepo-extended"
    assert child.meta["variant"] == "bepo-extended"
    assert child.meta["geometry"] == parent.meta["geometry"]


def test_extends_diff_build(tmp_path):
    fixtures = Path(__file__).parent / "extended-diff"
    child = KeyboardLayout(
        resolve_layout(fixtures / "extended" / "bepo_extended.toml")
    )
    dist = tmp_path / "dist"

    build_all(child, dist)

    stem = child.meta["fileName"]
    exts = (".ahk", ".klc", ".keylayout", ".xkb_keymap", ".xkb_symbols",
            ".json", ".svg", "_merged.toml")
    for ext in exts:
        assert (dist / f"{stem}{ext}").exists(), f"missing {stem}{ext}"

    # klc fails when name8 is too long (13 chars here) and writes a 0-byte file
    for ext in (".ahk", ".keylayout", ".xkb_keymap", ".xkb_symbols",
                ".json", ".svg", "_merged.toml"):
        assert (dist / f"{stem}{ext}").stat().st_size > 0, f"empty {stem}{ext}"

    data = json.loads((dist / f"{stem}.json").read_text(encoding="utf-8"))
    assert data["name"] == "bepo-extended"
    # diff overrides are visible in the generated JSON
    assert data["keymap"]["Digit2"][0] == "<"
    assert data["keymap"]["Digit3"][0] == ">"
    # parent-inherited cells passed through the merge
    assert data["keymap"]["KeyQ"][0] == "b"

    # Merged TOML: reload it as a standalone (no `extends`) layout and
    # verify the overrides survive a full round-trip through disk.
    reloaded = KeyboardLayout(resolve_layout(dist / f"{stem}_merged.toml"))
    assert "extends" not in reloaded.meta
    assert reloaded.layers[0]["tlde"] == "="
    assert reloaded.layers[0]["ae02"] == "<"
    assert reloaded.layers[0]["ad11"] == "w" and reloaded.layers[1]["ad11"] == "W"
    assert reloaded.layers[0]["ac01"] == child.layers[0]["ac01"]
    assert reloaded.has_altgr == child.has_altgr
