from __future__ import annotations
import copy
import mss
import cv2 as cv
import numpy as np
from os import path as os_path, makedirs

from pp_script.core import _logger, Rect, read_file_at_folder_or_zip

_logger = _logger.getChild("cv")


class ComputerVision:
    def __init__(self, cv_values: dict, load_path: str, debug_path: str):
        self._debug_folder = os_path.join(debug_path, "cv")
        self._capture: Capture = None
        self._rect: Rect = None
        self._enabled = False

        cv_values = copy.deepcopy(cv_values)
        _scaling_method = cv_values.get("scaling_method", (1920, 1080))
        if isinstance(_scaling_method, tuple):
            resolution_width = _scaling_method[0]
            resolution_height = _scaling_method[1]

            def scale_from_resolution(x, y, w, h, rx, ry, rw, rh):
                x *= rw / resolution_width
                x += rx
                y *= rh / resolution_height
                y += ry
                w *= rw / resolution_width
                h *= rh / resolution_height
                return x, y, w, h

            _scaling_method = scale_from_resolution

        self._regions: dict[str, Region] = {}
        regions: dict = cv_values.get("regions", {})
        for name, values in regions.items():
            if not isinstance(values, dict):
                raise ValueError()
            values.setdefault("scaling_method", _scaling_method)
            self._regions[name] = Region(values)

        self._templates: dict[str, Template] = {}
        templates: dict = cv_values.get("templates", {})
        for name, values in templates.items():
            if not isinstance(values, dict):
                raise ValueError()
            values.setdefault("scaling_method", _scaling_method)
            self._templates[name] = Template(values, folder_path=load_path)

    def update(self, rect: Rect, enable: bool):
        self._capture = None
        self._enabled = enable
        if rect != self._rect:
            for region in self._regions.values():
                region.scale(rect)
            for template in self._templates.values():
                template.scale(rect)
            self._rect = rect

    def capture_regions(self, regions: list[str] = [], debug=False):
        if not self._enabled or not self._rect:
            return False
        regions = regions if regions else [name for name in self._regions]
        regions: list[Region] = [self._regions[r] for r in regions]
        rects: list[Rect] = [r.rect for r in regions]
        left = min([r.left for r in rects])
        top = min([r.top for r in rects])
        right = max([r.right for r in rects])
        bottom = max([r.bottom for r in rects])
        regions_crop = Rect((left, top, right - left + 1, bottom - top + 1))
        try:
            self._capture = Capture(regions_crop)
            return True
        except Exception as e:
            if str(e) == "'_thread._local' object has no attribute 'data'":
                _logger.warning(f"Failed to capture rect {regions_crop}")
            else:
                raise e
            return False

    def _assert_capture(self):
        if self._capture is None:
            msg = f"Failed to assert capture. Make sure to call {self.capture_regions.__name__} and check if it returned True before calling other CV methods"
            _logger.error(msg)
            raise Exception(msg)

    def match_template(self, template_name, region_name, filter=None, debug=False):
        self._assert_capture()

        region_obj = self._regions[region_name]
        region_img = self._capture.get_region_crop(region_obj, filter)
        if region_img is None:
            return
        debug and self._save_image(region_img, f"region {region_name}")

        template_obj = self._templates[template_name]
        template_img = template_obj.scaled_and_filtered(filter)
        debug and self._save_image(template_img, f"template {template_name}")
        if t := template_img.dtype != np.uint8:
            raise Exception(f"Unexpected image type {t}")

        mask = template_obj.mask
        match_results = cv.matchTemplate(
            region_img, template_img, cv.TM_SQDIFF, mask=mask
        )
        min_val, max_val, min_loc, max_loc = cv.minMaxLoc(match_results)
        confidence = 1 - min_val / template_obj.size
        result = {
            "success": confidence >= template_obj.threshold,
            "region": region_name,
            "template": template_name,
            "confidence": confidence,
            "h_pos_percentage": min_loc[0] / region_img.shape[1],
            "v_pos_percentage": min_loc[1] / region_img.shape[0],
        }
        return result

    def get_region_fill_ratio(self, region_name, filter, div=(0, 1, 0, 1), debug=False):
        self._assert_capture()
        region_obj = self._regions[region_name]

        region_crop = self._capture.get_region_crop(region_obj, filter=filter)

        height, width = region_crop.shape[:2]
        left = int(width * div[0])
        right = int(width * div[1])
        top = int(height * div[2])
        bottom = int(height * div[3])
        if 0 <= left <= right <= width and 0 <= top <= bottom <= height:
            region_crop = region_crop[top:bottom, left:right]
        else:
            raise ValueError("Invalid crop dimensions")

        debug and self._save_image(
            region_crop, f"{region_name}_region_{left}_{right}_{top}_{bottom}"
        )
        if len(region_crop.shape) != 2:
            pass  # log warning
        return np.count_nonzero(region_crop) / region_crop.size

    def _save_image(self, image, name):
        path = self._debug_folder
        makedirs(path, exist_ok=True)
        path = os_path.join(path, f"{name}.png")
        cv.imwrite(path, image)


