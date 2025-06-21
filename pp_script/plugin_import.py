import typing
import yaml
import traceback

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
restricted_python_globals["enumerate"] = enumerate

from pp_script.core import _logger as parent_logger, read_file_at_folder_or_zip

logger = parent_logger.getChild("import")
from pp_script.plugin import Plugin


class ImportedPlugin(Plugin):
    @classmethod
    def set_class_data(cls, path, metadata):
        cls.PATH = path
        cls.NAME = metadata["name"]
        cls.SCRIPT_FILE_NAME = metadata["script"]

    def __init__(self):
        super().__init__()
        script = read_file_at_folder_or_zip(self.PATH, self.SCRIPT_FILE_NAME)
        script = script.decode("utf-8")
        # Developers might want import statements for static analysis and
        # autocompletion, but imports can't be compiled/executed, so we
        # remove them from the file first
        lines = script.splitlines()
        for i in range(len(lines)):
            if "import" in lines[i]:
                lines[i] = ""
            else:
                break
        script = "\n".join(lines)
        compiled = compile_restricted(script, self.SCRIPT_FILE_NAME, "exec")

        _globals = restricted_python_globals.copy()
        importable_attrs = self.get_importable_attributes()
        _globals.update(importable_attrs)
        _locals = {}
        exec(compiled, _globals, _locals)
        _globals.update(_locals)

        self._imported_update = _locals.get("update", None)
        if self._imported_update is None:
            self._logger.warning("Update fuction not found")

    def update(self):
        super().update()
        try:
            self._imported_update and self._imported_update()
            pass
        except Exception as e:
            tb = traceback.format_exc()
            raise RuntimeError(f"{tb}")

    def terminate(self):
        super().terminate()


def import_plugin_at_folder(folder_path: str) -> typing.Type[ImportedPlugin] | None:
    try:
        file = read_file_at_folder_or_zip(folder_path, "metadata.yaml")
    except FileNotFoundError:
        # No metadata file, not a plugin folder
        return

    class ThisImportedPlugin(ImportedPlugin): ...

    metadata = yaml.safe_load(file)
    ThisImportedPlugin.set_class_data(folder_path, metadata)
    return ThisImportedPlugin
