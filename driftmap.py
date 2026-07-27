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
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LAYER_SHELL_LIBRARY = "libgtk4-layer-shell.so"


def is_rgba_hex(value: str) -> bool:
    return len(value) == 8 and all(
        character in "0123456789abcdefABCDEF" for character in value
    )


def control_socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    display = os.environ.get("WAYLAND_DISPLAY", "wayland")
    return Path(runtime_dir) / "driftwm" / f"driftmap-control-{display}.sock"


def send_fast_control_command() -> None:
    """Contact the running instance without paying GTK's startup cost."""
    arguments = sys.argv[1:]
    command: str | None = None
    if arguments == ["--show"]:
        command = "show"
    elif len(arguments) == 3 and arguments[0] == "--toggle":
        try:
            scale = float(arguments[1])
        except ValueError:
            return
        canvas = arguments[2]
        if math.isfinite(scale) and scale > 0 and is_rgba_hex(canvas):
            command = f"toggle:{scale}:{canvas}"
    elif len(arguments) == 2 and arguments[0] == "--toggle-fullscreen":
        canvas = arguments[1]
        if is_rgba_hex(canvas):
            command = f"toggle-fullscreen:{canvas}"
    if command is None:
        return
    if not os.environ.get("WAYLAND_DISPLAY"):
        return

    connection = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        connection.sendto(
            command.encode(),
            str(control_socket_path()),
        )
    except OSError:
        # No running instance: continue with the normal application startup.
        return
    finally:
        connection.close()
    raise SystemExit(0)


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


send_fast_control_command()
preload_layer_shell()

import cairo  # noqa: E402
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")

from gi.repository import Gdk, Gio, GLib, Gtk, Gtk4LayerShell  # noqa: E402

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


def parse_rgba(value: str) -> tuple[float, float, float, float]:
    if not is_rgba_hex(value):
        raise argparse.ArgumentTypeError(
            "must be exactly 8 hexadecimal characters (RRGGBBAA)"
        )
    return tuple(
        int(value[index:index + 2], 16) / 255
        for index in range(0, 8, 2)
    )


def format_rgba(color: tuple[float, float, float, float]) -> str:
    return "".join(f"{round(channel * 255):02x}" for channel in color)


def positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def nonnegative_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="driftwm canvas minimap overlay")
    command = parser.add_mutually_exclusive_group()
    command.add_argument(
        "--show",
        action="store_true",
        help="show or hide the running map",
    )
    command.add_argument(
        "--toggle",
        nargs=2,
        metavar=("SCALE", "RRGGBBAA"),
        help="toggle a scaled profile with the given canvas RGBA",
    )
    command.add_argument(
        "--toggle-fullscreen",
        type=parse_rgba,
        metavar="RRGGBBAA",
        help="toggle a fullscreen profile with the given canvas RGBA",
    )
    snap = parser.add_mutually_exclusive_group()
    snap.add_argument(
        "--snap",
        dest="minimap_snap",
        type=positive_float,
        default=8.0,
        metavar="PX",
        help="minimap snap activation distance in pixels (default: 8)",
    )
    snap.add_argument(
        "--snap-off",
        action="store_true",
        help="disable snapping while dragging windows on the minimap",
    )
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
        "--canvas", type=parse_rgba, default=parse_rgba("2424244d"),
        metavar="RRGGBBAA", help="canvas color and opacity (default: 2424244d)",
    )
    parser.add_argument(
        "--window", type=parse_rgba, default=parse_rgba("b8bfd14d"),
        metavar="RRGGBBAA", help="normal window RGBA (default: b8bfd14d)",
    )
    parser.add_argument(
        "--active-window", type=parse_rgba, default=parse_rgba("59b8ff4d"),
        metavar="RRGGBBAA", help="focused window RGBA (default: 59b8ff4d)",
    )
    parser.add_argument(
        "--suspended", type=parse_rgba, default=parse_rgba("8f94a64d"),
        metavar="RRGGBBAA", help="suspended window RGBA (default: 8f94a64d)",
    )
    parser.add_argument(
        "--frame", type=parse_rgba, default=parse_rgba("f6e38066"),
        metavar="RRGGBBAA", help="viewport frame RGBA (default: f6e38066)",
    )
    parser.add_argument(
        "--frame-width", "--viewport-width", dest="frame_width",
        type=positive_float, default=1.0, metavar="PX",
        help="current viewport outline width (default: 1)",
    )
    parser.add_argument(
        "--bookmarks", type=parse_rgba, default=parse_rgba("ff8a6699"),
        metavar="RRGGBBAA", help="bookmark point RGBA (default: ff8a6699)",
    )
    parser.add_argument(
        "--home", type=parse_rgba, default=parse_rgba("66e0a399"),
        metavar="RRGGBBAA", help="home point RGBA (default: 66e0a399)",
    )
    parser.add_argument(
        "--bookmark-hitbox",
        nargs=2,
        type=float,
        default=(0.3, 8.0),
        metavar=("OPACITY", "PX"),
        help="bookmark hover opacity and extra hitbox radius (default: 0.3 8)",
    )
    parser.add_argument(
        "--home-hitbox",
        nargs=2,
        type=float,
        default=(0.3, 8.0),
        metavar=("OPACITY", "PX"),
        help="home hover opacity and extra hitbox radius (default: 0.3 8)",
    )
    parser.add_argument(
        "--dot-radius", type=nonnegative_float, default=2, metavar="PX",
        help="home and bookmark point radius; 0 disables points (default: 2)",
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
    args = parser.parse_args(argv)
    if args.toggle is not None:
        scale_value, canvas_value = args.toggle
        try:
            scale = positive_float(scale_value)
            canvas = parse_rgba(canvas_value)
        except argparse.ArgumentTypeError as error:
            parser.error(f"--toggle: {error}")
        args.toggle = (scale, canvas)
    for flag, values in (
        ("--bookmark-hitbox", args.bookmark_hitbox),
        ("--home-hitbox", args.home_hitbox),
    ):
        alpha, radius = values
        if not math.isfinite(alpha) or not 0 <= alpha <= 1:
            parser.error(f"{flag} OPACITY must be between 0 and 1")
        if not math.isfinite(radius) or radius < 0:
            parser.error(f"{flag} PX must be zero or greater")
    return args


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
    state: dict[str, Any],
    monitor_name: str | None = None,
    monitor_size: tuple[int, int] | None = None,
    monitor_index: int | None = None,
) -> dict[str, Any] | None:
    outputs = state.get("outputs", [])
    if monitor_name is not None:
        named = next(
            (output for output in outputs if output.get("name") == monitor_name),
            None,
        )
        if named is not None:
            return named
    if monitor_size is not None:
        same_size = [
            output
            for output in outputs
            if tuple(output.get("size", ())) == monitor_size
        ]
        if len(same_size) == 1:
            return same_size[0]
    if monitor_index is not None and 0 <= monitor_index < len(outputs):
        return outputs[monitor_index]
    if monitor_name is None and monitor_size is None and monitor_index is None:
        return active_output(state)
    return None


