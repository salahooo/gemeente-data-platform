"""Herbruikbare client voor de CBS OData API."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests

from gemeente_data_platform.config import Settings

logger = logging.getLogger(__name__)

TEMPORARY_STATUS_CODES = {429, 500, 502, 503, 504}


class CbsApiError(RuntimeError):
    """Basisklasse voor fouten tijdens communicatie met de CBS API."""


class CbsNetworkError(CbsApiError):
    """De CBS API kon niet via het netwerk worden bereikt."""


class CbsHttpError(CbsApiError):
    """De CBS API antwoordde met een ongeldige HTTP-status."""


class CbsInvalidJsonError(CbsApiError):
    """De CBS API antwoordde niet met geldige JSON."""


class CbsCollectionError(CbsApiError):
    """Een CBS-collectie voldoet niet aan het verwachte OData-contract."""


class CbsPaginationError(CbsApiError):
    """Paginering is ongeldig, herhaalt een link of overschrijdt een limiet."""


@dataclass(frozen=True)
class CollectionResult:
    """Ongemuteerde CBS-pagina's en de samengevoegde recordlijst."""

    pages: list[dict[str, Any]]
    records: list[dict[str, Any]]

    @property
    def page_count(self) -> int:
        """Geef het aantal opgehaalde API-pagina's terug."""
        return len(self.pages)


class CbsClient:
    """Haal JSON en gepagineerde collecties op uit één CBS-dataset."""

    user_agent = "gemeente-data-platform/0.1.0 (metadata client)"

    def __init__(
        self,
        base_url: str,
        dataset_code: str,
        timeout: float,
        session: requests.Session | None = None,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        max_pages: int = 100,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.dataset_code = dataset_code
        self.timeout = timeout
        self.session = session or requests.Session()
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.max_pages = max_pages
        self.sleep = sleep
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
            max_retries=settings.cbs_max_retries,
            retry_backoff_seconds=settings.cbs_retry_backoff_seconds,
            max_pages=settings.cbs_max_pages,
        )

    @property
    def dataset_url(self) -> str:
        """Geef de basis-URL van de ingestelde CBS-dataset terug."""
        return f"{self.base_url}/{self.dataset_code}"

    def get_json(
        self, endpoint: str, params: Mapping[str, str] | None = None
    ) -> dict[str, Any]:
        """Haal één JSON-response op en vertaal technische fouten duidelijk."""
        url = self._url_for(endpoint)

        for attempt in range(self.max_retries + 1):
            try:
                request_kwargs: dict[str, Any] = {"timeout": self.timeout}
                if params is not None:
                    request_kwargs["params"] = dict(params)
                response = self.session.get(url, **request_kwargs)
            except requests.RequestException as exc:
                if self._can_retry(attempt):
                    self._retry("network problem", attempt)
                    continue
                raise CbsNetworkError(f"CBS API could not be reached: {url}.") from exc

            status_code = getattr(response, "status_code", None)
            if isinstance(status_code, int) and status_code in TEMPORARY_STATUS_CODES:
                if self._can_retry(attempt):
                    self._retry(f"temporary HTTP status {status_code}", attempt)
                    continue

            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                raise CbsHttpError(
                    f"CBS API returned an HTTP error for endpoint {url}."
                ) from exc
            except requests.RequestException as exc:
                raise CbsNetworkError(
                    f"Request validation failed for CBS endpoint {url}."
                ) from exc

            try:
                payload = response.json()
            except ValueError as exc:
                raise CbsInvalidJsonError(
                    f"CBS API returned invalid JSON for endpoint {url}."
                ) from exc

            if not isinstance(payload, dict):
                raise CbsInvalidJsonError(
                    f"CBS API returned a JSON value instead of an object for {url}."
                )
            return payload

        raise CbsNetworkError(f"CBS API request retries were exhausted for {url}.")

    def get_table_info(self) -> dict[str, Any]:
        """Haal de metadata van de ingestelde CBS-dataset op."""
        return self.get_json("TableInfos")

    def get_collection(
        self,
        endpoint: str,
        params: Mapping[str, str] | None = None,
        max_pages: int | None = None,
    ) -> CollectionResult:
        """Haal een OData-collectie op, inclusief alle volgende pagina's."""
        page_limit = self.max_pages if max_pages is None else max_pages
        if page_limit < 1:
            raise CbsPaginationError("The maximum page limit must be at least one.")

        pages: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        next_endpoint = endpoint
        next_params = params
        seen_next_links: set[str] = set()

        while True:
            if len(pages) >= page_limit:
                raise CbsPaginationError(
                    "CBS pagination exceeded the configured limit of "
                    f"{page_limit} pages."
                )

            payload = self.get_json(next_endpoint, params=next_params)
            value = payload.get("value")
            if not isinstance(value, list):
                raise CbsCollectionError(
                    f"CBS collection {endpoint} does not contain a list in 'value'."
                )
            if not all(isinstance(record, dict) for record in value):
                raise CbsCollectionError(
                    f"CBS collection {endpoint} contains a non-object record."
                )

            pages.append(payload)
            records.extend(value)
            next_link = self._next_link(payload)
            if next_link is None:
                return CollectionResult(pages=pages, records=records)

            resolved_next_link = urljoin(f"{self.dataset_url}/", next_link)
            if resolved_next_link in seen_next_links:
                raise CbsPaginationError(
                    f"CBS pagination repeated a next-link for collection {endpoint}."
                )
            seen_next_links.add(resolved_next_link)
            next_endpoint = resolved_next_link
            next_params = None

    def _url_for(self, endpoint: str) -> str:
        """Maak een dataset-endpoint of behoud een absolute OData next-link."""
        if endpoint.startswith(("https://", "http://")):
            return endpoint
        return f"{self.dataset_url}/{endpoint.lstrip('/')}"

    def _can_retry(self, attempt: int) -> bool:
        """Bepaal of een volgende poging binnen de ingestelde grens valt."""
        return attempt < self.max_retries

    def _retry(self, reason: str, attempt: int) -> None:
        """Log een beperkte retry-melding en wacht volgens exponential backoff."""
        delay = self.retry_backoff_seconds * (2**attempt)
        logger.warning("CBS request retry: reason=%s attempt=%s", reason, attempt + 1)
        if delay > 0:
            self.sleep(delay)

    @staticmethod
    def _next_link(payload: Mapping[str, Any]) -> str | None:
        """Lees beide relevante OData-varianten voor de volgende pagina."""
        next_link = payload.get("odata.nextLink") or payload.get("@odata.nextLink")
        if next_link is None:
            return None
        if not isinstance(next_link, str) or not next_link:
            raise CbsPaginationError("CBS pagination contains an invalid next-link.")
        return next_link
