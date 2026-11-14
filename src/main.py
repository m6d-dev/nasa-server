import uvicorn

from src.app.shared_kernel.config.app_config import AppConfig


def main() -> None:
    cfg = AppConfig()
    uvicorn.run("src.config.asgi:app", host=cfg.host, port=cfg.port, ws_max_size=1 << 16)


if __name__ == "__main__":
    main()
