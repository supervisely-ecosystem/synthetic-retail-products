import os
from collections import defaultdict
import random
import supervisely_lib as sly

from init_ui import init_input_project, init_settings, init_preview

app: sly.AppService = sly.AppService()

TEAMP_ID = int(os.environ['context.teamId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])
PROJECT_ID = int(os.environ['modal.state.slyProjectId'])

PROJECT_INFO = app.public_api.project.get_info_by_id(PROJECT_ID)
if PROJECT_INFO is None:
    raise RuntimeError(f"Project id={PROJECT_ID} not found")
META = sly.ProjectMeta.from_json(app.public_api.project.get_meta(PROJECT_ID))


ALL_IMAGES_INFO = {}  # image id -> image info
IMAGE_PATH = {} # image id -> local path
ANNS = {}  # image id -> sly.Annotation
PRODUCTS = defaultdict(lambda: defaultdict(list))  # tag name (i.e. product-id) -> image id -> list of labels

# for debug
vis_dir = "../images"
sly.fs.mkdir(vis_dir)
sly.fs.clean_dir(vis_dir)

# CNT_GRID_COLUMNS = 1
# empty_gallery = {
#     "content": {
#         "projectMeta": sly.ProjectMeta().to_json(),
#         "annotations": {},
#         "layout": [[] for i in range(CNT_GRID_COLUMNS)]
#     },
#     "previewOptions": {
#         "enableZoom": True,
#         "resizeOnZoom": True
#     },
#     "options": {
#         "enableZoom": False,
#         "syncViews": False,
#         "showPreview": True,
#         "selectable": False,
#         "opacity": 0.5
#     }
# }


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
    global PRODUCTS, ANNS, IMAGE_PATH

    cache_dir = os.path.join(app.data_dir, "cache")
    sly.fs.mkdir(cache_dir)

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
                    # always one item in collection
                    for tag in label.tags:
                        PRODUCTS[tag.name][image_id].append(label)

                if num_image_products == 0:
                    sly.logger.warn(f"image {image_info.name} (id={image_info.id}) is skipped: doesn't have tagged products")
                    continue

                num_images_with_products += 1
                num_product_examples += num_image_products

                ANNS[image_id] = ann
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


@app.callback("preview")
@sly.timeit
def preview(api: sly.Api, task_id, context, state, app_logger):
    product_id = random.choice(list(PRODUCTS.keys()))
    image_id = random.choice(list(PRODUCTS[product_id].keys()))
    label = random.choice(list(PRODUCTS[product_id][image_id]))

    img = sly.image.read(IMAGE_PATH[image_id])
    sly.image.write(os.path.join(vis_dir, "img.jpg"), img)

    # ann = sly.Annotation.from_img_path
    # sly.aug.crop(img, sly.Annotation)

    # src_img_path = os.path.join(cache_dir, "res.png")
    # dst_img_path = os.path.join(f"/flying_object/{task_id}", "res.png")
    # sly.image.write(src_img_path, img)
    #
    # file_info = None
    # if api.file.exists(team_id, dst_img_path):
    #     api.file.remove(team_id, dst_img_path)
    # file_info = api.file.upload(team_id, src_img_path, dst_img_path)
    #
    # gallery = dict(empty_gallery)
    # gallery["content"]["projectMeta"] = res_meta.to_json()
    # gallery["content"]["annotations"] = {
    #     "preview": {
    #         "url": file_info.full_storage_url,
    #         "figures": [label.to_json() for label in ann.labels]
    #     }
    # }
    # gallery["content"]["layout"] = [["preview"]]
    #
    # fields = [
    #     {"field": "data.gallery", "payload": gallery},
    #     {"field": "state.previewLoading", "payload": False},
    # ]
    # api.task.set_fields(task_id, fields)


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


#@TODO: README: it is allowed to label several product examples on a single image
#@TODO: README: target background color vs original
#@TODO: motion blur + other augs
if __name__ == "__main__":
    sly.main_wrapper("main", main)
