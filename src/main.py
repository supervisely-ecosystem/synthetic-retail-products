import os
from collections import defaultdict
import supervisely_lib as sly

from init_ui import init_input_project, init_classes_stats, init_augs, init_progress, init_res_project, refresh_progress_images

app: sly.AppService = sly.AppService()

team_id = int(os.environ['context.teamId'])
workspace_id = int(os.environ['context.workspaceId'])
project_id = int(os.environ['modal.state.slyProjectId'])

project_info = app.public_api.project.get_info_by_id(project_id)
if project_info is None:
    raise RuntimeError(f"Project id={project_id} not found")

meta = sly.ProjectMeta.from_json(app.public_api.project.get_meta(project_id))


def validate_input():
    if len(meta.obj_classes) == 0:
        raise ValueError("Project should have at least one class")
    cnt_valid_classes = o
    for obj_class in meta.obj_classes:
        pass

validate_input()

images_info = {}
anns = {}
labels = defaultdict(lambda: defaultdict(list))


CNT_GRID_COLUMNS = 1
empty_gallery = {
    "content": {
        "projectMeta": sly.ProjectMeta().to_json(),
        "annotations": {},
        "layout": [[] for i in range(CNT_GRID_COLUMNS)]
    },
    "previewOptions": {
        "enableZoom": True,
        "resizeOnZoom": True
    },
    "options": {
        "enableZoom": False,
        "syncViews": False,
        "showPreview": True,
        "selectable": False,
        "opacity": 0.5
    }
}


@app.callback("cache_annotations")
@sly.timeit
def cache_annotations(api: sly.Api, task_id, context, state, app_logger):
    progress = sly.Progress("Cache annotations", project_info.items_count)
    for dataset in api.dataset.get_list(project_id):
        images = api.image.get_list(dataset.id)
        for batch in sly.batched(images):
            image_ids = [image_info.id for image_info in batch]
            ann_infos = api.annotation.download_batch(dataset.id, image_ids)
            for image_id, image_info, ann_info in zip(image_ids, batch, ann_infos):
                ann = sly.Annotation.from_json(ann_info.annotation, meta)
                anns[image_id] = ann
                images_info[image_id] = image_info
                for label in ann.labels:
                    labels[label.obj_class.name][image_id].append(label)
            progress.iters_done_report(len(batch))

    progress = sly.Progress("App is ready", 1)
    progress.iter_done_report()


@app.callback("select_all_classes")
@sly.timeit
def select_all_classes(api: sly.Api, task_id, context, state, app_logger):
    api.task.set_field(task_id, "state.classes", [True] * len(meta.obj_classes))


@app.callback("deselect_all_classes")
@sly.timeit
def deselect_all_classes(api: sly.Api, task_id, context, state, app_logger):
    api.task.set_field(task_id, "state.classes", [False] * len(meta.obj_classes))


@app.callback("preview")
@sly.timeit
def preview(api: sly.Api, task_id, context, state, app_logger):
    bg_images = update_bg_images(api, state)

    if len(bg_images) == 0:
        sly.logger.warn("There are no background images")
    else:
        cache_dir = os.path.join(app.data_dir, "cache_images_preview")
        sly.fs.mkdir(cache_dir)
        sly.fs.clean_dir(cache_dir)
        img, ann, res_meta = synthesize(api, task_id, state, meta, images_info, labels, bg_images, cache_dir)
        res_meta, ann = postprocess(state, ann, res_meta, sly.ProjectMeta())
        if state["taskType"] == "inst-seg" and state["highlightInstances"] is True:
            res_meta, ann = highlight_instances(res_meta, ann)
        src_img_path = os.path.join(cache_dir, "res.png")
        dst_img_path = os.path.join(f"/flying_object/{task_id}", "res.png")
        sly.image.write(src_img_path, img)

        file_info = None
        if api.file.exists(team_id, dst_img_path):
            api.file.remove(team_id, dst_img_path)
        file_info = api.file.upload(team_id, src_img_path, dst_img_path)

        gallery = dict(empty_gallery)
        gallery["content"]["projectMeta"] = res_meta.to_json()
        gallery["content"]["annotations"] = {
            "preview": {
                "url": file_info.full_storage_url,
                "figures": [label.to_json() for label in ann.labels]
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
    bg_images = update_bg_images(api, state)

    if len(bg_images) == 0:
        sly.logger.warn("There are no background images")
    else:
        cache_dir = os.path.join(app.data_dir, "cache_images_generate")
        sly.fs.mkdir(cache_dir)
        sly.fs.clean_dir(cache_dir)

        if state["destProject"] == "newProject":
            res_project_name = state["resProjectName"]
            if res_project_name == "":
                res_project_name = "synthetic"
            res_project = api.project.create(workspace_id, res_project_name, change_name_if_conflict=True)
        elif state["destProject"] == "existingProject":
            res_project = api.project.get_info_by_id(state["destProjectId"])

        res_dataset = api.dataset.get_or_create(res_project.id, state["resDatasetName"])
        res_meta = sly.ProjectMeta.from_json(api.project.get_meta(res_project.id))

        progress = sly.Progress("Generating images", state["imagesCount"])
        refresh_progress_images(api, task_id, progress)
        for i in range(state["imagesCount"]):
            img, ann, cur_meta = synthesize(api, task_id, state, meta, images_info, labels, bg_images, cache_dir, preview=False)
            merged_meta, new_ann = postprocess(state, ann, cur_meta, res_meta)
            if res_meta != merged_meta:
                api.project.update_meta(res_project.id, merged_meta.to_json())
                res_meta = merged_meta
            image_info = api.image.upload_np(res_dataset.id, f"{i + res_dataset.items_count}.png", img)
            api.annotation.upload_ann(image_info.id, new_ann)
            progress.iter_done_report()
            if progress.need_report():
                refresh_progress_images(api, task_id, progress)

    res_project = api.project.get_info_by_id(res_project.id)
    fields = [
        {"field": "data.started", "payload": False},
        {"field": "data.resProjectId", "payload": res_project.id},
        {"field": "data.resProjectName", "payload": res_project.name},
        {"field": "data.resProjectPreviewUrl", "payload": api.image.preview_url(res_project.reference_image_url, 100, 100)},
    ]
    api.task.set_fields(task_id, fields)
    #app.stop()


def main():
    data = {}
    state = {}

    init_input_project(app.public_api, data, project_info)

    data["classes"] = meta.obj_classes.items()[0].name
    data["classOptions"] = {
        "showLabel": False,
        "availableShapes": ["polygon", "bitmap"]
    }
    state["targetHeight"] = 200

    app.run(data=data, state=state, initial_events=[{"command": "cache_annotations"}])


#@TODO: ElasticTransformation
#@TODO: keep foreground w%/h% on background image
#@TODO: handle invalid augementations from user (validate augmentations)
#@TODO: check sum of objects for selected classes - disable buttons
#@TODO: output resolution
if __name__ == "__main__":
    sly.main_wrapper("main", main)