def monitor_is_fullscreen(
    state: dict[str, Any] | None,
    monitor_name: str | None,
    monitor_size: tuple[int, int],
    monitor_index: int,
) -> bool:
    if state is None:
        return False
    output = output_for_monitor(
        state, monitor_name, monitor_size, monitor_index
    )
    if output is None:
        return False
    output_name = output.get("name")
    return any(
        fullscreen.get("output") == output_name
        for fullscreen in state.get("fullscreen", [])
    )


@dataclass(frozen=True)
class SnapConfig:
    enabled: bool = True
    gap: float = 12.0
    distance: float = 24.0
    break_force: float = 32.0
    corners: bool = False
    centers: bool = False


@dataclass
class AxisSnap:
    snapped_pos: float
    natural_at_engage: float


@dataclass(frozen=True)
class Marker:
    action: str
    x: float
    y: float
    radius: float
    color: tuple[float, float, float, float]
    hover_opacity: float
    hitbox_padding: float


def load_snap_config() -> SnapConfig:
    config_home = Path(
        os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    )
    path = config_home / "driftwm" / "config.toml"
    try:
        values = tomllib.loads(path.read_text()).get("snap", {})
    except (OSError, tomllib.TOMLDecodeError):
        values = {}

    defaults = SnapConfig()
    return SnapConfig(
        enabled=bool(values.get("enabled", defaults.enabled)),
        gap=max(0.0, float(values.get("gap", defaults.gap))),
        distance=max(0.0, float(values.get("distance", defaults.distance))),
        break_force=max(
            0.0, float(values.get("break_force", defaults.break_force))
        ),
        corners=bool(values.get("corners", defaults.corners)),
        centers=bool(values.get("centers", defaults.centers)),
    )


def interval_distance(low: float, high: float, other_low: float, other_high: float) -> float:
    if high < other_low:
        return other_low - high
    if other_high < low:
        return low - other_high
    return 0.0


def find_snap_candidate(
    natural_low: float,
    extent: float,
    perp_low: float,
    perp_high: float,
    horizontal: bool,
    others: list[tuple[float, float, float, float]],
    config: SnapConfig,
    threshold: float,
) -> float | None:
    natural_high = natural_low + extent
    best: tuple[float, float] | None = None

    def candidate(position: float, distance: float) -> None:
        nonlocal best
        if distance < threshold and (best is None or distance < best[1]):
            best = (position, distance)

    for x_low, x_high, y_low, y_high in others:
        if horizontal:
            other_low, other_high = x_low, x_high
            other_perp_low, other_perp_high = y_low, y_high
        else:
            other_low, other_high = y_low, y_high
            other_perp_low, other_perp_high = x_low, x_high

        overlaps = (
            perp_high > other_perp_low and other_perp_high > perp_low
        )
        alignment_eligible = (
            not overlaps
            and interval_distance(
                perp_low, perp_high, other_perp_low, other_perp_high
            )
            < config.gap + threshold
        )
        if not overlaps and not (
            alignment_eligible and (config.corners or config.centers)
        ):
            continue

        if overlaps:
            candidate(
                other_low - config.gap - extent,
                abs(natural_high - other_low),
            )
            candidate(other_high + config.gap, abs(natural_low - other_high))
        if config.corners and alignment_eligible:
            candidate(other_low, abs(natural_low - other_low))
            candidate(other_high - extent, abs(natural_high - other_high))
        if config.centers and alignment_eligible:
            other_center = (other_low + other_high) / 2
            candidate(
                other_center - extent / 2,
                abs(natural_low + extent / 2 - other_center),
            )

    return best[0] if best is not None else None


