"""xkbcomp acceptance test for the 2dk vmod design.

Wraps a generated XKB symbols file into a complete `xkb_keymap { ... }`
shell and runs `xkbcomp -xkb` against it. Catches syntax errors and
unmapped-vmod warnings before they hit a live desktop session.

Skipped automatically when `xkbcomp` is not on PATH (e.g. macOS / Windows
CI runners).
"""

import shutil
import subprocess
import textwrap
import tomllib
from pathlib import Path

import pytest

from kalamine import KeyboardLayout
from kalamine.generators.xkb import xkb_table


FIXTURE_2DK = Path(__file__).parent / "fixtures" / "2dk.toml"

XKBCOMP = shutil.which("xkbcomp")


def _wrap_keymap(symbols_body: str) -> str:
    """Build a complete xkb_keymap source from a symbols-block body."""
    indented = textwrap.indent(symbols_body, "        ")
    return textwrap.dedent(
        """\
        xkb_keymap {{
            xkb_keycodes  {{ include "evdev"    }};
            xkb_types     {{ include "complete" }};
            xkb_compat    {{ include "complete" }};

            xkb_symbols "kalamine_2dk_test" {{
                name[group1] = "kalamine 2dk test";
        {body}
                modifier_map Mod3 {{ <HYPR> }};
                modifier_map Mod5 {{ <LVL3> }};
            }};
        }};
        """
    ).format(body=indented)


@pytest.mark.skipif(XKBCOMP is None, reason="xkbcomp not installed")
def test_2dk_xkbcomp_accepts_generated_keymap(tmp_path):
    with FIXTURE_2DK.open("rb") as f:
        layout = KeyboardLayout(tomllib.load(f))

    body = "\n".join(xkb_table(layout, xkbcomp=False))
    keymap_text = _wrap_keymap(body)

    src = tmp_path / "keymap.xkb"
    src.write_text(keymap_text)
    out = tmp_path / "keymap.compiled"

    result = subprocess.run(
        [XKBCOMP, "-xkb", "-w", "0", str(src), str(out)],
        capture_output=True,
        text=True,
    )

    # Surface stderr in the assertion message so failures are diagnosable.
    assert result.returncode == 0, (
        f"xkbcomp rejected the 2dk keymap.\n"
        f"--- stderr ---\n{result.stderr}\n"
        f"--- keymap (first 80 lines) ---\n"
        + "\n".join(keymap_text.splitlines()[:80])
    )
    # No silent warnings either — strict.
    assert "Warning" not in result.stderr, (
        f"xkbcomp emitted warnings on the 2dk keymap:\n{result.stderr}"
    )


@pytest.mark.skipif(XKBCOMP is None, reason="xkbcomp not installed")
def test_legacy_intl_xkbcomp_unaffected(tmp_path):
    """Regression: the existing intl layout must still compile clean."""
    from .util import get_layout_dict

    layout = KeyboardLayout(get_layout_dict("intl"))
    body = "\n".join(xkb_table(layout, xkbcomp=False))
    keymap_text = _wrap_keymap(body)

    src = tmp_path / "keymap.xkb"
    src.write_text(keymap_text)
    out = tmp_path / "keymap.compiled"

    result = subprocess.run(
        [XKBCOMP, "-xkb", "-w", "0", str(src), str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"xkbcomp rejected the intl keymap (regression).\n"
        f"stderr:\n{result.stderr}"
    )
