import os
import time
import mss
import numpy as np
import cv2 as cv
from ..utils import bundle_path
from .. import app

class ComputerVision():
    def __init__(self, module) -> None:
        self.module = module
        self.target_rect = {}
        self.resolution_scaling_factor = 1
        self.loaded = False
        self._filters =  {}
        self._load_filters()
        self._load_templates()

    def _load_filters(self):
        for filter_name, filter_def in self.module.filters.items():
            type_ = filter_def["type"]
            if type_ == "rgb":
                lower = tuple(filter_def["lower"][::-1])
                upper = tuple(filter_def["upper"][::-1])
                self._filters[filter_name] = lambda image, lower=lower, upper=upper: bgr_filter(image, lower, upper)
                continue

            app.logger.warning(f"Unexpected filter type {filter_name}: {filter_def}")

    def _scale_rect(self, rect):
        scaled_rect = {
            "x": max(int(rect["x"] * self.resolution_scaling_factor), 1),
            "y": max(int(rect["y"] * self.resolution_scaling_factor), 1),
            "w": max(int(rect["w"] * self.resolution_scaling_factor), 1),
            "h": max(int(rect["h"] * self.resolution_scaling_factor), 1)
        }
        return scaled_rect

    def _scale_template(self, template):
        original_image = template.get("original_image")

        i = self.module.config.get("aspect_ratio_index")
        base_res = str(self.module.aspect_ratios[i]["sample_w"]) + "x" + str(self.module.aspect_ratios[i]["sample_h"])
        default_template_scaling_factor = self.module.aspect_ratios[i].get("template_scaling", 1)

        scale_w = default_template_scaling_factor
        scale_h = default_template_scaling_factor

        template_on_base_res_settings = template.get(base_res)
        if template_on_base_res_settings:
            scale_w = template_on_base_res_settings.get("scale_w", scale_w)
            scale_h = template_on_base_res_settings.get("scale_h", scale_h)

        height = max(int(original_image.shape[0] * self.resolution_scaling_factor * scale_w), 1)
        width =  max(int(original_image.shape[1] * self.resolution_scaling_factor * scale_h), 1)

        image = cv.resize(original_image.copy(), (width, height))

        mask_color = template.get("mask_color")
        if mask_color:
            mask_color = tuple(mask_color[::-1])
            mask = cv.inRange(image, mask_color, mask_color)
            mask = cv.bitwise_not(mask)
            template["mask"] = mask
            if template.get("debug"):
                _show_image(mask, "loaded mask")

        if template.get("filter"):
            image = template.get("filter")(image)

        if template.get("debug"):
            _show_image(image, "loaded template")

        template["image"] = image
    
    def _load_templates(self):
        path = getattr(self.module, "path", None)
        if path is None:
            path = bundle_path()

        path = os.path.join(path, "templates")

        for template in self.module.templates.values():
            file_name = template["filename"]
            file_path = os.path.join(path, file_name)
            original_image = cv.imread(file_path)
            if original_image is None:
                app.logger.error(f"Failed to load template: {file_name}")
            else:
                template["original_image"] = original_image

    def set_target_rect(self, original_rect):
        sample_width = self.module.aspect_ratios[self.module.config.get("aspect_ratio_index")]["sample_w"]
        sample_height = self.module.aspect_ratios[self.module.config.get("aspect_ratio_index")]["sample_h"]
        
        game_rect = original_rect.copy()
        scale = 1

        try:
            monitor_aspect_ratio = original_rect["width"] / original_rect["height"]
        except:
            monitor_aspect_ratio = 0

        if monitor_aspect_ratio >= sample_width / sample_height:
            # scale to fit height, like fitting a 16:9 window on a 21:9 screen
            scale = original_rect["height"] / sample_height
            desired_width = int(sample_width * scale)
            black_bar_width = int((original_rect["width"] - desired_width) / 2)
            game_rect["width"] = desired_width
            game_rect["left"] += black_bar_width
        else:
            # scale to fit width, like fitting a 16:9 window on a 16:10 screen
            scale = original_rect["width"] / sample_width
            desired_height = int(sample_height * scale)
            black_bar_height = int((original_rect["height"] - desired_height) / 2)
            game_rect["height"] = desired_height
            game_rect["top"] += black_bar_height

        if self.target_rect != game_rect:
            app.logger.info(f'Setting computer vision Rect: {game_rect} and Scale: {scale}')
            self.target_rect = game_rect
            self.resolution_scaling_factor = scale
            self.setup_regions_and_templates()
            self.loaded = True

    def setup_regions_and_templates(self):
        for region in self.module.regions:
            i = self.module.config.get("aspect_ratio_index")
            base_resolution = str(self.module.aspect_ratios[i]["sample_w"]) + "x" + str(self.module.aspect_ratios[i]["sample_h"])
            rect = self.module.regions[region].get(base_resolution)
            if rect == None:
                app.logger.warning(f"Region {region} not defined for current aspect ratio")
                rect = self.module.regions[region].get("1920x1080")

            self.module.regions[region]["ScaledRect"] = self._scale_rect(rect)

        for template in self.module.templates:
            self._scale_template(self.module.templates[template])
     
    def grab_frame_cropped_to_regions(self, regionNames):
        if not self.target_rect:
            return
        top = self.target_rect["height"]
        left = self.target_rect["width"]
        bottom = 0
        right = 0

        # Find rect that encompasses all regions
        for region in regionNames:
            rect = self.module.regions[region]["ScaledRect"]
            top = min(top, rect["y"])
            bottom = max(bottom, rect["y"]+rect["h"])
            left = min(left, rect["x"])
            right = max(right, rect["x"]+rect["w"])

        self.frame_offset = (top, left)

        top += self.target_rect["top"]
        bottom += self.target_rect["top"]
        left += self.target_rect["left"]
        right += self.target_rect["left"]

        self.frame = _grab((left, top, right, bottom))
    
    def _get_cropped_frame_copy(self, rect):
        top = rect["y"] - self.frame_offset[0]
        bottom = rect["y"] + rect["h"] - self.frame_offset[0]
        left = rect["x"] - self.frame_offset[1]
        right = rect["x"] + rect["w"] - self.frame_offset[1]
        return self.frame[top:bottom, left:right].copy()

    def match_templates_on_region(self, region_key, template_keys, 
                                  crop_horizontal_center = False,
                                  method=cv.TM_CCOEFF_NORMED):
        t0 = time.perf_counter()
        matches = []

        if len(template_keys) == 0:
            return matches

        region = self.module.regions[region_key]
        crop = self._get_cropped_frame_copy(region["ScaledRect"])

        filtered_crops = {}
        for template_key in template_keys:
            filt = self.module.templates[template_key].get("filter")
            if filt is not None and filt not in filtered_crops:
                filtered_crops[filt] = filt(crop.copy())

        max_matches = region.get("max_matches", 1)
        for template_key in template_keys:
            if len(matches) >= max_matches:
                break

            template = self.module.templates[template_key]
            template_h, template_w = template["image"].shape[:2]
            filt = template.get("filter")
            if filt:
                selected_crop = filtered_crops[filt]
            else:
                selected_crop = crop

            crop_h, crop_w = selected_crop.shape[:2]
            if crop_horizontal_center:
                # To save performance and avoid false positives: crop the selected crop to the center, to fit the template's width
                crop_w = selected_crop.shape[1]
                left = int((crop_w - template_w)/2)
                right = left + template_w
                left = max(left - 3, 0)
                right = min(right + 3, crop_w)
                selected_crop = selected_crop[:,left:right,:]
                crop_w = right-left

            if template_h > crop_h or template_w > crop_w:
                app.logger.error(
                    f"Template {template_key} ({template_w}x{template_h}) is bigger than region crop ({crop_w}x{crop_h})"
                )
                continue

            match_max_value, match_loc = _match_template(selected_crop, template, method=method)
            
            if match_max_value >= template["threshold"]:
                template_w

                match = {
                    "region": region_key,
                    "template_name": template_key,
                    "confidence": match_max_value,
                    "h_pos_percentage": match_loc[0] / crop_w,
                    "v_pos_percentage": match_loc[1] / crop_h,
                }
                matches.append(match)
                
        return matches
      
    def get_region_fill_percentage(self, region_key, filters: list):
        rect = self.module.regions[region_key]["ScaledRect"]
        frame = self._get_cropped_frame_copy(rect)

        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        for filter_name in filters:
            mask_from_filter = self._filters[filter_name](frame)
            mask = cv.bitwise_or(mask, mask_from_filter)

        count = np.count_nonzero(mask)
        percentage = count/mask.size
        return {"region": region_key, "percentage": percentage}

    def read_bar_left_to_right(self, bar_region_name, filter_op, divisions = 20, precision = 0.5, debug = False):
        rect = self.module.regions[bar_region_name]["ScaledRect"]
        frame = self._get_cropped_frame_copy(rect)
        mask = filter_op(frame)
        width = rect["w"]
        height = rect["h"]
        percentage = 0
        for i in range(divisions):
            left = int(width * i / divisions)
            right = int(width * (i+1) / divisions)
            area = (right-left) * height
            if area == 0:
                break
            subdivision_percentage = np.count_nonzero(mask[:,left:right]) / area
            if subdivision_percentage < precision:
                percentage += subdivision_percentage / divisions
                break
            else:
                percentage += 1/divisions
        if debug:
            _show_image(mask, "region")
        return {"name": bar_region_name, "region": bar_region_name, "cv_value": percentage}

