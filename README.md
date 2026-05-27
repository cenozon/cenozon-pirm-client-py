# cenozon-pirm-client

A Python client for the Cenozon PIRM Data Gateway. Discover available reports, view their schemas, and securely download data as JSON, CSV, TSV, or Excel (xlsx).

Designed for data analysts and engineers pulling PIRM data into Python, pandas, Databricks, or any other downstream tool.

The package ships three layers:

* **`PirmClient`** — an async, ergonomic wrapper that returns native Python objects, handles slug-vs-display-name normalization, streams cleanly, and offers pandas / Spark integrations.
* **The generated OpenAPI layer** under `cenozon_pirm_client.api.*` and `cenozon_pirm_client.models.*` for callers who want the raw spec-shaped functions.
* **`pirm-dgw`** — an opt-in command-line interface, packaged separately as `cenozon-pirm-cli`.

All three are stable and have backward-compatible signatures with v1.0.0; the `PirmClient` is recommended for new code.

See [CHANGELOG.md](CHANGELOG.md) for the full release notes.

## Before You Begin

- Base URL: `https://platform.cenozon.com/api/pirm/data/v1`
- Access token: use a Personal Access Token (PAT) for scripts, notebooks, and automation
- Your identifiers:
  - Your Cenozon Client ID / GUID
  - Your target PIRM Deployment ID / GUID (e.g. production or test)

Ask your Cenozon administrator if you are unsure of these values.

**NOTE:** Bearer (JWT) authentication is also supported, but those workflows are more complex and outside the scope of these examples. Contact Cenozon for help wiring Bearer authentication.

## Install