class Capture:
    def __init__(self, rect: Rect):
        self._captured_image = None
        self._region_crops = {}
        self._offset = (rect.left, rect.top)

        bbox = rect.as_bbox()
        with mss.mss() as sct:
            self._captured_image = np.array(sct.grab(bbox))[:, :, :3]

    def get_region_crop(self, region: Region, filter=None) -> np.ndarray:
        if self._captured_image is None:
            return None

        crop_dict = self._region_crops.setdefault(region, {})
        if filter not in crop_dict:
            crop = self._crop(region.rect)
            if filter:
                crop = filter(crop)
            crop_dict[filter] = crop

        return crop_dict[filter]

    def _crop(self, region_rect: Rect):
        left, top, right, bottom = region_rect.as_bbox()
        left -= self._offset[0]
        right -= self._offset[0]
        top -= self._offset[1]
        bottom -= self._offset[1]
        crop = self._captured_image[top:bottom, left:right].copy()
        return crop


class Region:
    def __init__(self, values: dict):
        self._original_rect = Rect(values["rect"])
        self._label_position = values.get("label_position")
        self._scaling_method = values["scaling_method"]
        self._scaled_rect = None

    @property
    def rect(self):
        return self._scaled_rect

    def scale(self, rect: Rect):
        rx, ry, rw, rh = rect.as_tuple()
        x, y, w, h = self._original_rect.as_tuple()
        x, y, w, h = self._scaling_method(x, y, w, h, rx, ry, rw, rh)
        self._scaled_rect = Rect((x, y, w, h))


class Template:
    def __init__(self, values: dict, folder_path: str):
        self.threshold = values["threshold"]
        self._scaling_method = values["scaling_method"]
        self._mask_color = values.get("mask_color", None)
        self._scaled_and_filtered = {}
        self._original_image = None

        f = read_file_at_folder_or_zip(folder_path, values["file"])
        img_array = np.frombuffer(f, dtype=np.uint8)
        self._original_image = cv.imdecode(img_array, cv.IMREAD_COLOR)
        self.mask = None
        self.size = None

    def scale(self, rect: Rect):
        rx, ry, rw, rh = rect.as_tuple()
        h = self._original_image.shape[0]
        w = self._original_image.shape[1]
        _, _, scaled_w, scaled_h = self._scaling_method(0, 0, w, h, rx, ry, rw, rh)
        scaled_w = max(1, int(scaled_w))
        scaled_h = max(1, int(scaled_h))

        template = self._original_image
        if scaled_w != w or scaled_h != h:
            template = cv.resize(template.copy(), (scaled_w, scaled_h))
        self._scaled_and_filtered = {None: template}

        if mask_color := self._mask_color:
            mask = cv.inRange(template, mask_color, mask_color)
            mask = cv.bitwise_not(mask)
        else:
            mask = cv.inRange(template, (0, 0, 0), (255, 255, 255))
        self.mask = mask
        self.size = cv.countNonZero(mask) * template.shape[2] * 255 * 255

    def scaled_and_filtered(self, filter: callable = None) -> np.ndarray:
        if filter not in self._scaled_and_filtered:
            not_filtered = self._scaled_and_filtered[None]
            self._scaled_and_filtered[filter] = filter(not_filtered)
        return self._scaled_and_filtered[filter]


def cv_in_range(img, lower: tuple, upper: tuple):
    if lower[0] > upper[0]:
        # For HSV filters around the red hue (H=0) the H value can wrap around,
        # for example, if lower=(200, 10, 10) and upper=(30, 50, 50) then we do
        # range (0, 10, 10)(30, 50, 50) + range (200, 10, 10)(255, 50, 50)
        first = cv.inRange(img, (0,) + lower[1:], upper)
        second = cv.inRange(img, lower, (255,) + upper[1:])
        return cv.bitwise_or(first, second)
    else:
        return cv.inRange(img, lower, upper)


def cv_to_hsv(img):
    return cv.cvtColor(img, cv.COLOR_BGR2HSV_FULL)
