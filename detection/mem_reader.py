from pymem import Pymem
from pymem.process import module_from_name
from pymem.exception import ProcessNotFound, MemoryReadError
import logging

__all__ = ["ProcessMemoryReader"]

class ProcessMemoryReader:
    def __init__(self, process_name, variables) -> None:
        self.process_name = process_name
        self.variables = variables
        self.process_memory = None
        self.logger = logging.getLogger("app.process_memory_reader")
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug("PMR logger started")

    def check_process_memory(self):
        if self.process_memory is None:
            try:
                self.process_memory = Pymem(self.process_name)
                self.logger.info(f"Found process: {self.process_name}")
            except ProcessNotFound:
                pass
        return self.process_memory is not None

    def read_variable(self, name, debug=False):
        if debug:
            self.logger.debug(f"Try reading variable: {name}")
        if not self.check_process_memory():
            if debug:
                self.logger.debug("process not found")
            return None

        v = self.variables[name]
        address = None
        try:
            address = module_from_name(self.process_memory.process_handle, v["module"]).lpBaseOfDll
        except Exception as e:
            self.process_memory = None
            if "'NoneType' object has no attribute 'lpBaseOfDll'" in str(e):
                pass
            else:
                raise e
        if address is None:
            if debug:
                self.logger.debug(f"{name} module not found")
            return None

        if debug:
            self.logger.debug(f"Addr: {hex(address)}")
        try:
            for offset in v["offsets"][:-1]:
                # read pointers as longlong(8bits)
                address = self.process_memory.read_longlong(address + offset) 
                if debug:
                    self.logger.debug(f"Addr: {hex(address)}")
        except Exception as e:
            pass
            
        last_offset = v["offsets"][-1]
        address += last_offset

        result= None
        t = v.get("type")
        try:
            if t == "bool":
                result = self.process_memory.read_bool(address)
            if t == "int":
                result = self.process_memory.read_int(address)
            if t == "float":
                result = self.process_memory.read_float(address)
        except Exception as e:
            if "GetLastError: 998" in str(e):
                pass
            elif "GetLastError: 299" in str(e):
                pass
            elif "'NoneType' object has no attribute" in str(e):
                pass
            else:
                raise e

        if debug:
            self.logger.debug(f"{name} at addr {hex(address)} = {result}")
        return result