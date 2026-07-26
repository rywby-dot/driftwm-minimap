# Driftmap

An interactive Wayland minimap for
[Driftwm](https://github.com/malbiruk/driftwm). Driftmap follows the compositor's
infinite canvas through its IPC state subscription and renders one Layer Shell
overlay on every monitor.

The compact map is fully click-through. It shows normal, focused, and suspended
windows, plus the viewport frames of all connected outputs.

<img width="960" height="540" alt="Driftmap screenshot" src="https://github.com/user-attachments/assets/19332087-7939-4c80-8571-acb5f5e5c4ff" />

https://github.com/user-attachments/assets/00316dc0-1e01-428c-b349-e8ed278705a7

## Installation

```sh
git clone https://github.com/rywby-dot/driftwm-minimap.git
cd driftwm-minimap
pipx install .
```

Required at runtime:

- Driftwm;
- Python 3.11 or newer;
- GTK 4 and PyGObject;
- Cairo/Pycairo;
- gtk4-layer-shell.

Update an existing installation with:

```sh
cd driftwm-minimap
git pull
pipx upgrade driftwm-minimap
```

## Starting the map

Start Driftmap once inside a running Driftwm session:

```sh
driftmap
```

All appearance, placement, and snap flags are startup settings, just like
`--width`. To change them, stop Driftmap and start it again with the desired
arguments.

Running plain `driftmap` again does not hide or reconfigure an existing map.

## Runtime commands

Only the following commands modify an already-running instance. They use a
small local control socket, so switching is immediate and does not reload GTK.

### Show or hide

```sh
driftmap --show
```

Each invocation toggles visibility without terminating the background process.

### Interactive scaled mode

```sh
driftmap --toggle 2 0.8
```

`2` is the width and height multiplier; `0.8` is the opacity from `0` to `1`.
The example changes a `320×180` map into `640×360` and sets the canvas,
windows, and viewport frames to `0.8` opacity.

The interactive profile keeps the startup colors, position, zoom, radii, and
other settings. Calling the same toggle again returns to the compact
click-through profile. Switching profiles resets the minimap's interactive
camera, zoom animation, drag state, and snap state.

<img width="960" height="540" alt="image" src="https://github.com/user-attachments/assets/c5f911bd-5121-4341-8ed3-a3150baab07c" />

### Interactive fullscreen mode

```sh
driftmap --toggle-fullscreen 0.9
```

The argument is the canvas, window, and viewport-frame opacity. The surface is
anchored to all four output edges and sized by the compositor, so it covers the
monitor without gaps. Canvas corner rounding is forced off in this mode.

Calling the command again returns to the compact click-through profile.
Fullscreen mode remains visible even when Driftwm has a fullscreen client on
that output.

<img width="960" height="540" alt="image" src="https://github.com/user-attachments/assets/5e285a97-d0c8-4e02-bf1b-e4e3fc348dfd" />

## Interactive controls

Controls are enabled in scaled and fullscreen modes:

| Input | Result |
| --- | --- |
| Left click a window | Focus the window and center the Driftwm viewport on it |
| Middle click a window | Close that exact window by its stable Driftwm ID |
| Right-drag a window | Move it on the real Driftwm canvas |
| Left-drag empty space | Pan the minimap's independent camera |
| Two-finger scroll over empty space | Pan the minimap |
| Mouse wheel | Smoothly zoom the minimap around its center |

Zoom uses the same frame-rate-independent interpolation curve and default
animation speed as Driftwm. Panning and zooming affect only the minimap; they do
not move the real Driftwm viewport.

Window clicks and drags use stable window IDs from Driftwm IPC, so overlapping
windows and suspended stand-ins can be targeted individually.

## Window snapping

Right-button window dragging supports magnetic snapping. Driftmap reads these
values from `[snap]` in `~/.config/driftwm/config.toml`:

```toml
[snap]
enabled = true
gap = 12.0
distance = 24.0
break_force = 32.0
corners = true
centers = true
```

- `gap` is the canvas-space gap between neighboring windows.
- `break_force` controls how far a held snap must be dragged before release.
- `corners` enables parallel-edge alignment.
- `centers` enables midpoint alignment.

The minimap activation distance is configured separately at startup in minimap
screen pixels:

```sh
driftmap --snap 8
```

Disable snapping only for minimap drags with:

```sh
driftmap --snap-off
```

`--snap` and `--snap-off` are mutually exclusive. They are startup settings and
do not reconfigure a running instance.

## Fullscreen clients

By default, the compact or scaled map is hidden on an output containing a
fullscreen window. Keep it visible with the startup flag:

```sh
driftmap --show-fullscreen
```

This flag is not needed for `--toggle-fullscreen`, which always shows its
fullscreen map.

## Driftwm configuration

Example autostart and keybindings:

```toml
autostart = [
  "driftmap",
]

[keybindings]
"mod+u" = "spawn driftmap --show"
"mod+i" = "spawn driftmap --toggle 2 0.8"
"mod+o" = "spawn driftmap --toggle-fullscreen 0.9"
```

## Appearance and placement

```text
--width PX
    Compact map width. Default: 320.

--height PX
    Compact map height. Default: 180.

--zoom F
    Canvas scale relative to the current Driftwm viewport. Default: 0.15.

--position POSITION
    bottom, bottom-left, bottom-right, left, right, top, top-left, or top-right.
    Default: bottom-left.

--margin PX
    Distance from anchored screen edges. Default: 10.

--canvas-color HEX, --bg-color HEX
    Canvas background color. Default: #242424.

--canvas-opacity F, --bg-opacity F
    Compact canvas opacity from 0 to 1. Default: 0.3.

--window-color HEX
    Normal window color. Default: #b8bfd1.

--active-window-color HEX, --focused-color HEX
    Focused window color. Default: #59b8ff.

--suspended-color HEX
    Suspended stand-in color. Default: #8f94a6.

--window-opacity F
    Compact window opacity from 0 to 1. Default: 0.3.

--frame-color HEX, --viewport-color HEX
    Output viewport-frame color. Default: #f6e380.

--frame-opacity F, --viewport-opacity F
    Compact viewport-frame opacity from 0 to 1. Default: 0.4.

--frame-width PX, --viewport-width PX
    Viewport outline width. Default: 1.

--canvas-radius PX, --radius PX
    Canvas corner radius. Zero disables rounding. Default: 12.

--window-radius PX
    Window corner radius. Default: 3.
```

Colors accept six-digit hexadecimal values. Quote values beginning with `#` in
the shell.

Complete example:

```sh
driftmap \
  --width 320 \
  --height 180 \
  --zoom 0.15 \
  --position bottom-left \
  --margin 10 \
  --canvas-color '#242424' \
  --canvas-opacity 0.3 \
  --window-color '#b8bfd1' \
  --active-window-color '#59b8ff' \
  --suspended-color '#8f94a6' \
  --window-opacity 0.3 \
  --frame-color '#f6e380' \
  --frame-opacity 0.4 \
  --frame-width 1 \
  --canvas-radius 12 \
  --window-radius 3 \
  --snap 8 \
# --show-fullscreen \   #<-- show map when fullscreen  
# --snap-off   #<-- can not be use with --snap <PX>
```

Run `driftmap --help` for the generated command-line reference.

## Stopping Driftmap

Visibility toggling does not terminate the process. Stop it with:

```sh
pkill -f driftmap
```
