"""Compatibility functions backed by a durable journal, no transient dictionaries."""

from knowledge.core.task_store import get_store

TASK_STATUS_PROCESSING = "processing"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"


def add_running_task(task_id: str, node_name: str):
    def update(p):
        if node_name not in p["running_list"]:
            p["running_list"].append(node_name)

    get_store().mutate(task_id, update)
    get_store().emit(
        task_id,
        "progress",
        {"node": node_name, "phase": "started", **get_task_info(task_id)},
    )


def add_done_task(task_id: str, node_name: str):
    def update(p):
        if node_name in p["running_list"]:
            p["running_list"].remove(node_name)
        if node_name not in p["done_list"]:
            p["done_list"].append(node_name)

    get_store().mutate(task_id, update)
    get_store().emit(
        task_id,
        "progress",
        {"node": node_name, "phase": "finished", **get_task_info(task_id)},
    )


def get_running_task_list(task_id):
    return get_store().get(task_id)["running_list"]


def get_done_task_list(task_id):
    return get_store().get(task_id)["done_list"]


def get_task_status(task_id):
    return get_store().get(task_id)["status"]


def update_task_status(task_id, status_name):
    get_store().status(task_id, status_name)


def set_task_result(task_id, key, value):
    get_store().mutate(task_id, lambda p: p["results"].update({key: value}))


def get_task_result(task_id, key, default=""):
    return get_store().get(task_id)["results"].get(key, default)


def add_node_duration(task_id, node_name, duration):
    get_store().mutate(
        task_id, lambda p: p["durations"].update({node_name: round(duration, 3)})
    )


def get_node_durations(task_id):
    return get_store().get(task_id)["durations"]


def get_task_info(task_id):
    task = get_store().get(task_id)
    return {
        key: task[key]
        for key in [
            "status",
            "running_list",
            "done_list",
            "durations",
            "results",
            "cancel",
        ]
    }
