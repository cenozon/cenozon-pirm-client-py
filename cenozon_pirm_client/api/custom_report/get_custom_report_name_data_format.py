from http import HTTPStatus
from typing import Any, cast

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.csv_string_quoting import CsvStringQuoting
from ...models.problem_details import ProblemDetails
from ...types import UNSET, Response, Unset


def _get_kwargs(
    report_name: str,
    format_: str,
    *,
    group_type: str | Unset = UNSET,
    group_sid: int | Unset = UNSET,
    delimiter: str | Unset = UNSET,
    quote: str | Unset = UNSET,
    escape: str | Unset = UNSET,
    quote_strings: CsvStringQuoting | Unset = UNSET,
    compress_keys: bool | Unset = UNSET,
    strip_identifiers: bool | Unset = UNSET,
    x_cenozon_client_id: str | Unset = UNSET,
    x_cenozon_deployment_id: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(x_cenozon_client_id, Unset):
        headers["x-cenozon-client-id"] = x_cenozon_client_id

    if not isinstance(x_cenozon_deployment_id, Unset):
        headers["x-cenozon-deployment-id"] = x_cenozon_deployment_id

    params: dict[str, Any] = {}

    params["groupType"] = group_type

    params["groupSid"] = group_sid

    params["delimiter"] = delimiter

    params["quote"] = quote

    params["escape"] = escape

    json_quote_strings: int | Unset = UNSET
    if not isinstance(quote_strings, Unset):
        json_quote_strings = quote_strings.value

    params["quoteStrings"] = json_quote_strings

    params["compressKeys"] = compress_keys

    params["stripIdentifiers"] = strip_identifiers

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/custom/{report_name}/data/{format_}",
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Any | ProblemDetails | None:
    if response.status_code == 200:
        response_200 = cast(Any, None)
        return response_200

    if response.status_code == 400:
        response_400 = ProblemDetails.from_dict(response.json())

        return response_400

    if response.status_code == 401:
        response_401 = ProblemDetails.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ProblemDetails.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ProblemDetails.from_dict(response.json())

        return response_404

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Any | ProblemDetails]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    report_name: str,
    format_: str,
    *,
    client: AuthenticatedClient,
    group_type: str | Unset = UNSET,
    group_sid: int | Unset = UNSET,
    delimiter: str | Unset = UNSET,
    quote: str | Unset = UNSET,
    escape: str | Unset = UNSET,
    quote_strings: CsvStringQuoting | Unset = UNSET,
    compress_keys: bool | Unset = UNSET,
    strip_identifiers: bool | Unset = UNSET,
    x_cenozon_client_id: str | Unset = UNSET,
    x_cenozon_deployment_id: str | Unset = UNSET,
) -> Response[Any | ProblemDetails]:
    """Retrieves the data for the specified custom report.

    Args:
        report_name (str):
        format_ (str):
        group_type (str | Unset):
        group_sid (int | Unset):
        delimiter (str | Unset):
        quote (str | Unset):
        escape (str | Unset):
        quote_strings (CsvStringQuoting | Unset):
        compress_keys (bool | Unset):
        strip_identifiers (bool | Unset):
        x_cenozon_client_id (str | Unset):
        x_cenozon_deployment_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ProblemDetails]
    """

    kwargs = _get_kwargs(
        report_name=report_name,
        format_=format_,
        group_type=group_type,
        group_sid=group_sid,
        delimiter=delimiter,
        quote=quote,
        escape=escape,
        quote_strings=quote_strings,
        compress_keys=compress_keys,
        strip_identifiers=strip_identifiers,
        x_cenozon_client_id=x_cenozon_client_id,
        x_cenozon_deployment_id=x_cenozon_deployment_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    report_name: str,
    format_: str,
    *,
    client: AuthenticatedClient,
    group_type: str | Unset = UNSET,
    group_sid: int | Unset = UNSET,
    delimiter: str | Unset = UNSET,
    quote: str | Unset = UNSET,
    escape: str | Unset = UNSET,
    quote_strings: CsvStringQuoting | Unset = UNSET,
    compress_keys: bool | Unset = UNSET,
    strip_identifiers: bool | Unset = UNSET,
    x_cenozon_client_id: str | Unset = UNSET,
    x_cenozon_deployment_id: str | Unset = UNSET,
) -> Any | ProblemDetails | None:
    """Retrieves the data for the specified custom report.

    Args:
        report_name (str):
        format_ (str):
        group_type (str | Unset):
        group_sid (int | Unset):
        delimiter (str | Unset):
        quote (str | Unset):
        escape (str | Unset):
        quote_strings (CsvStringQuoting | Unset):
        compress_keys (bool | Unset):
        strip_identifiers (bool | Unset):
        x_cenozon_client_id (str | Unset):
        x_cenozon_deployment_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ProblemDetails
    """

    return sync_detailed(
        report_name=report_name,
        format_=format_,
        client=client,
        group_type=group_type,
        group_sid=group_sid,
        delimiter=delimiter,
        quote=quote,
        escape=escape,
        quote_strings=quote_strings,
        compress_keys=compress_keys,
        strip_identifiers=strip_identifiers,
        x_cenozon_client_id=x_cenozon_client_id,
        x_cenozon_deployment_id=x_cenozon_deployment_id,
    ).parsed


