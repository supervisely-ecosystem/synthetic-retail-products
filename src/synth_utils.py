import numpy as np
import cv2
import supervisely_lib as sly
import os
import random

def get_files_paths(src_dir, extensions):
    files_paths = []
    for root, dirs, files in os.walk(src_dir):
        for extension in extensions:
            for file in files:
                if file.endswith(extension):
                    file_path = os.path.join(root, file)
                    files_paths.append(file_path)

    return files_paths

def crop_label(img, ann: sly.Annotation, padding):
    h, w, _ = img.shape
    label = ann.labels[0]
    bbox: sly.Rectangle = label.geometry.to_bbox()

    obj_h = bbox.bottom - bbox.top
    obj_w = bbox.right - bbox.left

    top_pad = int(obj_h * padding)
    bottom_pad = int(obj_h * padding)
    left_pad = int(obj_w * padding)
    right_pad = int(obj_w * padding)
    if bbox.top - top_pad < 0:
        top_pad = bbox.top
    if bbox.bottom + bottom_pad >= h:
        bottom_pad = h - bbox.bottom - 1
    if bbox.left - left_pad < 0:
        left_pad = bbox.left
    if bbox.right + right_pad >= w:
        right_pad = w - bbox.right - 1

    pad = min(top_pad, bottom_pad, left_pad, right_pad)
    res_img, res_ann = sly.aug.crop(img, ann,
                                    bbox.top - pad, bbox.left - pad,
                                    h - (bbox.bottom + pad), w - (bbox.right + pad))
    return res_img, res_ann


def randomize_bg_color(img, mask):
    color_img = create_blank(img.shape[0], img.shape[1], sly.color.random_rgb())
    fg_h, fg_w, _ = mask.shape
    fg = cv2.bitwise_and(img, mask)
    bg_mask = 255 - mask
    color_img[0:fg_h, 0:fg_w, :] = cv2.bitwise_and(color_img[0:fg_h, 0:fg_w, :], bg_mask) + fg
    return color_img


def get_random_crop(image, crop_height, crop_width):

    max_x = image.shape[1] - crop_width
    max_y = image.shape[0] - crop_height

    x = np.random.randint(0, max_x)
    y = np.random.randint(0, max_y)

    crop = image[y: y + crop_height, x: x + crop_width]

    return crop


def randomize_bg_image(img, mask, backgrounds_dir):
    image_path = random.choice(get_files_paths(backgrounds_dir, ['.jpg', '.png']))

    background_image = cv2.imread(image_path)
    color_img = get_random_crop(background_image, img.shape[0], img.shape[1])
    # color_img = create_blank(img.shape[0], img.shape[1], sly.color.random_rgb())
    fg_h, fg_w, _ = mask.shape
    fg = cv2.bitwise_and(img, mask)
    bg_mask = 255 - mask
    color_img[0:fg_h, 0:fg_w, :] = cv2.bitwise_and(color_img[0:fg_h, 0:fg_w, :], bg_mask) + fg
    return color_img


def create_blank(height, width, rgb_color=[0, 0, 0]):
    """Create new image(numpy array) filled with certain color in RGB"""
    # Create black blank image
    image = np.zeros((height, width, 3), np.uint8)

    # Since OpenCV uses BGR, convert the color first
    color = tuple(reversed(rgb_color))
    # Fill image with color
    image[:] = color

    return image


def draw_white_mask(ann: sly.Annotation) -> np.ndarray:
    h, w = ann.img_size
    mask = np.zeros((h, w, 3), np.uint8)
    ann.draw(mask, [255, 255, 255])
    return mask


def crop_rb(y, x, original_h, original_w, image, mask):
    #mask = draw_white_mask(ann)
    h, w, _ = image.shape
    image_rb = image[max(0, h - y): h, max(0, w - x): w, :]
    mask_rb = mask[max(0, h - y): h, max(0, w - x): w, :]
    return image_rb, mask_rb


def place_lt(y, x, main_image, main_mask, image, mask):
    sec_h, sec_w, _ = image.shape
    secondary_object = cv2.bitwise_and(image, mask)
    secondary_bg = 255 - mask
    main_image[y - sec_h:y, x - sec_w:x, :] = cv2.bitwise_and(main_image[y - sec_h:y, x - sec_w:x, :], secondary_bg) + secondary_object
    main_mask[y - sec_h:y, x - sec_w:x, :] -= cv2.bitwise_and(main_mask[y - sec_h:y, x - sec_w:x, :], mask)


def crop_lb(y, x, original_h, original_w, image, mask):
    h, w, _ = image.shape
    #mask = draw_white_mask(ann)
    image = image[max(0, h - y): h, 0: min(w, original_w - x), :]
    mask = mask[max(0, h - y): h, 0: min(w, original_w - x), :]
    return image, mask


def place_rt(y, x, main_image, main_mask, image, mask):
    main_h, main_w, _ = main_image.shape
    sec_h, sec_w, _ = image.shape

    secondary_object = cv2.bitwise_and(image, mask)
    secondary_bg = 255 - mask

    main_image[y-sec_h:y, x:x+sec_w, :] = cv2.bitwise_and(main_image[y-sec_h:y, x:x+sec_w, :], secondary_bg) + secondary_object
    main_mask[y-sec_h:y, x:x+sec_w, :] -= cv2.bitwise_and(main_mask[y-sec_h:y, x:x+sec_w, :], mask) #mask


def crop_rt(y, x, original_h, original_w, image, mask):
    h, w, _ = image.shape
    #mask = draw_white_mask(ann)

    image = image[0: min(h, original_h - y), max(0, w - x): w, :]
    mask = mask[0: min(h, original_h - y), max(0, w - x): w, :]
    return image, mask


def place_lb(y, x, main_image, main_mask, image, mask):
    main_h, main_w, _ = main_image.shape
    sec_h, sec_w, _ = image.shape

    secondary_object = cv2.bitwise_and(image, mask)
    secondary_bg = 255 - mask

    main_image[y:y+sec_h, x-sec_w:x, :] = cv2.bitwise_and(main_image[y:y+sec_h, x-sec_w:x, :], secondary_bg) + secondary_object
    main_mask[y:y+sec_h, x-sec_w:x, :] -= cv2.bitwise_and(main_mask[y:y+sec_h, x-sec_w:x, :], mask) #mask


def crop_lt(y, x, original_h, original_w, image, mask):
    h, w, _ = image.shape
    #mask = draw_white_mask(ann)

    image = image[0: min(h, original_h - y), 0: min(w, original_w - x)]
    mask = mask[0: min(h, original_h - y), 0: min(w, original_w - x)]
    return image, mask


def place_rb(y, x, main_image, main_mask, image, mask):
    main_h, main_w, _ = main_image.shape
    sec_h, sec_w, _ = image.shape

    secondary_object = cv2.bitwise_and(image, mask)
    secondary_bg = 255 - mask

    main_image[y: y+sec_h, x: x+sec_w, :] = cv2.bitwise_and(main_image[y: y+sec_h, x: x+sec_w, :], secondary_bg) + secondary_object
    main_mask[y: y+sec_h, x: x+sec_w, :] -= cv2.bitwise_and(main_mask[y: y+sec_h, x: x+sec_w, :], mask) #mask


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