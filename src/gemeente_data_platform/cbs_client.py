"""Kleine client voor metadata uit de CBS OData API."""

from typing import Any

import requests

from gemeente_data_platform.config import Settings


class CbsApiError(RuntimeError):
    """Basisklasse voor fouten tijdens communicatie met de CBS API."""


class CbsNetworkError(CbsApiError):
    """De CBS API kon niet via het netwerk worden bereikt."""


class CbsHttpError(CbsApiError):
    """De CBS API antwoordde met een ongeldige HTTP-status."""


class CbsInvalidJsonError(CbsApiError):
    """De CBS API antwoordde niet met geldige JSON."""


class CbsClient:
    """Haal JSON-responses op uit één configureerbare CBS-dataset."""

    user_agent = "gemeente-data-platform/0.1.0 (metadata client)"

    def __init__(
        self,
        base_url: str,
        dataset_code: str,
        timeout: float,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.dataset_code = dataset_code
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {"Accept": "application/json", "User-Agent": self.user_agent}
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "CbsClient":
        """Maak een client op basis van applicatie-instellingen."""
        return cls(
            base_url=settings.cbs_base_url,
            dataset_code=settings.cbs_dataset_code,
            timeout=settings.cbs_request_timeout,
        )

    @property
    def dataset_url(self) -> str:
        """Geef de basis-URL van de ingestelde CBS-dataset terug."""
        return f"{self.base_url}/{self.dataset_code}"

    def get_json(self, endpoint: str) -> Any:
        """Haal één JSON-response op en vertaal technische fouten duidelijk."""
        url = f"{self.dataset_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            message = f"Network error while requesting CBS API endpoint {url}."
            raise CbsNetworkError(message) from exc

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            message = f"CBS API returned an HTTP error for endpoint {url}."
            raise CbsHttpError(message) from exc
        except requests.RequestException as exc:
            message = f"Request failed while validating CBS API endpoint {url}."
            raise CbsNetworkError(message) from exc

        try:
            return response.json()
        except ValueError as exc:
            message = f"CBS API returned invalid JSON for endpoint {url}."
            raise CbsInvalidJsonError(message) from exc

    def get_table_info(self) -> Any:
        """Haal de metadata van de ingestelde CBS-dataset op."""
        return self.get_json("TableInfos")
