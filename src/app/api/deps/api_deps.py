from src.app.infra.impls.live_hub import LiveHub
from src.app.shared_kernel.ports.mediator import MediatorProto
from src.bootstrap import Bootstrap


def get_mediator() -> MediatorProto:
    return Bootstrap.mediator()


def get_live_hub() -> LiveHub:
    return Bootstrap.container().infra.live_hub()
