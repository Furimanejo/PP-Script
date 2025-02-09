import time
from ..gui import BaseTabWidget, set_image_to_label, add_widget_row, TextBox, SpinBoxFromConfig, ComboBoxFromConfig, CheckBoxFromConfig
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal
from .. import app

class FrameData:
    def __init__(self) -> None:
        self.delta_time: float = None
        self.events: list[Event] = []
        self.cv_results: list[dict] = []
        self.debug_info: dict = {}

class Event:
    def __init__(self,
                 event_definition,
                 amount : float = None
                 ):
        self.event_def: EventDefinition = event_definition
        self._amount = amount

    def scaled_amount(self):
        if self.event_def.is_proportional:
            amount = self._amount
            amount /= self.event_def.proportionality_value
            return amount
        else:
            return 1

    def get_points(self, delta_time):
        # return additive_points, instant_points
        if self.event_def is None:
            return 0, 0

        points = self.event_def.get("points", 0)
        points *= self.scaled_amount()

        if self.event_def.duration is not None:
            points *= delta_time / self.event_def.duration

        if self.event_def.is_additive:
            return points, 0
        else:
            return 0, points

    @property
    def name(self):
        return self.event_def.name if self.event_def is not None else None

    @property
    def debug_text(self):
        if self.event_def.is_proportional:
            percent = int(100*self.scaled_amount())
            return f"{self.name} amount = {self._amount} ({percent}%)"
        return f"{self.name}"

class EventDefinition:
    def __init__(self, values: dict) -> None:
        self.name = values["name"]
        self.description = values.get("description", "")
        self.is_additive = values.get("additive")
        self.proportionality_value = values.get("proportional_to")
        self.duration = values.get("duration")
        self._test_event_requested = False

    def assign_config_object(self, config):
        self._config = config
        
    def create_event(self, amount:float = 1) -> Event:
        return Event(self, amount=amount)
        
    def set(self, var_path, value):
        self._config.set(f"events.{self.name}.{var_path}", value)

    def get(self, var_path, default=None):
        return self._config.get(f"events.{self.name}.{var_path}", default)
        
    @property
    def is_proportional(self):
        return self.proportionality_value is not None

    @property
    def point_specifiers_text(self):
        points_specifiers = []

        if self.is_additive:
            points_specifiers.append("Additive")
        else:
            points_specifiers.append("Instant")

        if self.proportionality_value is not None:
            points_specifiers.append(f"Proportional to {self.proportionality_value}")

        if self.duration is not None:
            if self.duration == 1:
                points_specifiers.append("Per Second")
            else:
                points_specifiers.append(f"Per {self.duration}s")

        if points_specifiers == []:
            return ""

        text = " | ".join(points_specifiers)
        return f"[{text}]"

    def set_test_event_requested(self, value: bool):
        self._test_event_requested = value

    def try_get_test_event(self):
        if self._test_event_requested:
            if self.is_additive and self.duration is None:
                self._test_event_requested = False
            return Event(self)
        return None

class BufferedVariable:
    import time as _time

    def __init__(self, buffer_length: float = 0, tolerance: float = float('inf')) -> None:
        self._buffer_length = buffer_length
        self._tolerance = tolerance
        self._buffer = {}
        self.value = None
        self.delta = None

    def update(self, value):
        self.delta = None

        if value is None:
            self.value = None
            self._buffer = {}
            return

        t = self._time.perf_counter()
        self._buffer[t] = value

        keys = list(self._buffer.keys())
        value_in_range = True
        for key in keys[::-1]:
            if value_in_range is False:
                del self._buffer[key]
                continue
            if t - key >= self._buffer_length:
                value_in_range = False

        if value_in_range is not False:
            # not enough values to fit the desired buffer length
            return
        
        values = list(self._buffer.values())
        if max(values) - min(values) <= self._tolerance:
            new_value = sum(values)/len(values)
            if self.value is not None:
                self.delta = new_value - self.value
            self.value = new_value


