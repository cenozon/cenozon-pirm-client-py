# Changelog

## 1.1.0 — 2026-05-27

### Fixed

- Send the `x-cenozon-environment` header on every request (defaults to
  `production`, configurable via `CENOZON_ENVIRONMENT_TYPE` or per-call).
  Without it the gateway returned a misleading
  `400 "PIRM Reporting API has not been enabled for this client"`.
- High-level wrapper resolves custom report URLs through the server-issued
  `data_uri` / `schema_uri`, so passing the display name
  (`"Master Pipeline Modified"`) no longer produces a 404 against the
  on-disk slug (`master-pipeline-modified`).

### Added

- `PirmClient` — async wrapper. `from_env()`, `from_databricks_secrets()`,
  `custom_reports()`, `custom_report(name)`, `asset_manager_reports([group])`,
  `asset_manager_report(name, group=)`, `asset_manager_report_by_sid(sid)`,
  one-shot `fetch_custom` / `custom_to_pandas` / `fetch_asset_manager` /
  `asset_manager_to_pandas`. Async context manager + idempotent `aclose()`.
- `CustomReport` / `AssetManagerReport` types with `fetch`, `fetch_text`,
  `stream`, `write_to`, `schema`, `to_pandas`, `to_spark`. Streaming methods
  are chunked and cancellation-safe (partial files are removed on error).
- `EnvironmentType` enum mirroring the server enum. Strings accepted
  everywhere.
- `ReportFormat` constants (`json`, `csv`, `tsv`, `xlsx`, `excel`).
- `PirmError` / `PirmHTTPError` exceptions with the original `httpx.Response`
  attached.
- Optional `PirmClient(cache_listings=True)` — coalesces concurrent
  first-time name lookups into one HTTP request. `invalidate_listing_cache()`
  forces a refresh.
- `pirm-dgw` CLI — separate `cenozon-pirm-cli` package. Subcommands `ping`,
  `whoami`, `list custom|asset-manager`, `schema custom|asset-manager`,
  `fetch custom|asset-manager`. Streaming downloads with a progress spinner.
  Install with
  `uv tool install 'cenozon-pirm-cli @ git+https://github.com/cenozon/cenozon-pirm-client-py.git@v1.1.0#subdirectory=cli'`.
- Optional extras: `[pandas]`, `[excel]`, `[databricks]`.
- Generated `api/*` endpoints updated to the current spec:
  `stripIdentifiers` added to every data + schema endpoint;
  `groupType` / `groupSid` added to the schema endpoints that were missing
  them. `xlsx` / `excel` formats accepted by the data endpoints.
- `Client` / `AuthenticatedClient` accept `environment_type=...` and gain a
  `with_environment_type(...)` method.

### Changed

- Default request timeout is now `httpx.Timeout(connect=30s, write=30s,
  pool=10s, read=None)` — multi-megabyte streams no longer hit httpx's
  5-second read default. Caller-supplied timeouts are honored verbatim.
- `pyproject.toml` migrated from `[tool.poetry]` to PEP 621 `[project]`.
  Wheel contents unchanged.

## 1.0.0 — 2025-10-28

Initial release. Generated OpenAPI client for the Cenozon PIRM Data Gateway.
