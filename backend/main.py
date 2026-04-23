# MIT License
# Copyright (c) 2026 Angshuman Nandy

"""
main.py — FastAPI application entry point for LLM Battleships.

Registers API routers, configures CORS for local development, and serves
the compiled React frontend as static files with a catch-all fallback to
index.html for client-side routing.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes_game import router as game_router
from .api.routes_sse import router as sse_router
from .config import ENV, DEFAULT_ANTHROPIC_API_KEY, DEFAULT_OPENAI_API_KEY

app = FastAPI(title="LLM Battleships")

# ---------------------------------------------------------------------------
# CORS — only enabled in development (not needed inside Docker)
# ---------------------------------------------------------------------------

if ENV == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ---------------------------------------------------------------------------
# Routers — must be registered before StaticFiles to take priority
# ---------------------------------------------------------------------------

app.include_router(game_router)
app.include_router(sse_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Simple liveness probe for Hugging Face Spaces."""
    return {"status": "ok"}


@app.get("/api/config")
async def client_config() -> dict:
    """Return non-secret defaults the frontend can use to pre-fill the setup form.

    available_providers lists only providers that have keys configured in env.
    The frontend uses this to hide providers that cannot be used.
    """
    available_providers: list[str] = []
    if DEFAULT_ANTHROPIC_API_KEY:
        available_providers.append("anthropic")
    if DEFAULT_OPENAI_API_KEY:
        available_providers.append("openai")

    return {"available_providers": available_providers}


# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------

# Resolve the frontend dist directory relative to this file so the path works
# both in local dev (backend/ sibling of frontend/) and inside the Docker image
# (where COPY puts dist at /app/frontend/dist).
_here = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.normpath(os.path.join(_here, "..", "frontend", "dist"))
assets_dir = os.path.join(static_dir, "assets")

if os.path.exists(assets_dir):
    # Mount hashed JS/CSS bundles under /assets — must be registered before the
    # catch-all route so Starlette's router wins the path match.
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{full_path:path}", response_model=None)
async def serve_frontend(full_path: str) -> FileResponse | dict[str, str]:
    """Catch-all that returns index.html for any unmatched path.

    This enables client-side routing in React without requiring the server to
    know about individual frontend routes.
    """
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    # Frontend has not been built yet (common in local backend-only dev).
    return {"error": "Frontend not built — run `npm run build` in frontend/"}
