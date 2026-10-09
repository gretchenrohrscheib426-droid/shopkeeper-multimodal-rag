from abc import ABC, abstractmethod
import logging
import time
from typing import TypeVar
from knowledge.processor.query_processor.config import QueryConfig, get_config
from knowledge.processor.query_processor.exceptions import QueryProcessError
from knowledge.core.task_store import get_store, TaskCancelled
from knowledge.utils.task_util import add_running_task, add_done_task, add_node_duration

T = TypeVar("T")


class BaseNode(ABC):
    name = "base_node"

    def __init__(self, config: QueryConfig | None = None):
        self.config = config or get_config()
        self.logger = logging.getLogger("query." + self.name)

    def __call__(self, state):
        task_id = state.get("task_id", "")
        start = time.monotonic()
        try:
            if task_id:
                get_store().check(task_id)
                add_running_task(task_id, self.name)
            result = self.process(state)
            if task_id:
                if not result.get("history_saved"):
                    get_store().check(task_id)
                add_node_duration(task_id, self.name, time.monotonic() - start)
                add_done_task(task_id, self.name)
            return result
        except TaskCancelled:
            raise
        except Exception as exc:
            if task_id:
                add_node_duration(task_id, self.name, time.monotonic() - start)
                get_store().emit(
                    task_id,
                    "progress",
                    {
                        "node": self.name,
                        "phase": "failed",
                        "error_type": type(exc).__name__,
                    },
                )
            raise QueryProcessError(
                message=str(exc), node_name=self.name, cause=exc
            ) from exc

    @abstractmethod
    def process(self, state): ...
    def log_step(self, step_name, message=""):
        self.logger.info("%s %s", step_name, message)


def setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
