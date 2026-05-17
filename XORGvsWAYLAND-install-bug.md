# xkalamine install bug — XOrg vs Wayland

## What actually broke

The installed `xkalamine` is stale and crashes on `bepo-extended.toml`:

```
File ".../kalamine/utils.py", line 10, in hex_ord
    return hex(ord(char))[2:].zfill(4)
TypeError: ord() expected a character, but string of length 2 found
```

- `/home/fakstory/.local/share/uv/tools/kalamine/lib/python3.13/site-packages/kalamine/generators/xkb.py`
  is dated **May 7** — pre-dates the 2dk_vmod fix.
- Local dev tree `kalamine/kalamine/generators/xkb.py` is May 8 with
  `c5139e3 fix(2dk): altgr-resident triggers + decoupled lock semantics`.
  Running `kalamine/.venv/bin/xkalamine install --yes …/bepo-extended.toml`
  succeeds.
- katanyx's `_ensure_peer_tools` installs xkalamine from
  `git+ssh://…/fakstory/kalamine.git@feat/extended-keyboard`
  (`katanyx/__init__.py:90`) — and that branch **lags `feat/main`**:
  it is missing the merges for `release/feat/1dk_lock`,
  `release/feat/2dk_vmod` (which contains `c5139e3`),
  `release/fix/wayland-install-clean`, and
  `release/fix/xkbcommon-analysis`.

So the TypeError is **not** a wayland-install bug. The fix already exists
on `feat/main`; the installed copy just doesn't have it because the
katanyx pin points at a stale branch.

## Side note — install-path traceback

The install actually attempted the root/system-wide path first and hit
`PermissionError: /usr/share/X11/xkb/rules/base.xml` — that's the EAFP
fallback in `cli_xkb.py:93-119`. On Wayland it then falls back to
user-space, but on XOrg it tells you to re-run with sudo. The
`TypeError` (the actual blocker) happens during the user-space retry:
same stale code, same crash.

## Fix

The `fix/xkalamine-wayland` branch is **not** where the bug lives — it
only carries `d24c665 fix: xkalamine install/remove on Wayland` plus its
tests, unrelated to the 2dk hex_ord crash.

The fix is upstream of kalamine, in katanyx:

- Bump `_KALAMINE_GIT_URL` in `katanyx/src/katanyx/__init__.py:90`
  from `…@feat/extended-keyboard` to `…@feat/main` (or to a release
  branch that includes the 2dk_vmod merge).
- Re-run `_ensure_peer_tools` so uv reinstalls the tool from the new
  ref.
