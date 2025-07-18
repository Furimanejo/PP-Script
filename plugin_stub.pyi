def init(data: dict): ...
def raise_event(values: dict): ...
def log_debug(msg, *args, **kwargs): ...
def get_time(): ...
class PPVar:
    def __init__(self, time_window: float = 0, tolerance: float = inf) -> None: ...
    def update(self, new_value: float) -> Any: ...
def capture(regions: tuple[str] = (), file: str = None, debug=False) -> bool: ...
def match_template(template: str, region: str, filter=None, div: tuple = (0, 1, 0, 1), debug: bool = False) -> dict: ...
def get_region_fill_ratio(region: str, filter=None, div: tuple = (0, 1, 0, 1), debug: bool = False) -> float: ...
def cv_in_range(img, lower: 'tuple', upper: 'tuple'): ...
def cv_to_hsv(img): ...
def cv_to_gray(img): ...
def read_pointer(pointer_name: str, debug=False): ...
def http_get(path_name: str) -> dict: ...
