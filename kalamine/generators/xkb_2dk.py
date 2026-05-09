"""
XKB emission for the 2dk / 3dk overlay layers.

Design: virtual-modifier + 8-level custom key type (per dk layer).
See `.docs/2dk.md` ("XKB strategy: virtual modifiers, single-group")
for the rationale and the rejected Group2/Group3 alternative.

Per-dk-layer type (`KALAMINE_DK2`, `KALAMINE_DK3`):

    type "KALAMINE_DK2" {
        modifiers = Shift + LevelThree + DK2;
        map[None]                          = level1;  // base
        map[Shift]                         = level2;  // shift
        map[LevelThree]                    = level3;  // altgr
        map[Shift+LevelThree]              = level4;  // altgr_shift
        map[DK2]                           = level5;  // 2dk-base
        map[Shift+DK2]                     = level6;  // 2dk-shift
        map[LevelThree+DK2]                = level7;  // 2dk-altgr
        map[Shift+LevelThree+DK2]          = level8;  // 2dk-altgr_shift
    };

Two distinct cell roles, distinguished by which layer the marker
sits in:

  * **Trigger**  — marker in a *legacy* layer (BASE/SHIFT/ALTGR/
    ALTGR_SHIFT). Emits `LatchMods(...,clearLocks)` so the next
    keypress sees the dk overlay; latch clears on use.

        `++` (BASE/SHIFT/ALTGR/ALTGR_SHIFT) → LatchMods(modifiers=DK2,clearLocks)
        `--` ditto                          → LatchMods(modifiers=DK2+LevelThree,clearLocks)
        `&&`                                → LatchMods(modifiers=DK3,clearLocks)
        `§§`                                → LatchMods(modifiers=DK3+LevelThree,clearLocks)

  * **Lock-promoter** — marker in a *dk overlay* layer (DK2,
    DK2_SHIFT, DK2_ALTGR, DK2_ALTGR_SHIFT, or the DK3 quartet).
    Reachable only while the dk is latched. Emits
    `LockMods(...,affect=both)` which toggles the lock state for
    that vmod. Pattern: tap a trigger, then tap the cell carrying
    the same marker on the dk overlay → the dk locks; tap that
    cell again later (it will fire because the lock keeps the dk
    overlay active) → unlock.

The trigger key is now free to host a glyph at its dk-overlay
slots (no implicit `latchToLock` consumes them). Locking is a
deliberate gesture on a dedicated lock-promoter cell.

This helper owns its own emission shape and is opt-in via
`is_enabled(layout)`. `xkb.py` keeps its main path almost untouched.
"""

from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

if TYPE_CHECKING:
    from ..layout import KeyboardLayout

from ..utils import DK_LAYERS, Layer

# `LatchMods(modifiers=...)` strings line up with the longest legacy
# action so multi-line emission columns stay aligned.
_NO_ACTION = "NoAction()"


def is_enabled(layout: "KeyboardLayout") -> bool:
    return bool(getattr(layout, "has_dk2", False) or getattr(layout, "has_dk3", False))


def _layer_quartet(base: Layer) -> Tuple[Layer, Layer, Layer, Layer]:
    """The four levels of a dk overlay, in XKB order: base / shift / altgr / altgr_shift."""
    return (base, Layer(int(base) + 1), Layer(int(base) + 2), Layer(int(base) + 3))


def _active_specs(layout: "KeyboardLayout") -> List[Tuple[str, str, str, Layer, str]]:
    """Filter DK_LAYERS to the dk pairs the layout actually uses.

    Each tuple: (toml_key, base_marker, altgr_marker, base_layer, vmod_name).
    """
    out: List[Tuple[str, str, str, Layer, str]] = []
    for toml_key, _, base_marker, altgr_marker, base_layer, vmod_name in DK_LAYERS:
        attr = "has_dk2" if base_layer == Layer.DK2 else "has_dk3"
        if getattr(layout, attr, False):
            out.append((toml_key, base_marker, altgr_marker, base_layer, vmod_name))
    return out


