# xkbcommon path discovery — root vs user install report

Investigation of the Wayland install regression where `xkalamine install` as
root followed by `xkalamine install` as user produces a broken layout. Per
`~/AGENTS.md`, the high-level patch in kalamine is a workaround; the real
defect lives in libxkbcommon and must be fixed there transparently.

## Branches involved

- `fix/xkalamine-wayland` — high-level workaround in kalamine. Commits
  `d24c665` (fix) and `a5f7353` (tests).
- `feat/xkbcommon-analysis` — vendors libxkbcommon at
  `third_party/xkbcommon`, pinned at fork commit `b1a8c03c` which adds
  `doc/kalamine-user-space-rules-issue.md` (no source changes yet).

## What kalamine does on each side

`kalamine/xkb_manager.py:21-50` defines two roots:

- `XKB_ROOT = $XKB_CONFIG_ROOT or /usr/share/X11/xkb` — used when `root=True`
- `XKB_HOME = $XDG_CONFIG_HOME/xkb` (fallback `$HOME/.config/xkb`) — used in
  user mode

`XKBManager.__init__` (`xkb_manager.py:71-73`) selects one of the two as
`_rootdir`. CLI (`cli_xkb.py:95-131`) instantiates `XKBManager(root=True)`
under sudo and `XKBManager()` under user mode.

Files written:

- system mode: `<root>/symbols/<locale>` and `<root>/rules/evdev.xml`
  (`xkb_manager.py:308`, `:156`, `:392`).
- user mode (after `d24c665`): same layout symbols + `evdev.xml` index, but
  **no** `rules/evdev` text file (commented at `xkb_manager.py:149-154`).

The previous user-mode behavior was to write `~/.config/xkb/rules/evdev` with:

```
include %S/evdev
```

That single line is what triggers the bug.

## Path discovery in libxkbcommon

`xkb_context_include_path_append_default()`
(`third_party/xkbcommon/src/context.c:243-340`) constructs the include path in
this fixed order:

1. `$XDG_CONFIG_HOME/xkb` or `$HOME/.config/xkb` — `context.c:253-269`
2. `$HOME/.xkb` (legacy) — `context.c:271-277`
3. `XKB_CONFIG_EXTRA_PATH` or `DFLT_XKB_CONFIG_EXTRA_PATH` — `context.c:279`
4. Extension dirs (versioned, unversioned) — `context.c:285-307`
5. `XKB_CONFIG_ROOT` or `DFLT_XKB_CONFIG_ROOT` — `context.c:317-319`
6. Fallback `DFLT_XKB_LEGACY_ROOT` — `context.c:330-336`

`FindFileInXkbPath()` (`src/xkbcomp/include.c:320-363`) walks this list and
returns the **first match**, so a user-space `rules/evdev` always shadows the
system one.

`%S` expansion happens in `expand_percent()`
(`src/xkbcomp/include.c:223-233`); it appends
`xkb_context_include_path_get_system_path(ctx)` + `/` + typeDir. That getter
(`context.c:228-237`) reads `XKB_CONFIG_ROOT` or falls back to
`DFLT_XKB_CONFIG_ROOT`.

## The actual failure

`matcher_include()` (`src/xkbcomp/rules.c:574-679`) processes the user file
`~/.config/xkb/rules/evdev`:

1. Sees `include %S/evdev`, calls `expand_path` → expanded absolute path
   `/usr/share/X11/xkb/rules/evdev`.
2. Takes the absolute-path branch (`rules.c:610`), calls
   `fopen(stmt_file, "rb")` on line 629.
3. Reads via `read_rules_file` (line 655). When that returns false, the
   absolute branch breaks out of the loop (line 666) — **no fallback search,
   no warning surfaced at default log level**.

The repro plan in
`third_party/xkbcommon/doc/kalamine-user-space-rules-issue.md` lists three
candidate causes:

1. `%S` mis-expansion in the user-rules entry context.
2. Include path stack reduced or reordered when invoked from a user rules
   file (vs. keymap compile entry).
3. Errors swallowed at default verbosity (`rules.c:660-678` only logs at
   error level after the loop, and the messages don't reach typical Wayland
   compositor stdout).

## What the investigation actually found

Building the vendored fork and reproducing per the dev-notes plan revealed
two separate problems, not one:

### Problem A — diagnostic mislabel in xkbcommon (real bug, fixed)

