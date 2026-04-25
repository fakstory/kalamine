from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..layout import KeyboardLayout


META_FIELDS = (
    "name",
    "name8",
    "variant",
    "locale",
    "description",
    "author",
    "url",
    "license",
    "version",
    "geometry",
)


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return _quote(str(value))


def merged_toml(layout: "KeyboardLayout") -> str:
    """Serialize a (possibly merged) layout as a standalone TOML descriptor."""
    lines = []
    for field in META_FIELDS:
        if field in layout.meta:
            lines.append(f"{field:<12}= {_quote(str(layout.meta[field]))}")
    lines.append("")

    def block(name: str, rows: list) -> None:
        lines.append(f"{name} = '''")
        lines.extend(rows)
        lines.append("'''")
        lines.append("")

    if layout.has_altgr and layout.has_1dk:
        block("base", layout.base)
        block("altgr", layout.altgr)
    elif layout.has_altgr:
        block("full", layout.full)
    else:
        block("base", layout.base)

    return "\n".join(lines)


def write_split_toml(layout: "KeyboardLayout", layout_path, out_dir) -> None:
    """Write base/extended/merged TOML files when requested."""
    from pathlib import Path

    from ..layout import resolve_parent_path

    layout_path = Path(layout_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    parent_path = resolve_parent_path(layout_path)
    if parent_path:
        (out_dir / parent_path.name).write_text(
            parent_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (out_dir / layout_path.name).write_text(
            layout_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
    else:
        (out_dir / layout_path.name).write_text(
            layout_path.read_text(encoding="utf-8"), encoding="utf-8"
        )

    merged_name = f"{layout.meta['fileName']}_merged.toml"
    (out_dir / merged_name).write_text(merged_toml(layout), encoding="utf-8")
