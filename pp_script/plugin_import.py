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

CURRENT_PP_SCRIPT_VERSION = 1
from pp_script.core import _logger as parent_logger, read_file_at_folder_or_zip

logger = parent_logger.getChild("import")
from pp_script.plugin import Plugin


class ImportedPlugin(Plugin):
    def __init__(self):
        super().__init__()
        script_name = self.METADATA.get("script")
        script = read_file_at_folder_or_zip(self.PATH, script_name)
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

        compiled = compile_restricted(script, script_name, "exec")
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
        logger.error(
            f"""Failed to import plugin at {folder_path}, no metadata file found in the folder, check for unwanted nested folders"""
        )
        return None

    metadata: dict = yaml.safe_load(file)
    required_version = metadata.get("req_lib_ver", 0)
    if required_version > CURRENT_PP_SCRIPT_VERSION:
        logger.error(
            f"""Failed to import plugin at {folder_path}, plugin requires library version {required_version}, current version is {CURRENT_PP_SCRIPT_VERSION}. Check for newer app versions"""
        )
        return None

    class ThisImportedPlugin(ImportedPlugin): ...

    ThisImportedPlugin.METADATA = metadata
    ThisImportedPlugin.PATH = folder_path

    return ThisImportedPlugin