`xkb_resolve_rules` in `src/xkbcomp/rules.c:2007-2049` reuses the same
`path[PATH_MAX]` buffer for the main rules file lookup and for the
`xkb_resolve_partial_rules` `.pre`/`.post` probes. `FindFileInXkbPath` calls
`snprintf` into that buffer on every probe, so when no `<rules>.pre` file
exists the buffer ends up holding the last attempted (non-existent)
`<rules>.pre` path. `read_rules_file` is then called with the main rules
`FILE *` but the stale `.pre` filename, producing diagnostics like:

```
ERROR: /usr/share/xkeyboard-config-2/rules/evdev.pre:2:1: unexpected token
ERROR: Error while parsing XKB rules "/usr/share/xkeyboard-config-2/rules/evdev.pre"
```

— even though no `evdev.pre` exists on disk and the file actually being
parsed is `~/.config/xkb/rules/evdev`. This mislabel is exactly what
prompted the dev-notes' "%S expansion silently fails" hypothesis: the
filename in the error pointed at a phantom file the user couldn't inspect.

**Fix:** commit `6abfad34` on `third_party/xkbcommon` branch
`fix/silent-include-failure` — give partial-rules its own
`partial_path[PATH_MAX]`, leaving the main rules `path` untouched. Also
adds `log_warn`/`log_dbg` lines around `%`-expansion and absolute-path
include opens (`src/xkbcomp/rules.c`) so include failures surface at default
verbosity. ABI-transparent, no public API changes.

**Regression test:** commit `cd8cc2a1` adds
`test/data/rules/inc-no-bang` and a new case in
`test/rules-file-includes.c` that captures the log via `log_fn` and asserts
the error names `inc-no-bang`, never `inc-no-bang.pre`. All 30 non-X11
tests in the meson suite pass; the 2 failing tests need Xvfb (unrelated).

### Problem B — dev-notes' "include silently fails" theory (not reproducible)

With the canonical syntax `! include %S/evdev` (which is what
`kalamine/xkb_manager.py:135-167` has *always* written — verified in git
history), the include chain works correctly under the patched fork:

```
$ XDG_CONFIG_HOME=/tmp/xkbrepro/xkb-config xkbcli compile-keymap \
    --rules evdev --layout fr --variant bepo-extended
xkb_symbols "pc_fr(bepo-extended)_inet(evdev)" { ... }   # success
```

Without the leading `!`, the rules grammar (rules.c:1733-1758) rejects
bare `include` as `unexpected token` — that is correct grammar
enforcement, not a bug. The dev-notes' line 25 ("docs show examples …
`include %S/evdev`") dropped the bang and built the wrong mental model.

So the "silent" failure was never silent — it was a real syntax error,
just reported under a phantom `.pre` filename due to Problem A.

### What this means for `d24c665` (kalamine workaround)

Because kalamine's user-mode include text was already syntactically
correct, restoring user-mode `rules/evdev` writes would also work fine
under the patched xkbcommon. But `d24c665` (omit the user `rules/evdev`,
let xkbcommon fall through to system rules) is a perfectly valid design
choice on its own — simpler, fewer files, identical runtime behavior. No
revert needed; per `~/AGENTS.md` the legacy must not break, and `d24c665`
already works. Leaving it in place.

## Status

- xkbcommon diagnostic bug — **fixed** on
  `third_party/xkbcommon@fix/silent-include-failure` (commits `6abfad34`,
  `cd8cc2a1`).
- xkbcommon submodule pin — still on `b1a8c03c` on the kalamine
  `feat/xkbcommon-analysis` branch. Bump that pin to `cd8cc2a1` (or merge
  the fix branch and bump) when ready to land.
- Kalamine `fix/xkalamine-wayland` — keep as-is.
- Suggested next: send the xkbcommon fix branch upstream as a PR. The fix
  is general (not kalamine-specific) and the regression test is
  self-contained.

## Reference

- `kalamine/cli_xkb.py:88-131` — install flow, root vs user dispatch
- `kalamine/xkb_manager.py:21-167` — path roots, file write sites
- `tests/test_xkalamine.py:35-73` — covers Xorg/Wayland install dispatch but
  not the root-then-user sequence
- `third_party/xkbcommon/src/context.c:228-340` — include path construction
- `third_party/xkbcommon/src/xkbcomp/include.c:195-363` — `%`-expansion and
  file lookup
- `third_party/xkbcommon/src/xkbcomp/rules.c:574-679` — rules-file include
  matcher (silent-failure site)
- `third_party/xkbcommon/doc/kalamine-user-space-rules-issue.md` — existing
  investigation plan
