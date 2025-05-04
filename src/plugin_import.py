from os import path as os_path
from os import listdir as os_listdir

from RestrictedPython import compile_restricted, safe_globals, limited_builtins
from RestrictedPython.Eval import default_guarded_getiter, default_guarded_getitem
from RestrictedPython.Guards import (
    guarded_iter_unpack_sequence,
    safer_getattr,
    full_write_guard,
)

restricted_python_globals = safe_globals.copy() | limited_builtins.copy()
restricted_python_globals["_getiter_"] = default_guarded_getiter
restricted_python_globals["_getitem_"] = default_guarded_getitem
restricted_python_globals["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence
restricted_python_globals["getattr"] = safer_getattr
restricted_python_globals["_write_"] = full_write_guard
restricted_python_globals["min"] = min
restricted_python_globals["max"] = max
restricted_python_globals["len"] = len

from .core import _logger as parent_logger

logger = parent_logger.getChild("import")
from .abstract_plugin import AbstractPlugin


def _try_find_script_file_in_folder(path: str):
    files = [f for f in os_listdir(path) if f.endswith(".py")]
    if len(files) == 0:
        logger.error(f"Plugin folder has no script: {path}")
        return None
    if len(files) > 1:
        logger.error(f"Plugin folder has more than one script: {path}")
        return None
    return files[0]


def try_import_plugin_at_folder(folder_path: str):
    script_filename = _try_find_script_file_in_folder(folder_path)
    if not script_filename:
        return None

    class ImportedPlugin(AbstractPlugin):
        _name = script_filename.rpartition(".")[0]
        _path = folder_path

        def __init__(self):
            super().__init__()
            self._imported_update = None

            _globals = restricted_python_globals.copy()
            attrs = self.get_importable_attributes()
            _globals.update(attrs)

            _locals = {}
            script_path = os_path.join(self._path, script_filename)
            with open(script_path, "r", encoding="utf-8") as f:
                script_text = f.read()
                # Developers might want import statements for static analysis and
                # autocompletion, but imports can't be compiled/executed, so we
                # remove them from the file first
                lines = script_text.splitlines()
                for line in lines:
                    if "import" in line:
                        lines = lines[1:]
                    else:
                        break
                script_text = "\n".join(lines)

                compiled_plugin = compile_restricted(script_text, script_path, "exec")
                exec(compiled_plugin, _globals, _locals)

            self._imported_update = _locals.get("update", None)

        def update(self):
            super().update()
            self._imported_update and self._imported_update()

        def terminate(self):
            super().terminate()
            del self._imported_update

    return ImportedPlugin
