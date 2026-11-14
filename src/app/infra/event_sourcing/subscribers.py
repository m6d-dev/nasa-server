"""Domain events → persistence, /live, narration and reporting.

Events are internal consequences of an accepted frame or command, so they are
not authorized. Subscribers are synchronous; slow work is spawned as a task.
"""

from src.app.application.crew.ports.services import CheckinFiled
from src.app.application.monitoring.services.presenters import notice_dto
from src.app.domain.monitoring.events.monitoring_events import (
    AlertChanged,
    BaselineStateChanged,
    DayChanged,
    LevelChanged,
    MinuteClosed,
    NarrationRequested,
)
from src.app.infra.di.root_di import RootDIContainer


def subscribe_all(c: RootDIContainer) -> None:
    bus = c.infra.event_bus()
    live = c.infra.live_hub()
    tasks = c.infra.tasks()
    queue = c.monitoring.queue()
    engine = c.monitoring.engine()
    narration = c.narration.service()
    autosave = c.reporting.autosave()

    # monitoring: persistence (history too) and /live (never for history, §3)
    bus.subscribe(MinuteClosed, lambda e: queue.enqueue_minute(e.result.as_row()))

    def on_alert(e: AlertChanged) -> None:
        queue.enqueue_alert(e.alert)
        if not e.history:
            live.publish(e.crew_id, {"t": "alert", "alert": notice_dto(e.alert, engine.now_ts(e.crew_id)).model_dump()})

    bus.subscribe(AlertChanged, on_alert)
    bus.subscribe(LevelChanged, lambda e: None if e.history else live.publish(
        e.crew_id, {"t": "level", "level": e.level, "critical_acked": e.critical_acked}))
    bus.subscribe(BaselineStateChanged, lambda e: None if e.history else live.publish(
        e.crew_id, {"t": "baseline", "state": e.state, "day": min(e.days, 7), "of": 7}))

    # crew → monitoring: close the To-do, feed symptoms to the text
    bus.subscribe(CheckinFiled, lambda e: engine.note_checkin(e.crew_id, e.day, e.symptoms))

    # narration: template is already out; maybe an LLM improves it
    bus.subscribe(NarrationRequested, narration.request)

    # reporting: save the finished day
    bus.subscribe(DayChanged, lambda e: tasks.spawn(
        autosave.save_day(e.crew_id, e.prev_day), name=f"report-{e.crew_id}-{e.prev_day}"))
