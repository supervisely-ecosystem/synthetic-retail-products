# import albumentations as A
# import os
# import supervisely_lib as sly
# from synth_utils import draw_white_mask
#
# # transform = A.Compose([
# #         A.RandomRotate90(),
# #         A.Flip(),
# #         A.Transpose(),
# #         A.OneOf([
# #             A.IAAAdditiveGaussianNoise(),
# #             A.GaussNoise(),
# #         ], p=0.2),
# #         A.OneOf([
# #             A.MotionBlur(p=.2),
# #             A.MedianBlur(blur_limit=3, p=0.1),
# #             A.Blur(blur_limit=3, p=0.1),
# #         ], p=0.2),
# #         A.ShiftScaleRotate(shift_limit=0.0625, scale_limit=0.2, rotate_limit=45, p=0.2),
# #         A.OneOf([
# #             A.OpticalDistortion(p=0.3),
# #             A.GridDistortion(p=.1),
# #             A.IAAPiecewiseAffine(p=0.3),
# #         ], p=0.2),
# #         A.OneOf([
# #             A.CLAHE(clip_limit=2),
# #             A.IAASharpen(),
# #             A.IAAEmboss(),
# #             A.RandomBrightnessContrast(),
# #         ], p=0.3),
# #         A.HueSaturationValue(p=0.3),
# #     ])
#
# _alpha = 300
# transform_main = A.Compose([
#     A.ElasticTransform(p=0.9, alpha=_alpha, sigma=_alpha * 0.05, alpha_affine=_alpha * 0.03),
# ])
# # https://albumentations.ai/docs/examples/example_kaggle_salt/#elastictransform
#
#
# def augment_main(image, mask):
#     augmented = transform_main(image=image, mask=mask)
#     image_aug = augmented['image']
#     mask_aug = augmented['mask']
#     return image_aug, mask_aug
#
#
# def test_augs(products, dest, count):
#     all_upcs = list(products.keys())
#     for main_upc in all_upcs:
#         upc_dir = os.path.join(dest, main_upc)
#         sly.fs.mkdir(upc_dir)
#         for example in products[main_upc]:
#             orig_image = example["img"].copy()
#             orig_mask = draw_white_mask(example["ann"])
#
#             for i in range(count):
#                 aug_orig_image, aug_orig_mask = augment_main(orig_image, orig_mask)
#                 sly.image.write(os.path.join(upc_dir, "{:05d}_image.jpg".format(i)), aug_orig_image)
#                 sly.image.write(os.path.join(upc_dir, "{:05d}_mask.jpg".format(i)), aug_orig_mask)
#             break
#         break


import cv2
import random
import imgaug.augmenters as iaa
from imgaug.augmentables.segmaps import SegmentationMapsOnImage
from ast import literal_eval
import supervisely_lib as sly
import albumentations as A

aug_color_fg = None
aug_spacial_fg = None


# imgaug
# name_func_color = {
#     "GaussianNoise": iaa.imgcorruptlike.GaussianNoise,
#     "GaussianBlur": iaa.imgcorruptlike.GaussianBlur,
#     "GammaContrast": iaa.GammaContrast,
#     "Contrast": iaa.imgcorruptlike.Contrast,
#     "Brightness": iaa.imgcorruptlike.Brightness
# }

name_func_color = {
    "RandomBrightnessContrast": A.RandomBrightnessContrast,
    "CLAHE": A.CLAHE,
    "Blur": A.Blur,
}


name_func_spacial = {
    "Rotate": iaa.Rotate,
    "ElasticTransformation": iaa.ElasticTransformation,
}


def init_fg_augs(settings):
    init_color_augs(settings['target'].get('color'))
    init_spacial_augs(settings['target'].get('spacial'))


def init_color_augs(data):
    global aug_color_fg
    augs = []
    if data is None:
        data = {}
    for key, value in data.items():
        if key not in name_func_color:
            sly.logger.warn(f"Aug {key} not found, skipped")
            continue
        if key == 'Blur':
            p = value['p']
            blur_limit = value['blur_limit']
            augs.append(A.Blur(blur_limit=blur_limit, p=p))
        else:
            augs.append(name_func_color[key]())
    aug_color_fg = A.Compose(augs)


def init_spacial_augs(data):
    global aug_spacial_fg
    if data is None:
        aug_spacial_fg = iaa.Sequential([], random_order=True)
        return
    augs = []
    for key, value in data.items():
        if key == 'ElasticTransformation':
            alpha = literal_eval(value['alpha'])
            sigma = literal_eval(value['sigma'])
            augs.append(iaa.ElasticTransformation(alpha=alpha, sigma=sigma))
            continue
        if key not in name_func_spacial:
            sly.logger.warn(f"Aug {key} not found, skipped")
            continue

        parsed_value = value
        if type(value) is str:
            parsed_value = literal_eval(value)

        if key == 'Rotate':
            a = iaa.Rotate(rotate=parsed_value, fit_output=True)
        else:
            a = name_func_spacial[key](parsed_value)
        augs.append(a)
    aug_spacial_fg = iaa.Sequential(augs, random_order=True)


def apply_to_foreground(image, mask):
    if image.shape[:2] != mask.shape[:2]:
        raise ValueError(f"Image ({image.shape}) and mask ({mask.shape}) have different resolutions")

    # apply color augs
    augmented = aug_color_fg(image=image, mask=mask)
    image_aug = augmented['image']
    mask_aug = augmented['mask']

    # apply spacial augs
    segmap = SegmentationMapsOnImage(mask_aug, shape=mask_aug.shape)
    image_aug, segmap_aug = aug_spacial_fg(image=image_aug, segmentation_maps=segmap)
    mask_aug = segmap_aug.get_arr()
    return image_aug, mask_aug
