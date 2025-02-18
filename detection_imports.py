from .detection.mem_reader import ProcessMemoryReader
from .core import PPVariable
imports_as_dict = {name:globals()[name] for name in dir() if not name.startswith("_")}