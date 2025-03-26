import logging
import time
from .core import PPEvent

logger = logging.getLogger("pp.plugin")
logger.setLevel(logging.DEBUG)

class AbstractPlugin():
    _name = "undefined name"

    def __init__(self):
        super().__init__()
        self._rect = None
        self._raised_events: list[PPEvent] = None

    def _get_event_types(self):
        return getattr(self, "event_types", {})

    def update(self):
        self._raised_events = []
        self.detect()
    
    def detect(self):
        logger.warning("plugin did not define the detect method")

    def append_event(self, values):
        self._raised_events.append(PPEvent(values))
        
    def get_time(self):
        return time.perf_counter()
