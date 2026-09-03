"""Tests voor de CBS OData-client zonder netwerkverbinding."""

from unittest.mock import Mock

import pytest
import requests

from gemeente_data_platform.cbs_client import (
    CbsClient,
    CbsHttpError,
    CbsInvalidJsonError,
)


def make_client(response: Mock) -> tuple[CbsClient, requests.Session]:
    """Maak een client met een gemockte HTTP-sessie."""
    session = requests.Session()
    session.get = Mock(return_value=response)
    client = CbsClient(
        base_url="https://example.test/OData",
        dataset_code="03759ned",
        timeout=12.5,
        session=session,
    )
    return client, session


def test_get_table_info_returns_successful_json() -> None:
    """Een geldige response wordt als JSON teruggegeven."""
    response = Mock()
    response.json.return_value = {"Title": "Bevolking"}
    client, session = make_client(response)

    result = client.get_table_info()

    assert result == {"Title": "Bevolking"}
    assert session.headers["User-Agent"] == CbsClient.user_agent
    session.get.assert_called_once_with(
        "https://example.test/OData/03759ned/TableInfos", timeout=12.5
    )


def test_get_table_info_raises_clear_error_for_http_failure() -> None:
    """Een HTTP-fout wordt niet stilzwijgend genegeerd."""
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError("404 Client Error")
    client, _ = make_client(response)

    with pytest.raises(CbsHttpError, match="HTTP error"):
        client.get_table_info()


def test_get_table_info_raises_clear_error_for_invalid_json() -> None:
    """Ongeldige JSON wordt niet stilzwijgend genegeerd."""
    response = Mock()
    response.json.side_effect = ValueError("Invalid JSON")
    client, _ = make_client(response)

    with pytest.raises(CbsInvalidJsonError, match="invalid JSON"):
        client.get_table_info()
