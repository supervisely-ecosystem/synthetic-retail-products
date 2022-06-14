import os
import yaml
from pathlib import Path
import sys
import json
import supervisely as sly


def init_input_project(api: sly.Api, data: dict, project_info):
    data["projectId"] = project_info.id
    data["projectName"] = project_info.name
    data["projectPreviewUrl"] = api.image.preview_url(project_info.reference_image_url, 100, 100)
    data["projectItemsCount"] = project_info.items_count

    data["imagesWithProductsCount"] = 0


def init_augs(state: dict):
    root_source_path = str(Path(sys.argv[0]).parents[0])
    with open(os.path.join(root_source_path, "augs.yaml"), 'r') as file:
        augs_str = file.read()
    state["augs"] = augs_str

    d = yaml.safe_load(augs_str)
    #print(json.dumps(d, indent=4))


CNT_GRID_COLUMNS = 2
empty_gallery = {
    "content": {
        "projectMeta": sly.ProjectMeta().to_json(),
        "annotations": {},
        "layout": [[] for i in range(CNT_GRID_COLUMNS)]
    },
    "previewOptions": {
        "opacity": 0.1,
        "enableZoom": True,
        "resizeOnZoom": True,
        "showOpacityInHeader": True,
    },
    "options": {
        "enableZoom": False,
        "syncViews": False,
        "showPreview": True,
        "selectable": False,
        "opacity": 0.1,
        "showOpacityInHeader": True,
        # "viewHeight": 450
    }
}


def init_preview(data, state):
    state["previewLoading"] = False
    data["gallery"] = empty_gallery
    state["previewCount"] = 4


def refresh_progress(api: sly.Api, task_id, progress: sly.Progress):
    fields = [
        {"field": "data.progressPercent", "payload": int(progress.current * 100 / progress.total)},
        {"field": "data.progressCurrent", "payload": progress.current},
        {"field": "data.progressTotal", "payload": progress.total},
    ]
    api.task.set_fields(task_id, fields)


def init_output(data, state):
    state["trainCount"] = 100
    state["valCount"] = 10
    state["outputProjectName"] = "synthetic products"
    data["progressPercent"] = 0
    data["progressCurrent"] = 0
    data["progressTotal"] = 0


def init_res_project(data, state):
    data["resProjectId"] = None
    state["resProjectName"] = None
    data["resProjectPreviewUrl"] = None
    data["started"] = False


