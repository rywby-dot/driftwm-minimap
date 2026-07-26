#!/usr/bin/env python3
"""Click-through driftwm canvas minimap for the layer-shell OVERLAY layer."""

from __future__ import annotations

import argparse
import ctypes.util
import json
import math
import os
import socket
import sys
from pathlib import Path
from typing import Any

LAYER_SHELL_LIBRARY = "libgtk4-layer-shell.so"


def preload_layer_shell() -> None:
    if LAYER_SHELL_LIBRARY in os.environ.get("LD_PRELOAD", ""):
        return

    library = ctypes.util.find_library("gtk4-layer-shell")
    if not library:
        for candidate in (
            "/usr/lib64/libgtk4-layer-shell.so",
            "/usr/lib/libgtk4-layer-shell.so",
        ):
            if Path(candidate).exists():
                library = candidate
                break
    if not library:
        raise SystemExit("libgtk4-layer-shell.so was not found")

    environment = os.environ.copy()
    previous = environment.get("LD_PRELOAD", "")
    environment["LD_PRELOAD"] = f"{library}:{previous}" if previous else library
    os.execve(sys.executable, [sys.executable, *sys.argv], environment)


preload_layer_shell()

import cairo  # noqa: E402
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")

from gi.repository import Gdk, GLib, Gtk, Gtk4LayerShell  # noqa: E402

Gtk.Window.set_auto_startup_notification(False)

EDGE = Gtk4LayerShell.Edge
POSITION_ANCHORS = {
    "top-left": (EDGE.TOP, EDGE.LEFT),
    "top-right": (EDGE.TOP, EDGE.RIGHT),
    "top": (EDGE.TOP,),
    "bottom-left": (EDGE.BOTTOM, EDGE.LEFT),
    "bottom-right": (EDGE.BOTTOM, EDGE.RIGHT),
    "bottom": (EDGE.BOTTOM,),
    "left": (EDGE.LEFT,),
    "right": (EDGE.RIGHT,),
}


def parse_hex_color(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    if len(value) != 6:
        raise argparse.ArgumentTypeError(f"invalid color: #{value}")
    try:
        red, green, blue = int(value[:2], 16), int(value[2:4], 16), int(value[4:], 16)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid color: #{value}") from error
    return red / 255, green / 255, blue / 255


def opacity(value: str) -> float:
    number = float(value)
    if not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return number


def positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="driftwm canvas minimap overlay")
    parser.add_argument(
        "--width", type=positive_int, default=320, metavar="PX",
        help="map width (default: 320)",
    )
    parser.add_argument(
        "--height", type=positive_int, default=180, metavar="PX",
        help="map height (default: 180)",
    )
    parser.add_argument(
        "--zoom",
        type=positive_float,
        default=0.15,
        metavar="F",
        help="map zoom relative to the current viewport (default: 0.15)",
    )
    parser.add_argument(
        "--position",
        choices=sorted(POSITION_ANCHORS),
        default="bottom-left",
        help="screen position (default: bottom-left)",
    )
    parser.add_argument(
        "--margin", type=int, default=10, metavar="PX",
        help="distance from anchored screen edges (default: 10)",
    )
    parser.add_argument(
        "--canvas-color", "--bg-color", dest="canvas_color",
        type=parse_hex_color, default=(0.0176, 0.0176, 0.0176),
        metavar="HEX", help="background color (default: #242424)",
    )
    parser.add_argument(
        "--canvas-opacity", "--bg-opacity", dest="canvas_opacity",
        type=opacity, default=0.45, metavar="F",
        help="canvas background opacity 0-1 (default: 0.45)",
    )
    parser.add_argument(
        "--window-color", type=parse_hex_color, default=(0.72, 0.75, 0.82),
        metavar="HEX", help="normal window color (default: #b8bfd1)",
    )
    parser.add_argument(
        "--active-window-color", "--focused-color", dest="active_window_color",
        type=parse_hex_color, default=(0.35, 0.72, 1.0),
        metavar="HEX", help="focused window color (default: #59b8ff)",
    )
    parser.add_argument(
        "--suspended-color", type=parse_hex_color, default=(0.56, 0.58, 0.65),
        metavar="HEX", help="suspended window color (default: #8f94a6)",
    )
    parser.add_argument(
        "--window-opacity", type=opacity, default=0.4, metavar="F",
        help="all window opacity 0-1 (default: 0.4)",
    )
    parser.add_argument(
        "--frame-color", "--viewport-color", dest="frame_color",
        type=parse_hex_color, default=(0.9216, 0.7682, 0.2159),
        metavar="HEX", help="current viewport outline color (default: #f6e380)",
    )
    parser.add_argument(
        "--frame-opacity", "--viewport-opacity", dest="frame_opacity",
        type=opacity, default=0.5, metavar="F",
        help="current viewport outline opacity 0-1 (default: 0.5)",
    )
    parser.add_argument(
        "--frame-width", "--viewport-width", dest="frame_width",
        type=positive_float, default=1.0, metavar="PX",
        help="current viewport outline width (default: 1)",
    )
    parser.add_argument(
        "--canvas-radius", "--radius", dest="canvas_radius",
        type=nonnegative_int, default=12, metavar="PX",
        help="canvas corner radius; 0 disables rounding (default: 12)",
    )
    parser.add_argument(
        "--window-radius", type=nonnegative_int, default=3, metavar="PX",
        help="window corner radius (default: 3)",
    )
    parser.add_argument(
        "--show-fullscreen",
        action="store_true",
        help="keep the map visible on outputs with a fullscreen window",
    )
    return parser.parse_args()


