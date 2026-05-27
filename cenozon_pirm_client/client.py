import os
import ssl
from enum import Enum
from typing import Any

import httpx
from attrs import define, evolve, field

ENVIRONMENT_TYPE_HEADER = "x-cenozon-environment"
ENVIRONMENT_TYPE_ENV_VAR = "CENOZON_ENVIRONMENT_TYPE"


class EnvironmentType(str, Enum):
    """Mirror of the server-side ``EnvironmentType`` enum (Cenozon.Indoraptor.Portal.V1).

    The wire value (sent in the ``x-cenozon-environment`` header) is the
    lowercased name. Use the enum members for type safety, or pass a plain
    string — both are accepted everywhere the client takes an environment.
    """

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PILOT = "pilot"
    PRODUCTION = "production"
    INTERNAL_ONLY = "internalonly"


DEFAULT_ENVIRONMENT_TYPE: EnvironmentType = EnvironmentType.PRODUCTION


def _coerce_environment_type(value: object) -> str | None:
    """Normalize an environment-type input into its wire string (or None to suppress)."""
    if value is None:
        return None
    if isinstance(value, EnvironmentType):
        return value.value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        return stripped
    raise TypeError(
        f"environment_type must be EnvironmentType, str, or None; got {type(value).__name__}"
    )


def _default_environment_type() -> str | None:
    raw = os.environ.get(ENVIRONMENT_TYPE_ENV_VAR)
    if raw is None:
        return DEFAULT_ENVIRONMENT_TYPE.value
    return _coerce_environment_type(raw)


def _merge_environment_header(
    headers: dict[str, str], environment_type: str | None
) -> dict[str, str]:
    """Return a copy of ``headers`` with the ``x-cenozon-environment`` header applied.

    The caller's explicit header value always wins. Pass an empty / None
    ``environment_type`` to opt out of sending the header entirely.
    """
    if not environment_type:
        return dict(headers)
    if any(k.lower() == ENVIRONMENT_TYPE_HEADER for k in headers):
        return dict(headers)
    merged = dict(headers)
    merged[ENVIRONMENT_TYPE_HEADER] = environment_type
    return merged


