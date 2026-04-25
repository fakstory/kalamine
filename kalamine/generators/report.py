"""Generate a merged_report.md summarising key changes in extended layouts."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..layout import KeyboardLayout

# Human-readable row labels derived from the key name prefix.
_ROW_LABEL = {
    "ae": "Number row",
    "ad": "Top row",
    "ac": "Home row",
    "ab": "Bottom row",
    "tl": "Tilde/backtick",
    "bk": "Backslash",
    "ls": "ISO key (lsgt)",
    "sp": "Space bar",
}

# Ordered sections matching LAYER_KEYS groupings.
_SECTION_ORDER = [
    ("ae", "Number row"),
    ("ad", "Top row (QWERTY row)"),
    ("ac", "Home row"),
    ("ab", "Bottom row"),
    ("tl", "Tilde / Backtick (tlde)"),
    ("bk", "Backslash (bksl)"),
    ("ls", "ISO key (lsgt)"),
    ("sp", "Space bar"),
]

# Layer display order and labels for the report table.
_LAYER_ORDER = [
    ("base", "Base"),
    ("shift", "Shift"),
    ("altgr", "AltGr"),
    ("altgr_shift", "AltGr+Shift"),
    ("1dk", "1dk"),
    ("1dk_shift", "1dk+Shift"),
]


def _char_repr(s: str) -> str:
    """Return a display-friendly representation of a character value."""
    if not s:
        return "*(none)*"
    # Dead key prefix
    if s.startswith("*") and len(s) == 2:
        return f"`*{s[1]}` (dead)"
    if len(s) == 1:
        code = f"U+{ord(s):04X}"
        if s.isprintable() and s not in ("`", "|", "\\"):
            return f"`{s}` ({code})"
        return code
    return repr(s)


def _key_section(key_name: str) -> str:
    """Return the two-letter prefix used for section grouping."""
    return key_name[:2].lower()


def merged_report(layout: "KeyboardLayout") -> str:
    """Return a Markdown report of all key changes introduced by this extended layout.

    Only generated (and meaningful) when the layout was built from an ``extends``
    descriptor that uses ``*_diff`` overlays — i.e. when ``layout.key_diffs`` is
    non-empty.
    """
    diffs = layout.key_diffs
    meta = layout.meta

    lines = []

    # ------------------------------------------------------------------ header
    lines.append(f"# {meta.get('name', 'layout')} — key change report")
    lines.append("")
    parent_name = meta.get("extends", "parent layout")
    lines.append(
        f"Extended from: **{parent_name}**  "
    )
    lines.append(
        f"Geometry: **{meta.get('geometry', '?')}** | "
        f"Version: **{meta.get('version', '?')}**"
    )
    lines.append("")

    if not diffs:
        lines.append("*No keys were changed from the parent layout.*")
        return "\n".join(lines)

    total_changed = len(diffs)
    lines.append(
        f"**{total_changed} key{'s' if total_changed != 1 else ''} changed** "
        f"compared to the parent layout."
    )
    lines.append("")

    # ----------------------------------------------- group keys by board row
    # Build section → list of (key_name, layer_changes) pairs.
    sections: dict = {}
    for key_name, layer_changes in sorted(diffs.items()):
        prefix = _key_section(key_name)
        sections.setdefault(prefix, []).append((key_name, layer_changes))

    # -------------------------------------------------- emit one section each
    for prefix, section_title in _SECTION_ORDER:
        if prefix not in sections:
            continue

        lines.append(f"## {section_title}")
        lines.append("")

        # Table header — only include layer columns that actually appear
        used_layers = set()
        for _, layer_changes in sections[prefix]:
            used_layers.update(layer_changes.keys())
        ordered_layers = [
            (lkey, llabel)
            for lkey, llabel in _LAYER_ORDER
            if lkey in used_layers
        ]

        header = "| Key | " + " | ".join(llabel for _, llabel in ordered_layers) + " |"
        sep = "|-----|" + "|".join("---" for _ in ordered_layers) + "|"
        lines.append(header)
        lines.append(sep)

        for key_name, layer_changes in sorted(sections[prefix]):
            cells = []
            for lkey, _ in ordered_layers:
                if lkey in layer_changes:
                    parent_val, child_val = layer_changes[lkey]
                    cells.append(
                        f"{_char_repr(parent_val)} → {_char_repr(child_val)}"
                    )
                else:
                    cells.append("—")
            lines.append(f"| `{key_name}` | " + " | ".join(cells) + " |")

        lines.append("")

    # --------------------------------------------- alphabetical summary list
    lines.append("## Summary: all changed keys")
    lines.append("")
    lines.append(
        "| Key | Layers changed |"
    )
    lines.append("|-----|----------------|")
    for key_name in sorted(diffs):
        layer_names = ", ".join(
            llabel
            for lkey, llabel in _LAYER_ORDER
            if lkey in diffs[key_name]
        )
        lines.append(f"| `{key_name}` | {layer_names} |")
    lines.append("")

    return "\n".join(lines)