def ipc_socket_path() -> Path:
    explicit = os.environ.get("DRIFTWM_SOCKET")
    if explicit:
        return Path(explicit)

    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    display = os.environ.get("WAYLAND_DISPLAY")
    if not display:
        raise RuntimeError("WAYLAND_DISPLAY is not set")
    return Path(runtime_dir) / "driftwm" / f"ipc-{display}.sock"


def active_output(state: dict[str, Any]) -> dict[str, Any] | None:
    outputs = state.get("outputs", [])
    return next((output for output in outputs if output.get("active")), None) or (
        outputs[0] if outputs else None
    )


def output_for_monitor(
    state: dict[str, Any], monitor_name: str | None
) -> dict[str, Any] | None:
    outputs = state.get("outputs", [])
    return next(
        (output for output in outputs if output.get("name") == monitor_name),
        None,
    ) or active_output(state)


def monitor_is_fullscreen(
    state: dict[str, Any] | None, monitor_name: str | None
) -> bool:
    if state is None:
        return False
    output = output_for_monitor(state, monitor_name)
    if output is None:
        return False
    output_name = output.get("name")
    return any(
        fullscreen.get("output") == output_name
        for fullscreen in state.get("fullscreen", [])
    )


class StateSubscription:
    def __init__(self, on_state) -> None:
        self.on_state = on_state
        self.connection: socket.socket | None = None
        self.source_id: int | None = None
        self.buffer = bytearray()
        self.retry_id: int | None = None

    def start(self) -> None:
        self._connect()

    def stop(self) -> None:
        if self.retry_id is not None:
            GLib.source_remove(self.retry_id)
        self._disconnect()

    def _connect(self) -> bool:
        self.retry_id = None
        try:
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.connect(str(ipc_socket_path()))
            connection.sendall(b'"Subscribe"\n')
            connection.setblocking(False)
        except (OSError, RuntimeError) as error:
            print(f"driftwm-minimap: {error}; retrying", file=sys.stderr)
            if "connection" in locals():
                connection.close()
            self.retry_id = GLib.timeout_add_seconds(1, self._connect)
            return False

        self.connection = connection
        self.buffer.clear()
        self.source_id = GLib.io_add_watch(
            connection.fileno(),
            GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
            self._on_io,
        )
        return False

    def _disconnect(self) -> None:
        if self.source_id is not None:
            GLib.source_remove(self.source_id)
            self.source_id = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _retry(self) -> None:
        self._disconnect()
        if self.retry_id is None:
            self.retry_id = GLib.timeout_add_seconds(1, self._connect)

    def _on_io(self, _fd: int, condition: GLib.IOCondition) -> bool:
        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            self.source_id = None
            self._retry()
            return False

        assert self.connection is not None
        try:
            chunk = self.connection.recv(65536)
        except BlockingIOError:
            return True
        except OSError:
            self.source_id = None
            self._retry()
            return False
        if not chunk:
            self.source_id = None
            self._retry()
            return False

        self.buffer.extend(chunk)
        while b"\n" in self.buffer:
            line, _, remainder = self.buffer.partition(b"\n")
            self.buffer = bytearray(remainder)
            try:
                message = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                print(f"driftwm-minimap: invalid IPC event: {error}", file=sys.stderr)
                continue
            if isinstance(message, dict) and isinstance(message.get("State"), dict):
                self.on_state(message["State"])
        return True


class MinimapWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application,
        config: argparse.Namespace,
        monitor: Gdk.Monitor,
    ) -> None:
        super().__init__(application=application)
        self.config = config
        self.monitor_name = monitor.get_connector()
        self.state: dict[str, Any] | None = None
        self.area = Gtk.DrawingArea()
        self.area.set_draw_func(self._draw)
        self.area.set_cursor_from_name("default")
        self.area.set_content_width(config.width)
        self.area.set_content_height(config.height)
        self.set_default_size(config.width, config.height)
        self.set_cursor_from_name("default")
        self.set_child(self.area)

        Gtk4LayerShell.init_for_window(self)
        Gtk4LayerShell.set_namespace(self, "driftwm-minimap")
        Gtk4LayerShell.set_layer(self, Gtk4LayerShell.Layer.OVERLAY)
        Gtk4LayerShell.set_keyboard_mode(self, Gtk4LayerShell.KeyboardMode.NONE)
        Gtk4LayerShell.set_exclusive_zone(self, -1)
        Gtk4LayerShell.set_monitor(self, monitor)
        for edge in POSITION_ANCHORS[config.position]:
            Gtk4LayerShell.set_anchor(self, edge, True)
            Gtk4LayerShell.set_margin(self, edge, config.margin)

        self.add_css_class("transparent")
        css = Gtk.CssProvider()
        css.load_from_string(
            ".transparent, .transparent * { "
            "background-color: rgba(0,0,0,0); background: none; }"
        )
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        self.connect("realize", self._make_click_through)

    @staticmethod
    def _make_click_through(window: Gtk.Window) -> None:
        window.get_surface().set_input_region(cairo.Region([]))

    def update_state(self, state: dict[str, Any]) -> None:
        self.state = state
        self.area.queue_draw()

    def _draw(
        self, _area: Gtk.DrawingArea, context: cairo.Context, width: int, height: int
    ) -> None:
        if self.state is None:
            return
        output = output_for_monitor(self.state, self.monitor_name)
        if output is None:
            return

        context.save()
        context.set_operator(cairo.OPERATOR_CLEAR)
        context.paint()
        context.restore()

        center_x, center_y = width / 2, height / 2
        camera_x, camera_y = output["camera"]
        output_width, output_height = output["size"]
        viewport_zoom = max(float(output.get("zoom", 1.0)), 1e-6)
        fit_scale = min(width / output_width, height / output_height)
        canvas_scale = viewport_zoom * fit_scale * self.config.zoom

        context.set_source_rgba(
            *self.config.canvas_color, self.config.canvas_opacity
        )
        rounded_rectangle(
            context, 0.5, 0.5, width - 1, height - 1, self.config.canvas_radius
        )
        context.fill()

        for window in reversed(self.state.get("windows", [])):
            x, y = window["position"]
            window_width, window_height = window["size"]
            draw_x = center_x + (x - camera_x - window_width / 2) * canvas_scale
            draw_y = center_y - (y - camera_y + window_height / 2) * canvas_scale
            draw_width = max(window_width * canvas_scale, 1)
            draw_height = max(window_height * canvas_scale, 1)

            if window.get("is_focused"):
                color = self.config.active_window_color
            elif window.get("suspended"):
                color = self.config.suspended_color
            else:
                color = self.config.window_color
            context.set_source_rgba(*color, self.config.window_opacity)
            rounded_rectangle(
                context,
                draw_x,
                draw_y,
                draw_width,
                draw_height,
                self.config.window_radius,
            )
            context.fill()

        context.set_source_rgba(
            *self.config.frame_color, self.config.frame_opacity
        )
        context.set_line_width(self.config.frame_width)
        outputs = self.state.get("outputs", [])
        ordered_outputs = sorted(outputs, key=lambda item: bool(item.get("active")))
        for map_output in ordered_outputs:
            map_camera_x, map_camera_y = map_output["camera"]
            map_output_width, map_output_height = map_output["size"]
            map_output_zoom = max(float(map_output.get("zoom", 1.0)), 1e-6)
            viewport_width = map_output_width / map_output_zoom * canvas_scale
            viewport_height = map_output_height / map_output_zoom * canvas_scale
            viewport_center_x = center_x + (map_camera_x - camera_x) * canvas_scale
            viewport_center_y = center_y - (map_camera_y - camera_y) * canvas_scale
            context.rectangle(
                viewport_center_x - viewport_width / 2,
                viewport_center_y - viewport_height / 2,
                viewport_width,
                viewport_height,
            )
            context.stroke()


