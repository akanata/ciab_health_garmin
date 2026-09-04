"""Owner-facing setup surface: /setup and its form posts.

The router strips any client-supplied ``X-OpenHost-*`` header before stamping its
own, so ``X-OpenHost-Is-Owner`` is trustworthy. These paths are also kept out of
the manifest's ``public_paths``, so this guard is the second of two locks.

The only HTML in the project is here, and it is plain server-rendered markup: this
is a JSON API with one setup page, not a frontend.
"""

from __future__ import annotations

from html import escape
from typing import Annotated
from typing import Any

from litestar import Router
from litestar import get
from litestar import post
from litestar.connection import ASGIConnection
from litestar.datastructures import State
from litestar.enums import MediaType
from litestar.enums import RequestEncodingType
from litestar.exceptions import NotAuthorizedException
from litestar.handlers.base import BaseRouteHandler
from litestar.params import Body
from litestar.response import Redirect
from litestar.status_codes import HTTP_303_SEE_OTHER

from garmin_health.auth import AuthError
from garmin_health.auth import AuthStatus
from garmin_health.auth import GarminAuthenticator
from garmin_health.auth import LinkState

PASSWORD_NOTICE = (
    "Garmin does not offer a consent-based API outside its developer portal, so linking "
    "replays your real Garmin Connect password against Garmin's sign-in form once. It is "
    "used for that request only, is never written to disk, and is discarded as soon as a "
    "token is saved. Only you, the owner of this bottle, can reach this page."
)


def owner_guard(connection: ASGIConnection[Any, Any, Any, Any], _: BaseRouteHandler) -> None:
    if connection.headers.get("x-openhost-is-owner") != "true":
        raise NotAuthorizedException()


def _authenticator(state: State) -> GarminAuthenticator:
    authenticator: GarminAuthenticator = state.authenticator
    return authenticator


def _render(status: AuthStatus) -> str:
    email = escape(status.email or "", quote=True)
    detail = escape(status.detail or "", quote=True)

    if status.state is LinkState.LINKED:
        headline = f"Linked to Garmin Connect as {email}." if email else "Linked to Garmin Connect."
    elif status.state is LinkState.AWAITING_MFA:
        headline = "Garmin sent a verification code."
    elif status.state is LinkState.NEEDS_REAUTH:
        headline = "This bottle is no longer linked to Garmin Connect."
    else:
        headline = "Not linked to Garmin Connect yet."

    body = [
        "<h1>Garmin Connect</h1>",
        f"<p class='state' data-state='{status.state.value}'>{escape(headline)}</p>",
    ]
    if detail:
        body.append(f"<p class='detail'>{detail}</p>")

    if status.state is LinkState.AWAITING_MFA:
        body.append(
            "<form method='post' action='/setup/mfa'>"
            "<label>Verification code<input name='code' inputmode='numeric' autocomplete='one-time-code'"
            " required autofocus></label>"
            "<button type='submit'>Finish linking</button>"
            "</form>"
            "<p class='note'>The challenge is held in memory and does not survive a restart or a "
            "rejected code. If either happens, sign in again.</p>"
        )
    elif status.state is LinkState.LINKED:
        body.append(
            "<form method='post' action='/setup/unlink'>"
            "<button type='submit'>Unlink this Garmin account</button>"
            "</form>"
            "<p class='note'>Unlinking deletes the saved token. Your downloaded health data is kept.</p>"
        )
    else:
        body.append(
            "<form method='post' action='/setup/credentials'>"
            f"<label>Garmin Connect email<input name='email' type='email' value='{email}' required></label>"
            "<label>Password<input name='password' type='password' autocomplete='current-password'"
            " required></label>"
            "<button type='submit'>Link Garmin account</button>"
            "</form>"
        )

    body.append(f"<p class='warning'>{escape(PASSWORD_NOTICE)}</p>")
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Garmin Connect setup</title><style>"
        "body{font:16px/1.5 system-ui,sans-serif;margin:0 auto;padding:2rem;max-width:34rem}"
        "label{display:block;margin:.75rem 0}input{display:block;width:100%;padding:.5rem;margin-top:.25rem}"
        "button{padding:.5rem 1rem;margin-top:.5rem}"
        ".detail{padding:.75rem;background:#fff4e5;border-left:3px solid #d97706}"
        ".warning,.note{color:#555;font-size:.875rem}"
        "</style></head><body>" + "".join(body) + "</body></html>"
    )


@get("/setup", media_type=MediaType.HTML, sync_to_thread=False)
def setup_page(state: State) -> str:
    return _render(_authenticator(state).status())


@get("/setup/status", sync_to_thread=False)
def setup_status(state: State) -> dict[str, str | None]:
    return _authenticator(state).status().as_dict()


@post("/setup/credentials", status_code=HTTP_303_SEE_OTHER)
async def submit_credentials(
    state: State,
    data: Annotated[dict[str, str], Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    # AuthError is deliberately swallowed here: its message is recorded on the
    # authenticator and rendered on /setup, so a failed attempt is an ordinary page
    # with an explanation rather than a 500.
    try:
        await _authenticator(state).login(data.get("email", ""), data.get("password", ""))
    except AuthError:
        pass
    return Redirect("/setup", status_code=HTTP_303_SEE_OTHER)


@post("/setup/mfa", status_code=HTTP_303_SEE_OTHER)
async def submit_mfa(
    state: State,
    data: Annotated[dict[str, str], Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    try:
        await _authenticator(state).complete_mfa(data.get("code", ""))
    except AuthError:
        pass
    return Redirect("/setup", status_code=HTTP_303_SEE_OTHER)


@post("/setup/unlink", status_code=HTTP_303_SEE_OTHER)
async def unlink(state: State) -> Redirect:
    await _authenticator(state).unlink()
    return Redirect("/setup", status_code=HTTP_303_SEE_OTHER)


owner_router = Router(
    path="/",
    route_handlers=[setup_page, setup_status, submit_credentials, submit_mfa, unlink],
    guards=[owner_guard],
)
