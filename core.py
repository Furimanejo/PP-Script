import logging
from time import perf_counter
from pywinctl import getWindowsWithTitle, Re
from pymonctl import getAllMonitors, enableUpdateInfo, Monitor
import mss

_logger = logging.getLogger().getChild("pp_script")


class PPEventType:
    def __init__(self, values: dict):
        self.description = values.get("description")


class PPEvent:
    def __init__(self, values: dict):
        self.type: PPEventType = None
        self.type_name = values.get("type", None)


class PPVariable:
    def __init__(
        self, buffer_length: float = 0, tolerance: float = float("inf")
    ) -> None:
        self._buffer_length = buffer_length
        self._tolerance = tolerance
        self._buffer = {}
        self.value = None
        self.delta = None

    def update(self, value):
        self.delta = None

        if value is None:
            self.value = None
            self._buffer = {}
            return

        t = get_time()
        self._buffer[t] = value

        keys = list(self._buffer.keys())
        value_in_range = True
        for key in keys[::-1]:
            if value_in_range is False:
                del self._buffer[key]
                continue
            if t - key >= self._buffer_length:
                value_in_range = False

        if value_in_range is not False:
            # not enough values to fit the desired buffer length
            return

        values = list(self._buffer.values())
        if max(values) - min(values) <= self._tolerance:
            new_value = sum(values) / len(values)
            if self.value is not None:
                self.delta = new_value - self.value
            self.value = new_value


def get_monitor_rect(monitor_number: int):
    with mss.mss() as sct:
        monitors = sct.monitors
        if monitor_number >= len(monitors):
            _logger.warning(
                f"Failed to get monitor {monitor_number}, returning monitor 1 instead"
            )
            monitor_number = 1
        return Rect(monitors[monitor_number])


def get_window_rect_and_focus(regex: str):
    rect = None
    focused = False

    window = None  # Maybe cache the windows
    if not window:
        results = getWindowsWithTitle(regex, condition=Re.MATCH)
        if results:
            window = results[0]

    if window:
        rect = Rect(window.getClientFrame()._asdict())
        focused = window.isActive

    return rect, focused


class Rect:
    def __init__(self, rect):
        if isinstance(rect, dict):
            left = next((rect[k] for k in ("x", "left") if k in rect))
            width = next((rect[k] for k in ("w", "width") if k in rect), None)
            if width is None:
                right = next((rect[k] for k in ("r", "right") if k in rect))
                width = right - left
            top = next((rect[k] for k in ("y", "top") if k in rect))
            height = next((rect[k] for k in ("h", "height") if k in rect), None)
            if height is None:
                bottom = next((rect[k] for k in ("b", "bottom") if k in rect))
                height = bottom - top
            rect = (left, top, width, height)

        rect = [int(v) for v in rect]
        self.left = rect[0]
        self.top = rect[1]
        self.width = rect[2]
        self.height = rect[3]

    def __eq__(self, value):
        if isinstance(value, Rect):
            return (
                self.left == value.left
                and self.top == value.top
                and self.width == value.width
                and self.height == value.height
            )
        return False

    def __ne__(self, value):
        return not self.__eq__(value)

    @property
    def right(self):
        return self.left + self.width

    @right.setter
    def right(self, value):
        self.width = value - self.left

    @property
    def bottom(self):
        return self.top + self.height

    @bottom.setter
    def bottom(self, value):
        self.height = value - self.top

    def as_bbox(self):
        return (self.left, self.top, self.left + self.width, self.top + self.height)

    def as_tuple(self):
        return (self.left, self.top, self.width, self.height)

    def as_dict(self):
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }

    def __repr__(self):
        return f"{self.as_dict()}"
