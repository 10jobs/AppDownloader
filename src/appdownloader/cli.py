from __future__ import annotations

import uvicorn

from .config import settings


def main() -> None:
    uvicorn.run(
        "appdownloader.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
