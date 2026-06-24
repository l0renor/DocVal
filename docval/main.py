"""Runnable entrypoint.

Builds the app with the real Azure GPT-5.5 client. The factory defers
`from_env()` until called, so importing this module never requires credentials.

Run (after creating a .env from .env.example):
    uv run uvicorn --factory docval.main:create
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from .app import build_app
from .azure_client import AzureModelClient


def create() -> FastAPI:
    config_path = os.getenv("DOCVAL_CONFIG", "config.example.yaml")
    return build_app(config_path, AzureModelClient.from_env())
