"""Trigger-cell fallback for generators that can't express 2dk / 3dk.

When a layout declares `2dk` / `3dk` overlays, the trigger-key cells
hold the doubled-marker string (`++`, `--`, `&&`, `§§`) in the BASE
layer. Generators that don't implement the dk machinery (currently
macOS .keylayout and Windows .klc) drop the overlay layers entirely
and substitute each marker cell with its first character — `++` → `+`,
`§§` → `§`, etc. This keeps the generated layout coherent on those
platforms instead of leaving the trigger key blank.

See `.docs/2dk.md` ("Trigger-cell fallback") for the design rationale.

This module also owns the lazy import-free warning rendering for
generators that need to announce the dropped layers.
"""

from typing import TYPE_CHECKING, Dict, Iterable

if TYPE_CHECKING:
    from ..layout import KeyboardLayout

from ..utils import DK_LAYERS, Layer


def _marker_set() -> Dict[str, str]:
    """marker_string → fallback char (first char of the doubled marker)."""
    out: Dict[str, str] = {}
    for _, _, base_marker, altgr_marker, _, _ in DK_LAYERS:
        out[base_marker] = base_marker[0]
        out[altgr_marker] = altgr_marker[0]
    return out


_MARKERS = _marker_set()


def apply_fallback_to_layers(layout: "KeyboardLayout", layers: Iterable[Layer]) -> None:
    """In-place: replace any dk-marker cell with its fallback char.

    Generators call this *before* iterating layers when they can't emit
    the 2dk/3dk overlays. Idempotent: a layout without markers is
    unaffected; a layout with markers loses the trigger semantics but
    keeps a sensible visible glyph.
    """
    for layer in layers:
        layer_dict = layout.layers[layer]
        for key, value in list(layer_dict.items()):
            if value in _MARKERS:
                layer_dict[key] = _MARKERS[value]


def has_any_dk_overlay(layout: "KeyboardLayout") -> bool:
    return bool(getattr(layout, "has_dk2", False) or getattr(layout, "has_dk3", False))


def warning_text(target: str) -> str:
    """Stable text used by tests."""
    return f"WARN: 2dk/3dk overlays not supported on {target} — layers dropped, trigger keys fall back to marker character."
