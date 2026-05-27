"""Async high-level wrapper around the generated PIRM Data Gateway client.

The low-level ``cenozon_pirm_client.api.*`` modules are auto-generated from the
OpenAPI spec and require callers to pass headers and identifiers on every call.
This module offers an :class:`PirmClient` that holds the client identity once
and exposes a fully **async** surface returning plain-Python objects you can
iterate, fetch from, and stream.

Every network method is ``async def`` — there is no synchronous variant.
Use ``asyncio.run(...)`` from scripts, or ``await`` from notebooks /
async contexts. The CLI (``pirm-dgw``) and a thin pandas/Spark layer drive
the same async core so behaviour is consistent everywhere.

The wrapper deliberately routes data and schema requests through the
``schemaUri`` / ``dataUri`` returned by the listing endpoints — those are the
canonical, server-issued URLs and avoid display-name-vs-slug mismatches when
the human-readable ``reportName`` (e.g. ``"Master Pipeline Modified"``) differs
from the path segment the gateway expects (``"master-pipeline-modified"``).

The generated ``AuthenticatedClient`` / ``Client`` and every ``api/*`` function
remain public and unchanged — this is purely additive.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

import httpx
from attrs import define, field

from .client import (
    DEFAULT_ENVIRONMENT_TYPE,
    ENVIRONMENT_TYPE_ENV_VAR,
    AuthenticatedClient,
    EnvironmentType,
    _coerce_environment_type,
)
from .models.csv_string_quoting import CsvStringQuoting
from .models.report_schema import ReportSchema
from .types import UNSET, Unset

DEFAULT_BASE_URL = "https://platform.cenozon.com/api/pirm/data/v1"
DEFAULT_AUTH_PREFIX = "Token"

CLIENT_ID_HEADER = "x-cenozon-client-id"
DEPLOYMENT_ID_HEADER = "x-cenozon-deployment-id"

# Default timeout for the high-level wrapper. httpx's library default is 5s for
# every phase including read, which is fine for small JSON listings but kills
# multi-megabyte streaming downloads. We keep a tight connect/write/pool budget
# and disable the read timeout entirely so long-running streams complete.
# Applied only when the caller doesn't pass ``timeout=`` explicitly.
_DEFAULT_TIMEOUT = httpx.Timeout(connect=30.0, write=30.0, pool=10.0, read=None)

# Environment variable conventions used by ``PirmClient.from_env``.
TOKEN_ENV_VAR = "CENOZON_API_TOKEN"
CLIENT_ID_ENV_VAR = "CENOZON_CLIENT_ID"
DEPLOYMENT_ID_ENV_VAR = "CENOZON_DEPLOYMENT_ID"
BASE_URL_ENV_VAR = "CENOZON_BASE_URL"


class ReportFormat:
    """String constants for the ``format`` path segment of data endpoints.

    The server accepts any of these; the constants exist for discoverability.
    """

    JSON = "json"
    CSV = "csv"
    TSV = "tsv"
    XLSX = "xlsx"
    EXCEL = "excel"  # alias for xlsx accepted by the gateway

    ALL: tuple[str, ...] = ("json", "csv", "tsv", "xlsx", "excel")
    TEXT: tuple[str, ...] = ("json", "csv", "tsv")
    BINARY: tuple[str, ...] = ("xlsx", "excel")

    @classmethod
    def is_binary(cls, format: str) -> bool:
        return format.lower() in cls.BINARY


_FORMAT_TO_PANDAS_READER = {
    "csv": ("read_csv", {}),
    "tsv": ("read_csv", {"sep": "\t"}),
    "json": ("read_json", {}),
    "xlsx": ("read_excel", {}),
    "excel": ("read_excel", {}),
}


class PirmError(RuntimeError):
    """Base class for errors raised by the high-level wrapper."""


class PirmHTTPError(PirmError):
    """Raised when the gateway returns a non-2xx response.

    The original ``httpx.Response`` is attached as ``response`` for callers
    that want to inspect status code, headers, or body directly.
    """

    def __init__(self, response: httpx.Response, message: str | None = None) -> None:
        self.response = response
        try:
            body = response.text[:500] if response.text else ""
        except Exception:
            body = ""
        super().__init__(
            message
            or f"PIRM request failed ({response.status_code} {response.reason_phrase}): {body}"
        )


def _build_csv_params(
    *,
    delimiter: str | None,
    quote: str | None,
    escape: str | None,
    quote_strings: CsvStringQuoting | int | None,
    compress_keys: bool | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if delimiter is not None:
        params["delimiter"] = delimiter
    if quote is not None:
        params["quote"] = quote
    if escape is not None:
        params["escape"] = escape
    if quote_strings is not None:
        params["quoteStrings"] = (
            quote_strings.value if isinstance(quote_strings, CsvStringQuoting) else quote_strings
        )
    if compress_keys is not None:
        params["compressKeys"] = compress_keys
    return params


def _build_hierarchy_params(
    *, group_type: str | None, group_sid: int | None, strip_identifiers: bool | None
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if group_type is not None:
        params["groupType"] = group_type
    if group_sid is not None:
        params["groupSid"] = group_sid
    if strip_identifiers is not None:
        params["stripIdentifiers"] = strip_identifiers
    return params


def _coalesce_uri(value: object) -> str | None:
    if value is None or isinstance(value, Unset):
        return None
    return str(value)


def _coalesce_str(value: object, default: str = "") -> str:
    if value is None or isinstance(value, Unset):
        return default
    return str(value)


def _coalesce_int(value: object) -> int | None:
    if value is None or isinstance(value, Unset):
        return None
    return int(value)  # type: ignore[arg-type]


def _coalesce_bool(value: object, default: bool = False) -> bool:
    if value is None or isinstance(value, Unset):
        return default
    return bool(value)


def _find_dbutils() -> Any:
    """Locate the Databricks ``dbutils`` object without requiring the caller to pass it.

    Looks in (a) every parent stack frame's locals and globals, (b) ``builtins``,
    and (c) the ``__main__`` module — covering notebook globals, IPython
    user_ns, and run-from-script setups. Returns ``None`` if nothing was found,
    in which case the caller should raise a clear error directing the user to
    pass ``dbutils=`` explicitly.
    """
    try:
        frame = sys._getframe(1)
    except ValueError:  # pragma: no cover - shouldn't happen
        frame = None
    while frame is not None:
        for ns in (frame.f_locals, frame.f_globals):
            candidate = ns.get("dbutils")
            if candidate is not None:
                return candidate
        frame = frame.f_back
    try:
        import builtins

        candidate = getattr(builtins, "dbutils", None)
        if candidate is not None:
            return candidate
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        import sys as _sys

        main = _sys.modules.get("__main__")
        if main is not None:
            candidate = getattr(main, "dbutils", None)
            if candidate is not None:
                return candidate
    except Exception:  # pragma: no cover - defensive
        pass
    return None


@define(slots=False)
class _ReportBase:
    """Fields common to custom and asset-manager reports."""

    name: str
    schema_uri: str | None
    data_uri: str | None
    supports_hierarchy_columns: bool
    _pirm: PirmClient = field(repr=False)

    def _require(self, uri: str | None, kind: str) -> str:
        if not uri:
            raise PirmError(
                f"Report {self.name!r} does not expose a {kind} URI; the gateway omitted it."
            )
        return uri

    def _data_url(self, format: str) -> str:
        """Compose ``<data_uri>/<format>`` while tolerating a trailing slash."""
        return f"{self._require(self.data_uri, 'data').rstrip('/')}/{format}"

    async def fetch(
        self,
        format: str = ReportFormat.JSON,
        *,
        group_type: str | None = None,
        group_sid: int | None = None,
        delimiter: str | None = None,
        quote: str | None = None,
        escape: str | None = None,
        quote_strings: CsvStringQuoting | int | None = None,
        compress_keys: bool | None = None,
        strip_identifiers: bool | None = None,
    ) -> bytes:
        """Fetch the full report payload for ``format`` and return the raw bytes.

        For very large reports prefer :py:meth:`stream` or :py:meth:`write_to`,
        which avoid buffering the full body in memory.
        """
        url = self._data_url(format)
        params = _build_hierarchy_params(
            group_type=group_type,
            group_sid=group_sid,
            strip_identifiers=strip_identifiers,
        )
        params.update(
            _build_csv_params(
                delimiter=delimiter,
                quote=quote,
                escape=escape,
                quote_strings=quote_strings,
                compress_keys=compress_keys,
            )
        )
        response = await self._pirm._get(url, params=params)
        return response.content

    async def fetch_text(
        self,
        format: str = ReportFormat.JSON,
        *,
        encoding: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Convenience wrapper around :py:meth:`fetch` for textual formats.

        ``xlsx``/``excel`` is binary — call :py:meth:`fetch` or :py:meth:`write_to`
        instead.
        """
        url = self._data_url(format)
        params = _build_hierarchy_params(
            group_type=kwargs.pop("group_type", None),
            group_sid=kwargs.pop("group_sid", None),
            strip_identifiers=kwargs.pop("strip_identifiers", None),
        )
        params.update(
            _build_csv_params(
                delimiter=kwargs.pop("delimiter", None),
                quote=kwargs.pop("quote", None),
                escape=kwargs.pop("escape", None),
                quote_strings=kwargs.pop("quote_strings", None),
                compress_keys=kwargs.pop("compress_keys", None),
            )
        )
        if kwargs:
            raise TypeError(f"Unexpected keyword arguments: {sorted(kwargs)!r}")
        response = await self._pirm._get(url, params=params)
        if encoding:
            return response.content.decode(encoding)
        return response.text

    @asynccontextmanager
    async def stream(
        self,
        format: str = ReportFormat.CSV,
        *,
        group_type: str | None = None,
        group_sid: int | None = None,
        delimiter: str | None = None,
        quote: str | None = None,
        escape: str | None = None,
        quote_strings: CsvStringQuoting | int | None = None,
        compress_keys: bool | None = None,
        strip_identifiers: bool | None = None,
        chunk_size: int | None = None,
    ) -> AsyncIterator[AsyncIterator[bytes]]:
        """Stream the data payload as a context-managed async byte iterator.

        Example::

            async with report.stream("csv") as chunks:
                async with aiofiles.open("report.csv", "wb") as fh:
                    async for chunk in chunks:
                        await fh.write(chunk)
        """
        url = self._data_url(format)
        params = _build_hierarchy_params(
            group_type=group_type,
            group_sid=group_sid,
            strip_identifiers=strip_identifiers,
        )
        params.update(
            _build_csv_params(
                delimiter=delimiter,
                quote=quote,
                escape=escape,
                quote_strings=quote_strings,
                compress_keys=compress_keys,
            )
        )
        httpx_client = self._pirm._client.get_async_httpx_client()
        async with httpx_client.stream("GET", url, params=params) as resp:
            if resp.status_code >= 400:
                await resp.aread()
                raise PirmHTTPError(resp)
            if chunk_size is None:
                yield resp.aiter_bytes()
            else:
                yield resp.aiter_bytes(chunk_size=chunk_size)

    async def write_to(
        self,
        destination: str | os.PathLike[str],
        format: str = ReportFormat.CSV,
        *,
        chunk_size: int = 1 << 16,
        on_progress: Any = None,
        **kwargs: Any,
    ) -> int:
        """Stream this report into ``destination`` and return the number of bytes written.

        ``on_progress`` may be a callable ``(bytes_written: int) -> None`` or
        an awaitable; it is called after every chunk for progress reporting.
        Synchronous file I/O is intentional — disk writes are cheap relative
        to the network fetch and aiofiles is not a required dependency.

        If the network stream errors mid-fetch, or ``on_progress`` raises, or
        the surrounding task is cancelled, the partially-written file is
        unlinked before the exception propagates so callers don't ship a
        truncated payload downstream.
        """
        path = os.fspath(destination)
        written = 0
        success = False
        try:
            async with self.stream(format=format, chunk_size=chunk_size, **kwargs) as chunks:
                with open(path, "wb") as fh:
                    async for chunk in chunks:
                        fh.write(chunk)
                        written += len(chunk)
                        if on_progress is not None:
                            result = on_progress(written)
                            if hasattr(result, "__await__"):
                                await result
            success = True
            return written
        finally:
            if not success:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    async def schema(
        self,
        *,
        group_type: str | None = None,
        group_sid: int | None = None,
        strip_identifiers: bool | None = None,
    ) -> ReportSchema:
        """Fetch this report's schema."""
        url = self._require(self.schema_uri, "schema")
        params = _build_hierarchy_params(
            group_type=group_type,
            group_sid=group_sid,
            strip_identifiers=strip_identifiers,
        )
        response = await self._pirm._get(url, params=params)
        return ReportSchema.from_dict(response.json())

    # ------------------------------------------------------------------
    # data-science / Databricks integrations

    async def to_pandas(
        self,
        format: str = ReportFormat.CSV,
        *,
        read_options: Mapping[str, Any] | None = None,
        **fetch_kwargs: Any,
    ):
        """Fetch this report and return a ``pandas.DataFrame``.

        ``format`` may be any of the supported formats; the matching ``pandas``
        reader is used (``read_csv`` for csv/tsv, ``read_json``, ``read_excel``).
        ``read_options`` is forwarded to the pandas reader; remaining kwargs are
        passed to :py:meth:`fetch`.

        The payload is streamed to a temporary file and parsed from disk, so
        peak memory is the resulting ``DataFrame`` plus a tempfile on disk
        rather than multiple in-RAM copies of the raw bytes.

        ``pandas`` must be installed — it is preinstalled on Databricks runtimes
        and pulled in by the ``[pandas]`` / ``[databricks]`` extras.
        """
        try:
            import pandas as pd  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise PirmError(
                "to_pandas() requires the 'pandas' package. Install it or call "
                "fetch()/fetch_text() to get raw bytes and parse them yourself."
            ) from exc

        format_lower = format.lower()
        reader_info = _FORMAT_TO_PANDAS_READER.get(format_lower)
        if reader_info is None:
            raise PirmError(
                f"No pandas reader is mapped for format={format!r}. Use fetch() and "
                f"parse the bytes directly."
            )
        reader_name, defaults = reader_info
        reader = getattr(pd, reader_name)

        opts = dict(defaults)
        if read_options:
            opts.update(read_options)

        # Stream the payload to a tempfile and hand pandas the path — that
        # avoids the bytes->str->StringIO->DataFrame chain and lets pandas
        # take its C-level fast path on a real file descriptor. ``delete=False``
        # because Windows can't reopen a NamedTemporaryFile while it's held
        # open by the original handle; we close it before pandas reads.
        suffix = f".{format_lower}"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            await self.write_to(tmp_path, format=format_lower, **fetch_kwargs)
            return reader(tmp_path, **opts)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def to_spark(
        self,
        spark: Any,
        format: str = ReportFormat.CSV,
        *,
        read_options: Mapping[str, Any] | None = None,
        via_pandas: bool = False,
        dbfs_staging_path: str | None = None,
        **fetch_kwargs: Any,
    ):
        """Fetch this report into a Spark DataFrame.

        Two strategies:

        * ``via_pandas=True`` — read into a pandas frame first and call
          ``spark.createDataFrame``. Simple but materializes the full payload
          in driver memory.
        * Default — stream the report to ``dbfs_staging_path`` (or a temp file
          under ``/dbfs/tmp/`` if not provided) and load it back with
          ``spark.read``. Recommended for larger reports on Databricks.
        """
        if via_pandas:
            pdf = await self.to_pandas(format, read_options=read_options, **fetch_kwargs)
            return spark.createDataFrame(pdf)

        format_lower = format.lower()
        if format_lower not in ("csv", "tsv", "json"):
            raise PirmError(
                f"format={format!r} is not directly supported by spark.read; "
                f"pass via_pandas=True to round-trip through a pandas DataFrame."
            )

        if dbfs_staging_path is None:
            import uuid

            dbfs_staging_path = f"/dbfs/tmp/pirm-{uuid.uuid4().hex}.{format_lower}"

        await self.write_to(dbfs_staging_path, format=format_lower, **fetch_kwargs)

        # The Spark side of the path must be ``dbfs:/...`` while the local side is ``/dbfs/...``
        spark_path = dbfs_staging_path
        if spark_path.startswith("/dbfs/"):
            spark_path = "dbfs:" + spark_path[len("/dbfs"):]

        reader = spark.read
        if read_options:
            reader = reader.options(**read_options)

        if format_lower == "csv":
            reader = reader.option("header", "true").option("inferSchema", "true")
            return reader.csv(spark_path)
        if format_lower == "tsv":
            reader = (
                reader.option("header", "true")
                .option("inferSchema", "true")
                .option("delimiter", "\t")
            )
            return reader.csv(spark_path)
        return reader.json(spark_path)