def _mods_for_marker(marker: str, base_marker: str, vmod: str) -> str:
    """Modifier string for a marker.

    Base-half marker latches/locks the vmod alone; altgr-half marker
    pairs the vmod with LevelThree so the dk overlay's altgr half
    (levels 7-8 of the custom type) is reached.
    """
    if marker == base_marker:
        return vmod
    return f"{vmod}+LevelThree"


def _trigger_action(marker: str, base_marker: str, vmod: str) -> str:
    """LatchMods action emitted on a trigger cell (legacy layer)."""
    mods = _mods_for_marker(marker, base_marker, vmod)
    return f"LatchMods(modifiers={mods},clearLocks)"


def _lock_action(marker: str, base_marker: str, vmod: str) -> str:
    """LockMods action emitted on a lock-promoter cell (dk overlay layer).

    `affect=both` is the XKB toggle behavior: pressing while unlocked
    sets the lock, pressing while locked clears it. Combined with the
    fact that this cell is only reachable while the dk is active
    (latched or already locked), the resulting UX is: trigger → lock
    → … → unlock by re-pressing the same lock-promoter cell.
    """
    mods = _mods_for_marker(marker, base_marker, vmod)
    return f"LockMods(modifiers={mods},affect=both)"


def _resolve_trigger_action(
    cell_value: Optional[str], specs: List[Tuple[str, str, str, Layer, str]]
) -> str:
    """Action for a *legacy*-layer cell. Marker → LatchMods; else NoAction."""
    if cell_value is None:
        return _NO_ACTION
    for _, base_marker, altgr_marker, _, vmod in specs:
        if cell_value == base_marker or cell_value == altgr_marker:
            return _trigger_action(cell_value, base_marker, vmod)
    return _NO_ACTION


def _resolve_lock_promoter_action(
    cell_value: Optional[str], specs: List[Tuple[str, str, str, Layer, str]]
) -> str:
    """Action for a *dk-overlay* cell. Marker → LockMods; else NoAction."""
    if cell_value is None:
        return _NO_ACTION
    for _, base_marker, altgr_marker, _, vmod in specs:
        if cell_value == base_marker or cell_value == altgr_marker:
            return _lock_action(cell_value, base_marker, vmod)
    return _NO_ACTION


def type_definitions(layout: "KeyboardLayout") -> List[str]:
    """Custom 8-level type definitions, one per active dk pair.

    Emitted once at the top of the symbols block. See `.docs/2dk.md`.
    """
    out: List[str] = []
    for _, _, _, _, vmod in _active_specs(layout):
        out.extend(
            [
                f'type "KALAMINE_{vmod}" {{',
                f"    modifiers = Shift+LevelThree+{vmod};",
                "    map[None]                       = level1;",
                "    map[Shift]                      = level2;",
                "    map[LevelThree]                 = level3;",
                "    map[Shift+LevelThree]           = level4;",
                f"    map[{vmod}]                          = level5;",
                f"    map[Shift+{vmod}]                    = level6;",
                f"    map[LevelThree+{vmod}]               = level7;",
                f"    map[Shift+LevelThree+{vmod}]         = level8;",
                '    level_name[Level1] = "Base";',
                '    level_name[Level2] = "Shift";',
                '    level_name[Level3] = "AltGr";',
                '    level_name[Level4] = "AltGr+Shift";',
                f'    level_name[Level5] = "{vmod}";',
                f'    level_name[Level6] = "{vmod}+Shift";',
                f'    level_name[Level7] = "{vmod}+AltGr";',
                f'    level_name[Level8] = "{vmod}+AltGr+Shift";',
                "};",
            ]
        )
    return out


def virtual_modifier_decl(layout: "KeyboardLayout") -> str:
    """`virtual_modifiers DK2, DK3;` declaration, one line."""
    names = [spec[4] for spec in _active_specs(layout)]
    return f"virtual_modifiers {', '.join(names)};"


