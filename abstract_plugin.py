from .core import logger as parent_logger_from_pp_script
from .core import PPEvent, PPVariable, get_time
from .detection.mem_reader import ProcessMemoryReader
from pywinctl import getWindowsWithTitle, getAllScreens, Re

parent_logger = parent_logger_from_pp_script.getChild("plugin")

class AbstractPlugin():
    _name = "undefined plugin name"

    def __init__(self):
        super().__init__()
        self._logger = parent_logger.getChild(self._name)
        self._target_settings = {}
        self._event_types = {}
        self._is_focused = None
        self._rect = None
        self._raised_events: list[PPEvent] = None

    def _get_importable_attributes(self):
        return {
            "set_target": self.set_target,
            "define_events": self.define_events,
            "log_debug": self._logger.debug,
            "get_time": get_time,
            "ProcessMemoryReader": ProcessMemoryReader,
            "PPVariable": PPVariable,
        }

    def set_target(self, args: dict):
        self._target_settings = args.copy()

    def define_events(self, input_event_types: dict):
        self._event_types = input_event_types.copy()

    def update(self):
        self._raised_events = []
        self.update_rect_and_focus()
    
    def update_rect_and_focus(self):
        self._rect = None
        self._is_focused = False
        window_regex = self._target_settings.get("window_title_regex")
        if window_regex:
            self._rect, self._is_focused = get_window_rect_and_focus_by_regex(window_regex)
            return
        
        monitor_number = self._target_settings.get("monitor_number")
        if monitor_number:
            self._rect = get_monitor_rect(monitor_number)
            self._is_focused = True
            return

    def append_event(self, values):
        self._raised_events.append(PPEvent(values))

def get_window_rect_and_focus_by_regex(regex: str):
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

def get_monitor_rect(monitor_number: int):
    screens = list(getAllScreens().values())
    if len(screens) < monitor_number - 1:
        parent_logger.warning(f"Failed to get monitor number {monitor_number}, getting monitor 1 instead")
        monitor_number = 1
    return screens[monitor_number-1]