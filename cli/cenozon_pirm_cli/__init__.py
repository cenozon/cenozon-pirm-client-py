"""Command-line interface for the Cenozon PIRM Data Gateway.

Installed as the ``pirm-dgw`` console script. Wraps the async
:class:`cenozon_pirm_client.PirmClient`, so auth and env headers behave
identically to the Python API. ``asyncio.run`` is used internally; users
of the CLI don't need to know about async at all.

Examples::

    pirm-dgw ping
    pirm-dgw list custom
    pirm-dgw list asset-manager --group my-group
    pirm-dgw fetch custom "Master Pipeline Modified" -f csv -o out.csv
    pirm-dgw fetch asset-manager 12345 -f xlsx -o out.xlsx
    pirm-dgw schema custom ili
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import os
import sys
import threading
import time
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from cenozon_pirm_client.client import ENVIRONMENT_TYPE_ENV_VAR
from cenozon_pirm_client.pirm import (
    BASE_URL_ENV_VAR,
    CLIENT_ID_ENV_VAR,
    DEFAULT_BASE_URL,
    DEPLOYMENT_ID_ENV_VAR,
    PirmClient,
    PirmError,
    PirmHTTPError,
    ReportFormat,
    TOKEN_ENV_VAR,
)

# ---------------------------------------------------------------------------
# pretty printing


def _use_color(stream: Any) -> bool:
    return stream.isatty() and os.getenv("NO_COLOR") is None and not os.getenv("CENOZON_NO_COLOR")


class _Style:
    """ANSI style helper that becomes a no-op when the stream isn't a tty."""

    def __init__(self, stream: Any = sys.stdout) -> None:
        self.enabled = _use_color(stream)

    def _wrap(self, codes: str, text: str) -> str:
        if not self.enabled:
            return text
        return f"\x1b[{codes}m{text}\x1b[0m"

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)


def _print_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    *,
    stream: Any = sys.stdout,
) -> None:
    if not _use_color(stream):
        print("\t".join(headers), file=stream)
        for row in rows:
            print("\t".join("" if cell is None else str(cell) for cell in row), file=stream)
        return

    string_rows = [["" if cell is None else str(cell) for cell in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in string_rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))

    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    style = _Style(stream)
    print(style.bold(style.cyan(fmt.format(*headers))), file=stream)
    print(style.cyan("  ".join("-" * w for w in widths)), file=stream)
    for idx, row in enumerate(string_rows):
        line = fmt.format(*row)
        if idx % 2 == 1:
            line = style.dim(line)
        print(line, file=stream)


# ---------------------------------------------------------------------------
# progress indicator (TTY only; silent otherwise)


def _format_bytes(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size) < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


class _Spinner:
    FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(self, message: str = "Downloading") -> None:
        self._message = message
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._downloaded = 0
        self._enabled = sys.stderr.isatty() and not os.getenv("CENOZON_NO_PROGRESS")

    def _spin(self) -> None:
        frames = itertools.cycle(self.FRAMES)
        while not self._stop.is_set():
            frame = next(frames)
            line = f"\r{frame} {self._message}... {_format_bytes(self._downloaded)}"
            sys.stderr.write(f"{line:<60}")
            sys.stderr.flush()
            time.sleep(0.1)

    def update(self, downloaded: int) -> None:
        # Called from the asyncio thread once per network chunk in write_to().
        # ``_downloaded`` is a plain int — assignment and read are each a
        # single bytecode op, atomic under CPython's GIL, so no Lock is
        # needed for the spinner thread to read it.
        self._downloaded = downloaded

    def start(self) -> None:
        if self._enabled:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._enabled:
            sys.stderr.write("\r" + " " * 60 + "\r")
            sys.stderr.flush()


# ---------------------------------------------------------------------------
# .env loader (tiny, no python-dotenv dep)


def _load_env_file(path: str | os.PathLike[str]) -> None:
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        # Skip obviously-invalid keys: empty after strip, contain whitespace,
        # or aren't valid POSIX-shell-style identifiers. Don't try to be too
        # clever — env files in the wild are messy, but a key with internal
        # whitespace is almost certainly a malformed line we shouldn't trust.
        if not key or any(c.isspace() for c in key):
            continue
        value = value.strip()
        # Strip a single pair of matching surrounding quotes (single or
        # double) — keeps base64 secrets containing '=' intact while still
        # letting users quote values with leading/trailing whitespace.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value


