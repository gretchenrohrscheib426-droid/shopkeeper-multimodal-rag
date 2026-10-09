import os
from pathlib import Path
from knowledge.core.configuration import load_environment, REPO_ROOT

load_environment()
KNOWLEDGE_ROOT = Path(__file__).resolve().parents[1]
LOCAL_BASE_DIR = Path(os.getenv("DATA_ROOT", str(REPO_ROOT / "data"))).resolve()


def get_local_base_dir() -> str:
    return str(LOCAL_BASE_DIR)


def get_front_page_dir() -> str:
    return str(KNOWLEDGE_ROOT / "front")
