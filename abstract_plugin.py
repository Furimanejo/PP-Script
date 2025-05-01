from time import perf_counter

from .core import (
    _logger,
    PPEventType,
    PPEvent,
    PPVariable,
    Rect,
    get_window_rect_and_focus,
    get_monitor_rect,
)
from .detection.computer_vision import ComputerVision
from .detection.mem_reader import ProcessMemoryReader


class AbstractPlugin:
    _name = "Abstract Plugin"
    _path = ""

    def __init__(self):
        self._event_types: dict[str:PPEventType] = {}
        super().__init__()
        self._logger = _logger.getChild(self._name)
        self._rect: Rect = None
        self._focused: bool = None
        self._rect_focus_getter = lambda: None, False
        self._raised_events: list[PPEvent] = None
        self._cv: ComputerVision = None

    def get_importable_attributes(self):
        return {
            "set_plugin_data": self._set_plugin_data,
            "raise_event": self._raise_event,
            "log_debug": self._logger.debug,
            "PPVariable": PPVariable,
            "capture_regions": self._capture_regions,
            "match_template": self._match_template,
        }

    def _set_plugin_data(self, data: dict):
        if target_window := data.get("target_window"):
            self._rect_focus_getter = lambda: get_window_rect_and_focus(target_window)

        if target_monitor := data.get("target_monitor"):
            self._rect_focus_getter = lambda: (get_monitor_rect(target_monitor), True)

        events: dict = data.get("events", {})
        for name, values in events.items():
            self._event_types[name] = PPEventType(values)

        if cv_values := data.get("cv"):
            self._cv = ComputerVision(cv_values, self._path)

    def pre_update(self):
        self._raised_events = []
        self._update_rect_and_focus()
        self._cv and self._cv.update()

    def post_update(self):
        pass

    def _update_rect_and_focus(self):
        t = perf_counter()
        rect, focused = self._rect_focus_getter()

        if rect != self._rect:
            self._logger.info(f"Setting rect to {rect}")
            self._rect = rect
            self._cv and self._cv.set_rect(rect)

        if focused != self._focused:
            self._logger.info(f"Setting focused to {focused}")
            self._focused = focused
            self._cv and self._cv.set_enabled(focused or True)

    def _raise_event(self, values: dict):
        event = PPEvent(values)
        type_name = values.get("type", None)
        event.type = self._event_types.get(type_name, None)
        self._raised_events.append(event)

    def terminate(self):
        pass

    # CV attributes
    @property
    def cv(self):
        if not self._cv:
            raise Exception("Internal CV object was not initialized.")
        return self._cv

    def _capture_regions(self, *args, **kwargs):
        return self.cv.capture_regions(*args, **kwargs)

    def _match_template(self, *args, **kwargs):
        return self.cv.match_template(*args, **kwargs)
