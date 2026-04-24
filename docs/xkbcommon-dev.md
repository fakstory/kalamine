# Using the bundled libxkbcommon

This repo vendors libxkbcommon as a git submodule at `third_party/xkbcommon`.
You can build it locally and point tooling (like `xkbcli`) to it instead of the
system-wide library. This is primarily for investigating xkbcommon behavior
related to `xkalamine` user-space installs.

## Initialize the submodule

```bash
git submodule update --init --recursive
```

## Build libxkbcommon

```bash
cd third_party/xkbcommon
meson setup build
meson compile -C build
```

Optional: run tests

```bash
meson test -C build
```

## Use the bundled library for xkbcli

This will run `xkbcli` from the submodule build directory and ensure the
libxkbcommon it uses is the locally-built one.

```bash
LD_LIBRARY_PATH="$(pwd)/third_party/xkbcommon/build" \
  "$(pwd)/third_party/xkbcommon/build/xkbcli" info
```

## Use the bundled library with custom config paths

You can force xkbcommon to look at specific config roots when testing rules
resolution. Example:

```bash
XKB_CONFIG_ROOT=/usr/share/X11/xkb \
XKB_CONFIG_EXTRA_PATH=/etc/xkb \
XDG_CONFIG_HOME="$HOME/.config" \
LD_LIBRARY_PATH="$(pwd)/third_party/xkbcommon/build" \
  "$(pwd)/third_party/xkbcommon/build/xkbcli" compile-keymap \
    --rules evdev --layout fr --variant bepo-extended --test
```

## Notes

- Kalamine itself does not link to libxkbcommon; compositors and `xkbcli` do.
- To affect system-wide behavior, you must install the built library in a
  system path or configure the compositor to use it.
