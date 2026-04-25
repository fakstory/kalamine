# Fix xkalamine Wayland user-space install

## TL;DR

`xkalamine install` works on both Xorg and Wayland **with sudo**. The bug occurred only when running without sudo on Wayland, which created broken user-space config due to a faulty `rules/evdev` include delegation.

## Summary

When `xkalamine install` runs without sudo on Wayland, it creates:

```
~/.config/xkb/rules/evdev      ← BROKEN (! include %S/evdev delegation fails)
~/.config/xkb/rules/evdev.xml  ← CORRECT
~/.config/xkb/symbols/<locale>  ← CORRECT
```

The `rules/evdev` file tries to delegate to system rules via `! include %S/evdev`, but this delegation **does not work reliably** in xkbcommon. The result: installed layouts produce wrong keys.

**Solution implemented:**
1. **Don't create `rules/evdev`** — xkbcommon falls through to system rules automatically
2. **Block non-root on Xorg** — always require sudo
3. **Allow user-space on Wayland** — works now without the broken file
4. **Confirmation prompt** — ask before user-space install; use `-y` to skip
5. **Better root detection** — check `os.geteuid() == 0` instead of XKB writability (fixes `sudo -u` case)

## Install paths on Linux

| Session | Permissions | Install path | Works? |
|---------|------------|------------|--------|
| Xorg + root | sudo | `/usr/share/X11/xkb/` | Yes |
| Xorg without root | sudo required | — | No (must use sudo) |
| Wayland + root | sudo | `/usr/share/X11/xkb/` | Yes |
| Wayland without root | user-space | `~/.config/xkb/` | **Yes** (fixed) |

## Changes

- `kalamine/cli_xkb.py` — install/remove logic, confirmation prompt, root detection
- `kalamine/xkb_manager.py` — no longer create `rules/evdev` in user-space
- `kalamine/xkb_manager.py` — improved Wayland detection (check `/proc` for compositor)
- `tests/test_xkalamine.py` — new tests

## Testing

```bash
pytest tests/test_xkalamine.py -v
# 5 passed
```