"""
GNU/Linux: XKB
- standalone xkb keymap file to be used by `xkbcomp` (XOrg only)
- xkb symbols/patch for XOrg (system-wide) & Wayland (system-wide/user-space)
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..layout import KeyboardLayout

from ..template import load_tpl, substitute_lines
from ..utils import DK_INDEX, LAYER_KEYS, ODK_ID, Layer, hex_ord, load_data
from . import xkb_2dk

XKB_KEY_SYM = load_data("key_sym")


def _legacy_symbol(
    layout: "KeyboardLayout", layer: "Layer", key_name: str, max_length: int = 16
) -> str:
    """Resolve a single (layer, key) cell into its XKB symbol token.

    Extracted so `xkb_2dk.collect_eight_level_symbols` can reuse the
    same keysym-resolution logic without duplicating it.
    """
    layer_dict = layout.layers[layer]
    if key_name not in layer_dict:
        return "VoidSymbol".ljust(max_length)
    keysym = layer_dict[key_name]
    if keysym in DK_INDEX:
        name = DK_INDEX[keysym].name
        symbol = "ISO_Level3_Latch" if keysym == ODK_ID else f"dead_{name}"
    elif keysym in XKB_KEY_SYM and len(XKB_KEY_SYM[keysym]) <= max_length:
        symbol = XKB_KEY_SYM[keysym]
    else:
        symbol = f"U{hex_ord(keysym).upper()}"
    return symbol.ljust(max_length)


def xkb_table(layout: "KeyboardLayout", xkbcomp: bool = False) -> List[str]:
    """GNU/Linux layout."""

    if layout.qwerty_shortcuts:
        print("WARN: keeping qwerty shortcuts is not yet supported for xkb")

    show_description = True
    eight_level = layout.has_altgr and layout.has_1dk and not xkbcomp
    odk_symbol = "ISO_Level5_Latch" if eight_level else "ISO_Level3_Latch"
    max_length = 16  # `ISO_Level3_Latch` should be the longest symbol name

    has_2dk = xkb_2dk.is_enabled(layout)

    output: List[str] = []
    if has_2dk:
        # Emit the virtual_modifiers declaration + custom 8-level types
        # at the top of the LAYOUT block so they're in scope before any
        # key block references them.
        output.append(xkb_2dk.virtual_modifier_decl(layout))
        output.extend(xkb_2dk.type_definitions(layout))
        output.append("")

    # Iterate only the legacy 6 layers so existing layouts stay byte-
    # identical. The 2dk/3dk overlay layers are handled per-key via the
    # `xkb_2dk` helper below.
    legacy_layers = [
        Layer.BASE,
        Layer.SHIFT,
        Layer.ODK,
        Layer.ODK_SHIFT,
        Layer.ALTGR,
        Layer.ALTGR_SHIFT,
    ]

    for key_name in LAYER_KEYS:
        if key_name.startswith("-"):  # separator
            if output:
                output.append("")
            output.append("//" + key_name[1:])
            continue

        # 2dk/3dk-bearing keys take a dedicated multi-line emission and
        # skip the standard 4/6-level symbol formatting below.
        if has_2dk:
            typename = xkb_2dk.key_type_for(layout, key_name)
            if typename is not None:
                symbols, actions = xkb_2dk.collect_eight_level_symbols(
                    layout,
                    key_name,
                    lambda layer, kn: _legacy_symbol(layout, layer, kn, max_length),
                )
                output.append(
                    xkb_2dk.format_key_block(key_name, typename, symbols, actions)
                )
                continue

        descs = []
        symbols = []
        for layer_index in legacy_layers:
            layer = layout.layers[layer_index]
            if key_name in layer:
                keysym = layer[key_name]
                desc = keysym
                # dead key?
                if keysym in DK_INDEX:
                    name = DK_INDEX[keysym].name
                    desc = layout.dead_keys[keysym][keysym]
                    symbol = odk_symbol if keysym == ODK_ID else f"dead_{name}"
                # regular key: use a keysym if possible, utf-8 otherwise
                elif keysym in XKB_KEY_SYM and len(XKB_KEY_SYM[keysym]) <= max_length:
                    symbol = XKB_KEY_SYM[keysym]
                else:
                    symbol = f"U{hex_ord(keysym).upper()}"
            else:
                desc = " "
                symbol = "VoidSymbol"

            descs.append(desc)
            symbols.append(symbol.ljust(max_length))

        key = "{{[ {0}, {1}, {2}, {3}]}}"  # 4-level layout by default
        description = "{0} {1} {2} {3}"
        if layout.has_altgr and layout.has_1dk:
            # 6 layers are needed: they won't fit on the 4-level format.
            if xkbcomp:  # user-space XKB keymap file (standalone)
                # standalone XKB files work best with a dual-group solution:
                # one 4-level group for base+1dk, one two-level group for AltGr
                key = "{{[ {}, {}, {}, {}],[ {}, {}]}}"
                description = "{} {} {} {} {} {}"
            else:  # eight_level XKB symbols (Neo-like)
                key = "{{[ {0}, {1}, {4}, {5}, {2}, {3}]}}"
                description = "{0} {1} {4} {5} {2} {3}"
        elif layout.has_altgr:
            del symbols[3]
            del symbols[2]
            del descs[3]
            del descs[2]

        line = f"key <{key_name.upper()}> {key.format(*symbols)};"
        if show_description:
            line += (" // " + description.format(*descs)).rstrip()
            if line.endswith("\\"):
                line += " "  # escape trailing backslash
        output.append(line)

    return output


def xkb_keymap(self) -> str:  # will not work with Wayland
    """GNU/Linux driver (standalone / user-space)"""

    out = load_tpl(self, ".xkb_keymap")
    out = substitute_lines(out, "LAYOUT", xkb_table(self, xkbcomp=True))
    return out


def xkb_symbols(self) -> str:
    """GNU/Linux driver (xkb patch, system or user-space)"""

    out = load_tpl(self, ".xkb_symbols")
    out = substitute_lines(out, "LAYOUT", xkb_table(self, xkbcomp=False))
    return out.replace("//#", "//")
