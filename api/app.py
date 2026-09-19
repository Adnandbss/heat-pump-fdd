"""ASGI entry for `uvicorn api.app:app`. Construction has no import-time I/O."""

from api.main import create_app

app = create_app()