# ---------------------------------------------------------------------------
# client construction


def _resolve_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    _load_env_file(args.env_file)

    token = args.token or os.environ.get(TOKEN_ENV_VAR) or os.environ.get("CENOZON_PAT")
    client_id = (
        args.client_id
        or os.environ.get(CLIENT_ID_ENV_VAR)
        or os.environ.get("CLIENT_GUID")
    )
    deployment_id = (
        args.deployment_id
        or os.environ.get(DEPLOYMENT_ID_ENV_VAR)
        or os.environ.get("DEPLOYMENT_GUID")
    )
    base_url = args.base_url or os.environ.get(BASE_URL_ENV_VAR) or DEFAULT_BASE_URL
    env_type = (
        args.environment_type
        if args.environment_type is not None
        else os.environ.get(ENVIRONMENT_TYPE_ENV_VAR) or os.environ.get("ENVIRONMENT_TYPE")
    )

    missing = [
        name
        for name, value in (
            ("token (--token / CENOZON_API_TOKEN)", token),
            ("client id (--client-id / CENOZON_CLIENT_ID)", client_id),
            ("deployment id (--deployment-id / CENOZON_DEPLOYMENT_ID)", deployment_id),
        )
        if not value
    ]
    if missing:
        raise PirmError("Missing required credentials: " + ", ".join(missing))

    kwargs: dict[str, Any] = {
        "token": token,
        "client_id": client_id,
        "deployment_id": deployment_id,
        "base_url": base_url,
        "auth_prefix": args.auth_prefix,
    }
    if env_type is not None:
        kwargs["environment_type"] = env_type
    return kwargs


def _build_data_params(args: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if args.group_type:
        params["group_type"] = args.group_type
    if args.group_sid is not None:
        params["group_sid"] = args.group_sid
    if args.strip_identifiers:
        params["strip_identifiers"] = True
    if args.compress_keys:
        params["compress_keys"] = True
    if args.delimiter:
        params["delimiter"] = args.delimiter
    if args.quote:
        params["quote"] = args.quote
    if args.escape:
        params["escape"] = args.escape
    return params


def _resolve_format(args: argparse.Namespace, default: str = ReportFormat.CSV) -> str:
    fmt = (args.format or default).lower()
    if fmt not in ReportFormat.ALL:
        print(
            f"warning: unknown format {fmt!r} (known: {', '.join(ReportFormat.ALL)})",
            file=sys.stderr,
        )
    return fmt


def _default_output_path(report_name: str, fmt: str) -> Path:
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in report_name).strip("-")
    return Path(f"{safe or 'report'}.{fmt}")


# ---------------------------------------------------------------------------
# command handlers (all async)


async def cmd_ping(args: argparse.Namespace) -> int:
    async with PirmClient(**_resolve_kwargs(args)) as pirm:
        print(await pirm.status())
    return 0


async def cmd_whoami(args: argparse.Namespace) -> int:
    async with PirmClient(**_resolve_kwargs(args)) as pirm:
        style = _Style(sys.stdout)
        print(style.bold("Cenozon PIRM client"))
        print(f"  base url    : {pirm.raw._base_url}")  # type: ignore[attr-defined]
        print(f"  client id   : {pirm.client_id}")
        print(f"  deployment  : {pirm.deployment_id}")
        print(f"  environment : {pirm.environment_type or '(suppressed)'}")
    return 0


async def cmd_list_custom(args: argparse.Namespace) -> int:
    async with PirmClient(**_resolve_kwargs(args)) as pirm:
        reports = await pirm.custom_reports()
    rows = [
        (r.name, "yes" if r.supports_hierarchy_columns else "", r.data_uri or "")
        for r in reports
    ]
    _print_table(("Report", "Hierarchy", "Data URI"), rows)
    return 0


