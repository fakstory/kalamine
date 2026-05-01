"""Pins all 8 levels of the `KALAMINE_DK2` custom type on the Q key.

The `2dk_full.toml` fixture stages a single key (Q, AD01) with every
one of the 8 levels (1=base / 2=shift / 3=altgr / 4=altgr+shift /
5=DK2 base / 6=DK2 shift / 7=DK2 altgr / 8=DK2 altgr+shift) carrying a
distinct, easily distinguishable glyph.

These tests catch off-by-one bugs in:
- `_parse_template`'s col_offset handling for the new DK2_ALTGR /
  DK2_ALTGR_SHIFT layers (the existing `2dk.toml` fixture only exercises
  levels 5-6, leaving 7-8 untested);
- `xkb_2dk.collect_eight_level_symbols`'s ordering of layers in the
  emitted `symbols[Group1]` list.
"""

import tomllib
from pathlib import Path

from kalamine import KeyboardLayout
from kalamine.generators.xkb import xkb_table
from kalamine.utils import Layer


FIXTURE = Path(__file__).parent / "fixtures" / "2dk_full.toml"


def _layout() -> KeyboardLayout:
    with FIXTURE.open("rb") as f:
        return KeyboardLayout(tomllib.load(f))


# ---- Parser-level: each layer slot for Q holds the right glyph ---------


def test_parser_levels_1_to_8_on_q():
    layout = _layout()
    expected = {
        Layer.BASE: "q",
        Layer.SHIFT: "Q",
        Layer.ALTGR: "1",
        Layer.ALTGR_SHIFT: "2",
        Layer.DK2: "α",
        Layer.DK2_SHIFT: "Α",
        Layer.DK2_ALTGR: "3",
        Layer.DK2_ALTGR_SHIFT: "4",
    }
    for layer, glyph in expected.items():
        actual = layout.layers[layer].get("ad01")
        assert actual == glyph, (
            f"Layer {layer.name}: expected {glyph!r}, got {actual!r}"
        )


def test_parser_2dk_active_with_altgr():
    layout = _layout()
    assert layout.has_dk2 is True
    assert layout.has_dk3 is False
    assert layout.has_altgr is True
    assert layout.has_1dk is False


# ---- XKB-level: emitted Q block carries the 8 glyphs in the right order


def test_xkb_q_block_has_eight_levels_in_order():
    layout = _layout()
    out = "\n".join(xkb_table(layout, xkbcomp=False))
    # Locate the Q key block (AD01).
    idx = out.index("key <AD01>")
    block_end = out.index("};", idx)
    block = out[idx:block_end]

    # Symbols line should hold exactly 8 entries, in this order:
    #   q, Q, 1, 2, α (U03B1), Α (U0391), 3, 4
    # Our generator emits Greek glyphs as U-encoded keysyms because they
    # don't match `XKB_KEY_SYM`. Latin/digit glyphs use their named keysyms.
    assert "type[Group1] = \"KALAMINE_DK2\"" in block
    sym_line = [line for line in block.splitlines() if "symbols[Group1]" in line][0]

    expected_tokens = [
        "q",
        "Q",
        "1",
        "2",
        "U03B1",  # α
        "U0391",  # Α
        "3",
        "4",
    ]
    # All tokens must appear in the symbols line, in the documented order.
    pos = -1
    for tok in expected_tokens:
        new_pos = sym_line.find(tok, pos + 1)
        assert new_pos > pos, (
            f"Token {tok!r} not found after position {pos} in: {sym_line!r}"
        )
        pos = new_pos


def test_xkb_q_actions_are_all_noaction():
    """Q is a content key, not a trigger — actions slot should be NoAction()
    for all 8 levels. The trigger key (W = AD02) is the one with LatchMods.
    """
    layout = _layout()
    out = "\n".join(xkb_table(layout, xkbcomp=False))
    idx = out.index("key <AD01>")
    block = out[idx : out.index("};", idx)]
    act_line = [line for line in block.splitlines() if "actions[Group1]" in line][0]
    # 8 NoAction() entries; no LatchMods on a content key.
    assert act_line.count("NoAction()") == 8
    assert "LatchMods" not in act_line


def test_xkb_w_trigger_has_latchmods_at_levels_1_and_2():
    """W (AD02) is the trigger: BASE = `--` (altgr-half latch), SHIFT = `++`
    (base-half latch). Levels 3-8 should be NoAction().
    """
    layout = _layout()
    out = "\n".join(xkb_table(layout, xkbcomp=False))
    idx = out.index("key <AD02>")
    block = out[idx : out.index("};", idx)]
    act_line = [line for line in block.splitlines() if "actions[Group1]" in line][0]
    # Both halves present; one with +LevelThree (altgr half), one without.
    assert "LatchMods(modifiers=DK2,latchToLock,clearLocks)" in act_line
    assert "LatchMods(modifiers=DK2+LevelThree,latchToLock,clearLocks)" in act_line
    # Levels 3-8 are NoAction (6 entries).
    assert act_line.count("NoAction()") == 6