@define(slots=False)
class CustomReport(_ReportBase):
    """A custom (deployment-wide) report listed under ``/custom``."""


@define(slots=False)
class AssetManagerReport(_ReportBase):
    """An Asset Manager report listed under ``/asset-manager``.

    ``report_sid`` and ``group_name`` are present when the gateway includes them.
    """

    report_sid: int | None = None
    group_name: str | None = None


class PirmClient:
    """Async high-level client for the Cenozon PIRM Data Gateway.

    Example::

        import asyncio
        from cenozon_pirm_client import PirmClient

        async def main():
            async with PirmClient.from_env() as pirm:
                for report in await pirm.custom_reports():
                    print(report.name)
                df = await pirm.custom_to_pandas("Master Pipeline Modified", "csv")

        asyncio.run(main())

    Compared to driving the generated ``api/*`` modules by hand:

    * Identity headers (``x-cenozon-client-id``, ``x-cenozon-deployment-id``,
      ``x-cenozon-environment``) are attached once at construction.
    * Data and schema requests go through the URIs returned in the listing,
      so display-name-vs-slug mismatches can't form a wrong URL.
    * All network calls are ``async def`` — modern API surface with no
      sync/async dichotomy to keep in sync.
    * Built-in helpers for streaming downloads, file writes, pandas, and Spark.

    The wrapper exposes its underlying :class:`AuthenticatedClient` via
    :py:attr:`raw` for cases where the generated async API is needed.
    """

    def __init__(
        self,
        *,
        token: str,
        client_id: str,
        deployment_id: str,
        base_url: str = DEFAULT_BASE_URL,
        environment_type: EnvironmentType | str | None | Unset = UNSET,
        auth_prefix: str = DEFAULT_AUTH_PREFIX,
        timeout: httpx.Timeout | float | None = None,
        verify_ssl: bool | str = True,
        follow_redirects: bool = False,
        raise_on_unexpected_status: bool = False,
        httpx_args: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        cache_listings: bool = False,
    ) -> None:
        if isinstance(environment_type, Unset):
            raw = os.environ.get(ENVIRONMENT_TYPE_ENV_VAR)
            resolved_env: EnvironmentType | str | None = (
                DEFAULT_ENVIRONMENT_TYPE if raw is None else raw
            )
        else:
            resolved_env = environment_type
        resolved_env = _coerce_environment_type(resolved_env)

        headers: dict[str, str] = {
            CLIENT_ID_HEADER: client_id,
            DEPLOYMENT_ID_HEADER: deployment_id,
        }
        if extra_headers:
            headers.update(extra_headers)

        if timeout is None:
            timeout_obj: httpx.Timeout | None = _DEFAULT_TIMEOUT
        elif isinstance(timeout, (int, float)):
            timeout_obj = httpx.Timeout(timeout)
        else:
            timeout_obj = timeout

        self._client = AuthenticatedClient(
            base_url=base_url,
            token=token,
            prefix=auth_prefix,
            environment_type=resolved_env,
            headers=headers,
            timeout=timeout_obj,
            verify_ssl=verify_ssl,
            follow_redirects=follow_redirects,
            raise_on_unexpected_status=raise_on_unexpected_status,
            httpx_args=dict(httpx_args) if httpx_args else {},
        )
        self._client_id = client_id
        self._deployment_id = deployment_id
        # Optional per-instance caches for the listing endpoints. Disabled by
        # default so callers never see stale data without opting in. When on,
        # ``custom_report(name)`` / ``asset_manager_report(name)`` reuse a
        # single listing per client lifetime — useful in scripts that pull
        # many reports back-to-back.
        self._cache_listings = cache_listings
        self._custom_listing_cache: list[CustomReport] | None = None
        self._asset_manager_listing_cache: dict[str | None, list[AssetManagerReport]] = {}
        # Locks so concurrent first-time ``custom_report(name)`` /
        # ``asset_manager_report(name)`` callers coalesce into one HTTP fetch
        # instead of stampeding the gateway with N identical listings. The
        # custom-report lock is eager (cheap, single instance); the asset-
        # manager locks are per-group, also eagerly upgraded under a coarse
        # guard so two concurrent first-time callers can't race to install
        # competing locks.
        self._custom_listing_lock: asyncio.Lock = asyncio.Lock()
        self._asset_manager_listing_locks: dict[str | None, asyncio.Lock] = {}
        self._asset_manager_locks_guard: asyncio.Lock = asyncio.Lock()
        self._closed = False

    @classmethod
    def from_env(
        cls,
        *,
        token: str | None = None,
        client_id: str | None = None,
        deployment_id: str | None = None,
        base_url: str | None = None,
        environment_type: EnvironmentType | str | None | Unset = UNSET,
        **kwargs: Any,
    ) -> PirmClient:
        """Build a client from ``CENOZON_*`` environment variables.

        Each constructor argument can still be passed explicitly to override
        the env-var lookup. Raises :class:`PirmError` if a required value is
        missing from both the arguments and the environment.
        """
        resolved_token = token or os.environ.get(TOKEN_ENV_VAR)
        resolved_client = client_id or os.environ.get(CLIENT_ID_ENV_VAR)
        resolved_deployment = deployment_id or os.environ.get(DEPLOYMENT_ID_ENV_VAR)
        resolved_base = base_url or os.environ.get(BASE_URL_ENV_VAR) or DEFAULT_BASE_URL

        missing = [
            name
            for name, value in (
                (TOKEN_ENV_VAR, resolved_token),
                (CLIENT_ID_ENV_VAR, resolved_client),
                (DEPLOYMENT_ID_ENV_VAR, resolved_deployment),
            )
            if not value
        ]
        if missing:
            raise PirmError(
                f"Missing required environment variable(s): {', '.join(missing)}"
            )

        return cls(
            token=resolved_token,  # type: ignore[arg-type]
            client_id=resolved_client,  # type: ignore[arg-type]
            deployment_id=resolved_deployment,  # type: ignore[arg-type]
            base_url=resolved_base,
            environment_type=environment_type,
            **kwargs,
        )

    @classmethod
    def from_databricks_secrets(
        cls,
        scope: str = "pirm",
        *,
        token_key: str = "api-token",
        client_id_key: str = "client-guid",
        deployment_id_key: str = "deployment-guid",
        environment_type_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        dbutils: Any = None,
        **kwargs: Any,
    ) -> PirmClient:
        """Build a client from Databricks secrets.

        ``dbutils`` defaults to the global ``dbutils`` provided by Databricks
        notebooks; pass it in explicitly when calling from a job / non-notebook
        context where the global isn't injected.

        Auto-detection walks the caller's stack looking for a ``dbutils``
        binding in any frame's locals or globals, then falls back to
        ``builtins`` and ``__main__``. The previous ``globals().get(...)``
        lookup only saw this module's globals and silently returned
        ``None``, so the auto-detect path never actually worked.

        Example (notebook)::

            async with PirmClient.from_databricks_secrets("pirm") as pirm:
                df = await pirm.custom_to_pandas("Master Pipeline Modified", "csv")
        """
        if dbutils is None:
            dbutils = _find_dbutils()
        if dbutils is None:
            raise PirmError(
                "from_databricks_secrets requires `dbutils`. In a notebook this "
                "is available as a global; in a job, pass `dbutils=...` "
                "explicitly. Auto-detect failed to find a `dbutils` binding "
                "in the caller's stack, builtins, or __main__."
            )

        get = dbutils.secrets.get
        token = get(scope=scope, key=token_key)
        client_id = get(scope=scope, key=client_id_key)
        deployment_id = get(scope=scope, key=deployment_id_key)
        env: EnvironmentType | str | None | Unset = UNSET
        if environment_type_key:
            env = get(scope=scope, key=environment_type_key)

        return cls(
            token=token,
            client_id=client_id,
            deployment_id=deployment_id,
            base_url=base_url,
            environment_type=env,
            **kwargs,
        )

    @property
    def raw(self) -> AuthenticatedClient:
        """The underlying generated :class:`AuthenticatedClient`."""
        return self._client

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def deployment_id(self) -> str:
        return self._deployment_id

    @property
    def environment_type(self) -> str | None:
        return self._client.environment_type

    async def aclose(self) -> None:
        """Close the underlying async (and sync, if created) HTTP transports.

        Safe to call multiple times — subsequent calls are no-ops. Also safe
        to call after exiting the ``async with`` block: the second close is
        skipped instead of raising or double-closing the underlying httpx
        clients.
        """
        if self._closed:
            return
        self._closed = True
        # Tolerate failures during cleanup so a flaky sync close doesn't
        # mask a more interesting failure already in flight.
        async_client = self._client._async_client  # type: ignore[attr-defined]
        if async_client is not None:
            await async_client.aclose()
        sync_client = self._client._client  # type: ignore[attr-defined]
        if sync_client is not None:
            sync_client.close()

    async def __aenter__(self) -> PirmClient:
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            # The generated Client only closes its async httpx client on
            # __aexit__; if the caller ever touched ``pirm.raw.get_httpx_client()``
            # a sync httpx.Client was lazily created and would leak. Close it
            # explicitly here so ``async with PirmClient`` is a complete
            # resource manager regardless of which transport got used.
            sync_client = self._client._client  # type: ignore[attr-defined]
            if sync_client is not None:
                sync_client.close()
        finally:
            await self._client.__aexit__(*args)

    # ------------------------------------------------------------------
    # status

    async def status(self) -> str:
        """Hit the service status endpoint; returns ``"alive"`` on success."""
        response = await self._get("/")
        return response.text.strip()

    # ------------------------------------------------------------------
    # custom reports

    async def custom_reports(self) -> list[CustomReport]:
        """List all custom reports for this deployment.

        Always issues a fresh HTTP request. The optional ``cache_listings``
        flag on the constructor only affects the by-name lookup helpers
        (:py:meth:`custom_report`, :py:meth:`asset_manager_report`).
        """
        response = await self._get("/custom")
        return [self._build_custom_report(item) for item in response.json()]

    async def _custom_listing(self) -> list[CustomReport]:
        if not self._cache_listings:
            return await self.custom_reports()
        if self._custom_listing_cache is not None:
            return self._custom_listing_cache
        async with self._custom_listing_lock:
            # Re-check under the lock so concurrent callers coalesce into one
            # HTTP fetch instead of issuing N identical listings.
            if self._custom_listing_cache is None:
                self._custom_listing_cache = await self.custom_reports()
            return self._custom_listing_cache

    def invalidate_listing_cache(self) -> None:
        """Drop any cached listings so the next by-name lookup re-fetches.

        Exposed for callers that hold a long-lived ``PirmClient`` with
        ``cache_listings=True`` and need to pick up reports added/removed
        on the server after construction.
        """
        self._custom_listing_cache = None
        self._asset_manager_listing_cache.clear()

    async def custom_report(self, name: str) -> CustomReport:
        """Look up a single custom report by its ``reportName``.

        ``name`` is matched case-insensitively against the display name
        returned in the listing. To call a slug directly, use
        :py:meth:`custom_report_from_uri`. When the client was constructed
        with ``cache_listings=True`` the listing is fetched once per client
        and reused for subsequent lookups; call
        :py:meth:`invalidate_listing_cache` to force a refresh.
        """
        target = name.casefold()
        for report in await self._custom_listing():
            if report.name.casefold() == target:
                return report
        raise PirmError(f"No custom report named {name!r} on this deployment")

    def custom_report_from_uri(self, data_uri: str, schema_uri: str | None = None) -> CustomReport:
        """Construct a :class:`CustomReport` from explicit URIs (e.g. for bookmarked endpoints).

        The slug used as the report ``name`` is extracted from the URI's path
        — query strings and trailing slashes are ignored. Expects the
        canonical ``.../custom/<slug>/data`` pattern; otherwise the fallback
        is the last non-empty path segment.
        """
        path = urlsplit(data_uri).path.rstrip("/")
        segments = [s for s in path.split("/") if s]
        if len(segments) >= 2 and segments[-1] == "data":
            name = segments[-2]
        elif segments:
            name = segments[-1]
        else:
            raise PirmError(f"Cannot derive a report name from data_uri={data_uri!r}")
        return CustomReport(
            name=name,
            schema_uri=schema_uri,
            data_uri=data_uri,
            supports_hierarchy_columns=False,
            pirm=self,
        )

    # ------------------------------------------------------------------
    # asset manager reports

    async def asset_manager_reports(self, group: str | None = None) -> list[AssetManagerReport]:
        """List Asset Manager reports — across all groups, or just one."""
        url = f"/asset-manager/group/{group}" if group else "/asset-manager"
        response = await self._get(url)
        return [self._build_asset_manager_report(item) for item in response.json()]

    async def _asset_manager_listing(self, group: str | None) -> list[AssetManagerReport]:
        if not self._cache_listings:
            return await self.asset_manager_reports(group=group)
        cached = self._asset_manager_listing_cache.get(group)
        if cached is not None:
            return cached
        # Take the coarse guard briefly to install a per-group lock without
        # racing — concurrent first-time callers must end up sharing the
        # SAME lock instance, otherwise they each fire their own HTTP fetch.
        async with self._asset_manager_locks_guard:
            lock = self._asset_manager_listing_locks.get(group)
            if lock is None:
                lock = asyncio.Lock()
                self._asset_manager_listing_locks[group] = lock
        async with lock:
            cached = self._asset_manager_listing_cache.get(group)
            if cached is None:
                cached = await self.asset_manager_reports(group=group)
                self._asset_manager_listing_cache[group] = cached
            return cached

    async def asset_manager_report(
        self, name: str, *, group: str | None = None
    ) -> AssetManagerReport:
        """Look up a single Asset Manager report by display name.

        Pass ``group`` to scope the search; otherwise the lookup spans every group.
        When the client was constructed with ``cache_listings=True`` the listing
        is fetched once per (group) key and reused for subsequent lookups.
        """
        target = name.casefold()
        for report in await self._asset_manager_listing(group):
            if report.name.casefold() == target:
                return report
        scope = f" in group {group!r}" if group else ""
        raise PirmError(f"No Asset Manager report named {name!r}{scope}")

    def asset_manager_report_by_sid(self, report_sid: int) -> AssetManagerReport:
        """Build an :class:`AssetManagerReport` from a known SID without listing."""
        base = self._client._base_url.rstrip("/")  # type: ignore[attr-defined]
        return AssetManagerReport(
            name=str(report_sid),
            schema_uri=f"{base}/asset-manager/{report_sid}/schema",
            data_uri=f"{base}/asset-manager/{report_sid}/data",
            supports_hierarchy_columns=False,
            pirm=self,
            report_sid=report_sid,
            group_name=None,
        )

    # ------------------------------------------------------------------
    # one-shot convenience: skip the explicit listing round-trip

    async def fetch_custom(
        self, report_name: str, format: str = ReportFormat.JSON, **kwargs: Any
    ) -> bytes:
        """Fetch a custom report's data in one call.

        ``report_name`` is matched case-insensitively against the display name.
        """
        report = await self.custom_report(report_name)
        return await report.fetch(format, **kwargs)

    async def fetch_asset_manager(
        self,
        report_name: str,
        format: str = ReportFormat.JSON,
        *,
        group: str | None = None,
        **kwargs: Any,
    ) -> bytes:
        """Fetch an Asset Manager report's data in one call."""
        report = await self.asset_manager_report(report_name, group=group)
        return await report.fetch(format, **kwargs)

    async def custom_to_pandas(
        self, report_name: str, format: str = ReportFormat.CSV, **kwargs: Any
    ):
        """Fetch a custom report into a pandas DataFrame in one call."""
        report = await self.custom_report(report_name)
        return await report.to_pandas(format, **kwargs)

    async def asset_manager_to_pandas(
        self,
        report_name: str,
        format: str = ReportFormat.CSV,
        *,
        group: str | None = None,
        **kwargs: Any,
    ):
        """Fetch an Asset Manager report into a pandas DataFrame in one call."""
        report = await self.asset_manager_report(report_name, group=group)
        return await report.to_pandas(format, **kwargs)

    # ------------------------------------------------------------------
    # internals

    def _build_custom_report(self, item: Mapping[str, Any]) -> CustomReport:
        return CustomReport(
            name=_coalesce_str(item.get("reportName")),
            schema_uri=_coalesce_uri(item.get("schemaUri")),
            data_uri=_coalesce_uri(item.get("dataUri")),
            supports_hierarchy_columns=_coalesce_bool(item.get("supportsHierarchyColumns")),
            pirm=self,
        )

    def _build_asset_manager_report(self, item: Mapping[str, Any]) -> AssetManagerReport:
        return AssetManagerReport(
            name=_coalesce_str(item.get("reportName")),
            schema_uri=_coalesce_uri(item.get("schemaUri")),
            data_uri=_coalesce_uri(item.get("dataUri")),
            supports_hierarchy_columns=_coalesce_bool(item.get("supportsHierarchyColumns")),
            pirm=self,
            report_sid=_coalesce_int(item.get("reportSid")),
            group_name=_coalesce_uri(item.get("groupName")),
        )

    async def _get(
        self, url: str, *, params: Mapping[str, Any] | None = None
    ) -> httpx.Response:
        httpx_client = self._client.get_async_httpx_client()
        response = await httpx_client.get(url, params=dict(params) if params else None)
        if response.status_code >= 400:
            raise PirmHTTPError(response)
        return response


__all__ = (
    "AssetManagerReport",
    "CustomReport",
    "EnvironmentType",
    "PirmClient",
    "PirmError",
    "PirmHTTPError",
    "ReportFormat",
)