def _grab(left_top_right_bottom):
    with mss.mss() as sct:
        return np.array(sct.grab(left_top_right_bottom))[:,:,:3]

def _match_template(frame, template, method=cv.TM_CCOEFF_NORMED):
    template_image = template["image"]
    template_mask = template.get("mask", np.ones((template_image.shape[0], template_image.shape[1], 1), dtype="uint8"))
    if method == "Custom":
        result = cv.matchTemplate(frame, template_image, cv.TM_SQDIFF, mask=template_mask)
        result /= 255
        result /= 255
        if len(template_image.shape) >= 3:
            result /= template_image.shape[2]
        result /= np.count_nonzero(template_mask)
        result = 1 - result
    else:
        result = cv.matchTemplate(frame, template_image, method, mask=template_mask)

    minVal, maxVal, minLoc, maxLoc = cv.minMaxLoc(result)
    if maxVal > 1:
        maxVal = 0

    if template.get("debug"):
        _show_image(frame, "match region")
        _show_image(result, "match result")
        app.logger.debug(f"maxVal: {maxVal}, maxLoc: {maxLoc}")

    return maxVal, maxLoc

def _show_image(image, name):
    cv.imshow(name, image)
    width = max(image.shape[1], 300)
    height = max(image.shape[0], 50)
    cv.resizeWindow(name, width, height)
    cv.waitKey(1)

