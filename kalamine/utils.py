import pkgutil
from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional

import yaml


def hex_ord(char: str) -> str:
    return hex(ord(char))[2:].zfill(4)


def lines_to_text(lines: List[str], indent: str = "") -> str:
    """
    From a list lines of string, produce a string concatenating the elements
    of lines indented by prepending indent and followed by a new line.
    Example: lines_to_text(["one", "two", "three"], "  ") returns
    '  one\n  two\n  three'
    """
    out = ""
    for line in lines:
        if len(line):
            out += indent + line
        out += "\n"
    return out[:-1]


def text_to_lines(text: str) -> List[str]:
    """Split given text into lines"""
    return text.split("\n")


def load_data(filename: str) -> Dict:
    descriptor = pkgutil.get_data(__package__, f"data/{filename}.yaml")
    if not descriptor:
        return {}
    return yaml.safe_load(descriptor.decode("utf-8"))


class Layer(IntEnum):
    """A layer designation."""

    BASE = 0
    SHIFT = 1
    ODK = 2
    ODK_SHIFT = 3
    ALTGR = 4
    ALTGR_SHIFT = 5
    DK2 = 6
    DK2_SHIFT = 7
    DK2_ALTGR = 8
    DK2_ALTGR_SHIFT = 9
    DK3 = 10
    DK3_SHIFT = 11
    DK3_ALTGR = 12
    DK3_ALTGR_SHIFT = 13

    def next(self) -> "Layer":
        """The shift counterpart of a base-position layer.

        Used in `_parse_template` after parsing the base half of a cell
        to access the shift half. Only valid on even-numbered layers.
        """
        return Layer(int(self) + 1)

    def necromance(self) -> "Layer":
        """Remove the effect of the dead key if any."""
        if self == Layer.ODK:
            return Layer.BASE
        elif self == Layer.ODK_SHIFT:
            return Layer.SHIFT
        return self


def upper_key(letter: Optional[str], blank_if_obvious: bool = True) -> str:
    """This is used for presentation purposes: in a key, the upper character
    becomes blank if it's an obvious uppercase version of the base character."""

    if letter is None:
        return " "

    custom_alpha = {
        "\u00df": "\u1e9e",  # ß ẞ
        "\u007c": "\u00a6",  # | ¦
        "\u003c": "\u2264",  # < ≤
        "\u003e": "\u2265",  # > ≥
        "\u2020": "\u2021",  # † ‡
        "\u2190": "\u21d0",  # ← ⇐
        "\u2191": "\u21d1",  # ↑ ⇑
        "\u2192": "\u21d2",  # → ⇒
        "\u2193": "\u21d3",  # ↓ ⇓
        "\u00b5": " ",  # µ (to avoid getting `Μ` as uppercase)
    }
    if letter in custom_alpha:
        return custom_alpha[letter]

    if len(letter) == 1 and letter.upper() != letter.lower():
        return letter.upper()

    # dead key or non-letter character
    return " " if blank_if_obvious else letter


@dataclass
class DeadKeyDescr:
    char: str
    name: str
    base: str
    alt: str
    alt_space: str
    alt_self: str


DEAD_KEYS = [DeadKeyDescr(**data) for data in load_data("dead_keys")]

DK_INDEX = {}
for dk in DEAD_KEYS:
    DK_INDEX[dk.char] = dk

SCAN_CODES = load_data("scan_codes")

ODK_ID = "**"  # must match the value in dead_keys.yaml

