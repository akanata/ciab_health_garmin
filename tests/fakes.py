"""A stand-in for garminconnect.Garmin that mirrors the real object's contracts.

The behaviours reproduced here are the ones auth.py has to code around, all read
off garminconnect 0.3.11:

- ``return_on_mfa`` is a CONSTRUCTOR argument, not a ``login()`` argument.
- In ``return_on_mfa`` mode ``login()`` returns early and NEVER dumps tokens, and
  never sets ``client._tokenstore_path`` -- so nothing persists the token unless
  the caller does it (``__init__.py:734-741``).
- ``resume_login()`` does not dump tokens either (``__init__.py:884``).
- ``client.resume_login(_client_state, mfa_code)`` IGNORES client_state; the
  pending challenge lives on the instance (``client.py:1608``).
- ``client.resume_login`` clears the pending-MFA state in a ``finally``, so a
  rejected code kills the challenge -- it cannot be retried on the same client.
"""

import json
from pathlib import Path
from typing import Any

from garminconnect import GarminConnectAuthenticationError


class FakeInnerClient:
    """Stands in for ``Garmin.client`` (the garth-like transport)."""

    def __init__(self) -> None:
        self.dumped_to: list[str] = []
        self._tokenstore_path: str | None = None

    def dump(self, path: str) -> None:
        self.dumped_to.append(path)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"di_token": "t", "di_refresh_token": "r", "di_client_id": "c"}))


class FakeGarmin:
    """Stands in for ``garminconnect.Garmin``."""

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        is_cn: bool = False,
        return_on_mfa: bool = False,
        *,
        needs_mfa: bool = False,
        mfa_code: str = "123456",
        login_error: Exception | None = None,
        **_: Any,
    ) -> None:
        self.username = email
        self.password = password
        self.is_cn = is_cn
        self.return_on_mfa = return_on_mfa
        self.client = FakeInnerClient()
        self.display_name = "rider"
        self.full_name = "Test Rider"
        self._needs_mfa = needs_mfa
        self._expected_code = mfa_code
        self._login_error = login_error
        self._mfa_pending = False
        self.login_calls: list[str | None] = []
        self.resume_calls: list[tuple[Any, str]] = []

    def login(self, tokenstore: str | None = None) -> tuple[str | None, str | None]:
        self.login_calls.append(tokenstore)
        if tokenstore and Path(tokenstore).is_file():
            return None, None  # cached-token path
        if self._login_error is not None:
            raise self._login_error
        if not self.username or not self.password:
            raise GarminConnectAuthenticationError("Username and password are required")
        if self._needs_mfa and self.return_on_mfa:
            self._mfa_pending = True
            # Real client returns early WITHOUT dumping tokens.
            return "needs_mfa", None
        return None, None

    def resume_login(self, client_state: Any, mfa_code: str) -> tuple[Any, Any]:
        self.resume_calls.append((client_state, mfa_code))
        try:
            if not self._mfa_pending:
                raise GarminConnectAuthenticationError("no MFA login in progress")
            if mfa_code != self._expected_code:
                raise GarminConnectAuthenticationError("invalid MFA code")
            return None, None
        finally:
            # Mirrors client.py's finally block: the challenge is consumed either way.
            self._mfa_pending = False


class RecordingFactory:
    """Captures the kwargs auth.py passes, so the constructor contract is testable."""

    def __init__(self, **client_kwargs: Any) -> None:
        self.client_kwargs = client_kwargs
        self.calls: list[dict[str, Any]] = []
        self.clients: list[FakeGarmin] = []

    def __call__(self, **kwargs: Any) -> FakeGarmin:
        self.calls.append(kwargs)
        client = FakeGarmin(**{**kwargs, **self.client_kwargs})
        self.clients.append(client)
        return client