def sobel_op(image, dx, dy, dilate=0):
    s = cv.Sobel(image, ddepth= cv.CV_8U, dx = dx, dy = dy, ksize = 3)
    s = cv.dilate(s, np.ones((3,3), np.uint8), iterations=dilate)
    return s

def sobel_proper(image, dx=True, dy=True, dilate=0):
    sobel_x = None
    sobel_y = None

    ksize = 3
    in_format = cv.CV_16S
    if dx:
        sobel_x = cv.Sobel(image, dx = 1, dy = 0, ksize=ksize, ddepth=in_format)
    if dy:
        sobel_y = cv.Sobel(image, dx = 0, dy = 1, ksize=ksize, ddepth=in_format)

    result = None
    if sobel_x is None:
        result =  sobel_y
    if sobel_y is None:
        result = sobel_x
    if result is None:
        result = cv.add(sobel_x, sobel_y)

    result = np.uint8(np.absolute(result))
    result = cv.dilate(result, np.ones((3,3), np.uint8), iterations=dilate)
    return result

def laplacian_op(image):
    i = cv.Laplacian(image, cv.CV_16S)
    i = np.uint8(np.absolute(i))
    i = cv.dilate(i, np.ones((3,3), np.uint8), iterations=1)
    return i

def canny_op(image, threshold1, threshold2):
    c = cv.Canny(image, threshold1, threshold2)
    c = cv.dilate(c, np.ones((3,3), np.uint8), iterations=1)
    c = cv.erode(c, np.ones((3,3), np.uint8), iterations=1)
    return c

def red_channel(image):
    (b,g,r) = cv.split(image)
    return r

def bgr_filter(image, lower_bgr, upper_bgr):
    return cv.inRange(image, lower_bgr, upper_bgr)

def hsv_filter(image, lower_hsv, upper_hsv, debug=False):
    hsv = cv.cvtColor(image, cv.COLOR_BGR2HSV)
    result = cv.inRange(hsv, lower_hsv, upper_hsv)
    if debug:
        _show_image(result, "Result")
        _show_image(cv.cvtColor(hsv, cv.COLOR_BGR2RGB), "HSV")
        if True:
            (h,s,v) = cv.split(hsv)
            _show_image(h, "H")
            _show_image(s, "S")
            _show_image(v, "V")

    return result

def prompt_filter(image):
    hsv = cv.cvtColor(image, cv.COLOR_BGR2HSV)
    (h, s, v) = cv.split(hsv)
    mean_v = cv.mean(v)[0]
    t = 200
    if mean_v > t:
        v = s
    v = cv.Canny(v, t, 0)
    v = cv.dilate(v, np.ones((3,3), np.uint8), iterations= 1)
    return cv.merge((v, v, v))

def popup_filter(image):
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)

    right = gray.shape[1]
    left = max(0, right - 50)
    mean = cv.mean(gray[:,left:right])
        
    sat = 50
    value = 130
    mask = cv.inRange(gray, int(mean[0] - sat), int( 0.5*mean[0] + value))
    image[(mask==0)] = [255, 255, 255]
    image[(mask==255)] = [0, 0, 0]
    return image

def light_gray_filter(image):
    hsv = cv.cvtColor(image, cv.COLOR_BGR2HSV)
    (h, s, v) = cv.split(hsv)
    light_gray = cv.subtract(v, s)
    return light_gray