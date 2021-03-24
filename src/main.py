import os
from collections import defaultdict
import random
import yaml
import cv2
import numpy as np
import logging
import supervisely_lib as sly
import augs

from init_ui import init_input_project, init_settings, init_preview, empty_gallery
from synth_utils import crop_label, draw_white_mask, randomize_bg_color
from synth_utils import crops_funcs, place_funcs, get_y_range, get_x_range

app: sly.AppService = sly.AppService()

TEAM_ID = int(os.environ['context.teamId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])
PROJECT_ID = int(os.environ['modal.state.slyProjectId'])

PROJECT_INFO = app.public_api.project.get_info_by_id(PROJECT_ID)
if PROJECT_INFO is None:
    raise RuntimeError(f"Project id={PROJECT_ID} not found")
META = sly.ProjectMeta.from_json(app.public_api.project.get_meta(PROJECT_ID))


ALL_IMAGES_INFO = {}  # image id -> image info
IMAGE_PATH = {} # image id -> local path
PRODUCTS = defaultdict(lambda: defaultdict(list))  # tag name (i.e. product-id) -> image id -> list of labels

# for debug
vis_dir = os.path.join(app.data_dir, "vis_images")
sly.fs.mkdir(vis_dir)
sly.fs.clean_dir(vis_dir)  # good for debug


def validate_project_meta():
    global META
    if len(META.obj_classes) == 0:
        raise ValueError("Project should have at least one class")
    cnt_valid_classes = 0
    for obj_class in META.obj_classes:
        obj_class: sly.ObjClass
        if obj_class.geometry_type in [sly.Polygon, sly.Bitmap]:
            cnt_valid_classes += 1
    if cnt_valid_classes == 0:
        raise ValueError("Project should have at least one class of type polygon or bitmap")

    if len(META.tag_metas) == 0:
        raise ValueError("Project should have at least two tags")
    cnt_valid_tags = 0
    for tag_meta in META.tag_metas:
        tag_meta: sly.TagMeta
        if tag_meta.value_type != sly.TagValueType.NONE:
            continue
        cnt_valid_tags += 1
    if cnt_valid_tags <= 1:
        raise ValueError("Project should have at least two tags with value_type NONE (tags without values)")


def cache_annotations(api: sly.Api, task_id, data):
    global PRODUCTS, IMAGE_PATH

    cache_dir = os.path.join(app.data_dir, "cache")
    sly.fs.mkdir(cache_dir)
    #sly.fs.clean_dir(cache_dir)

    num_images_with_products = 0
    num_product_examples = 0

    progress = sly.Progress("Cache annotations", PROJECT_INFO.items_count)
    for dataset in api.dataset.get_list(PROJECT_ID):
        images = api.image.get_list(dataset.id)
        download_ids = []
        download_paths = []
        for batch in sly.batched(images):
            image_ids = [image_info.id for image_info in batch]
            ann_infos = api.annotation.download_batch(dataset.id, image_ids)
            for image_id, image_info, ann_info in zip(image_ids, batch, ann_infos):
                ann = sly.Annotation.from_json(ann_info.annotation, META)

                if len(ann.labels) == 0:
                    sly.logger.warn(f"image {image_info.name} (id={image_info.id}) is skipped: doesn't have labels")

                num_image_products = 0
                for label in ann.labels:
                    label: sly.Label
                    if len(label.tags) == 0:
                        continue
                    elif len(label.tags) > 1:
                        continue
                    num_image_products += 1

                    # always max one item in collection
                    for tag in label.tags:
                        ann_for_label = ann.clone(labels=[label])
                        PRODUCTS[tag.name][image_id].append(ann_for_label)

                if num_image_products == 0:
                    sly.logger.warn(f"image {image_info.name} (id={image_info.id}) is skipped: doesn't have tagged products")
                    continue

                num_images_with_products += 1
                num_product_examples += num_image_products

                ALL_IMAGES_INFO[image_id] = image_info

                download_path = os.path.join(cache_dir, str(image_id) + sly.fs.get_file_ext(image_info.name))
                IMAGE_PATH[image_id] = download_path
                if sly.fs.file_exists(download_path):
                    continue
                download_ids.append(image_id)
                download_paths.append(download_path)

            progress.iters_done_report(len(batch))

            if len(download_ids) != 0:
                progress_images = sly.Progress("Cache images", len(download_ids))
                api.image.download_paths(dataset.id, download_ids, download_paths, progress_images.iters_done_report)

    progress = sly.Progress("App is ready", 1)
    progress.iter_done_report()

    data["imagesWithProductsCount"] = num_images_with_products
    data["productsCount"] = len(PRODUCTS.keys())
    data["examplesCount"] = num_product_examples


def generate_item(orig_image, orig_mask, orig_upc, all_upcs, orig_h, orig_w):
    # image = orig_image.copy()
    # mask = orig_mask.copy()
    image, mask = aug.augment_main(orig_image.copy(), orig_mask.copy())
    for crop_f, place_f, range_index in zip(crops_funcs, place_funcs, list(range(0, 4))):
        upc = random.choice(all_upcs)
        while upc == orig_upc:
            upc = random.choice(all_upcs)
        sec_example = random.choice(products[upc])
        try:
            sec_image = sec_example["img"].copy()
            sec_image, sec_ann = sly.aug.resize(sec_image, sec_example["ann"], (orig_h, -1))

            y_range = get_y_range(range_index, orig_h)
            x_range = get_x_range(range_index, orig_w)
            y = random.randint(int(y_range[0]), int(y_range[1]))
            x = random.randint(int(x_range[0]), int(x_range[1]))
            sec_image, sec_mask = crop_f(y, x, orig_h, orig_w, sec_image, sec_ann)
            place_f(y, x, image, mask, sec_image, sec_mask)
        except Exception as e:
            raise e
    return image, mask


def get_random_product(ignore_id=None):
    product_id = random.choice(list(PRODUCTS.keys()))
    while ignore_id is not None and product_id == ignore_id:
        product_id = random.choice(list(PRODUCTS.keys()))
    image_id = random.choice(list(PRODUCTS[product_id].keys()))
    img = sly.image.read(IMAGE_PATH[image_id])
    ann = random.choice(list(PRODUCTS[product_id][image_id]))
    return product_id, img, ann


def preprocess_product(img, ann, augs_settings, is_main):
    target_h = augs_settings['target']['height']
    pad_crop = 0
    if is_main is True:
        pad_crop = augs_settings['target']['padCrop']
    label_image, ann = crop_label(img, ann, pad_crop)
    label_image, ann = sly.aug.resize(label_image, ann, (target_h, -1))
    label_mask = draw_white_mask(ann)
    if is_main:
        label_image, label_mask = augs.apply_to_foreground(label_image, label_mask)
    if is_main is True and augs_settings['target']['background'] == "random_color":
        label_image = randomize_bg_color(label_image, label_mask)
    return label_image, label_mask


@app.callback("preview")
@sly.timeit
def preview(api: sly.Api, task_id, context, state, app_logger):
    product_id, img, ann = get_random_product()
    if logging.getLevelName(sly.logger.level) == 'DEBUG':
        sly.image.write(os.path.join(vis_dir, "01_img.png"), img)

    augs_settings = yaml.safe_load(state["augs"])
    augs.init_fg_augs(augs_settings)

    label_image, label_mask = preprocess_product(img, ann, augs_settings, is_main=True)
    if logging.getLevelName(sly.logger.level) == 'DEBUG':
        sly.image.write(os.path.join(vis_dir, "02_label_image.png"), label_image)
        sly.image.write(os.path.join(vis_dir, "03_label_mask.png"), label_mask)

    orig_h, orig_w = label_image.shape[:2]
    for crop_f, place_f, range_index in zip(crops_funcs, place_funcs, list(range(0, 4))):
        if random.uniform(0, 1) <= augs_settings['noise']['corner_probability']:
            _, noise_img, noise_ann = get_random_product(ignore_id=product_id)
            noise_img, noise_ann = crop_label(noise_img, noise_ann, padding=0)
            noise_mask = draw_white_mask(noise_ann)
            if logging.getLevelName(sly.logger.level) == 'DEBUG':
                sly.image.write(os.path.join(vis_dir, "04_noise_img.png"), noise_img)
            if random.uniform(0, 1) <= augs_settings['noise']['aug_probability']:
                noise_img, noise_mask = augs.apply_to_foreground(noise_img, noise_mask)

            y_range = get_y_range(range_index, orig_h)
            x_range = get_x_range(range_index, orig_w)
            y = random.randint(int(y_range[0]), int(y_range[1]))
            x = random.randint(int(x_range[0]), int(x_range[1]))
            noise_img, noise_mask = crop_f(y, x, orig_h, orig_w, noise_img, noise_mask)

            if logging.getLevelName(sly.logger.level) == 'DEBUG':
                sly.image.write(os.path.join(vis_dir, f"04_noise_img_{range_index}.png"), noise_img)
                sly.image.write(os.path.join(vis_dir, f"05_noise_mask_{range_index}.png"), noise_mask)
            place_f(y, x, label_image, label_mask, noise_img, noise_mask)

    preview_local_path = os.path.join(vis_dir, "preview_image.png")
    preview_remote_path = os.path.join(f"/synthetic-retail-products/{task_id}", "preview_image.png")

    sly.image.write(preview_local_path, label_image)

    preview_label = sly.Label(
        sly.Bitmap(label_mask[:, :, 0].astype(np.bool), origin=sly.PointLocation(0, 0)),
        ann.labels[0].obj_class
    )

    if logging.getLevelName(sly.logger.level) == 'DEBUG':
        sly.image.write(os.path.join(vis_dir, "06_final_mask.png"), label_mask)

    if api.file.exists(TEAM_ID, preview_remote_path):
        api.file.remove(TEAM_ID, preview_remote_path)
    file_info = api.file.upload(TEAM_ID, preview_local_path, preview_remote_path)

    gallery = dict(empty_gallery)
    gallery["content"]["projectMeta"] = META.to_json()
    gallery["content"]["annotations"] = {
        "preview": {
            "url": file_info.full_storage_url,
            "figures": [preview_label.to_json()]
        }
    }
    gallery["content"]["layout"] = [["preview"]]

    fields = [
        {"field": "data.gallery", "payload": gallery},
        {"field": "state.previewLoading", "payload": False},
    ]
    api.task.set_fields(task_id, fields)


@app.callback("generate")
@sly.timeit
def generate(api: sly.Api, task_id, context, state, app_logger):
    pass


def main():
    data = {}
    state = {}

    init_input_project(app.public_api, data, PROJECT_INFO)
    init_settings(data, state)
    init_preview(data, state)

    validate_project_meta()
    cache_annotations(app.public_api, app.task_id, data)

    app.run(data=data, state=state)


#@TODO: set max height like in preview
#@TODO: README: it is allowed to label several product examples on a single image
#@TODO: README: target background color vs original
#@TODO: motion blur + other augs
if __name__ == "__main__":
    sly.main_wrapper("main", main)