class EventWidget(QGroupBox):
    update_hotkeys_signal = pyqtSignal()

    def __init__(self, event_def: EventDefinition, image = None) -> None:
        super().__init__(event_def.name, None)
        self.event_def = event_def
        #self.setStyleSheet("border: 1px solid red;")
        self.layout = QGridLayout(self)
        self.test_triggered = False

        if image is not None:
            image_label = QLabel("", self)
            image_label.setMinimumWidth(60)
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            set_image_to_label(image, image_label)
            add_widget_row(image_label, self.layout)

        text = event_def.point_specifiers_text
        if event_def.description:
            text += " " + event_def.description
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        add_widget_row(label, self.layout, alignment=None)

        test_btn = QPushButton(self, text="Trigger Test Event")
        test_btn.pressed.connect(lambda: event_def.set_test_event_requested(True))
        test_btn.released.connect(lambda: event_def.set_test_event_requested(False))
        add_widget_row(test_btn, self.layout)

        self.row = self.layout.rowCount()
        self.col = 0
        def add_inner_widget(widget):
            self.layout.addWidget(widget, self.row, self.col)
            self.col += 1
            if self.col >= 2:
                self.row += 1
                self.col = 0

        from .. import app
        if app.sex_toy_control:
            points_layout = QGridLayout()
        
            box = SpinBoxFromConfig(event_def, "points", -999, 999)
            add_widget_row(box, points_layout, "Points")

            pattern_combo_box = ComboBoxFromConfig(event_def, "pattern")
            pattern_options = {key:key for key in app.config.get("patterns")}
            pattern_options = {"":""} | pattern_options
            pattern_combo_box.set_options(pattern_options)
            add_widget_row(pattern_combo_box, points_layout, "Pattern")

            intensity_spin = SpinBoxFromConfig(event_def, "pattern_intensity")
            intensity_spin.setSingleStep(5)
            add_widget_row(intensity_spin, points_layout, "Pattern Intensity (%)")

            pattern_disable_delay_spin = SpinBoxFromConfig(event_def, "pattern_disable_delay")
            add_widget_row(pattern_disable_delay_spin, points_layout, "Pattern Duration (s)")

            points_groupbox = QGroupBox("Points/Patterns", self)
            points_groupbox.setLayout(points_layout)
            add_inner_widget(points_groupbox)
            
        if app.shock_control and event_def.is_additive:
            shock_layout = QGridLayout()

            shock_intensity = SpinBoxFromConfig(event_def, "shock_intensity")
            shock_intensity.setSingleStep(5)
            add_widget_row(shock_intensity, shock_layout, "Intensity (%)")

            shock_duration = SpinBoxFromConfig(event_def, "shock_duration", min_= 1, max_= 15)
            add_widget_row(shock_duration, shock_layout, "Duration (s)")
            
            shock_cooldown = SpinBoxFromConfig(event_def, "shock_cooldown", max_= 999)
            shock_cooldown.setSingleStep(5)
            add_widget_row(shock_cooldown, shock_layout, "Cooldown (s)")
            
            shock_box = QGroupBox("Shock", self)
            shock_box.setLayout(shock_layout)
            add_inner_widget(shock_box)

        if app.vts_control:
            vtube_layout = QGridLayout()

            def _update_hotkeys():
                options = {"":""} | {key:key for key in app.vts_control.hotkey_list}
                self.hotkey.set_options(options)

            self.hotkey = ComboBoxFromConfig(event_def, "hotkey")
            _update_hotkeys()
            self.update_hotkeys_signal.connect(_update_hotkeys)
            add_widget_row(self.hotkey, vtube_layout, "Hotkey")

            hotkey_disable_delay = SpinBoxFromConfig(event_def, "hotkey_disable_delay", max_= 999)
            add_widget_row(hotkey_disable_delay, vtube_layout, "Hotkey Duration (s)")

            vtube_groupbox= QGroupBox("VTube Studio")
            vtube_groupbox.setLayout(vtube_layout)
            add_inner_widget(vtube_groupbox)

        if app.sound:
            box_layout = QGridLayout()
            
            label = QLabel()

            def update_filename():
                file = event_def.get("sfx_file")
                if file:
                    filename = file.split("/")[-1]
                    label.setText(f"SFX: {filename}")
                else:
                    label.setText("SFX: None")

            update_filename()

            def pick_file():
                filepath = app.sound.pick_sound_file()[0]
                if filepath:
                    event_def.set("sfx_file", filepath)
                    update_filename()

            def clear_file():
                event_def.set("sfx_file", "")
                update_filename()

            btn = QPushButton("Pick")
            btn.pressed.connect(pick_file)
            box_layout.addWidget(btn, 0, 0)

            clear_btn = QPushButton("Clear")
            clear_btn.pressed.connect(clear_file)
            box_layout.addWidget(clear_btn, 0, 1)
            
            add_widget_row(label, box_layout)

            cooldown = SpinBoxFromConfig(event_def, "sfx_cooldown", min_= 1, max_= 999)
            add_widget_row(cooldown, box_layout, "Cooldown (s)")

            box = QGroupBox("Sound Effect", self)
            box.setLayout(box_layout)
            add_inner_widget(box)

        del self.row
        del self.col
    
