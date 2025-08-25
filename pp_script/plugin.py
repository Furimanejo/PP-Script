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
from pp_script.detection.computer_vision import (
    ComputerVision,
    cv_in_range,
    cv_to_hsv,
    cv_to_gray,
)
from pp_script.detection.mem_reader import ProcessMemoryReader
from pp_script.detection.http import HTTPHandler


class Plugin:
    METADATA: dict = None
    PATH: str = None
    DEBUG_FOLDER: str = None

    def __init__(self):
        self._event_types: dict[str:EventType] = {}
        super().__init__()
        self._logger = _logger.getChild(self.METADATA.get("name", "plugin"))

        self._rect: Rect = None
        self._focused: bool = None
        self._target_window_regex = None
        self._force_focus = False
        self._target_monitor = 1

        self._cv: ComputerVision = None
        self._pmr: ProcessMemoryReader = None
        self._http_handler = None

        self.events: dict[typing.Any, Event] = {}

    def get_importable_attributes(self):
        attr = {
            "init": self._set_plugin_data,
            "raise_event": self._raise_event,
            "log_debug": self._logger.debug,
            "get_time": get_time,
            "PPVar": PPVar,
            # CV
            "capture": self.capture,
            "match_template": self.match_template,
            "get_region_fill_ratio": self.get_region_fill_ratio,
            "cv_in_range": cv_in_range,
            "cv_to_hsv": cv_to_hsv,
            "cv_to_gray": cv_to_gray,
            # Process Memory Reading
            "read_pointer": self.read_pointer,
            # HTTP
            "http_get": self.http_get,
        }

        return attr

    def _set_plugin_data(self, data: dict):
        if target_window := data.get("target_window"):
            self._target_window_regex = target_window

        events: dict = data.get("events", {})
        for name, values in events.items():
            assert isinstance(name, str)
            values: dict
            values.setdefault("name", name)
            self._event_types[name] = EventType(values)

        if cv_values := data.get("cv"):
            self._cv = ComputerVision(cv_values, self.PATH, self.DEBUG_FOLDER)

        if pmr_values := data.get("pmr"):
            self._pmr = ProcessMemoryReader(pmr_values, self._logger)

        if http_values := data.get("http"):
            self._http_handler = HTTPHandler(http_values, self._logger)

        self._update_internals()

    def update(self):
        self.events = {}
        self._update_internals()

    def _update_internals(self):
        rect, focused = self._get_rect_and_focus()
        self._set_rect(rect)
        self._set_focused(focused)
        self._cv and self._cv.update(self._rect, self._focused)
        self._pmr and self._pmr.update()

    @property
    def rect(self):
        return self._rect

    def _set_rect(self, rect):
        if rect != self._rect:
            self._logger.info(f"Setting rect to {rect}")
            self._rect = rect

    @property
    def focused(self):
        return self._focused

    def _set_focused(self, focused):
        if focused != self._focused:
            self._logger.info(f"Setting focused to {focused}")
            self._focused = focused

    def _get_rect_and_focus(self):
        rect = None
        focused = False
        if self._target_window_regex:
            rect, focused = get_window_rect_and_focus(self._target_window_regex)
        if rect is None:
            rect = get_monitor_rect(self._target_monitor)
        if self._force_focus:
            focused = True
        return rect, focused

    def _raise_event(self, values: dict):
        event_id = values.pop("id", uuid4())
        if event_id in self.events:
            raise Exception(f"2 events were raised with the same ID ({event_id})")
        type_name = values.pop("type", None)
        event_type = None if type_name is None else self._event_types[type_name]
        event = Event(event_type, values)
        self.events[event_id] = event

    def terminate(self):
        if self._http_handler:
            self._http_handler.terminate()

    # CV attributes
    @property
    def cv(self):
        if not self._cv:
            raise Exception("Internal CV object was not initialized.")
        return self._cv

    def capture(self, regions: tuple[str] = (), file: str = None, debug=False) -> bool:
        return self.cv.capture(regions=regions, file=file, debug=debug)

    def match_template(
        self,
        template: str,
        region: str,
        filter=None,
        div: tuple = (0, 1, 0, 1),
        debug: bool = False,
    ) -> dict:
        return self.cv.match_template(
            template_name=template,
            region_name=region,
            filter=filter,
            div=div,
            debug=debug,
        )

    def get_region_fill_ratio(
        self,
        region: str,
        filter=None,
        div: tuple = (0, 1, 0, 1),
        debug: bool = False,
    ) -> float:
        return self.cv.get_region_fill_ratio(
            region_name=region,
            filter=filter,
            div=div,
            debug=debug,
        )

    # PMR attributes
    @property
    def pmr(self):
        if not self._pmr:
            raise Exception("Internal PMR object was not initialized.")
        return self._pmr

    def read_pointer(self, pointer_name: str, debug=False):
        return self.pmr.read_pointer(pointer_name=pointer_name, debug=debug)

    # HTTP attributes
    @property
    def http_handler(self):
        if not self._http_handler:
            raise Exception("Internal HTTP object was not initialized.")
        return self._http_handler

    def http_get(self, path_name: str) -> dict:
        return self.http_handler.get(path_name=path_name)
