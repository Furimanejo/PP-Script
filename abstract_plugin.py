from .core import logger, PPEvent, PPVariable, get_time
from .detection.mem_reader import ProcessMemoryReader
from pywinctl import getWindowsWithTitle, getAllScreens, Re

class AbstractPlugin():
    _name = "Abstract Plugin"

    def __init__(self):
        super().__init__()
        self.b = None
        self._logger = logger.getChild(self._name)
        self._rect = None
        self._is_focused = None
        self._raised_events: list[PPEvent] = None

    def _get_importable_attributes(self):
        return {
            "set_plugin_data": self._set_plugin_data,
            "ProcessMemoryReader": ProcessMemoryReader,
            "PPVariable": PPVariable,
            "get_time": get_time,
            "log_debug": self._logger.debug,
        }

    def _set_plugin_data(self, data: dict):
        data = data.copy()
        self._event_types = data.pop("events", {})
        self._target_window = data.pop("target_window", None)
        self._target_monitor = data.pop("target_monitor", None)

    def update(self):
        self._raised_events = []
        self._update_rect_and_focus()
    
    def _update_rect_and_focus(self):
        self._rect = None
        self._is_focused = False
        if self._target_window:
            self._rect, self._is_focused = self._get_window_rect_and_focus_by_regex(self._target_window)
            return
        
        if self._target_monitor:
            self._rect = self._get_monitor_rect(self._target_monitor)
            self._is_focused = True
            return

    def _get_window_rect_and_focus_by_regex(self, regex: str):
        rect = None
        focused = False
        windows = getWindowsWithTitle(regex, condition=Re.MATCH)
        if windows:
            w = windows[0]
            frame = w.getClientFrame()
            rect = {
                "left": frame.left,
                "top": frame.top,
                "width": frame.right - frame.left,
                "height": frame.bottom - frame.top,
            }
            focused = w.isActive
        return rect, focused

    def _get_monitor_rect(self, monitor_number: int):
        screens = list(getAllScreens().values())
        if len(screens) < monitor_number - 1:
            self._logger.warning(f"Failed to get monitor number {monitor_number}, getting monitor 1 instead")
            monitor_number = 1
        return screens[monitor_number-1]

    def append_event(self, values):
        self._raised_events.append(PPEvent(values))

    def terminate(self):
        pass
