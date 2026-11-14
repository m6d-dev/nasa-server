from typing import Annotated

from pydantic import Field

from src.vigil_types.base import ATAlertId, Command
from src.vigil_types.ingest.frame import FRAME_SIZE


class IngestFrameCommand(Command):
    """One binary WebSocket message from `/ingest`. Length is re-checked on decode
    so a bad frame is counted rather than rejected by validation."""

    raw: Annotated[bytes, Field(max_length=FRAME_SIZE * 4)]


class AlertAckCommand(Command):
    alert_id: ATAlertId