_LEGACY_LAYERS = (Layer.BASE, Layer.SHIFT, Layer.ALTGR, Layer.ALTGR_SHIFT)


def key_type_for(layout: "KeyboardLayout", key_name: str) -> Optional[str]:
    """Return the custom type name a key needs, or None if it stays legacy.

    A key uses `KALAMINE_DK2` if any of:
      - it carries any 2dk overlay content (DK2 / DK2_SHIFT / DK2_ALTGR /
        DK2_ALTGR_SHIFT), which covers both glyph cells AND lock-promoter
        marker cells;
      - it is a 2dk trigger — any of its four legacy-layer cells (BASE,
        SHIFT, ALTGR, ALTGR_SHIFT) matches `++` or `--`.
    Same logic for 3dk with `&&` / `§§`.
    """
    for _, base_marker, altgr_marker, base_layer, vmod in _active_specs(layout):
        for layer in _layer_quartet(base_layer):
            if key_name in layout.layers[layer]:
                return f"KALAMINE_{vmod}"
        for layer in _LEGACY_LAYERS:
            v = layout.layers[layer].get(key_name)
            if v == base_marker or v == altgr_marker:
                return f"KALAMINE_{vmod}"
    return None


def collect_eight_level_symbols(
    layout: "KeyboardLayout",
    key_name: str,
    legacy_symbol_for: Callable[[Layer, str], str],
) -> Tuple[List[str], List[str]]:
    """Build the 8-symbol list + 8-action list for a dk-bearing key.

    `legacy_symbol_for(layer, key_name)` is supplied by `xkb.py` so this
    helper does not duplicate the keysym-resolution logic.
    """
    specs = _active_specs(layout)
    typename = key_type_for(layout, key_name)
    # Determine which dk pair this key belongs to.
    dk_quartet: Tuple[Layer, ...] = ()
    if typename:
        for _, _, _, base_layer, vmod in specs:
            if typename == f"KALAMINE_{vmod}":
                dk_quartet = _layer_quartet(base_layer)
                break

    symbols: List[str] = []
    actions: List[str] = []

    marker_set = set()
    for _, base_marker, altgr_marker, _, _ in specs:
        marker_set.add(base_marker)
        marker_set.add(altgr_marker)

    def _symbol_or_void(layer: Layer) -> str:
        # Trigger cells hold marker strings; the action carries the
        # behavior, the symbol slot is left as VoidSymbol so the keypress
        # produces no glyph if the action somehow doesn't fire.
        cell = layout.layers[layer].get(key_name)
        if cell in marker_set:
            return "VoidSymbol".ljust(16)
        return legacy_symbol_for(layer, key_name)

    # Levels 1-4: legacy base / shift / altgr / altgr_shift.
    for layer in _LEGACY_LAYERS:
        symbols.append(_symbol_or_void(layer))

    # Levels 5-8: dk overlay.
    for layer in dk_quartet:
        symbols.append(_symbol_or_void(layer))

    # Actions: legacy-layer marker cells latch the dk; dk-overlay marker
    # cells lock it (toggle). Non-marker cells stay NoAction.
    for layer in _LEGACY_LAYERS:
        actions.append(
            _resolve_trigger_action(layout.layers[layer].get(key_name), specs)
        )
    for layer in dk_quartet:
        actions.append(
            _resolve_lock_promoter_action(layout.layers[layer].get(key_name), specs)
        )

    return symbols, actions


def format_key_block(
    key_name: str, typename: str, symbols: List[str], actions: List[str]
) -> str:
    """Multi-line `key <X> { type[Group1] = "...", symbols=..., actions=... };` block."""
    sym_str = ", ".join(symbols)
    act_str = ", ".join(actions)
    return (
        f"key <{key_name.upper()}> {{\n"
        f'  type[Group1] = "{typename}",\n'
        f"  symbols[Group1] = [ {sym_str} ],\n"
        f"  actions[Group1] = [ {act_str} ]\n"
        f"}};"
    )
