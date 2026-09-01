# mypy: disable-error-code="no-untyped-def,arg-type,var-annotated"

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from infra.alpaca import (
    AlpacaAPIError,
    AlpacaConfigurationError,
    AlpacaHistoricalMarketDataProvider,
    AlpacaHTTPClient,
    AlpacaLiveMarketDataProvider,
    AlpacaPaperBrokerAdapter,
    AlpacaPaperConfiguration,
)
from infra.market_data import LocalParquetDatasetStorage
from quant.application import (
    CreateDatasetSnapshot,
    ImportHistoricalDataset,
    LoadDatasetSnapshot,
)
from quant.domain import (
    AdjustmentPolicy,
    HistoricalDataRequest,
    PaperOrderSide,
    PaperOrderType,
    PaperTimeInForce,
    SubmitAlpacaPaperOrder,
)


def configuration(**overrides: object) -> AlpacaPaperConfiguration:
    values: dict[str, object] = {
        "api_key": "paper-key",
        "api_secret": "paper-secret",
        "historical_max_retries": 0,
    }
    values.update(overrides)
    return AlpacaPaperConfiguration(**values)


def client_for(handler: httpx.MockTransport) -> AlpacaHTTPClient:
    config = configuration()
    return AlpacaHTTPClient(
        config,
        httpx.Client(transport=handler, headers=config.authentication_headers()),
        sleep=lambda _: None,
    )


def test_configuration_rejects_live_trading_url_and_uses_explicit_headers() -> None:
    with pytest.raises(AlpacaConfigurationError, match="live endpoints are forbidden"):
        configuration(paper_base_url="https://api.alpaca.markets")

    headers = configuration().authentication_headers()
    assert headers == {
        "APCA-API-KEY-ID": "paper-key",
        "APCA-API-SECRET-KEY": "paper-secret",
    }


def test_historical_provider_paginates_and_normalizes_daily_iex_bars() -> None:
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["APCA-API-KEY-ID"] == "paper-key"
        page = request.url.params.get("page_token")
        timestamp = "2024-01-03T05:00:00Z" if page else "2024-01-02T05:00:00Z"
        return httpx.Response(
            200,
            json={
                "bars": {
                    "SPY": [
                        {
                            "t": timestamp,
                            "o": 470,
                            "h": 472,
                            "l": 469,
                            "c": 471,
                            "v": 1000,
                        }
                    ]
                },
                "next_page_token": "page-2" if page is None else None,
            },
        )

    provider = AlpacaHistoricalMarketDataProvider(
        client_for(httpx.MockTransport(handle))
    )
    dataset = provider.load_historical(
        HistoricalDataRequest(
            "US_EQUITIES",
            "SPY",
            "1Day",
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 4, tzinfo=UTC),
            AdjustmentPolicy.RAW,
        )
    )

    assert len(calls) == 2
    assert calls[0].url.params["feed"] == "iex"
    assert calls[0].url.params["adjustment"] == "raw"
    assert calls[1].url.params["page_token"] == "page-2"
    assert tuple(bar.close for bar in dataset.bars) == (Decimal("471"),) * 2
    assert dataset.metadata["feed"] == "iex"


def test_historical_provider_preserves_explicit_sip_provenance() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.params["feed"] == "sip"
        return httpx.Response(
            200,
            json={
                "bars": {
                    "SPY": [
                        {
                            "t": "2024-01-02T05:00:00Z",
                            "o": 470,
                            "h": 472,
                            "l": 469,
                            "c": 471,
                            "v": 1000,
                        }
                    ]
                },
                "next_page_token": None,
            },
        )

    provider = AlpacaHistoricalMarketDataProvider(
        client_for(httpx.MockTransport(handle)), "sip"
    )
    dataset = provider.load_historical(
        HistoricalDataRequest(
            "US_EQUITIES",
            "SPY",
            "1Day",
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 4, tzinfo=UTC),
            AdjustmentPolicy.RAW,
        )
    )
    assert provider.name == "alpaca:sip"
    assert dataset.metadata["feed"] == "sip"


def test_live_provider_polls_forward_only_latest_iex_bar() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.params["feed"] == "iex"
        return httpx.Response(
            200,
            json={
                "bar": {
                    "t": "2024-01-02T15:31:00Z",
                    "o": 470,
                    "h": 472,
                    "l": 469,
                    "c": 471,
                    "v": 1000,
                }
            },
        )

    provider = AlpacaLiveMarketDataProvider(
        client_for(httpx.MockTransport(handle)), "SPY"
    )
    first = provider.next_bar()
    assert first is not None and first.close == Decimal("471")
    assert provider.next_bar() is None


