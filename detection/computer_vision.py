from __future__ import annotations
from os import path as os_path
import copy
import mss
import cv2 as cv
import numpy as np


class ComputerVision:
    def __init__(self, values: dict, path: str):
        self._enabled = False
        self._rect: Rect = None
        self._capture: Capture = None

        values = copy.deepcopy(values)
        _scaling_method = values.get("scaling_method", (1920, 1080))
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
        regions: dict = values.get("regions", {})
        for name, values in regions.items():
            values.setdefault("scaling_method", _scaling_method)
            self._regions[name] = Region(values)

        self._templates: dict[str, Template] = {}
        templates: dict = values.get("templates", {})
        for name, values in templates.items():
            values["path"] = os_path.join(path, values["file"])
            values.setdefault("scaling_method", _scaling_method)
            self._templates[name] = Template(values)

    def update(self, rect: dict):
        self._enabled = rect != None
        self._capture = None

        if rect and rect != self._rect:
            self._rect = rect
            for region in self._regions.values():
                region.scale(self._rect)
            for template in self._templates.values():
                template.scale(self._rect)

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

    def match_template(self, template, region_key):
        if not self._enabled:
            return
        region = self._regions[region_key]
        crop = self._capture.get_region_crop(region)
        _show_image(crop, region_key)


class Capture:
    def __init__(self, rect: Rect):
        self._captured_image = None
        self._region_crops = {}
        self._rect = rect
        self._grab()

    def _grab(self):
        bbox = self._rect.as_bbox()
        with mss.mss() as sct:
            self._captured_image = np.array(sct.grab(bbox))[:, :, :3]

    def get_region_crop(self, region: Region, filter_=None):
        crop_dict = self._region_crops.setdefault(region, {})
        if filter_ not in crop_dict:
            crop = self._get_rect_crop(region.rect)
            if filter_:
                crop = filter_(crop)
            crop_dict[filter_] = crop

        return crop_dict[filter_]

    def _get_rect_crop(self, region_rect: Rect):
        left, top, right, bottom = region_rect.as_bbox()
        left -= self._rect.left
        right -= self._rect.left
        top -= self._rect.top
        bottom -= self._rect.top
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


class Rect:
    def __init__(self, rect):
        if isinstance(rect, dict):
            left = next((rect[k] for k in ("x", "left") if k in rect))
            width = next((rect[k] for k in ("w", "width") if k in rect), None)
            if width is None:
                right = next((rect[k] for k in ("r", "right") if k in rect))
                width = right - left
            top = next((rect[k] for k in ("y", "top") if k in rect))
            height = next((rect[k] for k in ("h", "height") if k in rect), None)
            if height is None:
                bottom = next((rect[k] for k in ("b", "bottom") if k in rect))
                height = bottom - top
            rect = (left, top, width, height)

        rect = [int(v) for v in rect]
        self.left = rect[0]
        self.top = rect[1]
        self.width = rect[2]
        self.height = rect[3]

    def __eq__(self, value):
        if isinstance(value, Rect):
            return (
                self.left == value.left
                and self.top == value.top
                and self.width == value.width
                and self.height == value.height
            )
        return False

    def __ne__(self, value):
        return not self.__eq__(value)

    @property
    def right(self):
        return self.left + self.width

    @right.setter
    def right(self, value):
        self.width = value - self.left

    @property
    def bottom(self):
        return self.top + self.height

    @bottom.setter
    def bottom(self, value):
        self.height = value - self.top

    def as_bbox(self):
        return (self.left, self.top, self.left + self.width, self.top + self.height)

    def as_tuple(self):
        return (self.left, self.top, self.width, self.height)

    def as_dict(self):
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }

    def __repr__(self):
        return f"{self.as_dict()}"


def _show_image(image, name):
    cv.imshow(name, image)
    width = max(image.shape[1], 300)
    height = max(image.shape[0], 50)
    cv.resizeWindow(name, width, height)
    cv.waitKey(1)
