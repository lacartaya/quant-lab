from datetime import UTC, datetime, timedelta

import pytest

from quant.validation import OutOfSampleConfiguration

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_oos_configuration_requires_strict_temporal_separation() -> None:
    configuration = OutOfSampleConfiguration(
        NOW,
        NOW + timedelta(days=9),
        NOW + timedelta(days=10),
        NOW + timedelta(days=20),
    )
    assert configuration.training_end < configuration.test_start

    with pytest.raises(ValueError, match="temporally separated"):
        OutOfSampleConfiguration(
            NOW,
            NOW + timedelta(days=10),
            NOW + timedelta(days=10),
            NOW + timedelta(days=20),
        )