# --- Additional dead-key overlay layers (2dk, 3dk, ...) ----------------
#
# Each entry in DK_LAYERS defines one paired-trigger overlay analogous
# to 1dk: a full 4-level layer (base / shift / altgr / altgr_shift)
# reached via two doubled-marker triggers in the `base` template.
#
#   - The first marker (`++`, `&&`) latches the dk's base+shift half.
#   - The second marker (`--`, `§§`) latches the dk's altgr half.
#   - Double-tap of either marker promotes the latch to a lock.
#
# DK2_ID / DK3_ID are reserved synthetic identifiers. They are NOT
# currently stored in any layer (the trigger cells hold the marker
# strings themselves so generators can distinguish base-half vs altgr-
# half triggers), but the constants are kept for future use if a
# generator ever needs a single canonical id per dk pair.
#
# # HOW TO ADD A NEW dk LAYER (e.g. 4dk with markers `==` / `##`)
#
#   1. Append four entries to `Layer(IntEnum)` above:
#         DK4 = 14
#         DK4_SHIFT = 15
#         DK4_ALTGR = 16
#         DK4_ALTGR_SHIFT = 17
#   2. Define a synthetic id (kept symmetric with DK2_ID / DK3_ID):
#         DK4_ID = "##"   # (or any 2-char internal marker not in user TOML)
#   3. Append one tuple to DK_LAYERS below — the format is fixed and
#      consumed by `layout.py` (parser), `generators/xkb_2dk.py` (XKB
#      vmod emission), and `generators/dk_fallback.py` (Mac/Win fallback).
#         ("4dk", DK4_ID, "==", "##", Layer.DK4, "DK4"),
#   4. The parser (`_parse_template` in layout.py) reads the marker
#      chars from this registry — no further parser change is needed
#      as long as the markers are non-overlapping single-char prefixes.
#   5. XKB caps at ~8 levels per type; the vmod design works fine up to
#      4 dk overlays in principle, but watch real-mod budget on Linux
#      (see comments in generators/xkb_2dk.py).
#
# Deliberately NOT a TOML-driven registry — adding a dk overlay is a
# code change so that the marker chars, layer enum entries, and
# generator dispatch all stay in lockstep.
DK2_ID = "%%"  # internal marker — never appears in user TOML
DK3_ID = "@@"  # internal marker — never appears in user TOML

DK_LAYERS = [
    # (toml_key, layer_id, base_marker, altgr_marker, base_layer, vmod_name)
    #   toml_key      — top-level TOML key holding the overlay template
    #   layer_id      — synthetic id (currently unused at runtime; reserved)
    #   base_marker   — doubled-marker that triggers the base+shift half
    #   altgr_marker  — doubled-marker that triggers the altgr half
    #   base_layer    — first of the four `Layer` slots for this overlay
    #                   (the other three are int(base_layer)+1..+3)
    #   vmod_name     — XKB virtual modifier name; appears in the
    #                   generated `virtual_modifiers ...;` declaration
    #                   and in the `KALAMINE_<vmod>` custom type.
    ("2dk", DK2_ID, "++", "--", Layer.DK2, "DK2"),
    ("3dk", DK3_ID, "&&", "§§", Layer.DK3, "DK3"),
]

LAYER_KEYS = [
    "- Digits",
    "ae01",
    "ae02",
    "ae03",
    "ae04",
    "ae05",
    "ae06",
    "ae07",
    "ae08",
    "ae09",
    "ae10",
    "- Letters, first row",
    "ad01",
    "ad02",
    "ad03",
    "ad04",
    "ad05",
    "ad06",
    "ad07",
    "ad08",
    "ad09",
    "ad10",
    "- Letters, second row",
    "ac01",
    "ac02",
    "ac03",
    "ac04",
    "ac05",
    "ac06",
    "ac07",
    "ac08",
    "ac09",
    "ac10",
    "- Letters, third row",
    "ab01",
    "ab02",
    "ab03",
    "ab04",
    "ab05",
    "ab06",
    "ab07",
    "ab08",
    "ab09",
    "ab10",
    "- Pinky keys",
    "ae11",
    "ae12",
    "ae13",
    "ad11",
    "ad12",
    "ac11",
    "ab11",
    "tlde",
    "bksl",
    "lsgt",
    "- Space bar",
    "spce",
]
