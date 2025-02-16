from os import path as os_path
_plugin_file_name = "plugin.py"
def _plugin_file_in_folder(folder_path:str):
    return os_path.join(folder_path, _plugin_file_name)

import logging
logger = logging.getLogger("app.generic_plugin")
logger.setLevel(logging.DEBUG)

class GenericPlugin():
    path = None

    def __init__(self):
        with open(_plugin_file_in_folder(self.path), "r", encoding="utf-8") as file:
            plugin_as_text = file.read()
            from RestrictedPython import compile_restricted, safe_globals
            compiled_plugin = compile_restricted(plugin_as_text, "generic plugin", "exec")

            plugin_globals = safe_globals
            from RestrictedPython.Eval import default_guarded_getiter,default_guarded_getitem
            from RestrictedPython.Guards import guarded_iter_unpack_sequence,safer_getattr
            safe_globals['_getiter_'] = default_guarded_getiter
            safe_globals['_getitem_'] = default_guarded_getitem
            safe_globals['_iter_unpack_sequence_'] = guarded_iter_unpack_sequence
            safe_globals['getattr'] = safer_getattr

            from .detection_imports import imported_dict
            plugin_globals |= imported_dict
            
            plugin_globals["log_debug"] = logger.debug
            plugin_globals["append_event"] = self.append_event
            plugin_globals["path"] = self.path

            plugin_locals = {}
            exec(compiled_plugin, plugin_globals, plugin_locals)
            self.detect = plugin_locals["detect"]
            #self.__dict__.update(plugin_locals)
        pass

    def detect():
        print("plugin did not define the detect method")
        pass
    
    def update(self):
        self.detect()

    def append_event(self, name: str):
        print(name)
        pass

def try_import_plugin_at_folder(folder_path:str) -> GenericPlugin | None:
    if not os_path.exists(_plugin_file_in_folder(folder_path)):
        print("No plugin.py file, not a plugin folder")
        return None
    
    class ImportedPlugin(GenericPlugin):
        path = folder_path
    
    return ImportedPlugin
