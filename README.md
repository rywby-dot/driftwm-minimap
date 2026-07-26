# Driftmap

Wayland overlays minimap for [Driftwm](https://github.com/malbiruk/driftwm). Shows semi-transparent panels using Layer Shell's OVERLAY layer — sits above all windows and panels, fully click-through


<img width="960" height="540" alt="ScreenShot-2026-07-26_14-39-43" src="https://github.com/user-attachments/assets/19332087-7939-4c80-8571-acb5f5e5c4ff" />

# Install
```
git clone https://github.com/rywby-dot/driftwm-minimap.git
cd driftwm-minimap
pipx install .
```
To update run
```
cd driftwm-minimap
git pull
pipx upgrade driftwm-minimap
```

# Usage
```
driftmap
```

To turn off the minimap, you dont need to kill the process. Just run 
```
driftmap
```
one more time.

So, you can set it in your driftwm config file
```
autostart = [
  ...
  "driftmap",   <-- autostart map
]
```
```
[keybindings]
"mod+u" = "spawn driftmap"   <-- map toggle
```

To kill the process run
```
pkill -f driftmap
```

# Settings
run
```
driftmap --help
```
to see avalible options:
```
options:
  -h, --help            show this help message and exit
  --width PX            map width (default: 320)
  --height PX           map height (default: 180)
  --zoom F              map zoom relative to the current viewport (default: 0.15)
  --position {bottom,bottom-left,bottom-right,left,right,top,top-left,top-right}
                        screen position (default: bottom-left)
  --margin PX           distance from anchored screen edges (default: 10)
  --canvas-color, --bg-color HEX
                        background color (default: #242424)
  --canvas-opacity, --bg-opacity F
                        canvas background opacity 0-1 (default: 0.35)
  --window-color HEX    normal window color (default: #b8bfd1)
  --active-window-color, --focused-color HEX
                        focused window color (default: #59b8ff)
  --suspended-color HEX
                        suspended window color (default: #8f94a6)
  --window-opacity F    all window opacity 0-1 (default: 0.4)
  --frame-color, --viewport-color HEX
                        current viewport outline color (default: #f6e380)
  --frame-opacity, --viewport-opacity F
                        current viewport outline opacity 0-1 (default: 0.5)
  --frame-width, --viewport-width PX
                        current viewport outline width (default: 1)
  --canvas-radius, --radius PX
                        canvas corner radius; 0 disables rounding (default: 12)
  --window-radius PX    window corner radius (default: 3)
  --show-fullscreen     keep the map visible on outputs with a fullscreen window
  ```
Example:
```
driftmap \
  --width 320 \
  --height 180 \
  --zoom 0.15 \
  --position bottom-left \
  --margin 10 \
  --canvas-color '#242424' \
  --canvas-opacity 0.35 \
  --window-color '#b8bfd1' \
  --active-window-color '#59b8ff' \
  --suspended-color '#8f94a6' \
  --window-opacity 0.4 \
  --frame-color '#f6e380' \
  --frame-opacity 0.5 \
  --frame-width 1 \
  --canvas-radius 12 \
  --window-radius 3 \
  #--show-fullscreen
```

https://github.com/user-attachments/assets/01435579-189a-4176-ae45-6ff9a45c2b26

