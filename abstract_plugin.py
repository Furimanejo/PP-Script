from .core import PPEvent, PPVariable
from .detection.mem_reader import ProcessMemoryReader
from .core import logger as parent_logger_from_pp_script

parent_logger = parent_logger_from_pp_script.getChild("plugin")

class AbstractPlugin():
    _name = "undefined plugin name"

    def __init__(self):
        super().__init__()
        self._logger = parent_logger.getChild(self._name)
        self._event_types = {}
        self._is_focused = False
        self._rect = None
        self._raised_events: list[PPEvent] = None

    def _get_importable_attributes(self):
        return {
            "define_events": self.define_events,
            "log_debug": self._logger.debug,
            "ProcessMemoryReader": ProcessMemoryReader,
            "PPVariable": PPVariable,
        }

    def define_events(self, input_event_types: dict):
        self._event_types = input_event_types.copy()

    def update(self):
        self._raised_events = []
    
    def append_event(self, values):
        self._raised_events.append(PPEvent(values))
        