async def cmd_list_asset_manager(args: argparse.Namespace) -> int:
    async with PirmClient(**_resolve_kwargs(args)) as pirm:
        reports = await pirm.asset_manager_reports(group=args.group)
    rows = [
        (
            r.report_sid if r.report_sid is not None else "",
            r.group_name or "",
            r.name,
            "yes" if r.supports_hierarchy_columns else "",
        )
        for r in reports
    ]
    _print_table(("SID", "Group", "Report", "Hierarchy"), rows)
    return 0


async def cmd_schema_custom(args: argparse.Namespace) -> int:
    async with PirmClient(**_resolve_kwargs(args)) as pirm:
        report = await pirm.custom_report(args.report)
        schema = await report.schema(strip_identifiers=args.strip_identifiers)
    _print_schema(schema)
    return 0


async def cmd_schema_asset_manager(args: argparse.Namespace) -> int:
    async with PirmClient(**_resolve_kwargs(args)) as pirm:
        report = await _resolve_asset_manager(pirm, args.report, group=args.group)
        schema = await report.schema(strip_identifiers=args.strip_identifiers)
    _print_schema(schema)
    return 0


async def cmd_fetch_custom(args: argparse.Namespace) -> int:
    fmt = _resolve_format(args)
    async with PirmClient(**_resolve_kwargs(args)) as pirm:
        report = await pirm.custom_report(args.report)
        target = Path(args.output) if args.output else _default_output_path(report.name, fmt)
        await _stream_report(report, target=target, fmt=fmt, params=_build_data_params(args))
    return 0


async def cmd_fetch_asset_manager(args: argparse.Namespace) -> int:
    fmt = _resolve_format(args)
    async with PirmClient(**_resolve_kwargs(args)) as pirm:
        report = await _resolve_asset_manager(pirm, args.report, group=args.group)
        target = Path(args.output) if args.output else _default_output_path(report.name, fmt)
        await _stream_report(report, target=target, fmt=fmt, params=_build_data_params(args))
    return 0


async def _resolve_asset_manager(
    pirm: PirmClient, identifier: str, *, group: str | None
) -> Any:
    if identifier.isdigit():
        return pirm.asset_manager_report_by_sid(int(identifier))
    return await pirm.asset_manager_report(identifier, group=group)


def _print_schema(schema: Any) -> None:
    cols = schema.columns or []
    rows = [
        (c.index, c.name, c.type_, "yes" if c.is_nullable else "")
        for c in cols
    ]
    _print_table(("Index", "Name", "Type", "Nullable"), rows)


async def _stream_report(report: Any, *, target: Path, fmt: str, params: Mapping[str, Any]) -> None:
    spinner = _Spinner(f"Downloading {report.name}")
    spinner.start()
    try:
        written = await report.write_to(
            target,
            format=fmt,
            on_progress=spinner.update,
            **params,
        )
    finally:
        spinner.stop()
    print(f"wrote {_format_bytes(written)} to {target}", file=sys.stderr)


# ---------------------------------------------------------------------------
# parser


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to a .env file (default: ./.env).",
    )
    parser.add_argument(
        "--base-url",
        help=f"Override base URL (env var: {BASE_URL_ENV_VAR}).",
    )
    parser.add_argument(
        "--token",
        help=f"Override API token (env var: {TOKEN_ENV_VAR}).",
    )
    parser.add_argument(
        "--client-id",
        help=f"Override x-cenozon-client-id (env var: {CLIENT_ID_ENV_VAR}).",
    )
    parser.add_argument(
        "--deployment-id",
        help=f"Override x-cenozon-deployment-id (env var: {DEPLOYMENT_ID_ENV_VAR}).",
    )
    parser.add_argument(
        "--environment-type",
        help=(
            "Override x-cenozon-environment (default: production; env var: "
            f"{ENVIRONMENT_TYPE_ENV_VAR}). Pass empty string to suppress."
        ),
    )
    parser.add_argument(
        "--auth-prefix",
        default="Token",
        help="Authorization scheme prefix (default: Token).",
    )


