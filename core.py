class FrameData:
    def __init__(self) -> None:
        self.delta_time: float = None
        self.events: list[Event] = []
        self.cv_results: list[dict] = []
        self.debug_info: dict = {}

class Event:
    def __init__(self,
                 event_definition,
                 amount : float = None
                 ):
        self.event_def: EventDefinition = event_definition
        self._amount = amount

    def scaled_amount(self):
        if self.event_def.is_proportional:
            amount = self._amount
            amount /= self.event_def.proportionality_value
            return amount
        else:
            return 1

    def get_points(self, delta_time):
        # return additive_points, instant_points
        if self.event_def is None:
            return 0, 0

        points = self.event_def.get("points", 0)
        points *= self.scaled_amount()

        if self.event_def.duration is not None:
            points *= delta_time / self.event_def.duration

        if self.event_def.is_additive:
            return points, 0
        else:
            return 0, points

    @property
    def name(self):
        return self.event_def.name if self.event_def is not None else None

    @property
    def debug_text(self):
        if self.event_def.is_proportional:
            percent = int(100*self.scaled_amount())
            return f"{self.name} amount = {self._amount} ({percent}%)"
        return f"{self.name}"

class EventDefinition:
    def __init__(self, values: dict) -> None:
        self.name = values["name"]
        self.description = values.get("description", "")
        self.is_additive = values.get("additive")
        self.proportionality_value = values.get("proportional_to")
        self.duration = values.get("duration")
        self._test_event_requested = False

    def assign_config_object(self, config):
        self._config = config
        
    def create_event(self, amount:float = 1) -> Event:
        return Event(self, amount=amount)
        
    def set(self, var_path, value):
        self._config.set(f"events.{self.name}.{var_path}", value)

    def get(self, var_path, default=None):
        return self._config.get(f"events.{self.name}.{var_path}", default)
        
    @property
    def is_proportional(self):
        return self.proportionality_value is not None

    @property
    def point_specifiers_text(self):
        points_specifiers = []

        if self.is_additive:
            points_specifiers.append("Additive")
        else:
            points_specifiers.append("Instant")

        if self.proportionality_value is not None:
            points_specifiers.append(f"Proportional to {self.proportionality_value}")

        if self.duration is not None:
            if self.duration == 1:
                points_specifiers.append("Per Second")
            else:
                points_specifiers.append(f"Per {self.duration}s")

        if points_specifiers == []:
            return ""

        text = " | ".join(points_specifiers)
        return f"[{text}]"

    def set_test_event_requested(self, value: bool):
        self._test_event_requested = value

    def try_get_test_event(self):
        if self._test_event_requested:
            if self.is_additive and self.duration is None:
                self._test_event_requested = False
            return Event(self)
        return None

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