def update_axis_snap(
    snap: AxisSnap | None,
    cooldown: float | None,
    natural_pos: float,
    candidate: float | None,
    threshold: float,
    break_force: float,
) -> tuple[float, AxisSnap | None, float | None]:
    if snap is not None:
        if snap.snapped_pos > snap.natural_at_engage:
            retreat = snap.natural_at_engage - natural_pos
            overshoot = natural_pos - snap.snapped_pos
        else:
            retreat = natural_pos - snap.natural_at_engage
            overshoot = snap.snapped_pos - natural_pos
        if retreat >= break_force or overshoot >= break_force:
            return natural_pos, None, snap.snapped_pos
        return snap.snapped_pos, snap, cooldown

    if cooldown is not None and abs(natural_pos - cooldown) > threshold:
        cooldown = None
    if cooldown is None and candidate is not None:
        snap = AxisSnap(candidate, natural_pos)
        return candidate, snap, cooldown
    return natural_pos, snap, cooldown


class StateSubscription:
    def __init__(self, on_state, on_bookmarks) -> None:
        self.on_state = on_state
        self.on_bookmarks = on_bookmarks
        self.connection: socket.socket | None = None
        self.source_id: int | None = None
        self.buffer = bytearray()
        self.retry_id: int | None = None
        self.bookmark_poll_id: int | None = None

    def start(self) -> None:
        self._connect()
        self.bookmark_poll_id = GLib.timeout_add_seconds(
            1, self._request_bookmarks
        )

    def stop(self) -> None:
        if self.retry_id is not None:
            GLib.source_remove(self.retry_id)
        if self.bookmark_poll_id is not None:
            GLib.source_remove(self.bookmark_poll_id)
            self.bookmark_poll_id = None
        self._disconnect()

    def _connect(self) -> bool:
        self.retry_id = None
        try:
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.connect(str(ipc_socket_path()))
            connection.sendall(b'"Subscribe"\n{"Bookmark":{}}\n')
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

    def _request_bookmarks(self) -> bool:
        if self.connection is not None:
            try:
                self.connection.sendall(b'{"Bookmark":{}}\n')
            except (BlockingIOError, OSError):
                self._retry()
        return True

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
            bookmarks = (
                message.get("Ok", {}).get("Bookmarks")
                if isinstance(message, dict) and isinstance(message.get("Ok"), dict)
                else None
            )
            if isinstance(bookmarks, dict):
                self.on_bookmarks(bookmarks)
        return True


class CommandConnection:
    """Small persistent IPC connection for interactive minimap commands."""

    def __init__(self) -> None:
        self.connection: socket.socket | None = None

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def send(self, *requests: object) -> None:
        payload = b"".join(
            json.dumps(request, separators=(",", ":")).encode() + b"\n"
            for request in requests
        )
        for attempt in range(2):
            try:
                if self.connection is None:
                    self.connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self.connection.connect(str(ipc_socket_path()))
                    self.connection.setblocking(False)
                else:
                    try:
                        while self.connection.recv(65536):
                            pass
                    except BlockingIOError:
                        pass
                self.connection.sendall(payload)
                return
            except (BlockingIOError, OSError, RuntimeError) as error:
                self.close()
                if attempt:
                    print(f"driftwm-minimap: IPC command failed: {error}", file=sys.stderr)


class ControlServer:
    def __init__(self, on_command) -> None:
        self.on_command = on_command
        self.connection: socket.socket | None = None
        self.source_id: int | None = None
        self.owns_socket = False

    def start(self) -> None:
        path = control_socket_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.unlink()
        except FileNotFoundError:
            pass

        self.connection = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.connection.bind(str(path))
        self.owns_socket = True
        self.connection.setblocking(False)
        self.source_id = GLib.io_add_watch(
            self.connection.fileno(),
            GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
            self._on_io,
        )

    def stop(self) -> None:
        if self.source_id is not None:
            GLib.source_remove(self.source_id)
            self.source_id = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        if self.owns_socket:
            try:
                control_socket_path().unlink()
            except FileNotFoundError:
                pass
            self.owns_socket = False

    def _on_io(self, _fd: int, condition: GLib.IOCondition) -> bool:
        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            return True
        assert self.connection is not None
        try:
            command = self.connection.recv(64).decode()
        except (BlockingIOError, UnicodeDecodeError):
            return True
        if (
            command == "show"
            or command.startswith("toggle:")
            or command.startswith("toggle-fullscreen:")
        ):
            self.on_command(command)
        return True


class MinimapWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application,
        config: argparse.Namespace,
        monitor: Gdk.Monitor,
        monitor_index: int,
    ) -> None:
        super().__init__(application=application)
        self.config = config
        self.monitor_name = monitor.get_connector()
        geometry = monitor.get_geometry()
        self.monitor_size = (geometry.width, geometry.height)
        self.monitor_index = monitor_index
        self.state: dict[str, Any] | None = None
        self.command_connection = CommandConnection()
        self.snap_config = load_snap_config()
        self.minimap_snap_distance = config.minimap_snap
        self._apply_snap_config(config)
        self.interactive = False
        self.view_camera: tuple[float, float] | None = None
        self.view_zoom = 1.0
        self.target_view_zoom = 1.0
        self.zoom_tick_id: int | None = None
        self.zoom_frame_time: int | None = None
        self.window_rects: list[tuple[dict[str, Any], float, float, float, float]] = []
        self.bookmarks: dict[str, list[float]] = {}
        self.marker_hits: list[tuple[str, float, float, float]] = []
        self.hovered_marker: str | None = None
        self.last_canvas_scale = 1.0
        self.left_press: tuple[float, float, int | None] | None = None
        self.marker_press: str | None = None
        self.middle_press: tuple[float, float, int | None] | None = None
        self.pan_origin: tuple[float, float] | None = None
        self.move_origin: tuple[int, float, float] | None = None
        self.move_size: tuple[float, float] | None = None
        self.snap_others: list[tuple[float, float, float, float]] = []
        self.snap_x: AxisSnap | None = None
        self.snap_y: AxisSnap | None = None
        self.snap_cooldown_x: float | None = None
        self.snap_cooldown_y: float | None = None
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
        self.connect("realize", lambda _window: self._update_input_region())
        self._install_input_controllers()

    def apply_config(
        self, config: argparse.Namespace, fullscreen: bool = False
    ) -> None:
        self.config = config
        self._apply_snap_config(config)
        # With opposite layer-shell anchors, a zero requested dimension asks
        # the compositor to stretch the surface exactly between those edges.
        # This avoids one-pixel gaps caused by logical-size rounding.
        width, height = (0, 0) if fullscreen else (config.width, config.height)
        for edge in (EDGE.TOP, EDGE.RIGHT, EDGE.BOTTOM, EDGE.LEFT):
            Gtk4LayerShell.set_anchor(self, edge, fullscreen)
            Gtk4LayerShell.set_margin(self, edge, 0)
        if not fullscreen:
            for edge in POSITION_ANCHORS[config.position]:
                Gtk4LayerShell.set_anchor(self, edge, True)
                Gtk4LayerShell.set_margin(self, edge, config.margin)
        self.area.set_content_width(width)
        self.area.set_content_height(height)
        self.set_default_size(width, height)
        self.area.queue_resize()
        self.area.queue_draw()

    def _apply_snap_config(self, config: argparse.Namespace) -> None:
        compositor_snap = load_snap_config()
        self.snap_config = SnapConfig(
            enabled=compositor_snap.enabled and not config.snap_off,
            gap=compositor_snap.gap,
            distance=compositor_snap.distance,
            break_force=compositor_snap.break_force,
            corners=compositor_snap.corners,
            centers=compositor_snap.centers,
        )
        self.minimap_snap_distance = config.minimap_snap

    def set_interactive(self, interactive: bool) -> None:
        self.interactive = interactive
        self.view_camera = None
        self.view_zoom = 1.0
        self.target_view_zoom = 1.0
        if self.zoom_tick_id is not None:
            self.area.remove_tick_callback(self.zoom_tick_id)
            self.zoom_tick_id = None
        self.zoom_frame_time = None
        self.left_press = None
        self.marker_press = None
        self.hovered_marker = None
        self.middle_press = None
        self.pan_origin = None
        self.move_origin = None
        self.move_size = None
        self.snap_others = []
        self.snap_x = None
        self.snap_y = None
        self.snap_cooldown_x = None
        self.snap_cooldown_y = None
        self.area.set_cursor_from_name("default" if interactive else None)
        if self.get_realized():
            self._update_input_region()
        self.area.queue_draw()

    def _update_input_region(self) -> None:
        region = None if self.interactive else cairo.Region([])
        self.get_surface().set_input_region(region)

    def _install_input_controllers(self) -> None:
        click = Gtk.GestureClick.new()
        click.set_button(0)
        click.connect("pressed", self._on_button_pressed)
        click.connect("released", self._on_button_released)
        self.area.add_controller(click)

        pan = Gtk.GestureDrag.new()
        pan.set_button(Gdk.BUTTON_PRIMARY)
        pan.connect("drag-begin", self._on_pan_begin)
        pan.connect("drag-update", self._on_pan_update)
        pan.connect("drag-end", self._on_pan_end)
        self.area.add_controller(pan)

        move = Gtk.GestureDrag.new()
        move.set_button(Gdk.BUTTON_SECONDARY)
        move.connect("drag-begin", self._on_move_begin)
        move.connect("drag-update", self._on_move_update)
        move.connect("drag-end", self._on_move_end)
        self.area.add_controller(move)

        scroll = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.BOTH_AXES
        )
        scroll.connect("scroll", self._on_scroll)
        self.area.add_controller(scroll)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_pointer_motion)
        motion.connect("leave", self._on_pointer_leave)
        self.area.add_controller(motion)

    def _window_at(self, x: float, y: float) -> dict[str, Any] | None:
        for window, draw_x, draw_y, draw_width, draw_height in self.window_rects:
            if draw_x <= x <= draw_x + draw_width and draw_y <= y <= draw_y + draw_height:
                return window
        return None

    def _marker_at(self, x: float, y: float) -> str | None:
        for action, center_x, center_y, hit_radius in reversed(self.marker_hits):
            if math.hypot(x - center_x, y - center_y) <= hit_radius:
                return action
        return None

    def _on_pointer_motion(
        self, _controller: Gtk.EventControllerMotion, x: float, y: float
    ) -> None:
        marker = self._marker_at(x, y) if self.interactive else None
        if marker != self.hovered_marker:
            self.hovered_marker = marker
            self.area.queue_draw()

    def _on_pointer_leave(
        self, _controller: Gtk.EventControllerMotion
    ) -> None:
        if self.hovered_marker is not None:
            self.hovered_marker = None
            self.area.queue_draw()

    def _on_button_pressed(
        self, gesture: Gtk.GestureClick, _count: int, x: float, y: float
    ) -> None:
        if not self.interactive:
            return
        marker = self._marker_at(x, y)
        if gesture.get_current_button() == Gdk.BUTTON_PRIMARY and marker is not None:
            self.marker_press = marker
            self.left_press = None
            return
        window = self._window_at(x, y)
        window_id = int(window["id"]) if window is not None else None
        if gesture.get_current_button() == Gdk.BUTTON_PRIMARY:
            self.left_press = (x, y, window_id)
        elif gesture.get_current_button() == Gdk.BUTTON_MIDDLE:
            self.middle_press = (x, y, window_id)

    def _on_button_released(
        self, gesture: Gtk.GestureClick, _count: int, x: float, y: float
    ) -> None:
        if not self.interactive:
            return
        button = gesture.get_current_button()
        marker = self._marker_at(x, y)
        if button == Gdk.BUTTON_PRIMARY and self.marker_press is not None:
            if marker == self.marker_press:
                self.command_connection.send({"Action": marker})
            self.marker_press = None
            self.left_press = None
            self.middle_press = None
            return
        window = self._window_at(x, y)
        if window is None:
            self.left_press = None
            self.middle_press = None
            return
        window_id = int(window["id"])
        if button == Gdk.BUTTON_PRIMARY and self.left_press is not None:
            start_x, start_y, pressed_id = self.left_press
            if (
                pressed_id == window_id
                and math.hypot(x - start_x, y - start_y) < 5
            ):
                self.command_connection.send(
                    {"Focus": window_id},
                    {"Action": "center-window"},
                )
        elif button == Gdk.BUTTON_MIDDLE and self.middle_press is not None:
            start_x, start_y, pressed_id = self.middle_press
            if (
                pressed_id == window_id
                and math.hypot(x - start_x, y - start_y) < 5
            ):
                self.command_connection.send({"Close": window_id})
        self.left_press = None
        self.marker_press = None
        self.middle_press = None

    def _ensure_view_camera(self) -> tuple[float, float]:
        if self.view_camera is not None:
            return self.view_camera
        output = (
            output_for_monitor(
                self.state,
                self.monitor_name,
                self.monitor_size,
                self.monitor_index,
            )
            if self.state is not None
            else None
        )
        camera = output.get("camera", (0.0, 0.0)) if output is not None else (0.0, 0.0)
        self.view_camera = (float(camera[0]), float(camera[1]))
        return self.view_camera

    def _on_pan_begin(self, _gesture: Gtk.GestureDrag, x: float, y: float) -> None:
        if (
            not self.interactive
            or self._marker_at(x, y) is not None
            or self._window_at(x, y) is not None
        ):
            self.pan_origin = None
            return
        self.pan_origin = self._ensure_view_camera()
        self.area.set_cursor_from_name("grabbing")

    def _on_pan_update(
        self, _gesture: Gtk.GestureDrag, offset_x: float, offset_y: float
    ) -> None:
        if self.pan_origin is None:
            return
        scale = max(self.last_canvas_scale, 1e-9)
        self.view_camera = (
            self.pan_origin[0] - offset_x / scale,
            self.pan_origin[1] + offset_y / scale,
        )
        self.area.queue_draw()

    def _on_pan_end(
        self, _gesture: Gtk.GestureDrag, _offset_x: float, _offset_y: float
    ) -> None:
        self.pan_origin = None
        if self.interactive:
            self.area.set_cursor_from_name("default")

    def _on_move_begin(self, _gesture: Gtk.GestureDrag, x: float, y: float) -> None:
        if not self.interactive:
            return
        window = self._window_at(x, y)
        if window is None:
            self.move_origin = None
            return
        position_x, position_y = window["position"]
        self.move_origin = (int(window["id"]), float(position_x), float(position_y))
        width, height = window["size"]
        self.move_size = (float(width), float(height))
        self.snap_others = []
        for other in self.state.get("windows", []) if self.state is not None else []:
            if other.get("id") == window["id"] or other.get("is_widget"):
                continue
            other_x, other_y = other["position"]
            other_width, other_height = other["size"]
            self.snap_others.append(
                (
                    other_x - other_width / 2,
                    other_x + other_width / 2,
                    other_y - other_height / 2,
                    other_y + other_height / 2,
                )
            )
        self.snap_x = None
        self.snap_y = None
        self.snap_cooldown_x = None
        self.snap_cooldown_y = None
        self.area.set_cursor_from_name("grabbing")

    def _on_move_update(
        self, _gesture: Gtk.GestureDrag, offset_x: float, offset_y: float
    ) -> None:
        if self.move_origin is None:
            return
        window_id, origin_x, origin_y = self.move_origin
        scale = max(self.last_canvas_scale, 1e-9)
        target = [
            origin_x + offset_x / scale,
            origin_y - offset_y / scale,
        ]
        target = self._snap_move(target)
        target = [round(target[0]), round(target[1])]
        self.command_connection.send({"Move": {"window": window_id, "to": target}})

    def _snap_move(self, target: list[float]) -> list[float]:
        if (
            not self.snap_config.enabled
            or self.snap_config.distance <= 0
            or self.move_size is None
            or not self.snap_others
        ):
            return target

        width, height = self.move_size
        natural_x = target[0] - width / 2
        natural_y = target[1] - height / 2
        # Keep minimap snapping deliberately subtle: its activation band is
        # always two minimap pixels. Preserve the compositor config's
        # break-force/distance ratio so the held snap does not feel sticky.
        map_scale = max(self.last_canvas_scale, 1e-9)
        threshold = self.minimap_snap_distance / map_scale
        break_pixels = (
            self.minimap_snap_distance
            * self.snap_config.break_force
            / self.snap_config.distance
        )
        break_force = break_pixels / map_scale

        perp_y = self.snap_y.snapped_pos if self.snap_y is not None else natural_y
        candidate_x = find_snap_candidate(
            natural_x,
            width,
            perp_y,
            perp_y + height,
            True,
            self.snap_others,
            self.snap_config,
            threshold,
        )
        final_x, self.snap_x, self.snap_cooldown_x = update_axis_snap(
            self.snap_x,
            self.snap_cooldown_x,
            natural_x,
            candidate_x,
            threshold,
            break_force,
        )

        perp_x = self.snap_x.snapped_pos if self.snap_x is not None else natural_x
        candidate_y = find_snap_candidate(
            natural_y,
            height,
            perp_x,
            perp_x + width,
            False,
            self.snap_others,
            self.snap_config,
            threshold,
        )
        final_y, self.snap_y, self.snap_cooldown_y = update_axis_snap(
            self.snap_y,
            self.snap_cooldown_y,
            natural_y,
            candidate_y,
            threshold,
            break_force,
        )
        return [final_x + width / 2, final_y + height / 2]

    def _on_move_end(
        self, _gesture: Gtk.GestureDrag, _offset_x: float, _offset_y: float
    ) -> None:
        self.move_origin = None
        self.move_size = None
        self.snap_others = []
        self.snap_x = None
        self.snap_y = None
        self.snap_cooldown_x = None
        self.snap_cooldown_y = None
        if self.interactive:
            self.area.set_cursor_from_name("default")

    def _on_scroll(
        self, controller: Gtk.EventControllerScroll, dx: float, dy: float
    ) -> bool:
        if not self.interactive:
            return False
        event = controller.get_current_event()
        device = event.get_device() if event is not None else None
        source = device.get_source() if device is not None else Gdk.InputSource.MOUSE
        position = event.get_position() if event is not None else (False, 0.0, 0.0)
        _, pointer_x, pointer_y = position

        if source == Gdk.InputSource.TOUCHPAD:
            if self._window_at(pointer_x, pointer_y) is not None:
                return True
            camera_x, camera_y = self._ensure_view_camera()
            scale = max(self.last_canvas_scale, 1e-9)
            self.view_camera = (
                camera_x + dx * 24 / scale,
                camera_y - dy * 24 / scale,
            )
        else:
            if abs(dy) < 1e-9:
                return True
            # Backends disagree on wheel units: one notch may arrive as 1, 15,
            # or 120. Use its direction only, otherwise a single event can
            # throw the map straight to an extreme zoom.
            zoom_step = 1.15 if dy < 0 else 1 / 1.15
            old_target = self.target_view_zoom
            self.target_view_zoom = max(
                0.25, min(4.0, old_target * zoom_step)
            )
            if self.target_view_zoom == old_target:
                return True
            if self.zoom_tick_id is None:
                self.zoom_frame_time = None
                self.zoom_tick_id = self.area.add_tick_callback(self._on_zoom_tick)
        self.area.queue_draw()
        return True

    def _on_zoom_tick(
        self, _area: Gtk.DrawingArea, frame_clock: Gdk.FrameClock
    ) -> bool:
        now = frame_clock.get_frame_time()
        if self.zoom_frame_time is None:
            dt = 1 / 60
        else:
            dt = min((now - self.zoom_frame_time) / 1_000_000, 0.1)
        self.zoom_frame_time = now

        remaining = self.target_view_zoom - self.view_zoom
        if abs(remaining) < 0.001:
            self.view_zoom = self.target_view_zoom
            self.zoom_tick_id = None
            self.zoom_frame_time = None
            self.area.queue_draw()
            return False

        # Same frame-rate-independent lerp and default speed as driftwm's
        # camera/zoom animation: 0.3 of the remainder at 60 FPS.
        factor = 1.0 - (1.0 - 0.3) ** (dt * 60)
        self.view_zoom += remaining * factor
        self.area.queue_draw()
        return True

    def update_state(self, state: dict[str, Any]) -> None:
        self.state = state
        self.area.queue_draw()

    def update_bookmarks(self, bookmarks: dict[str, Any]) -> None:
        self.bookmarks = {
            str(name): [float(point[0]), float(point[1])]
            for name, point in bookmarks.items()
            if (
                isinstance(point, list)
                and len(point) == 2
                and all(isinstance(value, (int, float)) for value in point)
                and all(math.isfinite(float(value)) for value in point)
            )
        }
        self.area.queue_draw()

    def _draw(
        self, _area: Gtk.DrawingArea, context: cairo.Context, width: int, height: int
    ) -> None:
        if self.state is None:
            return
        output = output_for_monitor(
            self.state,
            self.monitor_name,
            self.monitor_size,
            self.monitor_index,
        )
        if output is None:
            return

        context.save()
        context.set_operator(cairo.OPERATOR_CLEAR)
        context.paint()
        context.restore()

        center_x, center_y = width / 2, height / 2
        output_camera_x, output_camera_y = output["camera"]
        if self.interactive:
            camera_x, camera_y = self._ensure_view_camera()
        else:
            camera_x, camera_y = output_camera_x, output_camera_y
        output_width, output_height = output["size"]
        viewport_zoom = max(float(output.get("zoom", 1.0)), 1e-6)
        fit_scale = min(width / output_width, height / output_height)
        canvas_scale = viewport_zoom * fit_scale * self.config.zoom * self.view_zoom
        self.last_canvas_scale = canvas_scale
        self.window_rects = []
        self.marker_hits = []

        context.set_source_rgba(*self.config.canvas)
        if self.config.canvas_radius == 0:
            context.rectangle(0, 0, width, height)
        else:
            rounded_rectangle(
                context,
                0.5,
                0.5,
                width - 1,
                height - 1,
                self.config.canvas_radius,
            )
        context.fill()

        drawn_windows = list(reversed(self.state.get("windows", [])))
        for window in drawn_windows:
            x, y = window["position"]
            window_width, window_height = window["size"]
            draw_x = center_x + (x - camera_x - window_width / 2) * canvas_scale
            draw_y = center_y - (y - camera_y + window_height / 2) * canvas_scale
            draw_width = max(window_width * canvas_scale, 1)
            draw_height = max(window_height * canvas_scale, 1)

            if window.get("is_focused"):
                color = self.config.active_window
            elif window.get("suspended"):
                color = self.config.suspended
            else:
                color = self.config.window
            context.set_source_rgba(*color)
            rounded_rectangle(
                context,
                draw_x,
                draw_y,
                draw_width,
                draw_height,
                self.config.window_radius,
            )
            context.fill()
            self.window_rects.insert(
                0, (window, draw_x, draw_y, draw_width, draw_height)
            )

        context.set_source_rgba(*self.config.frame)
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

        if self.config.dot_radius == 0:
            return

        markers: list[Marker] = []
        bookmark_hover_opacity, bookmark_hitbox_padding = (
            self.config.bookmark_hitbox
        )
        markers.extend(
            Marker(
                action=f"go-to-bookmark {name}",
                x=point[0],
                y=point[1],
                radius=self.config.dot_radius,
                color=self.config.bookmarks,
                hover_opacity=bookmark_hover_opacity,
                hitbox_padding=bookmark_hitbox_padding,
            )
            for name, point in self.bookmarks.items()
        )
        home_hover_opacity, home_hitbox_padding = self.config.home_hitbox
        markers.append(
            Marker(
                action="home-toggle",
                x=0.0,
                y=0.0,
                radius=self.config.dot_radius,
                color=self.config.home,
                hover_opacity=home_hover_opacity,
                hitbox_padding=home_hitbox_padding,
            )
        )
        for marker in markers:
            marker_x = center_x + (marker.x - camera_x) * canvas_scale
            marker_y = center_y - (marker.y - camera_y) * canvas_scale
            hit_radius = marker.radius + marker.hitbox_padding
            if marker.action == self.hovered_marker:
                context.set_source_rgba(
                    *marker.color[:3], marker.hover_opacity
                )
                context.arc(marker_x, marker_y, hit_radius, 0, math.tau)
                context.fill()
            context.set_source_rgba(*marker.color)
            context.arc(marker_x, marker_y, marker.radius, 0, math.tau)
            context.fill()
            self.marker_hits.append(
                (marker.action, marker_x, marker_y, hit_radius)
            )


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
        super().__init__(
            application_id="dev.driftwm.Minimap",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.base_config = config
        self.config = config
        self.windows: list[MinimapWindow] = []
        self.state: dict[str, Any] | None = None
        self.bookmarks: dict[str, Any] = {}
        self.subscription = StateSubscription(
            self.update_state, self.update_bookmarks
        )
        self.control_server = ControlServer(self._handle_command)
        self.maps_visible = False
        self.profile = "normal"
        self.profile_scale = 1.0
        self.profile_canvas = config.canvas
        self.started = False
        self.monitors: Gio.ListModel | None = None
        self.monitors_changed_id: int | None = None
        self.monitor_rebuild_id: int | None = None

    def _profile_config(self) -> argparse.Namespace:
        values = vars(self.base_config).copy()
        if self.profile == "large":
            values["width"] = max(1, round(values["width"] * self.profile_scale))
            values["height"] = max(1, round(values["height"] * self.profile_scale))
        if self.profile != "normal":
            values["canvas"] = self.profile_canvas
        if self.profile == "fullscreen":
            values["canvas_radius"] = 0
        return argparse.Namespace(**values)

    def _apply_profile(self) -> None:
        self.config = self._profile_config()
        for window in self.windows:
            window.apply_config(
                self.config, fullscreen=self.profile == "fullscreen"
            )
            window.set_interactive(self.profile != "normal")

    def _update_window_visibility(self) -> None:
        for window in self.windows:
            fullscreen_hidden = (
                self.profile != "fullscreen"
                and not self.config.show_fullscreen
                and monitor_is_fullscreen(
                    self.state,
                    window.monitor_name,
                    window.monitor_size,
                    window.monitor_index,
                )
            )
            window.set_visible(self.maps_visible and not fullscreen_hidden)

    def _create_windows(self) -> None:
        if self.monitors is None:
            return
        for index in range(self.monitors.get_n_items()):
            monitor = self.monitors.get_item(index)
            window = MinimapWindow(self, self.config, monitor, index)
            window.apply_config(
                self.config, fullscreen=self.profile == "fullscreen"
            )
            window.set_interactive(self.profile != "normal")
            if self.state is not None:
                window.update_state(self.state)
            window.update_bookmarks(self.bookmarks)
            self.windows.append(window)
        self._update_window_visibility()

    def _schedule_monitor_rebuild(
        self,
        _monitors: Gio.ListModel,
        _position: int,
        _removed: int,
        _added: int,
    ) -> None:
        if self.monitor_rebuild_id is None:
            self.monitor_rebuild_id = GLib.idle_add(self._rebuild_windows)

    def _rebuild_windows(self) -> bool:
        self.monitor_rebuild_id = None
        old_windows, self.windows = self.windows, []
        for window in old_windows:
            window.command_connection.close()
            window.close()
        self._create_windows()
        return False

    def _handle_command(self, command: str) -> None:
        if command == "show":
            self.maps_visible = not self.maps_visible
            self._update_window_visibility()
        elif command.startswith("toggle:"):
            _, scale, canvas = command.split(":")
            if self.profile == "large":
                self.profile = "normal"
            else:
                self.profile = "large"
                self.profile_scale = float(scale)
                self.profile_canvas = parse_rgba(canvas)
            self._apply_profile()
        elif command.startswith("toggle-fullscreen:"):
            if self.profile == "fullscreen":
                self.profile = "normal"
            else:
                self.profile = "fullscreen"
                self.profile_canvas = parse_rgba(command.partition(":")[2])
            self._apply_profile()

    def do_activate(self) -> None:
        if not self.started:
            self.started = True
            self.control_server.start()
            self.monitors = Gdk.Display.get_default().get_monitors()
            self.monitors_changed_id = self.monitors.connect(
                "items-changed", self._schedule_monitor_rebuild
            )
            self._create_windows()
            self.maps_visible = True
            self._update_window_visibility()
            self.subscription.start()
            self.hold()

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        arguments = [
            argument.decode() if isinstance(argument, bytes) else argument
            for argument in command_line.get_arguments()
        ]
        requested = parse_args(arguments[1:])
        first_run = not self.started
        self.activate()

        if first_run:
            if requested.toggle is not None:
                scale, canvas = requested.toggle
                self.profile = "large"
                self.profile_scale = scale
                self.profile_canvas = canvas
                self._apply_profile()
            elif requested.toggle_fullscreen is not None:
                self.profile = "fullscreen"
                self.profile_canvas = requested.toggle_fullscreen
                self._apply_profile()
        else:
            if requested.show:
                self._handle_command("show")
            elif requested.toggle is not None:
                scale, canvas = requested.toggle
                self._handle_command(
                    f"toggle:{scale}:{format_rgba(canvas)}"
                )
            elif requested.toggle_fullscreen is not None:
                self._handle_command(
                    "toggle-fullscreen:"
                    f"{format_rgba(requested.toggle_fullscreen)}"
                )
        return 0

    def update_state(self, state: dict[str, Any]) -> None:
        self.state = state
        for window in self.windows:
            window.update_state(state)
        self._update_window_visibility()

    def update_bookmarks(self, bookmarks: dict[str, Any]) -> None:
        self.bookmarks = bookmarks
        for window in self.windows:
            window.update_bookmarks(bookmarks)

    def do_shutdown(self) -> None:
        if self.monitor_rebuild_id is not None:
            GLib.source_remove(self.monitor_rebuild_id)
            self.monitor_rebuild_id = None
        if self.monitors is not None and self.monitors_changed_id is not None:
            self.monitors.disconnect(self.monitors_changed_id)
            self.monitors_changed_id = None
        self.control_server.stop()
        self.subscription.stop()
        for window in self.windows:
            window.command_connection.close()
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
        return application.run(sys.argv)
    except KeyboardInterrupt:
        application.quit()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