Recommended: [uv](https://docs.astral.sh/uv/) for environment + dependency management.

### Base library only

```sh
uv init
uv add 'git+https://github.com/cenozon/cenozon-pirm-client-py@v1.1.0'
```

*NOTE*: you should always use the *latest* published version (tag) of the package.

This gives you `PirmClient`, the generated `api/*` layer, models, and types. No CLI, no pandas, no Excel reader.

### Optional features — install only what you need

Every integration is an opt-in extra. Pick the ones that match your use case:

| Need | Install command |
| --- | --- |
| `report.to_pandas("csv")` and friends | `uv add 'cenozon-pirm-client[pandas] @ git+https://github.com/cenozon/cenozon-pirm-client-py.git@v1.1.0'` |
| Excel (`.xlsx`) parsing (pulls in `openpyxl`) | `uv add 'cenozon-pirm-client[excel] @ git+https://github.com/cenozon/cenozon-pirm-client-py.git@v1.1.0'` |
| Bundle for Databricks notebooks (pandas + Excel) | `uv add 'cenozon-pirm-client[databricks] @ git+https://github.com/cenozon/cenozon-pirm-client-py.git@v1.1.0'` |
| `pirm-dgw` command-line tool (separate package, no library bloat) | `uv tool install 'cenozon-pirm-cli @ git+https://github.com/cenozon/cenozon-pirm-client-py.git@v1.1.0#subdirectory=cli'` |

Multiple extras can be combined: `uv add 'cenozon-pirm-client[pandas,excel] @ git+...'`.

The CLI is shipped as a **separate distribution** (`cenozon-pirm-cli`) so that the base library install never pollutes consumer venvs with a stray script entry. Use `uv tool install` to drop the `pirm-dgw` binary into your shell PATH globally, or `uv add` it inside a project venv if you prefer.

### Credentials

Configure a `.env` next to your script (no angle brackets):

```env
CENOZON_API_TOKEN=<Personal Access Token>
CENOZON_CLIENT_ID=<Cenozon client id; supplied by Cenozon>
CENOZON_DEPLOYMENT_ID=<PIRM deployment id; supplied by Cenozon>
# Optional — defaults to "production"; set to "" to suppress the env header
CENOZON_ENVIRONMENT_TYPE=production
# Optional — overrides the default gateway URL
CENOZON_BASE_URL=https://platform.cenozon.com/api/pirm/data/v1
```

## Quick Start (Python)

```python
import asyncio
from cenozon_pirm_client import PirmClient


async def main() -> None:
    async with PirmClient.from_env() as pirm:
        # Discover
        for report in await pirm.custom_reports():
            print(report.name, "->", report.data_uri)

        # Pull data — display-name-friendly lookup, slug-correct under the hood
        report = await pirm.custom_report("Master Pipeline Modified")
        csv_bytes = await report.fetch("csv")                # raw bytes
        text = await report.fetch_text("json")                # str
        df = await report.to_pandas("csv")                    # pandas.DataFrame
        await report.write_to("/tmp/pipeline.csv", "csv")     # streams to disk

        # One-shot shortcuts
        df_ili = await pirm.custom_to_pandas("ILI", "csv")
        xlsx = await pirm.fetch_custom("Master Pipeline Modified", "xlsx")


asyncio.run(main())
```

Every network method is `async def`. Run from notebooks with `await ...` directly, or wrap with `asyncio.run(...)` from scripts.

## Quick Start (CLI)

After `uv tool install 'cenozon-pirm-cli @ git+...#subdirectory=cli'`, the `pirm-dgw` command is on your PATH:

```sh
# Sanity
pirm-dgw ping
pirm-dgw whoami

# Listings
pirm-dgw list custom
pirm-dgw list asset-manager --group my-group

# Schemas
pirm-dgw schema custom "Master Pipeline Modified"
pirm-dgw schema asset-manager 12345

# Downloads — auto-stream with a progress spinner; default output is <slug>.<format>
pirm-dgw fetch custom "Master Pipeline Modified" -f csv -o pipeline.csv
pirm-dgw fetch custom ili -f xlsx
pirm-dgw fetch asset-manager 12345 -f csv --group-type network --group-sid 7
pirm-dgw fetch custom incidents -f csv --strip-identifiers
```

The CLI reads the same `.env` the Python API uses (default `./.env`), or accepts every credential as a flag. Run `pirm-dgw <subcommand> --help` for the full surface. Output is plain tab-separated when stdout is piped (CI-friendly).

## Environment Type

All requests include an `x-cenozon-environment` header. It defaults to `production`; override it per-client:

```python
from cenozon_pirm_client import EnvironmentType, PirmClient

pirm = PirmClient.from_env(environment_type=EnvironmentType.STAGING)
# or as a string: environment_type="staging"
# pass "" to suppress the header entirely
```

The default can also be set via the `CENOZON_ENVIRONMENT_TYPE` environment variable. The `EnvironmentType` enum mirrors the server enum exactly and accepts:
`DEVELOPMENT`, `TEST`, `STAGING`, `PILOT`, `PRODUCTION`, `INTERNAL_ONLY`.

## Strip Internal Identifier Columns

Data and schema endpoints accept `strip_identifiers=True` to drop columns whose names end in `_sid`:

```python
df = await report.to_pandas("csv", strip_identifiers=True)
```

## Supported Formats

`json` (default), `csv`, `tsv`, `xlsx` (alias `excel`). Use `ReportFormat` for the string constants:

```python
from cenozon_pirm_client import ReportFormat

bytes_ = await report.fetch(ReportFormat.XLSX)
```

`to_pandas("xlsx")` requires the `[excel]` (or `[databricks]`) extra for the `openpyxl` reader.

## Streaming Large Reports

The default `PirmClient` timeout is generous (`read=None`, `connect=30s`), and `stream()` / `write_to()` push bytes through chunk-by-chunk with no intermediate buffer:

```python
async with report.stream("csv") as chunks:
    with open("big.csv", "wb") as fh:
        async for chunk in chunks:
            fh.write(chunk)
```

Or one-shot to disk (cleanup-safe — partial files are removed if the stream errors):

```python
n_bytes = await report.write_to("/tmp/big.csv", "csv")
```

The CLI's `fetch` subcommand already does this with a progress indicator.

## Databricks Usage

Install the package as a cluster library, or `%pip install` in a notebook. The `[databricks]` extra brings in pandas + openpyxl.

### From notebook secrets

```python
import asyncio
from cenozon_pirm_client import PirmClient

async def load() -> None:
    async with PirmClient.from_databricks_secrets(scope="pirm", dbutils=dbutils) as pirm:
        df = await pirm.custom_report("Master Pipeline Modified").to_pandas("csv")
        display(df)

await load()   # in a notebook
# or:
# asyncio.run(load())
```

Defaults the lookup keys to `api-token`, `client-guid`, `deployment-guid`; override via `token_key=`, `client_id_key=`, `deployment_id_key=`, `environment_type_key=`. Always pass `dbutils=dbutils` from the notebook scope (notebooks inject it as a global; library code can't reach it through `globals()`).

### Streaming into Spark

For larger reports, stream to DBFS and read with `spark.read` — avoids materializing the full payload on the driver:

```python
sdf = await pirm.custom_report("Master Pipeline Modified").to_spark(spark, "csv")
display(sdf)
```

Pass `via_pandas=True` to round-trip through a pandas DataFrame (driver-local; fine for small reports and required for Excel). Pass `dbfs_staging_path="/dbfs/tmp/...csv"` to control where the staging file lives.

### Concurrent fetches

A single `PirmClient` shares one async HTTP transport; many requests run concurrently with no extra setup:

```python
async with PirmClient.from_env() as pirm:
    pipeline, ili, status = await asyncio.gather(
        pirm.fetch_custom("Master Pipeline Modified", "csv"),
        pirm.fetch_custom("ILI", "csv"),
        pirm.status(),
    )
```

### Optional listing cache

`pirm.custom_report(name)` and `pirm.asset_manager_report(name)` re-list the gateway on every lookup by default. If you're pulling many reports from a stable deployment in one job, enable the cache:

```python
async with PirmClient.from_env(cache_listings=True) as pirm:
    df1 = await pirm.custom_to_pandas("ILI", "csv")
    df2 = await pirm.custom_to_pandas("Master Pipeline Modified", "csv")
    df3 = await pirm.custom_to_pandas("Chemical Pumps", "csv")
    # ...only one listing HTTP round-trip total

    pirm.invalidate_listing_cache()  # force a refresh if needed
```

The cache is in-memory and per-instance. It's off by default to keep the wrapper safe for long-running jobs.

## Hierarchy Filtering

Reports with `supports_hierarchy_columns=True` accept `group_type` and `group_sid` to filter to a portion of the network:

```python
report = await pirm.custom_report("Chemical Pumps")
df = await report.to_pandas("csv", group_type="network", group_sid=123)
```

`group_type` is one of `hierarchy`, `field` (or `system`), `network`.

## Asset Manager Reports

```python
# All groups
for r in await pirm.asset_manager_reports():
    print(r.group_name, r.name, r.report_sid)

# Single group
group_reports = await pirm.asset_manager_reports(group="my-group")

# By name (within a group, or across all groups)
r = await pirm.asset_manager_report("Some Report", group="my-group")
df = await r.to_pandas("csv")

# Or by SID without listing
r = pirm.asset_manager_report_by_sid(12345)
csv_bytes = await r.fetch("csv")
```

## Error Handling

```python
from cenozon_pirm_client import PirmError, PirmHTTPError

try:
    df = await pirm.custom_report("nope").to_pandas("csv")
except PirmHTTPError as e:
    print(e.response.status_code, e.response.text)
except PirmError as e:
    print("client-side error:", e)
```

Common cases:

* `401` / `403`: check your token, header GUIDs, and deployment permission.
* `404`: report name/SID or group doesn't exist for this deployment.
* `400`: unsupported `format` value or invalid formatting options.
* `400 "PIRM Reporting API has not been enabled for this client"`: the server could not resolve a backend connection string for your client + environment. Confirm `environment_type` is set (it defaults to `production`), or contact your Cenozon administrator.

## Using the Generated API Directly

The OpenAPI-generated layer is unchanged from v1.0.0 (purely additive). Useful when you need every knob from the spec:

```python
import os
from cenozon_pirm_client import AuthenticatedClient
from cenozon_pirm_client.api.custom_report import (
    get_custom,
    get_custom_report_name_data_format,
)

client = AuthenticatedClient(
    base_url="https://platform.cenozon.com/api/pirm/data/v1",
    token=os.environ["CENOZON_API_TOKEN"],
    prefix="Token",
    # environment_type defaults to "production"; pass "" to skip
)

reports = get_custom.sync(
    client=client,
    x_cenozon_client_id="<client-guid>",
    x_cenozon_deployment_id="<deployment-guid>",
)

resp = get_custom_report_name_data_format.sync_detailed(
    report_name="master-pipeline-modified",   # path slug, not display name
    format_="csv",
    client=client,
    strip_identifiers=True,
    x_cenozon_client_id="<client-guid>",
    x_cenozon_deployment_id="<deployment-guid>",
)
csv_bytes = resp.content
```

The generated layer requires the **slug** (kebab-cased) as the `report_name` path parameter — see the `dataUri` returned by `get_custom`. The high-level `PirmClient` handles this for you by routing requests through the server-issued URIs.

## Models at a Glance

* `AvailableReport`: `report_sid`, `group_name`, `report_name`, `supports_hierarchy_columns`, `schema_uri`, `data_uri`.
* `ReportSchema` and `ReportColumn`: column `index`, `name`, `type_`, `is_nullable`.
* `CsvStringQuoting` (for CSV): `VALUE_0` automatic, `VALUE_1` quote empty, `VALUE_2` quote non-empty, `VALUE_3` quote all strings.
* `ProblemDetails`: standard error payload for 4xx/5xx.
* `EnvironmentType`: enum mirroring the server side (`DEVELOPMENT`, `TEST`, `STAGING`, `PILOT`, `PRODUCTION`, `INTERNAL_ONLY`). Pass the enum or its lowercased string equivalent.

## Advanced httpx customization

Pass `httpx_args=...` (a dict) to `PirmClient` to set logging hooks, proxies, custom transports, etc. You can also reach `client.raw.get_async_httpx_client()` (or the sync variant) for direct access.


