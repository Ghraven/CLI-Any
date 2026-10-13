"""HTTP transport for the real Clockify core and Reports APIs."""

from __future__ import annotations

import math
import os
from typing import Any
from urllib.parse import quote, urlsplit

import requests

CORE_URL = "https://api.clockify.me/api/v1"
REPORTS_URL = "https://reports.api.clockify.me/v1"


class ClockifyError(Exception):
    """An actionable API or configuration failure."""

    def __init__(
        self, message: str, *, status: int | None = None, retry_after: str | None = None
    ):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"message": str(self)}
        if self.status is not None:
            result["status"] = self.status
        if self.retry_after is not None:
            result["retry_after"] = self.retry_after
        return result


def _base_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise ClockifyError("Invalid API URL.") from None
    local_http = parsed.scheme == "http" and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
    if (
        (parsed.scheme != "https" and not local_http)
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ClockifyError(
            "API URLs must use HTTPS (HTTP is allowed for loopback tests)."
        )
    return value.rstrip("/")


def path(*parts: str) -> str:
    """Encode each resource identifier as one URL segment."""
    if any(
        not isinstance(part, str) or not part or part in {".", ".."} for part in parts
    ):
        raise ClockifyError("Resource IDs must be nonempty path segments.")
    return "/".join(quote(part, safe="") for part in parts)


class ClockifyAPI:
    """A reusable HTTP session; mutations are never retried automatically."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        reports_url: str | None = None,
        timeout: float = 30.0,
    ):
        self.api_key = (
            api_key if api_key is not None else os.environ.get("CLOCKIFY_API_KEY", "")
        )
        self.base_url = _base_url(
            base_url or os.environ.get("CLOCKIFY_API_URL", CORE_URL)
        )
        self.reports_url = _base_url(
            reports_url or os.environ.get("CLOCKIFY_REPORTS_URL", REPORTS_URL)
        )
        if not math.isfinite(timeout) or timeout <= 0:
            raise ClockifyError("Request timeout must be positive.")
        self.timeout = timeout
        self.http = requests.Session()
        self._user_id: str | None = None

    def close(self) -> None:
        self.http.close()

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        reports: bool = False,
    ) -> Any:
        if not self.api_key:
            raise ClockifyError(
                "Set CLOCKIFY_API_KEY to an API key from Clockify profile settings."
            )
        base = self.reports_url if reports else self.base_url
        query = {
            key: str(value).lower() if isinstance(value, bool) else value
            for key, value in (params or {}).items()
            if value is not None
        }
        try:
            response = self.http.request(
                method,
                f"{base}/{endpoint}",
                headers={"X-Api-Key": self.api_key, "Accept": "application/json"},
                params=query,
                json=body,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.Timeout:
            raise ClockifyError(
                "Clockify request timed out. Check the remote state before retrying a write."
            ) from None
        except requests.RequestException:
            raise ClockifyError(
                "Could not connect to Clockify. Check the API URL and network connection."
            ) from None
        with response:
            if not 200 <= response.status_code < 300:
                message = f"Clockify returned HTTP {response.status_code}."
                try:
                    error = response.json()
                except ValueError:
                    error = None
                if isinstance(error, dict) and isinstance(error.get("message"), str):
                    message += " " + error["message"][:1000]
                message = message.replace(self.api_key, "[REDACTED]")
                raise ClockifyError(
                    message,
                    status=response.status_code,
                    retry_after=response.headers.get("Retry-After"),
                )
            if response.status_code == 204 or not response.content:
                return None
            try:
                return response.json()
            except ValueError:
                raise ClockifyError(
                    "Clockify returned an invalid JSON response."
                ) from None

    def current_user_id(self) -> str:
        if self._user_id is None:
            user = self.request("GET", "user")
            if (
                not isinstance(user, dict)
                or not isinstance(user.get("id"), str)
                or not user["id"]
            ):
                raise ClockifyError("Clockify user response has no user ID.")
            self._user_id = user["id"]
        return self._user_id

    def list_pages(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 50,
        all_pages: bool = False,
        max_pages: int = 1000,
    ) -> list[Any]:
        if page < 1 or page_size < 1 or max_pages < 1:
            raise ClockifyError("Pagination values must be positive.")
        items: list[Any] = []
        previous: list[Any] | None = None
        for offset in range(max_pages if all_pages else 1):
            batch = self.request(
                "GET",
                endpoint,
                params={
                    **(params or {}),
                    "page": page + offset,
                    "page-size": page_size,
                },
            )
            if not isinstance(batch, list):
                raise ClockifyError(
                    "Clockify returned a non-list response for a listing."
                )
            if batch and batch == previous:
                raise ClockifyError(
                    "Clockify repeated a page; refusing to return an incomplete listing."
                )
            items.extend(batch)
            if not all_pages or len(batch) < page_size:
                return items
            previous = batch
        raise ClockifyError(
            "Pagination limit reached; narrow the filters or increase --max-pages."
        )
