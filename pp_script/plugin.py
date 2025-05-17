import typing
from uuid import uuid4

from pp_script.core import (
    _logger,
    EventType,
    Event,
    Rect,
    get_window_rect_and_focus,
    get_monitor_rect,
    get_time,
    PPVar,
)
from pp_script.detection.computer_vision import ComputerVision, cv_in_range
from pp_script.detection.mem_reader import ProcessMemoryReader


class Plugin:
    _name = "Abstract Plugin"
    _path = ""

    def __init__(self):
        self._event_types: dict[str:EventType] = {}
        super().__init__()
        self._logger = _logger.getChild(self._name)
        self._rect: Rect = None
        self._focused: bool = None
        self._rect_focus_getter = lambda: None, False
        self._cv: ComputerVision = None
        self._pmr: ProcessMemoryReader = None
        self.events: dict[typing.Any, Event] = {}

    def get_importable_attributes(self):
        attr = {
            "init": self._set_plugin_data,
            "raise_event": self._raise_event,
            "log_debug": self._logger.debug,
            "get_time": get_time,
            "PPVar": PPVar,
            "capture_regions": self.capture_regions,
            "match_template": self.match_template,
            "get_region_fill_ratio": self.get_region_fill_ratio,
            "cv_in_range": cv_in_range,
            "read_pointer": self.read_pointer,
        }

        return attr

    def _set_plugin_data(self, data: dict):
        if target_window := data.get("target_window"):
            self._rect_focus_getter = lambda: get_window_rect_and_focus(target_window)

        if target_monitor := data.get("target_monitor"):
            self._rect_focus_getter = lambda: (get_monitor_rect(target_monitor), True)

        events: dict = data.get("events", {})
        for name, values in events.items():
            assert isinstance(name, str)
            values: dict
            values.setdefault("name", name)
            self._event_types[name] = EventType(values)

        if cv_values := data.get("cv"):
            self._cv = ComputerVision(cv_values, self._path)

        if pmr_values := data.get("pmr"):
            self._pmr = ProcessMemoryReader(pmr_values, self._logger)

    def update(self):
        self.events = {}
        self._update_rect_and_focus()
        self._cv and self._cv.update(self._rect, self._focused)
        self._pmr and self._pmr.update()

    def post_update(self):
        pass

    def _update_rect_and_focus(self):
        rect, focused = self._rect_focus_getter()

        if rect != self._rect:
            self._logger.debug(f"Setting rect to {rect}")
            self._rect = rect

        if focused != self._focused:
            self._logger.debug(f"Setting focused to {focused}")
            self._focused = focused

    def _raise_event(self, values: dict):
        event_id = values.pop("id", uuid4())
        if event_id in self.events:
            raise Exception(f"2 events were raised with the same ID ({event_id})")
        type_name = values.pop("type", None)
        event_type = None if type_name is None else self._event_types[type_name]
        event = Event(event_type, values)
        self.events[event_id] = event

    def terminate(self):
        pass

    # CV attributes
    @property
    def cv(self):
        if not self._cv:
            raise Exception("Internal CV object was not initialized.")
        return self._cv

    def capture_regions(self, regions: list[str] = [], debug=False) -> bool:
        return self.cv.capture_regions(regions=regions, debug=debug)

    def match_template(
        self, template: str, region: str, filter=None, debug: bool = False
    ) -> None | dict:
        return self.cv.match_template(
            template_name=template, region_name=region, filter=filter, debug=debug
        )

    def get_region_fill_ratio(self, region: str, filter, debug: bool = False) -> float:
        return self.cv.get_region_fill_ratio(
            region_name=region, filter=filter, debug=debug
        )

    # PMR attributes
    @property
    def pmr(self):
        if not self._pmr:
            raise Exception("Internal PMR object was not initialized.")
        return self._pmr

    def read_pointer(self, pointer_name: str, debug=False):
        return self.pmr.read_pointer(pointer_name=pointer_name, debug=debug)
