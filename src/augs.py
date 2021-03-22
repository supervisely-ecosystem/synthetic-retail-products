import albumentations as A
import os
import supervisely_lib as sly
from synth_utils import draw_white_mask

# transform = A.Compose([
#         A.RandomRotate90(),
#         A.Flip(),
#         A.Transpose(),
#         A.OneOf([
#             A.IAAAdditiveGaussianNoise(),
#             A.GaussNoise(),
#         ], p=0.2),
#         A.OneOf([
#             A.MotionBlur(p=.2),
#             A.MedianBlur(blur_limit=3, p=0.1),
#             A.Blur(blur_limit=3, p=0.1),
#         ], p=0.2),
#         A.ShiftScaleRotate(shift_limit=0.0625, scale_limit=0.2, rotate_limit=45, p=0.2),
#         A.OneOf([
#             A.OpticalDistortion(p=0.3),
#             A.GridDistortion(p=.1),
#             A.IAAPiecewiseAffine(p=0.3),
#         ], p=0.2),
#         A.OneOf([
#             A.CLAHE(clip_limit=2),
#             A.IAASharpen(),
#             A.IAAEmboss(),
#             A.RandomBrightnessContrast(),
#         ], p=0.3),
#         A.HueSaturationValue(p=0.3),
#     ])

_alpha = 300
transform_main = A.Compose([
    A.ElasticTransform(p=0.9, alpha=_alpha, sigma=_alpha * 0.05, alpha_affine=_alpha * 0.03),
])
# https://albumentations.ai/docs/examples/example_kaggle_salt/#elastictransform


def augment_main(image, mask):
    augmented = transform_main(image=image, mask=mask)
    image_aug = augmented['image']
    mask_aug = augmented['mask']
    return image_aug, mask_aug


def test_augs(products, dest, count):
    all_upcs = list(products.keys())
    for main_upc in all_upcs:
        upc_dir = os.path.join(dest, main_upc)
        sly.fs.mkdir(upc_dir)
        for example in products[main_upc]:
            orig_image = example["img"].copy()
            orig_mask = draw_white_mask(example["ann"])

            for i in range(count):
                aug_orig_image, aug_orig_mask = augment_main(orig_image, orig_mask)
                sly.image.write(os.path.join(upc_dir, "{:05d}_image.jpg".format(i)), aug_orig_image)
                sly.image.write(os.path.join(upc_dir, "{:05d}_mask.jpg".format(i)), aug_orig_mask)
            break
        break