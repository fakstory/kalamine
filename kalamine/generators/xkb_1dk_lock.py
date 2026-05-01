"""
Latch-to-lock support for the 1dk key on Linux/XKB.

Opt-in via `1dk_lock = true` in the layout TOML. When enabled, the 1dk key
emits an explicit `LatchMods(...,latchToLock,clearLocks)` action, so a double
tap locks the dead-key layer until the next keypress (or another tap to release).

This module owns all 1dk_lock-specific concerns so that `generators/xkb.py`
stays close to its main-branch shape: it only consults `is_enabled(layout)`
and, when a key needs the multi-line `symbols[Group1] / actions[Group1]` form,
delegates to `format_key_block`.
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..layout import KeyboardLayout


def is_enabled(layout: "KeyboardLayout") -> bool:
    return bool(layout.meta.get("1dk_lock", False)) and layout.has_1dk


def odk_action(eight_level: bool) -> str:
    level_modifier = "LevelFive" if eight_level else "LevelThree"
    return f"LatchMods(modifiers={level_modifier},latchToLock,clearLocks)"


def action_for(symbol: str, odk_symbol: str, odk_act: str, width: int) -> str:
    if symbol.strip() == odk_symbol:
        return odk_act.ljust(width)
    return "NoAction()".ljust(width)


def symbols_template(layout: "KeyboardLayout", xkbcomp: bool) -> str:
    """Mirror of the `key` symbol layout, but for the multi-line form."""
    if layout.has_altgr and layout.has_1dk:
        if xkbcomp:
            return (
                "[ {0}, {1}, {2}, {3} ],\n"
                "  symbols[Group2] = [ {4}, {5} ]"
            )
        return "[ {0}, {1}, {4}, {5}, {2}, {3} ]"
    return "[ {0}, {1}, {2}, {3} ]"


def actions_template(layout: "KeyboardLayout", xkbcomp: bool) -> str:
    if layout.has_altgr and layout.has_1dk:
        if xkbcomp:
            return (
                "[ {0}, {1}, {2}, {3} ],\n"
                "  actions[Group2] = [ {4}, {5} ]"
            )
        return "[ {0}, {1}, {4}, {5}, {2}, {3} ]"
    return "[ {0}, {1}, {2}, {3} ]"


def format_key_block(
    key_name: str,
    symbols: List[str],
    actions: List[str],
    layout: "KeyboardLayout",
    xkbcomp: bool,
) -> str:
    sym_tpl = symbols_template(layout, xkbcomp)
    act_tpl = actions_template(layout, xkbcomp)
    return (
        f"key <{key_name.upper()}> {{\n"
        f"  symbols[Group1] = {sym_tpl.format(*symbols)},\n"
        f"  actions[Group1] = {act_tpl.format(*actions)}\n"
        f"}};"
    )
