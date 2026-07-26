# Driftmap

An interactive Wayland minimap for
[Driftwm](https://github.com/malbiruk/driftwm). Driftmap follows the compositor's
infinite canvas through its IPC state subscription and renders one Layer Shell
overlay on every monitor.

The compact map is fully click-through. It shows normal, focused, and suspended
windows, the viewport frames of all connected outputs, Driftwm bookmarks, and
the canvas home point.

<img width="960" height="540" alt="Driftmap screenshot" src="https://github.com/user-attachments/assets/19332087-7939-4c80-8571-acb5f5e5c4ff" />

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
driftmap --toggle 2 242424cc
```

The first argument is the width and height multiplier. The second is the canvas
color in `RRGGBBAA` format. The example changes a `320×180` map into `640×360`
and uses `#242424` with 80% opacity for that profile's canvas.

The interactive profile keeps the remaining startup colors, position, zoom,
radii, and other settings. Calling the toggle again returns to the compact
click-through profile. Switching profiles resets the minimap's interactive
camera, zoom animation, drag state, and snap state.

### Interactive fullscreen mode

```sh
driftmap --toggle-fullscreen 242424e6
```

The argument is the fullscreen profile's canvas color in `RRGGBBAA` format.
The surface is anchored to all four output edges and sized by the compositor,
so it covers the monitor without gaps. Canvas corner rounding is forced off in
this mode.

Calling the command again returns to the compact click-through profile.
Fullscreen mode remains visible even when Driftwm has a fullscreen client on
that output.

## Interactive controls

Controls are enabled in scaled and fullscreen modes:

| Input | Result |
| --- | --- |
| Left click a window | Focus the window and center the Driftwm viewport on it |
| Left click a bookmark | Run `go-to-bookmark` for that bookmark |
| Left click home | Run `home-toggle` |
| Middle click a window | Close that exact window by its stable Driftwm ID |
| Right-drag a window | Move it on the real Driftwm canvas |
| Left-drag empty space | Pan the minimap's independent camera |
| Two-finger scroll over empty space | Pan the minimap |
| Mouse wheel | Smoothly zoom the minimap around its center |

Zoom uses the same frame-rate-independent interpolation curve and default
animation speed as Driftwm. Panning and zooming affect only the minimap; they do
not move the real Driftwm viewport.

Window clicks and drags use stable window IDs from Driftwm IPC, so overlapping
windows and suspended stand-ins can be targeted individually. Bookmark and home
hitboxes are highlighted when the pointer enters them.

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
  "driftmap --snap 8",
]

[keybindings]
"mod+u" = "spawn driftmap --show"
"mod+i" = "spawn driftmap --toggle 2 242424cc"
"mod+o" = "spawn driftmap --toggle-fullscreen 242424e6"
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

--canvas RRGGBBAA
    Canvas color and opacity. Default: 2424244d.

--window RRGGBBAA
    Normal window color and opacity. Default: b8bfd14d.

--active-window RRGGBBAA
    Focused window color and opacity. Default: 59b8ff4d.

--suspended RRGGBBAA
    Suspended stand-in color and opacity. Default: 8f94a64d.

--frame RRGGBBAA
    Output viewport-frame color and opacity. Default: f6e38066.

--frame-width PX, --viewport-width PX
    Viewport outline width. Default: 1.

--bookmarks RRGGBBAA
    Bookmark point color and opacity. Default: ff8a6699.

--home RRGGBBAA
    Home point color and opacity. Default: 66e0a399.

--bookmark-hitbox OPACITY PX
    Bookmark hover-highlight opacity and extra hitbox radius.
    Default: 0.3 8.

--home-hitbox OPACITY PX
    Home hover-highlight opacity and extra hitbox radius.
    Default: 0.3 8.

--dot-radius PX
    Radius shared by bookmark and home points. Zero disables the points and
    their hitboxes. Default: 2.

--canvas-radius PX, --radius PX
    Canvas corner radius. Zero disables rounding. Default: 12.

--window-radius PX
    Window corner radius. Default: 3.
```

Colors use eight hexadecimal characters in `RRGGBBAA` order. The final byte is
the alpha channel: `00` is transparent and `ff` is opaque. Do not include `#`,
so shell quoting is unnecessary.

Complete example:

```sh
driftmap \
  --width 320 \
  --height 180 \
  --zoom 0.15 \
  --position bottom-left \
  --margin 10 \
  --canvas 2424244d \
  --window b8bfd14d \
  --active-window 59b8ff4d \
  --suspended 8f94a64d \
  --frame f6e38066 \
  --frame-width 1 \
  --bookmarks ff8a6699 \
  --home 66e0a399 \
  --bookmark-hitbox 0.3 8 \
  --home-hitbox 0.3 8 \
  --dot-radius 2 \
  --canvas-radius 12 \
  --window-radius 3 \
  --snap 8 \
 # --show-fullscreen \
 # --snap-off   #can not be use with --snap <PX>
```

Run `driftmap --help` for the generated command-line reference.

## Stopping Driftmap

Visibility toggling does not terminate the process. Stop it with:

```sh
pkill -f driftmap
```

https://github.com/user-attachments/assets/01435579-189a-4176-ae45-6ff9a45c2b26
