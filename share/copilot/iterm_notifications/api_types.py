"""Structural types for the subset of the iTerm2 API used by the notifier."""

from __future__ import annotations

from typing import Protocol

from .diagnostics import DiagnosticError


class Profile(Protocol):
    guid: str
    original_guid: str | None


class Session(Protocol):
    session_id: str

    async def async_get_profile(self) -> Profile: ...

    async def async_get_variable(self, name: str) -> str | None: ...


class ApiTab(Protocol):
    tab_id: str
    current_session: Session | None


class ApiWindow(Protocol):
    window_id: str
    current_tab: ApiTab | None


class ApiApp(Protocol):
    app_active: bool | None
    current_window: ApiWindow | None

    async def async_refresh(self) -> None: ...

    def get_session_by_id(
        self,
        session_id: str,
        include_buried: bool = True,
    ) -> Session | None: ...

    def get_window_and_tab_for_session(
        self,
        session: Session,
    ) -> tuple[ApiWindow, ApiTab] | tuple[None, None]: ...

    def get_tab_and_window_for_session(
        self,
        session: Session,
    ) -> tuple[ApiWindow, ApiTab] | tuple[None, None]: ...


class ApiWebsocket(Protocol):
    async def close(self) -> None: ...


class ApiConnection(Protocol):
    websocket: ApiWebsocket


class ApiConnectionFactory(Protocol):
    @staticmethod
    async def async_create() -> ApiConnection: ...


class ItermAPI(Protocol):
    Connection: type[ApiConnectionFactory]

    async def async_get_app(self, connection: ApiConnection) -> ApiApp | None: ...


class ApiRPCModule(Protocol):
    RPCException: type[Exception]


class ApiNotificationErrors(Protocol):
    SubscriptionException: type[Exception]


class ApiWebsocketErrors(Protocol):
    WebSocketException: type[Exception]


class Reporter(Protocol):
    def __call__(self, error: DiagnosticError) -> None: ...