class DetectionModule:
    from .computer_vision import ComputerVision
    def __init__(self, module_definitions) -> None:
        self.description = module_definitions.get("description")
        self.process_names = module_definitions.get("process_names")

        # Events
        self.events: dict[str, EventDefinition] = {}
        events_to_define = module_definitions.get("events", {})
        for key, values in events_to_define.items():
            values["name"] = key
            self.events[key] = EventDefinition(values)

        self._variables: dict[str, BufferedVariable] = {}
        for key, values in module_definitions.get("variables", {}).items():
            args = {}
            if "buffer_length" in values:
                args["buffer_length"] = values["buffer_length"]
            if "tolerance" in values:
                args["tolerance"] = values["tolerance"]
            self._variables[key] = BufferedVariable(**args)

        self._triggers = module_definitions.get("triggers")

        # CV
        self.cv = None
        cv_def = module_definitions.get("cv")
        if cv_def:
            self.aspect_ratios = cv_def["aspect_ratios"]
            self.regions = cv_def["regions"]
            self.filters = cv_def.get("filters", {})
            self.templates = cv_def.get("templates", {})
            self.cv = self.ComputerVision(self)

        # Config
        self._custom_config_fields = module_definitions.get("custom_config_fields", {})
        default_config = module_definitions["default_config"]
        if "events" not in default_config:
            default_config["events"] = {}

        default_event_values = {
            "points": 0,

            "pattern": "",
            "pattern_intensity": 50,
            "pattern_disable_delay": 1,

            "shock_intensity": 0,
            "shock_duration": 1,
            "shock_cooldown": 0,

            "sfx_file": "",
            "sfx_cooldown": 1,

            "hotkey": "",
            "hotkey_disable_delay": 0,
        }

        for event in self.events:
            if event not in default_config["events"]:
                default_config["events"][event] = {}
            for key in default_event_values:
                if key not in default_config["events"][event]:
                    default_config["events"][event][key] = default_event_values[key]

        from ..utils import Config
        self.config = Config(module_definitions["config_name"],
                             default_config)

        for event in self.events.values():
            event.assign_config_object(self.config)

    def update(self, frame_data: FrameData) -> FrameData:
        t = time.perf_counter()
        if self.cv:
            # Naive approach, improve later
            self.cv.grab_frame_cropped_to_regions([r for r in self.regions])

        d = time.perf_counter()-t
        d = int(1000*d)
        print(f"ss delay: {d}")

        self._previous_triggers = {}
        for trigger_name, arguments in self._triggers.items():
            if not isinstance(arguments, list):
                app.logger.error(f"Trigger {trigger_name} is not a list")
                continue
            results = {}

            t = time.perf_counter()
            self.execute_trigger(arguments, results)
            d = time.perf_counter()-t
            d = int(1000*d)
            print(f"trigger {trigger_name} delay: {d}")

            frame_data.events.extend(results.get("events", []))
            frame_data.cv_results.extend(results.get("cv_results", []))
            self._previous_triggers[trigger_name] = results

        return frame_data

    def get_value_from_cmd(self, cmd: dict, context: dict):
        if "value" in cmd:
            return cmd["value"]

        if "value_from_trigger" in cmd:
            return self._previous_triggers[cmd["value_from_trigger"]]
                
        if "value_from_config" in cmd:
            return self.config.get(cmd["value_from_config"])
        
        if "value_from_variable" in cmd:
            return self._variables[cmd["value_from_variable"]].value

        if "delta_from_variable" in cmd:
            return self._variables[cmd["delta_from_variable"]].delta

        if "value_from_cv_result" in cmd:
            return context["current_cv_result"][cmd["value_from_cv_result"]]

        return context["value"]

    def execute_trigger(self, argument_list: list, context: dict = {}) -> bool:
        if not context:
            context |= {
                "events": [],
                "cv_results": [],
                "value": None,
            }

        for cmd in argument_list:
            if not isinstance(cmd, dict):
                app.logger.error(f"CMD is not a dict = {cmd}")
                continue

            cmd_name = cmd["cmd"]

            # Value operations
            if cmd_name == "set_trigger_value":
                context["value"] = self.get_value_from_cmd(cmd, context)
                continue
            
            if cmd_name == "apply_value_to_variable":
                var_name = cmd["name"]
                self._variables[var_name].update(context["value"])
                continue

            # Math operations
            if cmd_name == "multiply":
                context["value"] *= self.get_value_from_cmd(cmd, context)
                continue

            if cmd_name == "sum":
                context["value"] += self.get_value_from_cmd(cmd, context)
                continue

            if cmd_name == "cast_to_int":
                context["value"] = int(context["value"])
                continue

            # Flux control
            if cmd_name == "if":
                value_to_check = self.get_value_from_cmd(cmd, context)
                if value_to_check is not None:
                    if "equals" in cmd:
                        check = value_to_check == cmd["equals"]
                    if "more_than" in cmd:
                        check = value_to_check > cmd["more_than"]
                    if "less_than" in cmd:
                        check = value_to_check < cmd["less_than"]

                    case_true = cmd.get("case_true")
                    if case_true is not None and check is True:
                        if self.execute_trigger(case_true, context):
                            return True

                continue

            if cmd_name == "return":
                return True
            
            # CV
            if cmd_name == "match_template":
                t = time.perf_counter()
                matches = self.cv.match_templates_on_region(
                    cmd["region"],
                    cmd["templates"]
                )
                d = time.perf_counter()-t
                d = int(1000*d)
                print(f"match delay: {d}")

                if "on_match" in cmd:
                    for match in matches:
                        context["current_cv_result"] = match
                        if self.execute_trigger(cmd["on_match"], context):
                            return True
                continue

            if cmd_name == "get_region_fill_percentage":
                result = self.cv.get_region_fill_percentage(cmd["region"], cmd["filters"])
                context["current_cv_result"] = result
                continue

            # Results
            if cmd_name == "set_cv_result_label":
                txt = cmd["format"].format(value=context["value"])
                context["current_cv_result"]["text"] = txt
                continue

            if cmd_name == "append_cv_result":
                context["cv_results"].append(context["current_cv_result"])
                continue

            if cmd_name == "raise_event":
                args = {"value": context["value"]} | context["current_cv_result"]
                event_name = cmd["name"].format(**args)
                amount = self.get_value_from_cmd(cmd, context)
                e = self.events[event_name].create_event(amount=amount)
                context["events"].append(e)
                continue

            if cmd_name == "debug":
                app.logger.debug(f"{context}")
                continue

            app.logger.warning(f"Unexpected command ({cmd_name}) in trigger")

        return False

    def create_widget(self):
        self.create_widget_start()

        if self.cv:
            self.create_widget_computer_vision()

        self.create_widget_custom_fields()
        self.create_widget_points()
        self.create_widget_events()

    def create_widget_start(self):
        self.widget = BaseTabWidget()

        if self.description:
            add_widget_row(TextBox(self.description), self.widget.inner_layout, alignment=None)

    def create_widget_computer_vision(self):
        aspect_ratio = ComboBoxFromConfig(self.config, "aspect_ratio_index")
        options = {}
        for i in self.aspect_ratios:
            options[i] = self.aspect_ratios[i]["id"]
        aspect_ratio.set_options(options)
        add_widget_row(aspect_ratio, self.widget.inner_layout, "Aspect Ratio")

    
    def create_widget_custom_fields(self):
        for key, value in self._custom_config_fields.items():
            type_ = value["type"]
            if type_ == "checkbox":
                field = CheckBoxFromConfig(self.config, key)
                label = value.get("label", key)
                add_widget_row(field, self.widget.inner_layout, label)

    def create_widget_points(self):
        if self.config.get("decay"):
            box = SpinBoxFromConfig(self.config, "decay", max_= 9999)
            add_widget_row(box, self.widget.inner_layout, "Score Decay Per Minute")

        if self.config.get("score_cap"):
            box = SpinBoxFromConfig(self.config, "score_cap", max_= 9999)
            add_widget_row(box, self.widget.inner_layout, "Score Cap")

    def create_widget_events(self):
        label = QLabel("Events:")
        add_widget_row(label, self.widget.inner_layout)
        self.event_widgets = []

        for event_name, event_def in self.events.items():
            image = None
            if hasattr(self, "templates"):
                image = self.templates.get(event_name, {}).get("original_image")

            event_widget = EventWidget(event_def, image=image)
            self.event_widgets.append(event_widget)
            add_widget_row(event_widget, self.widget.inner_layout)
    
    def __del__(self):
        name = self.definitions.get("name")
        try:
            app.logger.debug(f"GC-ing module: {name}")
        except:
            pass