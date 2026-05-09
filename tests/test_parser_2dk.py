"""Parser-level tests for the 2dk / 3dk overlay layers.

These tests do not exercise any generator (XKB / macOS / Windows). They
validate that a layout TOML carrying `2dk` triggers and a `2dk` template
is parsed into the expected `KeyboardLayout` shape, and that legacy
fixtures stay untouched.
"""

import tomllib
from pathlib import Path

from kalamine import KeyboardLayout
from kalamine.utils import DK2_ID, DK_LAYERS, Layer

from .util import get_layout_dict

FIXTURE_2DK = Path(__file__).parent / "fixtures" / "2dk.toml"


def load_2dk() -> KeyboardLayout:
    with FIXTURE_2DK.open("rb") as f:
        return KeyboardLayout(tomllib.load(f))


def test_dk_layers_registry_shape():
    """Sanity check: the registry stays the shape generators rely on."""
    assert len(DK_LAYERS) == 2
    keys = [spec[0] for spec in DK_LAYERS]
    assert keys == ["2dk", "3dk"]
    base_layers = [spec[4] for spec in DK_LAYERS]
    assert base_layers == [Layer.DK2, Layer.DK3]


def test_2dk_fixture_parses():
    layout = load_2dk()
    assert layout.has_dk2 is True
    assert layout.has_dk3 is False
    # Legacy flags must remain off — the fixture has no altgr / 1dk.
    assert layout.has_1dk is False
    assert layout.has_altgr is False


def test_2dk_trigger_markers_in_base_layer():
    """`++` and `--` must land in the BASE/SHIFT layers as literal markers."""
    layout = load_2dk()
    base_w = layout.layers[Layer.BASE].get("ad02")
    shift_w = layout.layers[Layer.SHIFT].get("ad02")
    # The fixture puts `--` in the base half (visual top) and `++` in shift.
    # _parse_template's BASE pass reads the bottom row of each cell as base.
    assert {base_w, shift_w} == {"++", "--"}


def test_2dk_template_glyphs_land_in_dk2_layers():
    layout = load_2dk()
    # The fixture seeds Greek glyphs at Q, A, S, D in the 2dk template.
    assert layout.layers[Layer.DK2].get("ad01") == "α"
    assert layout.layers[Layer.DK2_SHIFT].get("ad01") == "Α"
    assert layout.layers[Layer.DK2].get("ac01") == "β"
    assert layout.layers[Layer.DK2_SHIFT].get("ac01") == "Β"
    assert layout.layers[Layer.DK2].get("ac02") == "σ"
    assert layout.layers[Layer.DK2].get("ac03") == "δ"


def test_legacy_intl_layout_unaffected():
    """Layouts not declaring 2dk/3dk must come out exactly as before."""
    layout = KeyboardLayout(get_layout_dict("intl"))
    assert layout.has_dk2 is False
    assert layout.has_dk3 is False
    # 1dk + altgr remain detected.
    assert layout.has_1dk is True
    # All DK2/DK3 layer slots stay empty.
    for layer in (
        Layer.DK2,
        Layer.DK2_SHIFT,
        Layer.DK2_ALTGR,
        Layer.DK2_ALTGR_SHIFT,
        Layer.DK3,
        Layer.DK3_SHIFT,
        Layer.DK3_ALTGR,
        Layer.DK3_ALTGR_SHIFT,
    ):
        assert layout.layers[layer] == {}


def test_legacy_ansi_layout_unaffected():
    layout = KeyboardLayout(get_layout_dict("ansi"))
    assert layout.has_dk2 is False
    assert layout.has_dk3 is False


def test_dk2_id_is_marker_pair_first_char_doubled():
    """The synthetic ID convention is documented; tests pin it."""
    # DK2_ID is used internally; the live trigger value is the marker itself.
    assert DK2_ID == "%%"
    # The actual cell content is the marker, not the synthetic ID — this
    # ensures the generator can distinguish `++` (base half) from `--`
    # (altgr half) by the cell value.
    layout = load_2dk()
    # No cell should hold the synthetic ID — it's reserved for future use.
    for layer in layout.layers.values():
        for value in layer.values():
            assert value != DK2_ID
