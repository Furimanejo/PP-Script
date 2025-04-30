from .core import logger, PPEventType, PPEvent, PPVariable, get_time
from .detection.computer_vision import ComputerVision, Rect
from .detection.mem_reader import ProcessMemoryReader
from pywinctl import getWindowsWithTitle, Re
from pymonctl import getAllMonitors


class AbstractPlugin:
    _name = "Abstract Plugin"
    _path = ""

    def __init__(self):
        self._event_types: dict[str:PPEventType] = {}
        super().__init__()
        self.b = None
        self._logger = logger.getChild(self._name)
        self._rect = None
        self._is_focused = False
        self._raised_events: list[PPEvent] = None
        self._cv: ComputerVision = None

    def get_importable_attributes(self):
        return {
            "set_plugin_data": self._set_plugin_data,
            "raise_event": self._raise_event,
            "get_time": get_time,
            "log_debug": self._logger.debug,
            "PPVariable": PPVariable,
            "capture_regions": self._capture_regions,
            "match_template": self._match_template,
        }

    def _set_plugin_data(self, data: dict):
        self._target_window = data.get("target_window", None)
        self._target_monitor = data.get("target_monitor", None)
        events: dict = data.get("events", {})
        for name, values in events.items():
            self._event_types[name] = PPEventType(values)
        if cv_values := data.get("cv"):
            self._cv = ComputerVision(cv_values, self._path)

    def update(self):
        self._raised_events = []
        self._update_rect_and_focus()
        self._cv and self._cv.update(self._rect)

    def _update_rect_and_focus(self):
        is_focused = False
        rect = False

        if self._target_window:
            rect, is_focused = self._get_rect_and_focus_by_regex(self._target_window)
        elif self._target_monitor:
            rect = self._get_monitor_rect(self._target_monitor)
            is_focused = True

        if not rect == self._rect:
            self._rect = rect
            self._logger.info(f"Plugin rect set to {self._rect}")

        if is_focused != self._is_focused:
            self._is_focused = is_focused
            self._logger.info(f"Plugin focus set to {self._is_focused}")

    def _get_rect_and_focus_by_regex(self, regex: str):
        rect = None
        focused = False
        windows = getWindowsWithTitle(regex, condition=Re.MATCH)
        if windows:
            w = windows[0]
            rect = Rect(w.getClientFrame()._asdict())
            if rect.width <= 0 or rect.height <= 0:
                rect = None
            focused = w.isActive
        return rect, focused

    def _get_monitor_rect(self, monitor_number: int):
        monitor_index = monitor_number - 1
        screens = getAllMonitors()
        if len(screens) < monitor_index:
            self._logger.warning(
                f"Failed to get monitor number {monitor_number}, getting monitor 1 instead"
            )
            monitor_index = 0
        monitor = screens[monitor_index]
        return Rect(monitor.rect._asdict())

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