@define
class Client:
    """A class for keeping track of data related to the API

    The following are accepted as keyword arguments and will be used to construct httpx Clients internally:

        ``base_url``: The base URL for the API, all requests are made to a relative path to this URL

        ``cookies``: A dictionary of cookies to be sent with every request

        ``headers``: A dictionary of headers to be sent with every request

        ``timeout``: The maximum amount of a time a request can take. API functions will raise
        httpx.TimeoutException if this is exceeded.

        ``verify_ssl``: Whether or not to verify the SSL certificate of the API server. This should be True in production,
        but can be set to False for testing purposes.

        ``follow_redirects``: Whether or not to follow redirects. Default value is False.

        ``httpx_args``: A dictionary of additional arguments to be passed to the ``httpx.Client`` and ``httpx.AsyncClient`` constructor.

        ``environment_type``: Value to send in the ``x-cenozon-environment`` request header on every
        request. Defaults to the ``CENOZON_ENVIRONMENT_TYPE`` environment variable if set, otherwise
        ``"production"``. Pass ``None`` or ``""`` to suppress the header entirely.


    Attributes:
        raise_on_unexpected_status: Whether or not to raise an errors.UnexpectedStatus if the API returns a
            status code that was not documented in the source OpenAPI document. Can also be provided as a keyword
            argument to the constructor.
    """

    raise_on_unexpected_status: bool = field(default=False, kw_only=True)
    _base_url: str = field(alias="base_url")
    _cookies: dict[str, str] = field(factory=dict, kw_only=True, alias="cookies")
    _headers: dict[str, str] = field(factory=dict, kw_only=True, alias="headers")
    _timeout: httpx.Timeout | None = field(default=None, kw_only=True, alias="timeout")
    _verify_ssl: str | bool | ssl.SSLContext = field(default=True, kw_only=True, alias="verify_ssl")
    _follow_redirects: bool = field(default=False, kw_only=True, alias="follow_redirects")
    _httpx_args: dict[str, Any] = field(factory=dict, kw_only=True, alias="httpx_args")
    _environment_type: str | None = field(
        factory=_default_environment_type,
        kw_only=True,
        alias="environment_type",
        converter=_coerce_environment_type,
    )
    _client: httpx.Client | None = field(default=None, init=False)
    _async_client: httpx.AsyncClient | None = field(default=None, init=False)

    @property
    def environment_type(self) -> str | None:
        """The value sent in the ``x-cenozon-environment`` header (or ``None`` if suppressed)."""
        return self._environment_type

    def _effective_headers(self) -> dict[str, str]:
        return _merge_environment_header(self._headers, self._environment_type)

    def with_headers(self, headers: dict[str, str]) -> "Client":
        """Get a new client matching this one with additional headers"""
        if self._client is not None:
            self._client.headers.update(headers)
        if self._async_client is not None:
            self._async_client.headers.update(headers)
        return evolve(self, headers={**self._headers, **headers})

    def with_cookies(self, cookies: dict[str, str]) -> "Client":
        """Get a new client matching this one with additional cookies"""
        if self._client is not None:
            self._client.cookies.update(cookies)
        if self._async_client is not None:
            self._async_client.cookies.update(cookies)
        return evolve(self, cookies={**self._cookies, **cookies})

    def with_timeout(self, timeout: httpx.Timeout) -> "Client":
        """Get a new client matching this one with a new timeout (in seconds)"""
        if self._client is not None:
            self._client.timeout = timeout
        if self._async_client is not None:
            self._async_client.timeout = timeout
        return evolve(self, timeout=timeout)

    def with_environment_type(
        self, environment_type: EnvironmentType | str | None
    ) -> "Client":
        """Get a new client matching this one with a different environment type.

        Pass ``None`` or ``""`` to suppress the ``x-cenozon-environment`` header.
        Returns a brand-new :class:`Client`; the original is left untouched —
        its existing httpx clients keep their original env header. Unlike
        :py:meth:`with_headers` / :py:meth:`with_cookies` / :py:meth:`with_timeout`
        which mutate the in-flight httpx clients (for backwards compat with the
        generated code), this method intentionally avoids that mutation: env
        type is a logical-tenant routing concern and silently flipping it on
        the original client is unsafe.
        """
        wire = _coerce_environment_type(environment_type)
        return evolve(self, environment_type=wire)

    def set_httpx_client(self, client: httpx.Client) -> "Client":
        """Manually set the underlying httpx.Client

        **NOTE**: This will override any other settings on the client, including cookies, headers, and timeout.
        """
        self._client = client
        return self

    def get_httpx_client(self) -> httpx.Client:
        """Get the underlying httpx.Client, constructing a new one if not previously set"""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                cookies=self._cookies,
                headers=self._effective_headers(),
                timeout=self._timeout,
                verify=self._verify_ssl,
                follow_redirects=self._follow_redirects,
                **self._httpx_args,
            )
        return self._client

    def __enter__(self) -> "Client":
        """Enter a context manager for self.client—you cannot enter twice (see httpx docs)"""
        self.get_httpx_client().__enter__()
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        """Exit a context manager for internal httpx.Client (see httpx docs)"""
        self.get_httpx_client().__exit__(*args, **kwargs)

    def set_async_httpx_client(self, async_client: httpx.AsyncClient) -> "Client":
        """Manually the underlying httpx.AsyncClient

        **NOTE**: This will override any other settings on the client, including cookies, headers, and timeout.
        """
        self._async_client = async_client
        return self

    def get_async_httpx_client(self) -> httpx.AsyncClient:
        """Get the underlying httpx.AsyncClient, constructing a new one if not previously set"""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self._base_url,
                cookies=self._cookies,
                headers=self._effective_headers(),
                timeout=self._timeout,
                verify=self._verify_ssl,
                follow_redirects=self._follow_redirects,
                **self._httpx_args,
            )
        return self._async_client

    async def __aenter__(self) -> "Client":
        """Enter a context manager for underlying httpx.AsyncClient—you cannot enter twice (see httpx docs)"""
        await self.get_async_httpx_client().__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        """Exit a context manager for underlying httpx.AsyncClient (see httpx docs)"""
        await self.get_async_httpx_client().__aexit__(*args, **kwargs)


