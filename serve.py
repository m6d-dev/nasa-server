"""Dev server with auto-reload, like the CRM's serve.py. Production: `python -m src.main`."""

import uvicorn

from src.app.shared_kernel.config.app_config import AppConfig

if __name__ == "__main__":
    cfg = AppConfig()  # PORT / HOST from .env, default 0.0.0.0:8000
    uvicorn.run(
        # Import string only: with ``reload`` the reloader process must not build
        # the app too (it would configure everything twice).
        app="src.config.asgi:app",
        host=cfg.host,
        port=cfg.port,
        log_level="debug",
        reload=True,
        reload_dirs=["src"],
        ws_max_size=1 << 16,
    )