async def asyncio_detailed(
    report_name: str,
    format_: str,
    *,
    client: AuthenticatedClient,
    group_type: str | Unset = UNSET,
    group_sid: int | Unset = UNSET,
    delimiter: str | Unset = UNSET,
    quote: str | Unset = UNSET,
    escape: str | Unset = UNSET,
    quote_strings: CsvStringQuoting | Unset = UNSET,
    compress_keys: bool | Unset = UNSET,
    strip_identifiers: bool | Unset = UNSET,
    x_cenozon_client_id: str | Unset = UNSET,
    x_cenozon_deployment_id: str | Unset = UNSET,
) -> Response[Any | ProblemDetails]:
    """Retrieves the data for the specified custom report.

    Args:
        report_name (str):
        format_ (str):
        group_type (str | Unset):
        group_sid (int | Unset):
        delimiter (str | Unset):
        quote (str | Unset):
        escape (str | Unset):
        quote_strings (CsvStringQuoting | Unset):
        compress_keys (bool | Unset):
        strip_identifiers (bool | Unset):
        x_cenozon_client_id (str | Unset):
        x_cenozon_deployment_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ProblemDetails]
    """

    kwargs = _get_kwargs(
        report_name=report_name,
        format_=format_,
        group_type=group_type,
        group_sid=group_sid,
        delimiter=delimiter,
        quote=quote,
        escape=escape,
        quote_strings=quote_strings,
        compress_keys=compress_keys,
        strip_identifiers=strip_identifiers,
        x_cenozon_client_id=x_cenozon_client_id,
        x_cenozon_deployment_id=x_cenozon_deployment_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    report_name: str,
    format_: str,
    *,
    client: AuthenticatedClient,
    group_type: str | Unset = UNSET,
    group_sid: int | Unset = UNSET,
    delimiter: str | Unset = UNSET,
    quote: str | Unset = UNSET,
    escape: str | Unset = UNSET,
    quote_strings: CsvStringQuoting | Unset = UNSET,
    compress_keys: bool | Unset = UNSET,
    strip_identifiers: bool | Unset = UNSET,
    x_cenozon_client_id: str | Unset = UNSET,
    x_cenozon_deployment_id: str | Unset = UNSET,
) -> Any | ProblemDetails | None:
    """Retrieves the data for the specified custom report.

    Args:
        report_name (str):
        format_ (str):
        group_type (str | Unset):
        group_sid (int | Unset):
        delimiter (str | Unset):
        quote (str | Unset):
        escape (str | Unset):
        quote_strings (CsvStringQuoting | Unset):
        compress_keys (bool | Unset):
        strip_identifiers (bool | Unset):
        x_cenozon_client_id (str | Unset):
        x_cenozon_deployment_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ProblemDetails
    """

    return (
        await asyncio_detailed(
            report_name=report_name,
            format_=format_,
            client=client,
            group_type=group_type,
            group_sid=group_sid,
            delimiter=delimiter,
            quote=quote,
            escape=escape,
            quote_strings=quote_strings,
            compress_keys=compress_keys,
            strip_identifiers=strip_identifiers,
            x_cenozon_client_id=x_cenozon_client_id,
            x_cenozon_deployment_id=x_cenozon_deployment_id,
        )
    ).parsed
