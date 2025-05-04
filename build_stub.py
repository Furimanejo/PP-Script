from src.abstract_plugin import AbstractPlugin
import inspect

importables = AbstractPlugin().get_importable_attributes()
text = ""
for name, attribute in importables.items():
    sig = inspect.signature(attribute)
    text += f"def {name}{sig}:\n"
    text += f"    ...\n"

import os

path = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(path, "plugin_stub.pyi")

with open(path, "w") as file:
    file.write(text)
