import logging
from typing import Callable, Any
from pymem import Pymem
from pymem.process import module_from_name
from pymem.exception import ProcessNotFound


class ProcessMemoryReader:
    def __init__(self, values: dict, logger: logging.Logger) -> None:
        self._logger = logger.getChild("pmr")
        self._process_name = values.get("process")

        self._pointers: dict[str, Pointer] = {}
        pointers: dict = values.get("pointers", {})
        for name, pointer_values in pointers.items():
            self._pointers[name] = Pointer(values=pointer_values)

        self._memory = None

    def update(self):
        has_prev_memory = self._memory is not None

        if not self._memory:
            try:
                self._memory = Pymem(self._process_name)
            except ProcessNotFound:
                self._memory = None

        if self._memory:
            try:
                self._memory.read_bytes(self._memory.base_address, 1)
            except Exception as e:
                self._memory = None
                if "Could not find process first module" in str(e):
                    pass
                else:
                    raise e

        has_memory = self._memory is not None
        if has_memory and not has_prev_memory:
            self._logger.info(f"Found process memory: {self._process_name}")
        if has_prev_memory and not has_memory:
            self._logger.info(f"Lost process memory: {self._process_name}")

        for p in self._pointers.values():
            p.update(self._memory)

    def read_pointer(self, pointer_name, debug=False):
        pointer: Pointer = self._pointers[pointer_name]
        value = pointer.read()
        debug and self._logger.debug(f"{pointer_name}: {value}")
        return value


class Pointer:
    def __init__(self, values: dict):
        self.module_name: str = values["module"]
        self.offsets: list = values["offsets"]
        self.type_read_method: Callable[[Pymem, Any], Any] = {
            "bool": Pymem.read_bool,
            "int": Pymem.read_int,
            "float": Pymem.read_float,
        }[values["type"]]

        self._memory: Pymem = None

    def update(self, memory: Pymem):
        self._memory = memory

    def read(self):
        if not self._memory:
            return

        module_info = module_from_name(self._memory.process_handle, self.module_name)
        if module_info is None:
            return

        address = module_info.lpBaseOfDll

        try:
            for offset in self.offsets[:-1]:
                address = self._memory.read_longlong(address + offset)
            address += self.offsets[-1]
            return self.type_read_method(self._memory, address)
        except Exception as e:
            if "GetLastError: 998" in str(e):
                pass
            elif "GetLastError: 299" in str(e):
                pass
            elif "'NoneType' object has no attribute" in str(e):
                pass
            else:
                raise e