def rounded_rectangle(
    context: cairo.Context, x: float, y: float, width: float, height: float, radius: float
) -> None:
    radius = min(radius, width / 2, height / 2)
    context.new_sub_path()
    context.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
    context.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
    context.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
    context.arc(x + radius, y + radius, radius, math.pi, math.pi * 1.5)
    context.close_path()


class MinimapApplication(Gtk.Application):
    def __init__(self, config: argparse.Namespace) -> None:
        super().__init__(application_id="dev.driftwm.Minimap")
        self.config = config
        self.windows: list[MinimapWindow] = []
        self.state: dict[str, Any] | None = None
        self.subscription = StateSubscription(self.update_state)
        self.maps_visible = False

    def _update_window_visibility(self) -> None:
        for window in self.windows:
            fullscreen_hidden = (
                not self.config.show_fullscreen
                and monitor_is_fullscreen(self.state, window.monitor_name)
            )
            window.set_visible(self.maps_visible and not fullscreen_hidden)

    def do_activate(self) -> None:
        if not self.windows:
            monitors = Gdk.Display.get_default().get_monitors()
            for index in range(monitors.get_n_items()):
                monitor = monitors.get_item(index)
                window = MinimapWindow(self, self.config, monitor)
                if self.state is not None:
                    window.update_state(self.state)
                self.windows.append(window)
            self.maps_visible = True
            self._update_window_visibility()
            self.subscription.start()
            self.hold()
            return

        self.maps_visible = not self.maps_visible
        self._update_window_visibility()

    def update_state(self, state: dict[str, Any]) -> None:
        self.state = state
        for window in self.windows:
            window.update_state(state)
        self._update_window_visibility()

    def do_shutdown(self) -> None:
        self.subscription.stop()
        self.release()
        Gtk.Application.do_shutdown(self)


def main() -> int:
    config = parse_args()
    if not os.environ.get("WAYLAND_DISPLAY"):
        print("driftwm-minimap: run this inside a driftwm Wayland session", file=sys.stderr)
        return 1
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        print("driftwm-minimap: cannot connect to the Wayland display", file=sys.stderr)
        return 1
    application = MinimapApplication(config)
    try:
        return application.run([sys.argv[0]])
    except KeyboardInterrupt:
        application.quit()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
