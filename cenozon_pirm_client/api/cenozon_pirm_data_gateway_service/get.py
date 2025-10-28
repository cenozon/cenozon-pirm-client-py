from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    x_cenozon_client_id: str | Unset = UNSET,
    x_cenozon_deployment_id: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(x_cenozon_client_id, Unset):
        headers["x-cenozon-client-id"] = x_cenozon_client_id

    if not isinstance(x_cenozon_deployment_id, Unset):
        headers["x-cenozon-deployment-id"] = x_cenozon_deployment_id

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/",
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> str | None:
    if response.status_code == 200:
        response_200 = response.text
        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[str]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    x_cenozon_client_id: str | Unset = UNSET,
    x_cenozon_deployment_id: str | Unset = UNSET,
) -> Response[str]:
    """
    Args:
        x_cenozon_client_id (str | Unset):
        x_cenozon_deployment_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[str]
    """

    kwargs = _get_kwargs(
        x_cenozon_client_id=x_cenozon_client_id,
        x_cenozon_deployment_id=x_cenozon_deployment_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    x_cenozon_client_id: str | Unset = UNSET,
    x_cenozon_deployment_id: str | Unset = UNSET,
) -> str | None:
    """
    Args:
        x_cenozon_client_id (str | Unset):
        x_cenozon_deployment_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        str
    """

    return sync_detailed(
        client=client,
        x_cenozon_client_id=x_cenozon_client_id,
        x_cenozon_deployment_id=x_cenozon_deployment_id,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    x_cenozon_client_id: str | Unset = UNSET,
    x_cenozon_deployment_id: str | Unset = UNSET,
) -> Response[str]:
    """
    Args:
        x_cenozon_client_id (str | Unset):
        x_cenozon_deployment_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[str]
    """

    kwargs = _get_kwargs(
        x_cenozon_client_id=x_cenozon_client_id,
        x_cenozon_deployment_id=x_cenozon_deployment_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    x_cenozon_client_id: str | Unset = UNSET,
    x_cenozon_deployment_id: str | Unset = UNSET,
) -> str | None:
    """
    Args:
        x_cenozon_client_id (str | Unset):
        x_cenozon_deployment_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        str
    """

    return (
        await asyncio_detailed(
            client=client,
            x_cenozon_client_id=x_cenozon_client_id,
            x_cenozon_deployment_id=x_cenozon_deployment_id,
        )
    ).parsed