def test_historical_get_retries_rate_limit_but_order_post_does_not() -> None:
    attempts = 0

    def get_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429 if attempts == 1 else 200, json={"ok": True})

    config = configuration(historical_max_retries=1)
    client = AlpacaHTTPClient(
        config,
        httpx.Client(transport=httpx.MockTransport(get_handler)),
        sleep=lambda _: None,
    )
    assert client.market_data_get("/bars", {}) == {"ok": True}
    assert attempts == 2

    post_attempts = 0

    def post_handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_attempts
        post_attempts += 1
        return httpx.Response(500, json={"message": "temporary"})

    client.client = httpx.Client(transport=httpx.MockTransport(post_handler))
    with pytest.raises(AlpacaAPIError, match="temporary"):
        client.paper_post("/v2/orders", {})
    assert post_attempts == 1


def test_upstream_error_redacts_paper_credentials() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422, json={"message": "paper-key and paper-secret must never leak"}
        )

    client = client_for(httpx.MockTransport(handle))
    with pytest.raises(AlpacaAPIError) as captured:
        client.paper_get("/v2/account")
    assert "paper-key" not in str(captured.value)
    assert "paper-secret" not in str(captured.value)
    assert str(captured.value).count("[REDACTED]") == 2


def test_paper_account_order_and_position_mapping_are_explicitly_simulated() -> None:
    responses = {
        "/v2/account": {
            "id": "account-id",
            "account_number": "PA123",
            "status": "ACTIVE",
            "currency": "USD",
            "cash": "10000",
            "buying_power": "20000",
            "equity": "10500",
            "portfolio_value": "10500",
            "trading_blocked": False,
            "pattern_day_trader": False,
        },
        "/v2/orders": {
            "id": "order-id",
            "client_order_id": "ql-test-1",
            "symbol": "SPY",
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
            "status": "accepted",
            "qty": "1",
            "filled_qty": "0",
            "filled_avg_price": None,
            "submitted_at": "2024-01-02T15:00:00Z",
            "filled_at": None,
        },
        "/v2/positions/SPY": {
            "symbol": "SPY",
            "qty": "1",
            "avg_entry_price": "470",
            "market_value": "471",
            "current_price": "471",
            "unrealized_pl": "1",
            "unrealized_plpc": "0.00212766",
        },
    }

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses[request.url.path])

    tracked = []
    broker = AlpacaPaperBrokerAdapter(
        client_for(httpx.MockTransport(handle)), tracked.append
    )
    account = broker.get_account()
    order = broker.submit_order(
        SubmitAlpacaPaperOrder(
            "SPY",
            Decimal("1"),
            PaperOrderSide.BUY,
            PaperOrderType.MARKET,
            PaperTimeInForce.DAY,
            "ql-test-1",
        )
    )
    position = broker.get_position("spy")

    assert account.simulated is True
    assert order.status == "accepted" and order.simulated is True
    assert tracked == [order]
    assert position.unrealized_pnl == Decimal("1") and position.simulated is True


def test_alpaca_import_reuses_immutable_parquet_snapshot_workflow(tmp_path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "bars": {
                    "SPY": [
                        {
                            "t": "2024-01-02T05:00:00Z",
                            "o": 470,
                            "h": 472,
                            "l": 469,
                            "c": 471,
                            "v": 1000,
                        }
                    ]
                },
                "next_page_token": None,
            },
        )

    class Repository:
        def __init__(self) -> None:
            self.value = None

        def add(self, value) -> None:
            self.value = value

        def get(self, identity):
            return self.value if self.value and self.value.id == identity else None

        def list_all(self):
            return [] if self.value is None else [self.value]

    repository = Repository()
    storage = LocalParquetDatasetStorage(tmp_path)
    loader = LoadDatasetSnapshot(storage, repository)
    service = ImportHistoricalDataset(
        CreateDatasetSnapshot(
            AlpacaHistoricalMarketDataProvider(client_for(httpx.MockTransport(handle))),
            storage,
            repository,
        ),
        loader,
    )
    result = service.execute(
        market="US_EQUITIES",
        instrument="SPY",
        timeframe="1Day",
        start_at=datetime(2024, 1, 1, tzinfo=UTC),
        end_at=datetime(2024, 1, 3, tzinfo=UTC),
        adjustment_policy=AdjustmentPolicy.RAW,
    )

    assert result.bar_count == 1
    assert result.snapshot.provider == "alpaca:iex"
    assert result.snapshot.checksum.startswith("sha256:")
    assert (tmp_path / result.snapshot.storage_location).is_file()
