"""Synchronous, deadline-bounded bridge to iTerm2's asynchronous public API."""

from __future__ import annotations

import asyncio
import importlib
import logging
from collections.abc import Awaitable
from types import TracebackType
from typing import TypeVar, cast

from .api_guard import guarded_call
from .api_types import (
    ApiApp, ApiConnection, ApiNotificationErrors, ApiRPCModule, ApiWebsocketErrors, ItermAPI,
    Profile, Reporter, Session,
)
from .diagnostics import DiagnosticError
from .worker import DeliveryError


OPERATION_TIMEOUT = 15.0
PROFILE_GUID = "870214EA-844A-4654-A241-B7EB0B766076"
LOGGER = logging.getLogger(__name__)


_Result = TypeVar("_Result")


async def _bounded(awaitable: Awaitable[_Result]) -> _Result:
    return await asyncio.wait_for(awaitable, OPERATION_TIMEOUT)


def _load_known_errors() -> tuple[type[BaseException], ...]:
    rpc = cast(ApiRPCModule, importlib.import_module("iterm2.rpc"))
    notifications = cast(
        ApiNotificationErrors, importlib.import_module("iterm2.notifications"),
    )
    websocket = cast(ApiWebsocketErrors, importlib.import_module("websockets.exceptions"))
    return (
        OSError, TimeoutError, rpc.RPCException, notifications.SubscriptionException,
        websocket.WebSocketException,
    )


def _diagnose(
    reporter: Reporter | None, code: str, error: BaseException | None = None,
) -> None:
    diagnostic = DiagnosticError(code)
    if error is not None:
        diagnostic.__cause__ = error
    if reporter is not None:
        reporter(diagnostic)
    elif error is None:
        LOGGER.warning("%s", code)
    else:
        LOGGER.warning("%s (%s)", code, type(error).__name__)


def _profile_matches(profile: Profile) -> bool:
    try:
        original_guid = profile.original_guid
    except AttributeError:
        original_guid = None
    identity = original_guid if isinstance(original_guid, str) and original_guid else profile.guid
    return isinstance(identity, str) and identity.casefold() == PROFILE_GUID.casefold()


def _session_id(session: Session) -> str:
    return session.session_id.casefold()


class ItermBridge:
    """Own one connection and expose only source-identity and focus operations."""

    def __init__(self, report: Reporter | None) -> None:
        self._reporter = report
        self._runner: asyncio.Runner | None = None
        self._errors: tuple[type[BaseException], ...] | None = None
        self._connection: ApiConnection | None = None
        self._app: ApiApp | None = None

    def _run(self, awaitable: Awaitable[_Result]) -> _Result:
        if self._runner is None:
            raise RuntimeError("iTerm2 bridge is not open")
        with guarded_call(OPERATION_TIMEOUT):
            return self._runner.run(_bounded(awaitable))

    def __enter__(self) -> ItermBridge:
        try:
            api = cast(ItermAPI, importlib.import_module("iterm2"))
            errors = _load_known_errors()
        except ModuleNotFoundError as error:
            raise DeliveryError("terminal_api_unavailable") from error
        self._errors = errors
        self._runner = asyncio.Runner()
        try:
            try:
                self._connection = self._run(api.Connection.async_create())
                app = self._run(api.async_get_app(self._connection))
                if app is None:
                    raise DeliveryError("iterm_app_unavailable")
                self._app = app
            except errors as error:
                raise DeliveryError("iterm_connection_failed") from error
            except SystemExit as error:
                # iterm2 exits the process when the server rejects its protocol version.
                raise DeliveryError("iterm_api_incompatible") from error
        finally:
            if self._app is None:
                self._close_connection()
                self._close_runner()
        return self

    def _close_connection(self) -> None:
        if self._connection is None or self._errors is None or self._runner is None:
            return
        try:
            self._run(self._connection.websocket.close())
        except self._errors as error:
            _diagnose(self._reporter, "iterm_disconnect_failed", error)

    def _close_runner(self) -> None:
        if self._runner is not None:
            self._runner.close()
            self._runner = None

    def __exit__(
        self, _exc_type: type[BaseException] | None, _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        try:
            self._close_connection()
        finally:
            self._close_runner()

    def session(self, source_uuid: str) -> Session | None:
        if self._app is None or self._errors is None:
            raise RuntimeError("iTerm2 bridge is not open")
        session: Session | None = None
        try:
            # Live iTerm2 IDs are uppercase and its lookup is case-sensitive.
            for candidate in dict.fromkeys((source_uuid.upper(), source_uuid)):
                session = self._app.get_session_by_id(candidate, include_buried=False)
                if session is not None:
                    break
        except self._errors as error:
            _diagnose(self._reporter, "source_lookup_failed", error)
            return None
        if session is None or not isinstance(session.session_id, str):
            _diagnose(self._reporter, "source_identity_unknown")
            return None
        if _session_id(session) != source_uuid.casefold():
            _diagnose(self._reporter, "source_identity_unknown")
            return None
        return session

    def report(self, code: str, error: BaseException | None = None) -> None:
        _diagnose(self._reporter, code, error)

    def profile_allowed(self, session: Session) -> bool:
        if self._errors is None:
            raise RuntimeError("iTerm2 bridge is not open")
        try:
            profile = cast(Profile, self._run(session.async_get_profile()))
            return _profile_matches(profile)
        except self._errors as error:
            _diagnose(self._reporter, "source_profile_unknown", error)
            return False
        except (AttributeError, TypeError):
            _diagnose(self._reporter, "profile_identity_unknown")
            return False

    def variable(self, session: Session, name: str) -> str | None:
        if self._errors is None:
            raise RuntimeError("iTerm2 bridge is not open")
        try:
            value = self._run(session.async_get_variable(name))
        except self._errors as error:
            if name == "tty":
                raise DeliveryError("tty_unavailable") from error
            _diagnose(self._reporter, "source_context_unavailable", error)
            return None
        return value if isinstance(value, str) else None

    def focused(self, session: Session) -> bool:
        if self._app is None or self._errors is None:
            raise RuntimeError("iTerm2 bridge is not open")
        try:
            self._run(self._app.async_refresh())
            source = self.session(session.session_id)
            if source is None:
                _diagnose(self._reporter, "source_changed")
                return False
            active = self._app.app_active
            if active is not True:
                if active is not False:
                    _diagnose(self._reporter, "focus_unknown")
                return False
            current_window = self._app.current_window
            if current_window is None:
                raise LookupError("focus_window_missing")
            try:
                source_window, source_tab = self._app.get_window_and_tab_for_session(source)
            except AttributeError:
                source_window, source_tab = self._app.get_tab_and_window_for_session(source)
            if source_window is None or source_tab is None:
                raise LookupError("focus_source_location_missing")
            current_tab = current_window.current_tab
            if current_tab is None:
                raise LookupError("focus_tab_missing")
            current_session = current_tab.current_session
            if current_session is None:
                raise LookupError("focus_session_missing")
            return (
                source_window.window_id == current_window.window_id
                and source_tab.tab_id == current_tab.tab_id
                and _session_id(current_session) == _session_id(source)
            )
        except (*self._errors, LookupError, AttributeError) as error:
            _diagnose(self._reporter, "focus_unknown", error)
            return False
