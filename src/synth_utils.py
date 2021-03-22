import numpy as np
import cv2
import supervisely_lib as sly


def draw_white_mask(ann: sly.Annotation) -> np.ndarray:
    h, w = ann.img_size
    mask = np.zeros((h, w, 3), np.uint8)
    ann.draw(mask, [255, 255, 255])
    return mask


def crop_rb(y, x, original_h, original_w, image, ann):
    mask = draw_white_mask(ann)
    h, w, _ = image.shape
    image_rb = image[max(0, h - y): h, max(0, w - x): w, :]
    mask_rb = mask[max(0, h - y): h, max(0, w - x): w, :]
    return image_rb, mask_rb


def place_lt(y, x, main_image, main_mask, image, mask):
    sec_h, sec_w, _ = image.shape
    secondary_object = cv2.bitwise_and(image, mask)
    secondary_bg = 255 - mask
    main_image[y - sec_h:y, x - sec_w:x, :] = cv2.bitwise_and(main_image[y - sec_h:y, x - sec_w:x, :], secondary_bg) + secondary_object
    main_mask[y - sec_h:y, x - sec_w:x, :] -= mask


def crop_lb(y, x, original_h, original_w, image, ann):
    h, w, _ = image.shape
    mask = draw_white_mask(ann)
    image = image[max(0, h - y): h, 0: min(w, original_w - x), :]
    mask = mask[max(0, h - y): h, 0: min(w, original_w - x), :]
    return image, mask


def place_rt(y, x, main_image, main_mask, image, mask):
    main_h, main_w, _ = main_image.shape
    sec_h, sec_w, _ = image.shape

    secondary_object = cv2.bitwise_and(image, mask)
    secondary_bg = 255 - mask

    main_image[y-sec_h:y, x:x+sec_w, :] = cv2.bitwise_and(main_image[y-sec_h:y, x:x+sec_w, :], secondary_bg) + secondary_object
    main_mask[y-sec_h:y, x:x+sec_w, :] -= mask


def crop_rt(y, x, original_h, original_w, image, ann):
    h, w, _ = image.shape
    mask = draw_white_mask(ann)

    image = image[0: min(h, original_h - y), max(0, w - x): w, :]
    mask = mask[0: min(h, original_h - y), max(0, w - x): w, :]
    return image, mask


def place_lb(y, x, main_image, main_mask, image, mask):
    main_h, main_w, _ = main_image.shape
    sec_h, sec_w, _ = image.shape

    secondary_object = cv2.bitwise_and(image, mask)
    secondary_bg = 255 - mask

    main_image[y:y+sec_h, x-sec_w:x, :] = cv2.bitwise_and(main_image[y:y+sec_h, x-sec_w:x, :], secondary_bg) + secondary_object
    main_mask[y:y+sec_h, x-sec_w:x, :] -= mask


def crop_lt(y, x, original_h, original_w, image, ann):
    h, w, _ = image.shape
    mask = draw_white_mask(ann)

    image = image[0: min(h, original_h - y), 0: min(w, original_w - x)]
    mask = mask[0: min(h, original_h - y), 0: min(w, original_w - x)]
    return image, mask


def place_rb(y, x, main_image, main_mask, image, mask):
    main_h, main_w, _ = main_image.shape
    sec_h, sec_w, _ = image.shape

    secondary_object = cv2.bitwise_and(image, mask)
    secondary_bg = 255 - mask

    main_image[y: y+sec_h, x: x+sec_w, :] = cv2.bitwise_and(main_image[y: y+sec_h, x: x+sec_w, :], secondary_bg) + secondary_object
    main_mask[y: y+sec_h, x: x+sec_w, :] -= mask


crops_funcs = [crop_rb,  crop_lb,  crop_rt,  crop_lt]
place_funcs = [place_lt, place_rt, place_lb, place_rb]


def get_y_range(index, h, portion=0.75):
    # 0 <= index <= 3
    y_ranges = [
        [0 + 5, h * portion],
        [0 + 5, h * portion],
        [h - h * portion, h - 1 - 5],
        [h - h * portion, h - 1 - 5]
    ]
    return y_ranges[index]


def get_x_range(index, w, portion=0.75):
    # 0 <= index <= 3
    x_ranges = [
        [0 + 5, w * portion],
        [w - w * portion, w - 1 - 5],
        [0 + 5, w * portion],
        [w - w * portion, w - 1 - 5]
    ]
    return x_ranges[index]