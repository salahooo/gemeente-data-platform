"""Tests voor de CBS OData-client zonder netwerkverbinding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import requests

from gemeente_data_platform.cbs_client import (
    CbsClient,
    CbsCollectionError,
    CbsHttpError,
    CbsInvalidJsonError,
    CbsPaginationError,
)


@dataclass
class FakeResponse:
    """Kleine HTTP-responsefixture voor clienttests."""

    payload: dict[str, Any] | None = None
    status_code: int = 200
    json_error: ValueError | None = None

    def raise_for_status(self) -> None:
        """Simuleer permanente HTTP-fouten."""
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} HTTP error")

    def json(self) -> dict[str, Any]:
        """Geef de fixturepayload terug of gooi een JSON-fout."""
        if self.json_error is not None:
            raise self.json_error
        assert self.payload is not None
        return self.payload


class FakeSession:
    """Sessie die vooraf bepaalde responses of exceptions teruggeeft."""

    def __init__(self, outcomes: list[FakeResponse | Exception]) -> None:
        self.headers: dict[str, str] = {}
        self.outcomes = outcomes
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        """Registreer de call en geef de volgende fixture-uitkomst terug."""
        self.calls.append((url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_client(
    outcomes: list[FakeResponse | Exception], **kwargs: Any
) -> tuple[CbsClient, FakeSession]:
    """Maak een client met een gemockte HTTP-sessie."""
    session = FakeSession(outcomes)
    client = CbsClient(
        base_url="https://example.test/OData",
        dataset_code="03759ned",
        timeout=12.5,
        session=session,  # type: ignore[arg-type]
        retry_backoff_seconds=0,
        **kwargs,
    )
    return client, session


def test_get_table_info_returns_successful_json() -> None:
    """Een geldige response wordt als JSON teruggegeven."""
    client, session = make_client([FakeResponse({"Title": "Bevolking"})])

    result = client.get_table_info()

    assert result == {"Title": "Bevolking"}
    assert session.headers["User-Agent"] == CbsClient.user_agent
    assert session.calls == [
        ("https://example.test/OData/03759ned/TableInfos", {"timeout": 12.5})
    ]


def test_get_json_passes_odata_query_parameters() -> None:
    """OData-queryparameters worden ongewijzigd aan requests doorgegeven."""
    client, session = make_client([FakeResponse({"value": []})])
    params = {"$filter": "Perioden ge '2020JJ00'", "$select": "RegioS"}

    client.get_json("TypedDataSet", params=params)

    assert session.calls[0][1] == {"timeout": 12.5, "params": params}


def test_get_collection_handles_one_page_without_next_link() -> None:
    """Een collectie zonder next-link eindigt na één pagina."""
    client, _ = make_client([FakeResponse({"value": [{"Key": "A"}]})])

    result = client.get_collection("Geslacht")

    assert result.page_count == 1
    assert result.records == [{"Key": "A"}]


def test_get_collection_handles_multiple_pages() -> None:
    """Records uit meerdere pagina's worden zonder mutatie samengevoegd."""
    client, session = make_client(
        [
            FakeResponse(
                {
                    "value": [{"Key": "A"}],
                    "odata.nextLink": "https://example.test/page-2",
                }
            ),
            FakeResponse({"value": [{"Key": "B"}]}),
        ]
    )

    result = client.get_collection("Geslacht")

    assert result.page_count == 2
    assert result.records == [{"Key": "A"}, {"Key": "B"}]
    assert session.calls[1] == ("https://example.test/page-2", {"timeout": 12.5})


@pytest.mark.parametrize("next_link_key", ["odata.nextLink", "@odata.nextLink"])
def test_get_collection_supports_both_next_link_variants(next_link_key: str) -> None:
    """Beide OData-varianten voor de volgende pagina worden ondersteund."""
    client, _ = make_client(
        [
            FakeResponse({"value": [{"Key": "A"}], next_link_key: "/page-2"}),
            FakeResponse({"value": [{"Key": "B"}]}),
        ]
    )

    assert client.get_collection("Geslacht").records == [{"Key": "A"}, {"Key": "B"}]


def test_get_collection_rejects_repeated_next_link() -> None:
    """Een herhaalde next-link voorkomt oneindige paginering."""
    repeated_link = "https://example.test/page-2"
    client, _ = make_client(
        [
            FakeResponse({"value": [], "odata.nextLink": repeated_link}),
            FakeResponse({"value": [], "odata.nextLink": repeated_link}),
        ]
    )

    with pytest.raises(CbsPaginationError, match="repeated"):
        client.get_collection("Geslacht")


def test_get_collection_rejects_maximum_page_limit() -> None:
    """De ingestelde paginalimiet stopt onbegrensde collecties."""
    client, _ = make_client(
        [FakeResponse({"value": [], "odata.nextLink": "https://example.test/page-2"})]
    )

    with pytest.raises(CbsPaginationError, match="limit of 1"):
        client.get_collection("Geslacht", max_pages=1)


def test_get_json_retries_temporary_server_error() -> None:
    """Een tijdelijke serverfout wordt gevolgd door een succesvolle retry."""
    client, session = make_client(
        [FakeResponse({"value": []}, status_code=503), FakeResponse({"value": []})]
    )

    assert client.get_json("Geslacht") == {"value": []}
    assert len(session.calls) == 2


def test_get_json_raises_clear_error_for_permanent_http_failure() -> None:
    """Een permanente HTTP-fout wordt niet stilzwijgend genegeerd."""
    client, _ = make_client([FakeResponse(status_code=404)])

    with pytest.raises(CbsHttpError, match="HTTP error"):
        client.get_json("Geslacht")


def test_get_json_raises_clear_error_for_invalid_json() -> None:
    """Ongeldige JSON wordt niet stilzwijgend genegeerd."""
    client, _ = make_client([FakeResponse(json_error=ValueError("Invalid JSON"))])

    with pytest.raises(CbsInvalidJsonError, match="invalid JSON"):
        client.get_json("Geslacht")


def test_get_collection_rejects_missing_value_list() -> None:
    """Een collectie zonder `value`-lijst breekt het datacontract."""
    client, _ = make_client([FakeResponse({"unexpected": []})])

    with pytest.raises(CbsCollectionError, match="list in 'value'"):
        client.get_collection("Geslacht")
