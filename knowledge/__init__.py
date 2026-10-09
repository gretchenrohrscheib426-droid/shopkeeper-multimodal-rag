"""Resolve the selected configuration before SDKs can auto-load a different .env."""

from knowledge.core.configuration import load_environment

load_environment()