def _add_data_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-f",
        "--format",
        default="csv",
        help="Output format: " + ", ".join(ReportFormat.ALL),
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file (defaults to <report-slug>.<format>).",
    )
    parser.add_argument("--group-type", help="Hierarchy filter groupType.")
    parser.add_argument("--group-sid", type=int, help="Hierarchy filter groupSid.")
    parser.add_argument(
        "--strip-identifiers",
        action="store_true",
        help="Drop internal *_sid identifier columns.",
    )
    parser.add_argument(
        "--compress-keys",
        action="store_true",
        help="JSON only — emit compact DataTable-style keys.",
    )
    parser.add_argument("--delimiter", help="CSV delimiter (default ,)")
    parser.add_argument("--quote", help='CSV quote (default ")')
    parser.add_argument("--escape", help="CSV escape (default #)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pirm-dgw",
        description="CLI for the Cenozon PIRM Data Gateway — list, inspect, and download reports.",
    )
    _add_common_args(parser)
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p_ping = sub.add_parser("ping", help="Check gateway connectivity.")
    p_ping.set_defaults(handler=cmd_ping)

    p_whoami = sub.add_parser("whoami", help="Show the resolved client config.")
    p_whoami.set_defaults(handler=cmd_whoami)

    p_list = sub.add_parser("list", help="List reports.")
    list_sub = p_list.add_subparsers(dest="kind", required=True, metavar="KIND")

    p_list_custom = list_sub.add_parser("custom", help="List custom reports.")
    p_list_custom.set_defaults(handler=cmd_list_custom)

    p_list_am = list_sub.add_parser("asset-manager", help="List Asset Manager reports.")
    p_list_am.add_argument("--group", help="Restrict to a single group.")
    p_list_am.set_defaults(handler=cmd_list_asset_manager)

    p_fetch = sub.add_parser("fetch", help="Download a report's data.")
    fetch_sub = p_fetch.add_subparsers(dest="kind", required=True, metavar="KIND")

    p_fetch_custom = fetch_sub.add_parser("custom", help="Download a custom report.")
    p_fetch_custom.add_argument("report", help="Report display name (case-insensitive).")
    _add_data_args(p_fetch_custom)
    p_fetch_custom.set_defaults(handler=cmd_fetch_custom)

    p_fetch_am = fetch_sub.add_parser(
        "asset-manager",
        help="Download an Asset Manager report (by name or SID).",
    )
    p_fetch_am.add_argument(
        "report",
        help="Display name or numeric SID. SIDs are detected automatically.",
    )
    p_fetch_am.add_argument("--group", help="Restrict to a single group when looking up by name.")
    _add_data_args(p_fetch_am)
    p_fetch_am.set_defaults(handler=cmd_fetch_asset_manager)

    p_schema = sub.add_parser("schema", help="Print a report's column schema.")
    schema_sub = p_schema.add_subparsers(dest="kind", required=True, metavar="KIND")

    p_schema_custom = schema_sub.add_parser("custom", help="Custom report schema.")
    p_schema_custom.add_argument("report", help="Report display name.")
    p_schema_custom.add_argument("--strip-identifiers", action="store_true")
    p_schema_custom.set_defaults(handler=cmd_schema_custom)

    p_schema_am = schema_sub.add_parser("asset-manager", help="Asset Manager schema.")
    p_schema_am.add_argument("report", help="Display name or numeric SID.")
    p_schema_am.add_argument("--group", help="Restrict to a single group when looking up by name.")
    p_schema_am.add_argument("--strip-identifiers", action="store_true")
    p_schema_am.set_defaults(handler=cmd_schema_asset_manager)

    return parser


def run_cli(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return asyncio.run(handler(args))
    except PirmHTTPError as exc:
        style = _Style(sys.stderr)
        # Body access can raise if the response was never fully read (e.g.
        # a streaming response that errored before aread() ran). Swallow
        # that so we always emit a useful one-liner to stderr.
        try:
            body = exc.response.text[:500]
        except Exception:
            body = ""
        print(
            style.red(f"HTTP {exc.response.status_code}") + f" — {body}",
            file=sys.stderr,
        )
        return 2
    except PirmError as exc:
        style = _Style(sys.stderr)
        print(style.red("error:") + f" {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("aborted", file=sys.stderr)
        return 130


def main(argv: Iterable[str] | None = None) -> None:
    raise SystemExit(run_cli(argv))


if __name__ == "__main__":
    main()