@define
class AuthenticatedClient:
    """A Client which has been authenticated for use on secured endpoints

    The following are accepted as keyword arguments and will be used to construct httpx Clients internally:

        ``base_url``: The base URL for the API, all requests are made to a relative path to this URL

        ``cookies``: A dictionary of cookies to be sent with every request

        ``headers``: A dictionary of headers to be sent with every request

        ``timeout``: The maximum amount of a time a request can take. API functions will raise
        httpx.TimeoutException if this is exceeded.

        ``verify_ssl``: Whether or not to verify the SSL certificate of the API server. This should be True in production,
        but can be set to False for testing purposes.

        ``follow_redirects``: Whether or not to follow redirects. Default value is False.

        ``httpx_args``: A dictionary of additional arguments to be passed to the ``httpx.Client`` and ``httpx.AsyncClient`` constructor.

        ``environment_type``: Value to send in the ``x-cenozon-environment`` request header on every
        request. Defaults to the ``CENOZON_ENVIRONMENT_TYPE`` environment variable if set, otherwise
        ``"production"``. Pass ``None`` or ``""`` to suppress the header entirely.


    Attributes:
        raise_on_unexpected_status: Whether or not to raise an errors.UnexpectedStatus if the API returns a
            status code that was not documented in the source OpenAPI document. Can also be provided as a keyword
            argument to the constructor.
        token: The token to use for authentication
        prefix: The prefix to use for the Authorization header
        auth_header_name: The name of the Authorization header
    """

    raise_on_unexpected_status: bool = field(default=False, kw_only=True)
    _base_url: str = field(alias="base_url")
    _cookies: dict[str, str] = field(factory=dict, kw_only=True, alias="cookies")
    _headers: dict[str, str] = field(factory=dict, kw_only=True, alias="headers")
    _timeout: httpx.Timeout | None = field(default=None, kw_only=True, alias="timeout")
    _verify_ssl: str | bool | ssl.SSLContext = field(default=True, kw_only=True, alias="verify_ssl")
    _follow_redirects: bool = field(default=False, kw_only=True, alias="follow_redirects")
    _httpx_args: dict[str, Any] = field(factory=dict, kw_only=True, alias="httpx_args")
    _environment_type: str | None = field(
        factory=_default_environment_type,
        kw_only=True,
        alias="environment_type",
        converter=_coerce_environment_type,
    )
    _client: httpx.Client | None = field(default=None, init=False)
    _async_client: httpx.AsyncClient | None = field(default=None, init=False)

    token: str
    prefix: str = "Bearer"
    auth_header_name: str = "Authorization"

    @property
    def environment_type(self) -> str | None:
        """The value sent in the ``x-cenozon-environment`` header (or ``None`` if suppressed)."""
        return self._environment_type

    def _effective_headers(self) -> dict[str, str]:
        headers = dict(self._headers)
        headers[self.auth_header_name] = f"{self.prefix} {self.token}" if self.prefix else self.token
        return _merge_environment_header(headers, self._environment_type)

    def with_headers(self, headers: dict[str, str]) -> "AuthenticatedClient":
        """Get a new client matching this one with additional headers"""
        if self._client is not None:
            self._client.headers.update(headers)
        if self._async_client is not None:
            self._async_client.headers.update(headers)
        return evolve(self, headers={**self._headers, **headers})

    def with_cookies(self, cookies: dict[str, str]) -> "AuthenticatedClient":
        """Get a new client matching this one with additional cookies"""
        if self._client is not None:
            self._client.cookies.update(cookies)
        if self._async_client is not None:
            self._async_client.cookies.update(cookies)
        return evolve(self, cookies={**self._cookies, **cookies})

    def with_timeout(self, timeout: httpx.Timeout) -> "AuthenticatedClient":
        """Get a new client matching this one with a new timeout (in seconds)"""
        if self._client is not None:
            self._client.timeout = timeout
        if self._async_client is not None:
            self._async_client.timeout = timeout
        return evolve(self, timeout=timeout)

    def with_environment_type(
        self, environment_type: EnvironmentType | str | None
    ) -> "AuthenticatedClient":
        """Get a new client matching this one with a different environment type.

        Pass ``None`` or ``""`` to suppress the ``x-cenozon-environment`` header.
        Returns a brand-new :class:`AuthenticatedClient`; the original is left
        untouched — its existing httpx clients keep their original env header.
        Unlike :py:meth:`with_headers` / :py:meth:`with_cookies` /
        :py:meth:`with_timeout` which mutate the in-flight httpx clients (for
        backwards compat with the generated code), this method intentionally
        avoids that mutation: env type is a logical-tenant routing concern and
        silently flipping it on the original client is unsafe.
        """
        wire = _coerce_environment_type(environment_type)
        return evolve(self, environment_type=wire)

    def set_httpx_client(self, client: httpx.Client) -> "AuthenticatedClient":
        """Manually set the underlying httpx.Client

        **NOTE**: This will override any other settings on the client, including cookies, headers, and timeout.
        """
        self._client = client
        return self

    def get_httpx_client(self) -> httpx.Client:
        """Get the underlying httpx.Client, constructing a new one if not previously set"""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                cookies=self._cookies,
                headers=self._effective_headers(),
                timeout=self._timeout,
                verify=self._verify_ssl,
                follow_redirects=self._follow_redirects,
                **self._httpx_args,
            )
        return self._client

    def __enter__(self) -> "AuthenticatedClient":
        """Enter a context manager for self.client—you cannot enter twice (see httpx docs)"""
        self.get_httpx_client().__enter__()
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        """Exit a context manager for internal httpx.Client (see httpx docs)"""
        self.get_httpx_client().__exit__(*args, **kwargs)

    def set_async_httpx_client(self, async_client: httpx.AsyncClient) -> "AuthenticatedClient":
        """Manually the underlying httpx.AsyncClient

        **NOTE**: This will override any other settings on the client, including cookies, headers, and timeout.
        """
        self._async_client = async_client
        return self

    def get_async_httpx_client(self) -> httpx.AsyncClient:
        """Get the underlying httpx.AsyncClient, constructing a new one if not previously set"""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self._base_url,
                cookies=self._cookies,
                headers=self._effective_headers(),
                timeout=self._timeout,
                verify=self._verify_ssl,
                follow_redirects=self._follow_redirects,
                **self._httpx_args,
            )
        return self._async_client

    async def __aenter__(self) -> "AuthenticatedClient":
        """Enter a context manager for underlying httpx.AsyncClient—you cannot enter twice (see httpx docs)"""
        await self.get_async_httpx_client().__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        """Exit a context manager for underlying httpx.AsyncClient (see httpx docs)"""
        await self.get_async_httpx_client().__aexit__(*args, **kwargs)
