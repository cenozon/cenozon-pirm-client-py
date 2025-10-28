# cenozon-pirm-client
A Python client for the Cenozon PIRM Data Gateway that lets you discover available reports, view their schemas, and securely download data as JSON, CSV, or TSV.

This guide is written for users (data analysts, engineers) who want to pull PIRM data into tools like Python, Excel, or Databricks.

## Before You Begin

- Base URL: `https://platform.cenozon.com/api/pirm/data/v1`
- Access token: use a Personal Access Token (PAT) for scripts, notebooks, and automation
- Your identifiers:
  - Your Cenozon Client ID / GUID
  - Your target PIRM Deployment ID / GUID (e.g. production or test)

Ask your Cenozon administrator if you are unsure of these values.

**NOTE**: Bearer (JWT) authentication is also supported, however, these authentication workflows are more complex and outside of the scope of the provided examples.  Please contact Cenozon for assistance in utilizing Bearer authentication.

## Quick Start (Step‑by‑Step)

We recommend using [uv](https://docs.astral.sh/uv/) for python package / dependency management.

```sh
uv init
uv add git+https://github.com/cenozon/cenozon-pirm-client-py@v1.0.0
uv add python-dotenv
```

Next, create a plaintext file called `.env` and populate it for your environment (note: do not include `<>` as part of your values; these are just placeholders):

```env
CENOZON_API_TOKEN=<Personal Access Token>
CENOZON_CLIENT_ID=<Cenozon client id; supplied by Cenozon>
CENOZON_DEPLOYMENT_ID=<PIRM deployment id; supplied by Cenozon>
```

And lastly, a working example which lists available Asset Manager reports within the specified PIRM deployment:

```python
import os
from dotenv import load_dotenv
from cenozon_pirm_client import AuthenticatedClient
from cenozon_pirm_client.api.asset_manager_report import get_asset_manager
from cenozon_pirm_client.types import UNSET

def main():
    load_dotenv()

    token=os.environ.get("CENOZON_API_TOKEN")
    client_id=os.environ.get("CENOZON_CLIENT_ID")
    deployment_id=os.environ.get("CENOZON_DEPLOYMENT_ID")

    client = AuthenticatedClient(
        base_url="https://platform.cenozon.com/api/pirm/data/v1",
        token=token,
        prefix="Token",
    )

    reports = get_asset_manager.sync(
        client=client,
        x_cenozon_client_id=client_id,
        x_cenozon_deployment_id=deployment_id,
    )
    for report in reports:
        print(report)
        print()

if __name__ == "__main__":
    main()
```

## Models at a Glance
- `AvailableReport`: `report_sid`, `group_name`, `report_name`, `supports_hierarchy_columns`, `schema_uri`, `data_uri`.
- `ReportSchema` and `ReportColumn`: column `index`, `name`, `type`, `is_nullable`.
- `CsvStringQuoting` (for CSV): `0` automatic, `1` quote empty, `2` quote non-empty, `3` quote all strings.
- `ProblemDetails`: standard error payload for 4xx/5xx.

## Step 1 — Find Available Reports

Asset Manager reports (all groups):
```python
from cenozon_pirm_client.api.asset_manager_report import get_asset_manager
from cenozon_pirm_client.types import UNSET

reports = get_asset_manager.sync(
    client=client,
    x_cenozon_client_id="<client-guid>",
    x_cenozon_deployment_id="<deployment-guid>",
)
# returns List[AvailableReport]
```

Asset Manager reports for a specific group:
```python
from cenozon_pirm_client.api.asset_manager_report import get_asset_manager_group_group_name

group_reports = get_asset_manager_group_group_name.sync(
    group_name="my-group",
    client=client,
    x_cenozon_client_id="<client-guid>",
    x_cenozon_deployment_id="<deployment-guid>",
)
```

Custom reports (deployment-wide):
```python
from cenozon_pirm_client.api.custom_report import get_custom

custom_reports = get_custom.sync(
    client=client,
    x_cenozon_client_id="<client-guid>",
    x_cenozon_deployment_id="<deployment-guid>",
)
```

Tip: First list reports, then follow the `schema_uri` / `data_uri` in each `AvailableReport` to work with a specific report.

## Step 2 — Understand the Columns (Schemas)

By Asset Manager group + report name:
```python
from cenozon_pirm_client.api.asset_manager_report import get_asset_manager_group_group_name_schema

schema = get_asset_manager_group_group_name_schema.sync(
    group_name="my-group",
    report_name="my-report",
    client=client,
    x_cenozon_client_id="<client-guid>",
    x_cenozon_deployment_id="<deployment-guid>",
)
# returns ReportSchema
```

By Asset Manager report SID:
```python
from cenozon_pirm_client.api.asset_manager_report import get_asset_manager_report_sid_schema

schema = get_asset_manager_report_sid_schema.sync(
    report_sid=12345,
    client=client,
    x_cenozon_client_id="<client-guid>",
    x_cenozon_deployment_id="<deployment-guid>",
)
```

Custom report schema:
```python
from cenozon_pirm_client.api.custom_report import get_custom_report_name_schema

schema = get_custom_report_name_schema.sync(
    report_name="my-custom-report",
    client=client,
    x_cenozon_client_id="<client-guid>",
    x_cenozon_deployment_id="<deployment-guid>",
)
```

## Step 3 — Download Data (JSON, CSV, TSV)

Optional hierarchy filtering lets you limit results to a portion of your network:
- `groupType`: one of `hierarchy`, `field` (or `system`), `network`
- `groupSid`: the identifier for the selected group
Ask your administrator if you are unsure which values to use.

Output formatting options:
- CSV/TSV: `delimiter`, `quote`, `escape`, `quoteStrings` (0..3)
- JSON: `compressKeys=True` produces compact “DataTable‑style” keys

Note on return type: For data endpoints, the client’s `sync_detailed` variant returns a `Response` with raw bytes in `content` (the `parsed` field is `None` on success).

Asset Manager by group + name:
```python
from cenozon_pirm_client.api.asset_manager_report import get_asset_manager_group_group_name_data_format
from cenozon_pirm_client.models import csv_string_quoting as quoting

resp = get_asset_manager_group_group_name_data_format.sync_detailed(
    group_name="my-group",
    format_="csv",                                  # "json", "csv", or "tsv"
    client=client,
    report_name="my-report",
    group_type="network",                           # optional
    group_sid=123,                                   # optional
    delimiter=",", quote="\"", escape="#",        # optional CSV tweaks
    quote_strings=quoting.CsvStringQuoting.VALUE_0,  # 0..3
    compress_keys=False,                             # JSON output only
    x_cenozon_client_id="<client-guid>",
    x_cenozon_deployment_id="<deployment-guid>",
)
if resp.status_code == 200:
    data_bytes = resp.content  # write to a file, parse with pandas, etc.
else:
    print("Request failed:", resp.status_code, resp.content)
```

Asset Manager by SID:
```python
from cenozon_pirm_client.api.asset_manager_report import get_asset_manager_report_sid_data_format

resp = get_asset_manager_report_sid_data_format.sync_detailed(
    report_sid=12345,
    format_="json",
    client=client,
    group_type="hierarchy", group_sid=999,          # optional
    x_cenozon_client_id="<client-guid>",
    x_cenozon_deployment_id="<deployment-guid>",
)
```

Custom report data:
```python
from cenozon_pirm_client.api.custom_report import get_custom_report_name_data_format

resp = get_custom_report_name_data_format.sync_detailed(
    report_name="my-custom-report",
    format_="tsv",
    client=client,
    x_cenozon_client_id="<client-guid>",
    x_cenozon_deployment_id="<deployment-guid>",
)
```

### Step 4 — Open in Excel or pandas
```python
import io, pandas as pd

resp = get_asset_manager_report_sid_data_format.sync_detailed(
    report_sid=12345, format_="csv", client=client,
    x_cenozon_client_id="<client-guid>", x_cenozon_deployment_id="<deployment-guid>",
)
df = pd.read_csv(io.BytesIO(resp.content))
```

### Large downloads (streaming)
For very large result sets, stream to a file to avoid running out of memory:

```python
import httpx

headers = {
    "x-cenozon-client-id": "<client-guid>",
    "x-cenozon-deployment-id": "<deployment-guid>",
}

with client.get_httpx_client().stream(
    "GET", "/asset-manager/12345/data/csv", params={}, headers=headers
) as r, open("report.csv", "wb") as f:
    for chunk in r.iter_bytes():
        f.write(chunk)
```

## Databricks Usage

- Install the client as a cluster library (wheel or source). If needed, `pip install` from your workspace repo or artifact store.
- Store your token and GUIDs in Databricks Secrets and retrieve them at runtime.
- Use the full gateway path: `https://platform.cenozon.com/api/pirm/data/v1`.
- For private networks with custom CAs, pass a CA bundle path in `verify_ssl` (avoid disabling verification).

Example (pandas + Spark):
```python
import io, pandas as pd
from cenozon_pirm_client import AuthenticatedClient
from cenozon_pirm_client.api.asset_manager_report import get_asset_manager_report_sid_data_format

token = dbutils.secrets.get(scope="pirm", key="api-token")
client_guid = dbutils.secrets.get(scope="pirm", key="client-guid")
deployment_guid = dbutils.secrets.get(scope="pirm", key="deployment-guid")

client = AuthenticatedClient(
    base_url="https://platform.cenozon.com/api/pirm/data/v1",
    token=token,                  # store PAT in a secret
    prefix="Token",
)

resp = get_asset_manager_report_sid_data_format.sync_detailed(
    report_sid=12345, format_="csv", client=client,
    x_cenozon_client_id=client_guid,
    x_cenozon_deployment_id=deployment_guid,
)

pdf = pd.read_csv(io.BytesIO(resp.content))
spark_df = spark.createDataFrame(pdf)
display(spark_df)
```

Notes for Databricks:
- For huge outputs, use the streaming example to write to DBFS (e.g., `/dbfs/tmp/report.csv`) and then `spark.read.csv`.
- If your environment uses HTTP proxies, pass `httpx_args={"proxies": "http://proxy:port"}` to the client.

## Service Health Check
```python
from cenozon_pirm_client.api.cenozon_pirm_data_gateway_service import get as get_root

alive = get_root.sync(
    client=client,
    x_cenozon_client_id="<client-guid>",
    x_cenozon_deployment_id="<deployment-guid>",
)
# returns "alive" on success
```

## Errors and Troubleshooting
- 401 or 403: Check your token, header GUIDs, and that you have permission to access the deployment.
- 404: The report name/SID or group doesn’t exist for this deployment.
- 400: Unsupported `format` (only `json`, `csv`, `tsv`) or invalid formatting options.
- For data endpoints, inspect `resp.status_code` and `resp.content` (the parsed field is not used for data).
- Still stuck? Contact your Cenozon administrator.

## Advanced httpx customization
Pass `httpx_args` to the client to add logging hooks, proxies, timeouts, etc. You can also call `client.get_httpx_client()` or `client.get_async_httpx_client()` for direct access when needed.
