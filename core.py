import logging
LOGGER_NAME = "pp_script"
logger = logging.getLogger(LOGGER_NAME)

def set_parent_logger(parent_logger: logging.Logger):
    global logger
    logger = parent_logger.getChild(LOGGER_NAME)

class PPEvent:
    def __init__(self, values: dict):
        self.type_name = values.pop("type", None)

class PPVariable:
    import time as _time

    def __init__(self, buffer_length: float = 0, tolerance: float = float('inf')) -> None:
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

        t = self._time.perf_counter()
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
            new_value = sum(values)/len(values)
            if self.value is not None:
                self.delta = new_value - self.value
            self.value = new_value
