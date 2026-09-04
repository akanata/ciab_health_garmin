"""Litestar application: the health probe plus the owner setup surface.

The ``/v1/*`` spec surface is not implemented yet (it is the serving layer, and it
needs the GarminDB mapping work). The manifest already advertises the service, which
is safe: the spec's consumer client treats any non-200 from a provider as "this
provider has nothing", so a consumer routed here simply sees no data.
"""

from __future__ import annotations

import logging

from litestar import Litestar
from litestar import get
from litestar.datastructures import State

from garmin_health.auth import GarminAuthenticator
from garmin_health.config import Settings
from garmin_health.config import settings_from_env
from garmin_health.routes.owner import owner_router


@get("/health", sync_to_thread=False)
def health() -> dict[str, str]:
    """The router's liveness probe.

    Deliberately unconditional: an unlinked account or a stale sync is a normal
    state awaiting owner input, and failing the probe for it would make the router
    restart a container that is working correctly.
    """
    return {"status": "ok"}


def create_app(
    *,
    settings: Settings | None = None,
    authenticator: GarminAuthenticator | None = None,
) -> Litestar:
    settings = settings if settings is not None else settings_from_env()
    authenticator = authenticator if authenticator is not None else GarminAuthenticator(settings)
    return Litestar(
        route_handlers=[health, owner_router],
        state=State({"settings": settings, "authenticator": authenticator}),
    )


logging.basicConfig(level=logging.INFO)

app = create_app()
