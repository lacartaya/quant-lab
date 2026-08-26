import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

import httpx

from infra.alpaca.configuration import AlpacaPaperConfiguration


class AlpacaAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str, request_id: str | None = None):
        self.status_code = status_code
        self.request_id = request_id
        super().__init__(message)


@dataclass(slots=True)
class AlpacaHTTPClient:
    configuration: AlpacaPaperConfiguration
    client: httpx.Client
    sleep: Callable[[float], None] = time.sleep

    @classmethod
    def create(cls, configuration: AlpacaPaperConfiguration) -> "AlpacaHTTPClient":
        return cls(
            configuration,
            httpx.Client(
                headers=configuration.authentication_headers(),
                timeout=configuration.timeout_seconds,
            ),
        )

    def market_data_get(
        self, path: str, params: Mapping[str, object]
    ) -> dict[str, Any]:
        return self._get(self.configuration.market_data_base_url, path, params, True)

    def paper_get(
        self, path: str, params: Mapping[str, object] | None = None
    ) -> object:
        return self._request(
            "GET", self.configuration.paper_base_url, path, params=params
        )

    def paper_post(self, path: str, payload: Mapping[str, object]) -> object:
        # Trading writes are deliberately never retried here.
        return self._request(
            "POST", self.configuration.paper_base_url, path, json=payload
        )

    def paper_delete(
        self, path: str, params: Mapping[str, object] | None = None
    ) -> object:
        # A close-position write is deliberately never retried here.
        return self._request(
            "DELETE", self.configuration.paper_base_url, path, params=params
        )

    def _get(
        self,
        base_url: str,
        path: str,
        params: Mapping[str, object],
        retry: bool,
    ) -> dict[str, Any]:
        attempts = self.configuration.historical_max_retries + 1 if retry else 1
        for attempt in range(attempts):
            try:
                value = self._request("GET", base_url, path, params=params)
                if not isinstance(value, dict):
                    raise AlpacaAPIError(502, "Alpaca returned an invalid object")
                return value
            except AlpacaAPIError as error:
                transient = error.status_code == 429 or error.status_code >= 500
                if not transient or attempt + 1 == attempts:
                    raise
                self.sleep(float(2**attempt))
        raise AssertionError("unreachable")

    def _request(
        self,
        method: str,
        base_url: str,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
        json: Mapping[str, object] | None = None,
    ) -> object:
        try:
            response = self.client.request(
                method,
                f"{base_url}{path}",
                params=cast(Any, params),
                json=json,
            )
        except httpx.TimeoutException as error:
            raise AlpacaAPIError(504, "Alpaca request timed out") from error
        except httpx.HTTPError as error:
            raise AlpacaAPIError(502, "Alpaca network request failed") from error
        if response.is_success:
            if response.status_code == 204 or not response.content:
                return {}
            return response.json()
        request_id = response.headers.get("X-Request-ID")
        message = _redact_secrets(
            _safe_error_message(response),
            self.configuration.api_key,
            self.configuration.api_secret,
        )
        raise AlpacaAPIError(response.status_code, message, request_id)


def _safe_error_message(response: httpx.Response) -> str:
    labels = {
        401: "Alpaca paper credentials are invalid",
        403: "Alpaca denied the paper/feed request",
        404: "Alpaca resource was not found",
        429: "Alpaca rate limit exceeded",
    }
    if response.status_code in labels:
        return labels[response.status_code]
    try:
        payload = response.json()
    except ValueError:
        return f"Alpaca request failed with status {response.status_code}"
    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str):
            return message
    return f"Alpaca request failed with status {response.status_code}"


def _redact_secrets(message: str, *secrets: str) -> str:
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message
