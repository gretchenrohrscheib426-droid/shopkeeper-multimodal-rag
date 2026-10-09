"""Load one explicit configuration file; never mix keys from nested .env files."""

import os
from pathlib import Path
from threading import Lock
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[2]
_lock = Lock()
_loaded = False
ALIASES = (
    ("OPENAI_API_BASE", "OPENAI_BASE_URL"),
    ("MODEL", "LLM_DEFAULT_MODEL"),
    ("MINIO_BUCKET_NAME", "MINIO_BUCKET"),
)
MODEL_KEYS = (
    "OPENAI_API_KEY",
    "OPENAI_API_BASE",
    "OPENAI_BASE_URL",
    "LLM_DEFAULT_MODEL",
    "MODEL",
    "VL_MODEL",
    "ITEM_MODEL",
)


def resolve_values(
    file_values: dict[str, str | None], environment: dict[str, str]
) -> dict[str, str]:
    """Process environment wins as a layer; conflicting aliases within a layer fail."""
    model_source = file_values.get("MODEL_CONFIG_SOURCE", "environment")
    if model_source not in ("file", "environment"):
        raise ValueError("MODEL_CONFIG_SOURCE must be file or environment")
    process_values = dict(environment)
    if model_source == "file":
        # Keep the whole authentication tuple together; reject stale OS overrides.
        for key in MODEL_KEYS:
            process_values.pop(key, None)
        for key in (
            "OPENAI_API_KEY",
            "OPENAI_API_BASE",
            "LLM_DEFAULT_MODEL",
            "VL_MODEL",
            "ITEM_MODEL",
        ):
            if not file_values.get(key):
                raise ValueError(
                    "Missing file-authoritative model configuration: " + key
                )
    layers: list[dict[str, str | None]] = [dict(file_values), dict(process_values)]
    for layer in layers:
        for aliases in ALIASES:
            present = {layer[key] for key in aliases if layer.get(key)}
            if len(present) > 1:
                raise ValueError(
                    "Conflicting configuration aliases: " + ", ".join(aliases)
                )
            if present:
                value = present.pop()
                for key in aliases:
                    layer[key] = value
    return {k: v for layer in layers for k, v in layer.items() if v is not None}


def load_environment() -> None:
    global _loaded
    with _lock:
        if _loaded:
            return
        default_path = REPO_ROOT / ".env.local"
        if not default_path.exists():
            default_path = REPO_ROOT / ".env"
        config_path = Path(
            os.environ.get("SHOPKEEPER_ENV_FILE", default_path)
        ).resolve()
        values = resolve_values(
            dict(dotenv_values(config_path, interpolate=False)), dict(os.environ)
        )
        os.environ.update(values)
        _loaded = True


def required(name: str) -> str:
    load_environment()
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing configuration: {name}")
    return value
