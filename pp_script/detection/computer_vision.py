from __future__ import annotations
import copy
import mss
import cv2 as cv
import numpy as np
import os
import shutil

from pp_script.core import _logger, Rect, read_file_at_folder_or_zip

_logger = _logger.getChild("cv")


class ComputerVision:
    def __init__(self, cv_values: dict, load_path: str, debug_path: str):
        self._load_path = load_path
        self._capture: Capture = None
        self._rect: Rect = None
        self._enabled = False

        debug_path = os.path.join(debug_path, "cv")
        try:
            shutil.rmtree(debug_path)
        except:
            pass
        os.makedirs(debug_path, exist_ok=True)
        self._debug_folder = debug_path

        cv_values = copy.deepcopy(cv_values)
        _scaling_method = cv_values.get("scaling_method", (1920, 1080))
        if isinstance(_scaling_method, tuple):
            ref_rw, ref_rh = _scaling_method

            # scale keeping aspect ratio, possibly letterboxing
            def scale_from_resolution(x, y, w, h, rw, rh):
                scale = min(rw / ref_rw, rh / ref_rh)
                desired_rw = ref_rw * scale
                desired_rh = ref_rh * scale
                offset_x = (rw - desired_rw) / 2
                offset_y = (rh - desired_rh) / 2
                x = x * scale + offset_x
                y = y * scale + offset_y
                w *= scale
                h *= scale
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
            self._scale_all(rect=rect)
            self._rect = rect

    def _scale_all(self, rect: Rect, debug=False):
        for region in self._regions.values():
            region.scale(rect)
        for template in self._templates.values():
            template.scale(rect)

    def _regions_bbox(self, region_names: set[str]):
        regions = [self._regions[k] for k in region_names]
        region_rects = [region.rect for region in regions]
        left = min([r.left for r in region_rects])
        top = min([r.top for r in region_rects])
        right = max([r.right for r in region_rects])
        bottom = max([r.bottom for r in region_rects])
        return left, top, right, bottom

    def capture(self, regions: tuple[str] = (), file: str = None, debug=False):
        regions = sorted(regions)

        capture_rect = self._rect
        offsets = (0, 0)

        img = None
        if file is not None:
            path = os.path.join(self._load_path, file)
            img = cv.imread(filename=path)[:, :, ::-1]
            width = img.shape[1]
            height = img.shape[0]
            capture_rect = Rect((0, 0, width, height))
            self._scale_all(capture_rect, debug=debug)

        if regions:
            regions_bbox = self._regions_bbox(regions)
            offsets = regions_bbox[:2]
            capture_rect = Rect(
                (
                    regions_bbox[0] + capture_rect.left,
                    regions_bbox[1] + capture_rect.top,
                    regions_bbox[2] - regions_bbox[0],
                    regions_bbox[3] - regions_bbox[1],
                )
            )

        if self._enabled or img is not None:
            self._capture = Capture(rect=capture_rect, offsets=offsets, img=img)
            if debug:
                regions_text = "_".join(regions)
                img = self._capture._captured_image.copy()
                for region in self._regions.values():
                    left, top, right, bottom = region.rect.as_bbox()
                    cv.rectangle(
                        img,
                        (
                            left - self._capture._offsets[0],
                            top - self._capture._offsets[1],
                        ),
                        (
                            right - self._capture._offsets[0] - 1,
                            bottom - self._capture._offsets[1] - 1,
                        ),
                        (0, 255, 0),
                        1,
                    )
                self._save_image(img, f"capture {regions_text}")

        return self._capture is not None
        # except Exception as e:
        #     if str(e) == "'_thread._local' object has no attribute 'data'":
        #         _logger.warning(f"Failed to capture rect {regions_crop}")
        #     else:
        #         raise e
        #     return False

    def _assert_capture(self):
        if self._capture is None:
            msg = f"Failed to assert capture. Make sure to call {self.capture.__name__} and check if it returned True before calling other CV methods"
            _logger.error(msg)
            raise Exception(msg)

    def _try_get_region_crop(self, region_name, filter, div, debug):
        region_obj = self._regions[region_name]
        img = None
        try:
            img = self._capture.get_region_crop(region_obj, filter=filter)
        except Capture.RegionOutOfBounds as e:
            raise Capture.RegionOutOfBounds(
                f"Failed to get region {region_name}, out of capture bounds. {e}"
            ) from e

        height, width = img.shape[:2]
        left = int(width * div[0])
        right = int(width * div[1])
        top = int(height * div[2])
        bottom = int(height * div[3])

        if 0 <= left <= right <= width and 0 <= top <= bottom <= height:
            img = img[top:bottom, left:right].copy()
        else:
            raise ValueError(f"Invalid div {div} -> {(left, right, top, bottom)}")

        if debug:
            filter_name = filter.__name__ if filter else ""
            name = f"{region_name} region {filter_name} {(left, right, top, bottom)}"
            self._save_image(img, name)
        return img

    def match_template(
        self,
        template_name,
        region_name,
        filter=None,
        div=(0, 1, 0, 1),
        debug=False,
    ):
        self._assert_capture()

        region_img = self._try_get_region_crop(
            region_name=region_name, filter=filter, div=div, debug=debug
        )

        template_obj = self._templates[template_name]
        template_img, template_mask = template_obj.scaled_and_filtered(filter)
        if debug:
            filter_name = filter.__name__ if filter else ""
            self._save_image(template_img, f"{template_name} template {filter_name}")
        if t := template_img.dtype != np.uint8:
            raise Exception(f"Unexpected image type {t}")

        match_results = cv.matchTemplate(
            region_img, template_img, cv.TM_SQDIFF, mask=template_mask
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

    def get_region_fill_ratio(
        self,
        region_name,
        filter,
        div=(0, 1, 0, 1),
        debug=False,
    ):
        self._assert_capture()
        region_crop = self._try_get_region_crop(
            region_name=region_name, filter=filter, div=div, debug=debug
        )
        if len(region_crop.shape) != 2:
            pass  # log warning
        return np.count_nonzero(region_crop) / region_crop.size

    def _save_image(self, image, name):
        path = os.path.join(self._debug_folder, f"{name}.png")
        if len(image.shape) == 2:
            cv.imwrite(path, image)
        else:
            cv.imwrite(path, image[:, :, ::-1])


class Capture:
    def __init__(self, rect: Rect = None, offsets=(0, 0), img=None):
        self._crops = {}
        self._offsets = offsets
        left, top, right, bottom = rect.as_bbox()
        right += 1
        bottom += 1

        if img is None:
            with mss.mss() as sct:
                bgr = np.array(sct.grab((left, top, right, bottom)))[:, :, :3]
                self._captured_image = bgr[:, :, ::-1]  # BGR to RGB
        else:
            self._captured_image = img[top:bottom, left:right]

    def get_region_crop(self, region: Region, filter=None) -> np.ndarray:
        crop_dict = self._crops.setdefault(region, {})
        if filter not in crop_dict:
            left, top, right, bottom = region.rect.as_bbox()
            left -= self._offsets[0]
            right -= self._offsets[0]
            top -= self._offsets[1]
            bottom -= self._offsets[1]
            height, width = self._captured_image.shape[:2]

            if left < 0 or top < 0 or right > width or bottom > height:
                msg = f"Region={region.rect.as_tuple()}"
                msg += f", Capture={self._offsets+(width, height)}"
                raise Capture.RegionOutOfBounds(msg)

            crop = self._captured_image[top:bottom, left:right].copy()
            if filter:
                crop = filter(crop)
            crop_dict[filter] = crop

        crop = crop_dict[filter]
        return crop

    class RegionOutOfBounds(RuntimeError):
        pass


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
        x, y, w, h = self._scaling_method(x, y, w, h, rw, rh)
        self._scaled_rect = Rect((x, y, w, h))


class Template:
    def __init__(self, values: dict, folder_path: str):
        self.threshold = values["threshold"]
        self._scaling_method = values["scaling_method"]
        self._base_image = None

        f = read_file_at_folder_or_zip(folder_path, values["file"])
        img_array = np.frombuffer(f, dtype=np.uint8)
        self._base_image = cv.imdecode(img_array, cv.IMREAD_COLOR_RGB)
        if mask_color := values.get("mask_color", None):
            mask = cv.inRange(self._base_image, mask_color, mask_color)
            self._base_mask = cv.bitwise_not(mask)
        else:
            self._base_mask = cv.inRange(self._base_image, (0, 0, 0), (255, 255, 255))

        self._scaled_mask = None
        self._scaled_and_filtered = {}

    def scale(self, rect: Rect):
        rx, ry, rw, rh = rect.as_tuple()
        h = self._base_image.shape[0]
        w = self._base_image.shape[1]
        _, _, scaled_w, scaled_h = self._scaling_method(0, 0, w, h, rw, rh)
        scaled_w = max(1, int(scaled_w))
        scaled_h = max(1, int(scaled_h))

        template = self._base_image
        mask = self._base_mask
        if scaled_w != w or scaled_h != h:
            template = cv.resize(
                self._base_image,
                (scaled_w, scaled_h),
                interpolation=cv.INTER_NEAREST_EXACT,
            )
            mask = cv.resize(
                mask,
                (scaled_w, scaled_h),
                interpolation=cv.INTER_NEAREST_EXACT,
            )

        self.size = cv.countNonZero(mask) * template.shape[2] * 255 * 255
        self._scaled_and_filtered = {None: template}
        self._scaled_mask = mask

    def scaled_and_filtered(self, filter: callable = None) -> np.ndarray:
        if filter not in self._scaled_and_filtered:
            not_filtered = self._scaled_and_filtered[None]
            self._scaled_and_filtered[filter] = filter(not_filtered)
        return self._scaled_and_filtered[filter], self._scaled_mask


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
    return cv.cvtColor(img, cv.COLOR_RGB2HSV_FULL)


def cv_to_gray(img):
    return cv.cvtColor(img, cv.COLOR_RGB2GRAY)
