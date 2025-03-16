import time
import logging
from os import path as os_path
from os import listdir as os_listdir
from .core import FrameData

logger = logging.getLogger("pp.plugin")
logger.setLevel(logging.DEBUG)

class BasePlugin():
    name = None

    def __init__(self):
        super().__init__()
        self.events = {}

    def update(self, frame_data: FrameData = None):
        if not frame_data:
            frame_data = FrameData()
        self._frame_data = frame_data
        
        self.detect()
    
    def detect(self):
        logger.warning("plugin did not define the detect method")

    def append_event(self, event_dict):
        self._frame_data.events.append(event_dict)
        
    def get_time(self):
        return time.perf_counter()

def _try_find_script_file_in_folder(path: str):
    files = [f for f in os_listdir(path) if f.endswith(".py")]
    if len(files) == 0:
        logger.error(f"Plugin folder has no script: {path}")
        return None
    if len(files) > 1:
        logger.error(f"Plugin folder has more than one script: {path}")
        return None
    return files[0]

def _try_import_script_file(script_path: str):
    script_text = None
    with open(script_path, "r", encoding="utf-8") as f:
        script_text = f.read()

    from RestrictedPython import compile_restricted, safe_globals, limited_builtins
    from RestrictedPython.Eval import default_guarded_getiter,default_guarded_getitem
    from RestrictedPython.Guards import guarded_iter_unpack_sequence,safer_getattr, full_write_guard
    from .detection_imports import imports_as_dict
    plugin_globals = safe_globals.copy() | limited_builtins.copy()
    plugin_globals['_getiter_'] = default_guarded_getiter
    plugin_globals['_getitem_'] = default_guarded_getitem
    plugin_globals['_iter_unpack_sequence_'] = guarded_iter_unpack_sequence
    plugin_globals['getattr'] = safer_getattr
    plugin_globals['_write_'] = full_write_guard
    plugin_globals |= imports_as_dict
    plugin_globals["log_debug"] = logger.debug

    plugin_locals = {}

    try:
        compiled_plugin = compile_restricted(script_text, script_path, "exec")
        exec(compiled_plugin, plugin_globals, plugin_locals)
    except Exception as e:
        logger.error(f"Failed to import script at {script_path}")
        logger.error(e)
        return None
    
    scope_variables = {
        "globals": plugin_globals,
        "locals": plugin_locals,
    }
    return scope_variables

def try_import_plugin_at_folder(folder_path: str, plugin_class: type=BasePlugin):
    script_filename = _try_find_script_file_in_folder(folder_path)
    if not script_filename:
        return None
    
    plugin_scope_variables = _try_import_script_file(os_path.join(folder_path, script_filename))
    if plugin_scope_variables is None:
        return None

    plugin_name = script_filename.rpartition(".")[0]

    class ImportedPlugin(plugin_class):
        path = folder_path
        name = plugin_name

        def __init__(self):
            super().__init__()
            globals_to_add = {
                "append_event": self.append_event,
                "get_time": self.get_time
            }
            plugin_scope_variables["globals"].update(globals_to_add)
            self.__dict__.update(plugin_scope_variables["locals"])
    
    return ImportedPlugin
