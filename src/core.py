import logging
import mss
import os
import zipfile
from typing import Any
from pywinctl import getWindowsWithTitle, Re
from time import perf_counter as get_time

_logger = logging.getLogger().getChild("pp_script")


class PPEventType:
    def __init__(self, values: dict):
        self._name = values["name"]
        self._description = values.get("description")
        self.normalize = values.get("scale_amount", lambda x: x)

    def __repr__(self):
        return self._name


class PPEvent:
    def __init__(self, event_type: PPEventType | None, values: dict):
        self._type: PPEventType | None = event_type
        self._raw_amount = values.pop("amount", None)
        if self._type and self._raw_amount is not None:
            self._scaled_amount = self._type.normalize(self._raw_amount)
        else:
            self._scaled_amount = 1
        self.other_data = values

    @property
    def type(self):
        return self._type

    @property
    def scaled_amount(self):
        return self._scaled_amount

    def __repr__(self):
        name = self._type._name if self._type else None
        amount_text = ""
        if self._raw_amount is not None:
            if self._raw_amount % 1 == 0:
                amount_text += f"{int(self._raw_amount)}"
            else:
                amount_text += f"{self._raw_amount:.2f}"

            percent = int(100 * self._scaled_amount)
            amount_text += f" | {percent}%"

        text = f"{name}"
        if amount_text:
            text += f" ({amount_text})"
        return text


class PPVariable:
    def __init__(self, time_window: float = 0, tolerance: float = float("inf")) -> None:
        self._time_window = time_window
        self._tolerance = tolerance
        self._value = None
        self._buffer = {}

    @property
    def value(self):
        return self._value

    def update(self, new_value: float, time: float = 0) -> Any:
        if new_value is None:
            self._value = None
            self._buffer = {}
            return

        self._buffer[time] = new_value
        keys = list(self._buffer)
        biggest_key = max(keys)
        assert biggest_key == time
        if biggest_key - min(keys) < self._time_window:  # not enough values to analyse
            return

        min_key_allowed = biggest_key - self._time_window
        for k in keys:
            if k < min_key_allowed:
                del self._buffer[k]
            else:
                if abs(new_value - self._buffer[k]) > self._tolerance:
                    return

        delta = new_value - self._value if self._value is not None else None
        self._value = new_value
        return delta


def read_file_at_folder_or_zip(folder_path: str, file_path: str) -> bytes:
    if folder_path.endswith(".zip"):
        with zipfile.ZipFile(folder_path) as zip:
            try:
                with zip.open(file_path) as file:
                    return file.read()
            except KeyError:
                raise FileNotFoundError()
    else:
        with open(os.path.join(folder_path, file_path), "rb") as file:
            return file.read()


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
