class Detector():
    def detect(self, name):
        print(f"detected: {name}")

class PluginBase():
    def __init__(self, plugin_folder_path):
        return 
    
        import os.path as path
        plugin_def_path = path.join(plugin_folder_path, "plugin.py")
        with open(plugin_def_path, "r", encoding="utf-8") as file:
            plugin_as_text = file.read()

            from RestrictedPython import compile_restricted, safe_globals
            compiled_plugin = compile_restricted(plugin_as_text, "<string>", "exec")

            plugin_globals = safe_globals
            plugin_locals = {}
            exec(compiled_plugin, plugin_globals, plugin_locals)
            self.__dict__.update(plugin_locals)

            detector = Detector()
            plugin_globals.update({'detect': detector.detect})

    def update(self):
        print("plugin did not define the update method")