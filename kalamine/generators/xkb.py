"""
GNU/Linux: XKB
- standalone xkb keymap file to be used by `xkbcomp` (XOrg only)
- xkb symbols/patch for XOrg (system-wide) & Wayland (system-wide/user-space)
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..layout import KeyboardLayout

from ..template import load_tpl, substitute_lines
from ..utils import DK_INDEX, LAYER_KEYS, ODK_ID, hex_ord, load_data

XKB_KEY_SYM = load_data("key_sym")


def xkb_table(layout: "KeyboardLayout", xkbcomp: bool = False) -> List[str]:
    """GNU/Linux layout."""

    if layout.qwerty_shortcuts:
        print("WARN: keeping qwerty shortcuts is not yet supported for xkb")

    show_description = True
    eight_level = layout.has_altgr and layout.has_1dk and not xkbcomp
    odk_symbol = "ISO_Level5_Latch" if eight_level else "ISO_Level3_Latch"
    level_modifier = "LevelFive" if eight_level else "LevelThree"
    odk_action = f"LatchMods(modifiers={level_modifier},latchToLock,clearLocks)"
    lock_1dk = getattr(layout, "lock_1dk", False) and layout.has_1dk
    max_length = 16  # `ISO_Level3_Latch` should be the longest symbol name
    action_width = len(odk_action)  # pad NoAction() to align with odk_action

    output: List[str] = []
    for key_name in LAYER_KEYS:
        if key_name.startswith("-"):  # separator
            if output:
                output.append("")
            output.append("//" + key_name[1:])
            continue

        descs = []
        symbols = []
        actions = []
        has_odk = False
        for layer in layout.layers.values():
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
            if symbol == odk_symbol:
                actions.append(odk_action.ljust(action_width))
                has_odk = True
            else:
                actions.append("NoAction()".ljust(action_width))

        key = "{{[ {0}, {1}, {2}, {3}]}}"  # 4-level layout by default
        description = "{0} {1} {2} {3}"
        # parallel templates used for the lock_1dk multi-line block:
        symbols_tpl = "[ {0}, {1}, {2}, {3} ]"
        actions_tpl = "[ {0}, {1}, {2}, {3} ]"
        if layout.has_altgr and layout.has_1dk:
            # 6 layers are needed: they won't fit on the 4-level format.
            if xkbcomp:  # user-space XKB keymap file (standalone)
                # standalone XKB files work best with a dual-group solution:
                # one 4-level group for base+1dk, one two-level group for AltGr
                key = "{{[ {}, {}, {}, {}],[ {}, {}]}}"
                description = "{} {} {} {} {} {}"
                symbols_tpl = (
                    "[ {0}, {1}, {2}, {3} ],\n"
                    "  symbols[Group2] = [ {4}, {5} ]"
                )
                actions_tpl = (
                    "[ {0}, {1}, {2}, {3} ],\n"
                    "  actions[Group2] = [ {4}, {5} ]"
                )
            else:  # eight_level XKB symbols (Neo-like)
                key = "{{[ {0}, {1}, {4}, {5}, {2}, {3}]}}"
                description = "{0} {1} {4} {5} {2} {3}"
                symbols_tpl = "[ {0}, {1}, {4}, {5}, {2}, {3} ]"
                actions_tpl = "[ {0}, {1}, {4}, {5}, {2}, {3} ]"
        elif layout.has_altgr:
            del symbols[3]
            del symbols[2]
            del descs[3]
            del descs[2]
            del actions[3]
            del actions[2]

        if lock_1dk and has_odk:
            line = (
                f"key <{key_name.upper()}> {{\n"
                f"  symbols[Group1] = {symbols_tpl.format(*symbols)},\n"
                f"  actions[Group1] = {actions_tpl.format(*actions)}\n"
                f"}};"
            )
        else:
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
