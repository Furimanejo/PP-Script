from src.abstract_plugin import AbstractPlugin
import inspect

importables = AbstractPlugin().get_importable_attributes()
text = ""
for name, attribute in importables.items():
    if inspect.isroutine(attribute):
        sig = inspect.signature(attribute)
        text += f"def {name}{sig}: ...\n"
    if inspect.isclass(attribute):
        text += f"class {name}:\n"
        class_attrs = inspect.getmembers(attribute)
        for class_attr_name, class_attr in class_attrs:
            if class_attr_name.startswith("_") and class_attr_name != "__init__":
                continue
            if inspect.isroutine(class_attr):
                sig = inspect.signature(class_attr)
                text += f"    def {class_attr_name}{sig}: ...\n"

import os

path = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(path, "plugin_stub.pyi")

with open(path, "w") as file:
    file.write(text)
