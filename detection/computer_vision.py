from __future__ import annotations
import copy
import mss
import cv2 as cv
import numpy as np
from os import path as os_path

from ..core import _logger, Rect

_logger = _logger.getChild("cv")


class ComputerVision:
    def __init__(self, cv_values: dict, path: str):
        self._enabled = False
        self._rect: Rect = None
        self._capture: Capture = None

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
            values["path"] = os_path.join(path, values["file"])
            values.setdefault("scaling_method", _scaling_method)
            self._templates[name] = Template(values)

    def update(self):
        self._capture = None

    def set_rect(self, rect: dict):
        if rect and rect != self._rect:
            self._rect = rect
            for region in self._regions.values():
                region.scale(self._rect)
            for template in self._templates.values():
                template.scale(self._rect)

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def capture_regions(self, regions=None):
        if not self._enabled:
            return
        regions = regions if regions else [name for name in self._regions]
        regions: list[Region] = [self._regions[r] for r in regions]
        rects: list[Rect] = [r.rect for r in regions]
        left = min([r.left for r in rects])
        top = min([r.top for r in rects])
        right = max([r.right for r in rects])
        bottom = max([r.bottom for r in rects])
        regions_crop = Rect((left, top, right - left, bottom - top))
        self._capture = Capture(regions_crop)

    def match_template(self, template_key, region_key, filter=None):
        results = {}
        if not self._enabled:
            return results
        if not self._capture:
            _logger.error(
                f"You must call {self.capture_regions.__name__} before calling {self.match_template.__name__}"
            )
            return results

        region_obj = self._regions[region_key]
        region_img = self._capture.get_region_crop(region_obj, filter)
        if region_img is None:
            return results

        template_obj = self._templates[template_key]
        template_img: np.ndarray = template_obj.scaled_and_filtered(filter)
        if t := template_img.dtype != np.uint8:
            raise Exception(f"Unexpected image type {t}")

        match_results = cv.matchTemplate(region_img, template_img, cv.TM_SQDIFF)
        min_val, max_val, min_loc, max_loc = cv.minMaxLoc(match_results)
        confidence = 1 - min_val / (template_img.size * 255 * 255)
        print(confidence)

        return results


class Capture:
    def __init__(self, rect: Rect):
        self._captured_image = None
        self._region_crops = {}
        self._offset = (rect.left, rect.top)

        with mss.mss() as sct:
            bbox = rect.as_bbox()
            try:
                self._captured_image = np.array(sct.grab(bbox))[:, :, :3]
            except Exception as e:
                if str(e) == "'_thread._local' object has no attribute 'data'":
                    _logger.warning(f"Failed to capture rect {rect}")
                else:
                    raise e

    def get_region_crop(self, region: Region, filter_=None):
        if self._captured_image is None:
            return None

        crop_dict = self._region_crops.setdefault(region, {})
        if filter_ not in crop_dict:
            crop = self._get_rect_crop(region.rect)
            if filter_:
                crop = filter_(crop)
            crop_dict[filter_] = crop

        return crop_dict[filter_]

    def _get_rect_crop(self, region_rect: Rect):
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
    def __init__(self, values: dict):
        path = values["path"]
        self._original_image = cv.imread(path)
        if self._original_image is None:
            raise Exception(f"Failed to load template: {path}")
        self.scaling_method = values["scaling_method"]
        self._scaled_and_filtered = {}

    def scale(self, rect: Rect):
        rx, ry, rw, rh = rect.as_tuple()
        w = self._original_image.shape[1]
        h = self._original_image.shape[0]
        _, _, scaled_w, scaled_h = self.scaling_method(0, 0, w, h, rx, ry, rw, rh)
        scaled_w = int(scaled_w)
        scaled_h = int(scaled_h)

        self._scaled_and_filtered = {}
        if scaled_w != w or scaled_h != h:
            resized = cv.resize(self._original_image.copy(), (scaled_w, scaled_h))
            self._scaled_and_filtered[None] = resized
        else:
            self._scaled_and_filtered[None] = self._original_image

    def scaled_and_filtered(self, filter: callable = None):
        if filter not in self._scaled_and_filtered:
            not_filtered = self._scaled_and_filtered[None]
            self._scaled_and_filtered[filter] = filter(not_filtered)
        return self._scaled_and_filtered[filter]


def _show_image(image, name):
    cv.imshow(name, image)
    width = max(image.shape[1], 300)
    height = max(image.shape[0], 50)
    cv.resizeWindow(name, width, height)
    cv.waitKey(1)
