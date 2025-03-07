from os import path as os_path
from os import listdir as os_listdir
import logging

logger = logging.getLogger("app.plugin")
logger.setLevel(logging.DEBUG)

class BasePlugin():
    name = None

    def __init__(self):
        super().__init__()
        self.events = {}

    def detect(self):
        logger.warning("plugin did not define the detect method")
    
    def update(self):
        self.detect()

    def append_event(self, name: str):
        print(name)

    def print_events(self):
        print(self.events)
        
def _try_get_script_file_in_folder(path: str):
    files = [f for f in os_listdir(path) if f.endswith(".py")]
    if len(files) == 0:
        logger.error(f"Plugin folder has no script: {path}")
        return None
    if len(files) > 1:
        logger.error(f"Plugin folder has more than one script: {path}")
        return None
    return files[0]

def _try_import_script_as_locals(script_path: str):
    script_text = None
    with open(script_path, "r", encoding="utf-8") as f:
        script_text = f.read()

    from RestrictedPython import compile_restricted, safe_globals
    from RestrictedPython.Eval import default_guarded_getiter,default_guarded_getitem
    from RestrictedPython.Guards import guarded_iter_unpack_sequence,safer_getattr
    from .detection_imports import imports_as_dict
    plugin_globals = safe_globals
    plugin_globals['_getiter_'] = default_guarded_getiter
    plugin_globals['_getitem_'] = default_guarded_getitem
    plugin_globals['_iter_unpack_sequence_'] = guarded_iter_unpack_sequence
    plugin_globals['getattr'] = safer_getattr
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
    
    return plugin_locals

def try_import_plugin_at_folder(folder_path: str, plugin_class: type=BasePlugin):
    script_filename = _try_get_script_file_in_folder(folder_path)
    if not script_filename:
        return None
    
    imported_locals = _try_import_script_as_locals(os_path.join(folder_path, script_filename))
    if imported_locals is None:
        return None

    plugin_name = script_filename.rpartition(".")[0]

    class ImportedPlugin(plugin_class):
        path = folder_path
        name = plugin_name

        def __init__(self):
            super().__init__()
            self.__dict__.update(imported_locals)
    
    return ImportedPlugin
