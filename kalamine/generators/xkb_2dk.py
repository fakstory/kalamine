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

Trigger keys emit single-action latches:

    `++` → LatchMods(modifiers=DK2,latchToLock,clearLocks)             (base half)
    `--` → LatchMods(modifiers=DK2+LevelThree,latchToLock,clearLocks)  (altgr half)
    `&&` → LatchMods(modifiers=DK3,latchToLock,clearLocks)
    `§§` → LatchMods(modifiers=DK3+LevelThree,latchToLock,clearLocks)

A single press latches; `latchToLock` promotes the latch to a true
mod-lock on second press. The lock lives in `locked_mods`, untouched
by `clearLocks` on inner dead-key latches — that's the XKB invariant
backing the chained-deadkey-while-locked behavior.

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


def _trigger_action(marker: str, base_marker: str, vmod: str) -> str:
    """Single-action LatchMods string for a trigger marker."""
    if marker == base_marker:
        mods = vmod
    else:
        # The altgr-half marker reaches levels 7-8 of the dk type by
        # latching DK<N> together with LevelThree.
        mods = f"{vmod}+LevelThree"
    return f"LatchMods(modifiers={mods},latchToLock,clearLocks)"


def _resolve_action(
    cell_value: Optional[str], specs: List[Tuple[str, str, str, Layer, str]]
) -> str:
    """Map a cell value to its emitted action.

    Trigger cells (matching one of the doubled markers) emit a LatchMods
    action; everything else emits `NoAction()`.
    """
    if cell_value is None:
        return _NO_ACTION
    for _, base_marker, altgr_marker, _, vmod in specs:
        if cell_value == base_marker or cell_value == altgr_marker:
            return _trigger_action(cell_value, base_marker, vmod)
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


def key_type_for(layout: "KeyboardLayout", key_name: str) -> Optional[str]:
    """Return the custom type name a key needs, or None if it stays legacy.

    A key uses `KALAMINE_DK2` if it carries any 2dk content (in DK2,
    DK2_SHIFT, DK2_ALTGR, or DK2_ALTGR_SHIFT) OR if it's a 2dk trigger
    (BASE/SHIFT cell value matches `++` or `--`). Same for 3dk.
    """
    for _, base_marker, altgr_marker, base_layer, vmod in _active_specs(layout):
        for layer in _layer_quartet(base_layer):
            if key_name in layout.layers[layer]:
                return f"KALAMINE_{vmod}"
        for layer in (Layer.BASE, Layer.SHIFT):
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
    for layer in (Layer.BASE, Layer.SHIFT, Layer.ALTGR, Layer.ALTGR_SHIFT):
        symbols.append(_symbol_or_void(layer))

    # Levels 5-8: dk overlay.
    for layer in dk_quartet:
        symbols.append(_symbol_or_void(layer))

    # Actions: only the trigger key (BASE/SHIFT marker cells) gets a real action.
    for layer in (Layer.BASE, Layer.SHIFT, Layer.ALTGR, Layer.ALTGR_SHIFT):
        actions.append(_resolve_action(layout.layers[layer].get(key_name), specs))
    for _ in dk_quartet:
        actions.append(_NO_ACTION)

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
