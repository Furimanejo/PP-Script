from src.abstract_plugin import AbstractPlugin
import inspect

importables = AbstractPlugin().get_importable_attributes()
text = ""
for name, attribute in importables.items():
    sig = inspect.signature(attribute)
    text += f"def {name}{sig}:\n"
    text += f"    ...\n"
print(text)
