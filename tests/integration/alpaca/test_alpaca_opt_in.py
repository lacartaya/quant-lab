import os
from datetime import UTC, datetime, timedelta

import pytest

from infra.alpaca import (
    AlpacaHistoricalMarketDataProvider,
    AlpacaHTTPClient,
    AlpacaPaperBrokerAdapter,
    AlpacaPaperConfiguration,
)
from quant.domain import AdjustmentPolicy, HistoricalDataRequest

pytestmark = pytest.mark.alpaca_integration


@pytest.mark.skipif(
    os.getenv("RUN_ALPACA_INTEGRATION_TESTS", "false").lower() != "true",
    reason="real Alpaca read-only checks are explicitly opt-in",
)
def test_real_paper_account_and_recent_spy_daily_data() -> None:
    configuration = AlpacaPaperConfiguration.from_environment()
    client = AlpacaHTTPClient.create(configuration)
    try:
        account = AlpacaPaperBrokerAdapter(client).get_account()
        assert account.simulated is True
        end = datetime.now(UTC)
        dataset = AlpacaHistoricalMarketDataProvider(client).load_historical(
            HistoricalDataRequest(
                "US_EQUITIES",
                "SPY",
                "1Day",
                end - timedelta(days=30),
                end,
                AdjustmentPolicy.RAW,
            )
        )
        assert len(dataset.bars) > 5
        assert tuple(dataset.bars) == tuple(
            sorted(dataset.bars, key=lambda item: item.timestamp)
        )
    finally:
        client.client.close()
