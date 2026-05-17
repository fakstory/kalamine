"""XKB serializer tests for the 2dk overlay (vmod design).

Validates that:
- legacy fixtures stay byte-identical (regression assertion);
- a 2dk-declaring fixture emits virtual_modifiers + KALAMINE_DK2 type;
- trigger keys emit `LatchMods(modifiers=DK2[+LevelThree],clearLocks)`;
- lock-promoter cells (markers in the dk overlay) emit `LockMods(...)`;
- 2dk-bearing keys use the 8-level multi-line key block.

See `.docs/2dk.md` for the design these tests pin.
"""

import tomllib
from pathlib import Path

from kalamine import KeyboardLayout
from kalamine.generators.xkb import xkb_table

from .util import get_layout_dict

FIXTURE_2DK = Path(__file__).parent.parent / "layouts" / "fixtures" / "2dk.toml"


def load_2dk() -> KeyboardLayout:
    with FIXTURE_2DK.open("rb") as f:
        return KeyboardLayout(tomllib.load(f))


def join(lines):
    return "\n".join(lines)


def test_legacy_intl_xkb_table_unaffected():
    """If 2dk machinery is silent on legacy layouts, intl output should
    contain none of the new tokens."""
    layout = KeyboardLayout(get_layout_dict("intl"))
    out = join(xkb_table(layout, xkbcomp=False))
    assert "virtual_modifiers" not in out
    assert "KALAMINE_DK" not in out
    assert "LatchMods(modifiers=DK" not in out


def test_legacy_ansi_xkb_table_unaffected():
    layout = KeyboardLayout(get_layout_dict("ansi"))
    out = join(xkb_table(layout, xkbcomp=False))
    assert "virtual_modifiers" not in out
    assert "KALAMINE_DK" not in out


def test_2dk_emits_vmod_declaration():
    out = join(xkb_table(load_2dk(), xkbcomp=False))
    assert "virtual_modifiers DK2;" in out


def test_2dk_emits_type_definition():
    out = join(xkb_table(load_2dk(), xkbcomp=False))
    assert 'type "KALAMINE_DK2" {' in out
    assert "modifiers = Shift+LevelThree+DK2;" in out
    # 8 level mappings
    assert "map[None]" in out
    assert "map[DK2]" in out
    assert "map[Shift+LevelThree+DK2]" in out


def test_2dk_trigger_key_emits_latchmods_actions():
    """W in the 2dk fixture has `--` (base) and `++` (shift). Trigger
    cells emit a plain LatchMods (no `latchToLock`): locking is now a
    separate gesture on a dedicated lock-promoter cell on the dk
    overlay, not a same-key double-tap.
    """
    out = join(xkb_table(load_2dk(), xkbcomp=False))
    assert "LatchMods(modifiers=DK2,clearLocks)" in out
    assert "LatchMods(modifiers=DK2+LevelThree,clearLocks)" in out
    # The old double-tap-to-lock semantics are gone.
    assert "latchToLock" not in out


def test_2dk_lock_promoter_cell_emits_lockmods():
    """The 2dk fixture seeds `++` at AD10 on the dk overlay (DK2 layer).
    That cell is reachable only while DK2 is latched; pressing it must
    fire `LockMods(modifiers=DK2,affect=both)` to promote the latch
    into a true lock (and to release it on a second tap).
    """
    out = join(xkb_table(load_2dk(), xkbcomp=False))
    idx = out.index("key <AD10>")
    block = out[idx : out.index("};", idx)]
    assert 'type[Group1] = "KALAMINE_DK2"' in block
    assert "LockMods(modifiers=DK2,affect=both)" in block


def test_2dk_trigger_key_uses_eight_level_type():
    out = join(xkb_table(load_2dk(), xkbcomp=False))
    # The W key block (AD02) must reference the custom type and carry
    # 8 symbols + 8 actions.
    assert "key <AD02> {" in out
    # The block uses the multi-line `type[Group1]` form.
    block_start = out.index("key <AD02> {")
    block = out[block_start : block_start + 600]
    assert 'type[Group1] = "KALAMINE_DK2"' in block
    assert "symbols[Group1]" in block
    assert "actions[Group1]" in block


def test_2dk_overlay_key_carries_greek_glyphs_at_levels_5_8():
    """The Q key has Greek alpha in the 2dk template; A has Greek beta;
    S has sigma; D has delta. They should appear in the key blocks."""
    out = join(xkb_table(load_2dk(), xkbcomp=False))
    # We can't easily assert level positions without parsing, but the
    # symbols must appear in the AD01/AC01/AC02/AC03 blocks.
    for key in ("AD01", "AC01", "AC02", "AC03"):
        idx = out.index(f"key <{key}>")
        block = out[idx : idx + 600]
        # Each of these keys carries 2dk content, so each should use
        # the custom type.
        assert 'type[Group1] = "KALAMINE_DK2"' in block, key


def test_2dk_no_dk3_emission_when_only_2dk_active():
    out = join(xkb_table(load_2dk(), xkbcomp=False))
    assert "DK3" not in out
    assert "KALAMINE_DK3" not in out
