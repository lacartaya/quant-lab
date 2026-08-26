import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

ALPACA_PAPER_ORIGIN = "https://paper-api.alpaca.markets"
ALPACA_DATA_ORIGIN = "https://data.alpaca.markets"


class AlpacaConfigurationError(ValueError):
    """Raised when paper-only Alpaca configuration is absent or unsafe."""


@dataclass(frozen=True, slots=True)
class AlpacaPaperConfiguration:
    api_key: str
    api_secret: str
    paper_base_url: str = ALPACA_PAPER_ORIGIN
    market_data_base_url: str = ALPACA_DATA_ORIGIN
    market_data_feed: str = "iex"
    timeout_seconds: float = 10.0
    historical_max_retries: int = 2

    def __post_init__(self) -> None:
        if not self.api_key.strip() or not self.api_secret.strip():
            raise AlpacaConfigurationError(
                "Alpaca paper credentials are not configured"
            )
        _require_exact_origin(self.paper_base_url, ALPACA_PAPER_ORIGIN, "paper")
        _require_exact_origin(
            self.market_data_base_url, ALPACA_DATA_ORIGIN, "market data"
        )
        if self.market_data_feed.lower() != "iex":
            raise AlpacaConfigurationError("the supported Alpaca Basic feed is IEX")
        if self.timeout_seconds <= 0:
            raise AlpacaConfigurationError("Alpaca timeout must be positive")
        if self.historical_max_retries < 0 or self.historical_max_retries > 5:
            raise AlpacaConfigurationError("historical retries must be between 0 and 5")

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "AlpacaPaperConfiguration":
        values = os.environ if environment is None else environment
        return cls(
            api_key=values.get("ALPACA_PAPER_API_KEY", ""),
            api_secret=values.get("ALPACA_PAPER_API_SECRET", ""),
            paper_base_url=values.get("ALPACA_PAPER_BASE_URL", ALPACA_PAPER_ORIGIN),
            market_data_base_url=values.get(
                "ALPACA_MARKET_DATA_BASE_URL", ALPACA_DATA_ORIGIN
            ),
            market_data_feed=values.get("ALPACA_MARKET_DATA_FEED", "iex"),
        )

    def authentication_headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
        }


def _require_exact_origin(value: str, expected: str, label: str) -> None:
    parsed = urlparse(value)
    normalized = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""
    if (
        normalized != expected
        or parsed.path != ""
        or parsed.query
        or parsed.fragment
    ):
        raise AlpacaConfigurationError(
            f"Alpaca {label} URL must be exactly {expected}; "
            "live endpoints are forbidden"
        )
